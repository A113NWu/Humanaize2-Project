# -*- coding: utf-8 -*-
"""
Humanaize MCP 客戶端技能

以 HTTP Streamable 傳輸接入外部 MCP 服務器（Tulpa、各類 MCP Server），
讓 Aize 能列舉並調用外部工具。配置保存在同目錄 config.json。
"""

import base64
import json
import os
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "Humanaize2", "version": "1.0.0"}
DEFAULT_TIMEOUT = 240
DEFAULT_MAX_CHARS = 20000
MAX_IMAGE_BYTES = 10 * 1024 * 1024

_clients: Dict[str, "McpHttpClient"] = {}
_clients_lock = threading.Lock()


class McpError(Exception):
    """MCP 協議或傳輸錯誤。"""


# ---------------------------------------------------------------------------
# HTTP Streamable 客戶端
# ---------------------------------------------------------------------------

class McpHttpClient:
    """單個 MCP 服務器的 JSON-RPC over HTTP Streamable 客戶端。"""

    def __init__(self, name: str, url: str, headers: Dict[str, str] = None,
                 timeout: int = DEFAULT_TIMEOUT):
        self.name = name
        self.url = url
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.protocol_version: Optional[str] = None
        self._initialized = False
        self._next_id = 0
        self._lock = threading.RLock()

    # -- 傳輸 ---------------------------------------------------------------

    def _request_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        headers.update(self.headers)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if self.protocol_version:
            headers["MCP-Protocol-Version"] = self.protocol_version
        return headers

    def _post(self, payload: Dict) -> Optional[Dict]:
        try:
            resp = requests.post(
                self.url,
                json=payload,
                headers=self._request_headers(),
                timeout=self.timeout,
                stream=True,
            )
        except requests.exceptions.Timeout:
            raise McpError(f"連接 {self.url} 超時（{self.timeout}s）")
        except requests.exceptions.ConnectionError as e:
            raise McpError(f"無法連接 {self.url}：{e}")
        except requests.exceptions.RequestException as e:
            raise McpError(f"請求失敗：{e}")

        with resp:
            session_id = resp.headers.get("Mcp-Session-Id")
            if session_id:
                self.session_id = session_id
            if resp.status_code >= 400:
                raise McpError(f"HTTP {resp.status_code}：{_read_body(resp)}")

            message_id = payload.get("id")
            if message_id is None:  # notification，服務器不回內容
                _drain(resp)
                return None

            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "text/event-stream" in content_type:
                return _read_sse_response(resp, message_id)
            body = resp.text
            if not body.strip():
                raise McpError("服務器返回空內容")
            try:
                return json.loads(body)
            except ValueError:
                return _parse_sse_text(body, message_id)

    def _rpc(self, method: str, params: Optional[Dict] = None) -> Any:
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            payload["params"] = params
        response = self._post(payload)
        if not isinstance(response, dict):
            raise McpError(f"{method} 回應格式不合法")
        if response.get("error"):
            error = response["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise McpError(f"MCP 錯誤（{method}）：{message}")
        return response.get("result")

    # -- 會話 ---------------------------------------------------------------

    def ensure_initialized(self):
        with self._lock:
            if self._initialized:
                return
            self.session_id = None
            result = self._rpc("initialize", {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            }) or {}
            self.protocol_version = result.get("protocolVersion") or PROTOCOL_VERSION
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
            self._initialized = True

    def server_info(self) -> Dict:
        with self._lock:
            self.ensure_initialized()
            return {
                "protocol_version": self.protocol_version,
                "session_id": (self.session_id or "")[:8] or None,
            }

    # -- 能力 ---------------------------------------------------------------

    def list_tools(self) -> List[Dict]:
        with self._lock:
            self.ensure_initialized()
            tools: List[Dict] = []
            cursor = None
            for _ in range(50):
                params = {"cursor": cursor} if cursor else {}
                result = self._rpc("tools/list", params) or {}
                batch = result.get("tools") or []
                if isinstance(batch, list):
                    tools.extend(item for item in batch if isinstance(item, dict))
                cursor = result.get("nextCursor")
                if not cursor:
                    break
            return tools

    def call_tool(self, tool: str, arguments: Dict) -> Dict:
        with self._lock:
            self.ensure_initialized()
            return self._rpc("tools/call", {"name": tool, "arguments": arguments}) or {}


# ---------------------------------------------------------------------------
# 傳輸輔助
# ---------------------------------------------------------------------------

def _read_body(resp, limit: int = 800) -> str:
    try:
        text = resp.text or ""
    except Exception:
        return "(無法讀取回應內容)"
    text = text.strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _drain(resp):
    """消費掉 notification 的回應體，避免連線殘留。"""
    try:
        for _ in resp.iter_content(chunk_size=8192):
            pass
    except Exception:
        pass


def _read_sse_response(resp, message_id) -> Dict:
    """從 SSE 串流中取出與請求 id 對應的 JSON-RPC 回應。"""
    started = time.time()
    for raw_line in resp.iter_lines(decode_unicode=True):
        if time.time() - started > 600:
            raise McpError("等待 MCP 串流回應超過 600 秒")
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data in ("", "[DONE]"):
            continue
        try:
            payload = json.loads(data)
        except ValueError:
            continue
        if (isinstance(payload, dict) and payload.get("id") == message_id
                and ("result" in payload or "error" in payload)):
            return payload
    raise McpError("串流已結束，但未收到對應的 JSON-RPC 回應")


def _parse_sse_text(text: str, message_id) -> Dict:
    """有些服務器會以整段 SSE 文本回傳，退化解析。"""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except ValueError:
            continue
        if isinstance(payload, dict) and payload.get("id") == message_id:
            return payload
    raise McpError("無法解析服務器回應")


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def _load_config() -> Dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError):
        return {}
    return config if isinstance(config, dict) else {}


def _configured_servers(config: Dict) -> Dict[str, Dict]:
    servers = config.get("servers")
    if not isinstance(servers, dict):
        return {}
    return {name: spec for name, spec in servers.items()
            if isinstance(spec, dict) and spec.get("url")}


def _server_signature(name: str, spec: Dict) -> str:
    return json.dumps(
        [name, spec.get("url"), spec.get("token"),
         spec.get("headers") or {}, spec.get("timeout")],
        sort_keys=True, ensure_ascii=False, default=str,
    )


def _build_client(name: str, spec: Dict) -> McpHttpClient:
    headers = spec.get("headers")
    headers = dict(headers) if isinstance(headers, dict) else {}
    token = str(spec.get("token") or "").strip()
    if token and not any(str(k).lower() == "authorization" for k in headers):
        headers["Authorization"] = f"Bearer {token}"
    try:
        timeout = max(5, int(spec.get("timeout") or DEFAULT_TIMEOUT))
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT
    return McpHttpClient(name, str(spec["url"]).strip(), headers, timeout)


def _get_client(name: str, spec: Dict) -> McpHttpClient:
    signature = _server_signature(name, spec)
    with _clients_lock:
        cached = _clients.get(name)
        if cached is not None and getattr(cached, "_signature", None) == signature:
            return cached
        client = _build_client(name, spec)
        client._signature = signature
        _clients[name] = client
        return client


def _reset_clients():
    with _clients_lock:
        _clients.clear()


# ---------------------------------------------------------------------------
# 結果整理
# ---------------------------------------------------------------------------

def _save_image(item: Dict) -> Dict:
    """把 MCP 影像內容落到臨時文件，返回可供 vision 技能讀取的路徑。"""
    data = item.get("data") or ""
    mime = str(item.get("mimeType") or "image/png")
    if not data:
        return {"type": "image", "note": "空影像"}
    try:
        raw = base64.b64decode(data, validate=False)
    except Exception as e:
        return {"type": "image", "note": f"影像解碼失敗：{e}"}
    if len(raw) > MAX_IMAGE_BYTES:
        return {"type": "image", "note": f"影像過大（{len(raw)} bytes），已省略"}
    ext = mime.rsplit("/", 1)[-1].split(";")[0].strip() or "png"
    folder = os.path.join(tempfile.gettempdir(), "humanaize-mcp")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{int(time.time() * 1000)}.{ext}")
    with open(path, "wb") as f:
        f.write(raw)
    return {"type": "image", "path": path, "mime": mime, "bytes": len(raw)}


def _flatten_tool_result(result: Dict, max_chars: int) -> Dict:
    texts: List[str] = []
    images: List[Dict] = []
    for item in result.get("content") or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "text":
            texts.append(str(item.get("text") or ""))
        elif kind == "image":
            images.append(_save_image(item))
        elif kind == "resource":
            resource = item.get("resource") or {}
            if isinstance(resource, dict):
                texts.append(str(resource.get("text") or resource.get("uri") or ""))
            else:
                texts.append(str(resource))
        else:
            texts.append(json.dumps(item, ensure_ascii=False))

    if not texts and result.get("structuredContent") is not None:
        texts.append(json.dumps(result["structuredContent"], ensure_ascii=False, indent=2))

    output = "\n".join(part for part in texts if part)
    truncated = False
    if max_chars and len(output) > max_chars:
        output = output[:max_chars] + f"\n…（已截斷，原長 {len(output)} 字符）"
        truncated = True

    payload = {
        "success": not result.get("isError", False),
        "output": output or "（工具未返回文本內容）",
        "truncated": truncated,
    }
    if images:
        payload["images"] = images
    if result.get("isError"):
        payload["error"] = payload["output"]
    return payload


def _tool_brief(tool: Dict) -> Dict:
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    properties = schema.get("properties") if isinstance(schema, dict) else {}
    required = schema.get("required") if isinstance(schema, dict) else None
    return {
        "name": tool.get("name"),
        "description": (tool.get("description") or "").strip()[:400],
        "parameters": list(properties.keys()) if isinstance(properties, dict) else [],
        "required": required or [],
    }


# ---------------------------------------------------------------------------
# 輸入歸一化
# ---------------------------------------------------------------------------

def _normalize(input_data: Any) -> Dict:
    """統一成扁平的動作字典；params 內的鍵會上提到頂層（不覆蓋已有鍵）。"""
    if isinstance(input_data, dict):
        data = dict(input_data)
    elif isinstance(input_data, str):
        data = {"command": input_data.strip()}
    else:
        data = {}
    params = data.get("params")
    if isinstance(params, dict):
        for key, value in params.items():
            data.setdefault(key, value)
    return data


def _pick(data: Dict, *keys, default=None):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _parse_arguments(value: Any) -> Dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


HELP_TEXT = (
    "MCP 客戶端用法：\n"
    '1. {"command":"list_servers"} 查看已配置的 MCP 服務器\n'
    '2. {"command":"list_tools","server":"tulpa"} 列出服務器工具\n'
    '3. {"command":"call","server":"tulpa","tool":"get_data_status","arguments":{}} 調用工具\n'
    '4. {"command":"ping","server":"tulpa"} 僅測試連線\n'
    "服務器配置在 Dashboard → 技能 → MCP 客戶端 的配置界面。"
)


# ---------------------------------------------------------------------------
# 動作
# ---------------------------------------------------------------------------

def _action_list_servers(config: Dict) -> Dict:
    servers = _configured_servers(config)
    items = []
    for name, spec in servers.items():
        items.append({
            "name": name,
            "url": spec.get("url"),
            "enabled": bool(spec.get("enabled", True)),
            "token_configured": bool(str(spec.get("token") or "").strip()),
            "timeout": spec.get("timeout") or DEFAULT_TIMEOUT,
            "note": spec.get("note") or "",
        })
    return {
        "success": True,
        "count": len(items),
        "servers": items,
        "hint": "用 list_tools 查看某個服務器的工具" if items else
                "尚未配置服務器，請到 Dashboard → 技能 → MCP 客戶端 添加",
    }


def _server_target(config: Dict, data: Dict, require: bool = True):
    servers = _configured_servers(config)
    name = str(_pick(data, "server", "server_name", "name", default="")).strip()
    if not name:
        enabled = [n for n, s in servers.items() if s.get("enabled", True)]
        if len(enabled) == 1:
            name = enabled[0]
        elif require:
            raise McpError(
                "請指定 server 參數；已配置：" + (", ".join(servers.keys()) or "無"))
        else:
            return None, None
    spec = servers.get(name)
    if spec is None:
        for candidate, candidate_spec in servers.items():
            if candidate.lower() == name.lower():
                name, spec = candidate, candidate_spec
                break
    if spec is None:
        raise McpError(f"未找到服務器 '{name}'；已配置：{', '.join(servers.keys()) or '無'}")
    if not spec.get("enabled", True):
        raise McpError(f"服務器 '{name}' 已停用，請在配置界面啟用")
    return name, spec


def _action_list_tools(config: Dict, data: Dict) -> Dict:
    name, spec = _server_target(config, data, require=False)
    targets = [(name, spec)] if name else [
        (n, s) for n, s in _configured_servers(config).items() if s.get("enabled", True)]

    results = []
    for target_name, target_spec in targets:
        try:
            client = _get_client(target_name, target_spec)
            tools = client.list_tools()
            results.append({
                "server": target_name,
                "success": True,
                "count": len(tools),
                "tools": [_tool_brief(tool) for tool in tools],
            })
        except McpError as e:
            results.append({"server": target_name, "success": False, "error": str(e)})

    return {
        "success": any(item.get("success") for item in results) if results else False,
        "servers": results,
    }


def _action_call(config: Dict, data: Dict) -> Dict:
    name, spec = _server_target(config, data)
    tool = str(_pick(data, "tool", "tool_name", "method", default="")).strip()
    if not tool:
        raise McpError("請指定要調用的工具名（tool）")
    arguments = _parse_arguments(
        _pick(data, "arguments", "params", "args", default={}))
    max_chars = config.get("max_result_chars") or DEFAULT_MAX_CHARS
    try:
        max_chars = max(1000, int(max_chars))
    except (TypeError, ValueError):
        max_chars = DEFAULT_MAX_CHARS

    client = _get_client(name, spec)
    result = client.call_tool(tool, arguments)
    payload = _flatten_tool_result(result, max_chars)
    payload["server"] = name
    payload["tool"] = tool
    return payload


def _action_ping(config: Dict, data: Dict) -> Dict:
    name, spec = _server_target(config, data, require=False)
    targets = [(name, spec)] if name else [
        (n, s) for n, s in _configured_servers(config).items()]

    results = []
    for target_name, target_spec in targets:
        started = time.time()
        try:
            client = _get_client(target_name, target_spec)
            client.ensure_initialized()
            tools = client.list_tools()
            results.append({
                "server": target_name,
                "success": True,
                "latency_ms": int((time.time() - started) * 1000),
                "protocol_version": client.protocol_version,
                "tool_count": len(tools),
            })
        except McpError as e:
            results.append({"server": target_name, "success": False, "error": str(e)})
    return {"success": all(item.get("success") for item in results), "servers": results}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def execute(input_data: Any) -> Dict:
    """執行 MCP 客戶端動作。"""
    if requests is None:
        return {"success": False, "error": "requests 未安裝，無法使用 MCP 客戶端"}

    config = _load_config()
    data = _normalize(input_data)
    action = str(_pick(data, "command", "action", default="")).strip().lower()

    if not action:
        if _pick(data, "tool", "tool_name"):
            action = "call"
        elif _pick(data, "server", "server_name"):
            action = "list_tools"
        else:
            action = "help"

    if action in ("refresh", "reload"):
        _reset_clients()
        return {"success": True, "message": "已清除 MCP 連線快取"}

    try:
        if action in ("help", "usage"):
            return {"success": True, "output": HELP_TEXT}
        if action in ("list_servers", "servers", "status"):
            return _action_list_servers(config)
        if action in ("list_tools", "tools"):
            return _action_list_tools(config, data)
        if action in ("call", "invoke", "execute", "call_tool"):
            return _action_call(config, data)
        if action in ("ping", "test", "check"):
            return _action_ping(config, data)
    except McpError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"執行失敗：{e}"}

    return {"success": False, "error": f"未知動作 '{action}'。\n{HELP_TEXT}"}
