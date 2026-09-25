"""Misskey 機器人技能（預設接入 hub.imikufans.com）。

設計要點（凍結自 Misskey 2026.6.0 API）：
- 鑑權：POST JSON body 帶 "i": token（Misskey 慣例，無 Bearer）
- 機器人標註：POST /api/i/update {"i": token, "isBot": true}
- 發文：POST /api/notes/create {"i": token, "text": ..., "visibility": ...}
- 回覆：notes/create 帶 replyId
- 提及：POST /api/notes/mentions
- 時間線：POST /api/notes/local-timeline 或 /api/notes/timeline
- 本機代理環境（ICUBE_PROXY_HOST）會攔截外網請求 → session.trust_env = False
- 所有對外發出文本先過 content_filter，命中即拒發
"""

import json
import os
import threading
import importlib.util
from typing import Any, Dict, List, Optional

import requests

_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
_STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
_DEFAULT_HOST = "hub.imikufans.com"
_DEFAULT_VISIBILITY = "home"  # 機器人默認不進公共時間線，降低騷擾風險
_MAX_NOTE_LEN = 3000

def _load_content_filter():
    """技能以隔離方式載入，包名可能解析不到；按候選路徑顯式載入 content_filter。"""
    try:
        from core.tools import content_filter
        return content_filter
    except ImportError:
        pass
    try:
        from tools import content_filter
        return content_filter
    except ImportError:
        pass
    import sys
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates += [
            os.path.join(meipass, "core", "tools", "content_filter.py"),
            os.path.join(meipass, "src", "core", "tools", "content_filter.py"),
        ]
    # dev：skills/misskey-bot -> 項目根/src/core/tools
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates.append(os.path.join(root, "src", "core", "tools", "content_filter.py"))
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("humanaize_content_filter", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


content_filter = _load_content_filter()


def _filter_check(text: str) -> (bool, List[str]):
    if content_filter is None:
        return True, []
    return content_filter.check(text)


class MisskeyBot:
    def __init__(self):
        self._lock = threading.Lock()
        self.config = self._load_json(_CONFIG_FILE, {
            "host": _DEFAULT_HOST,
            "token": "",
            "bot_marked": False,
            "default_visibility": _DEFAULT_VISIBILITY,
        })
        self.state = self._load_json(_STATE_FILE, {"last_mention_id": None})
        self._session = requests.Session()
        self._session.trust_env = False  # 繞過本機代理環境變數
        self._session.headers.update({"Content-Type": "application/json"})

    # ---------- 配置與狀態 ----------
    @staticmethod
    def _load_json(path: str, default: Dict) -> Dict:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        merged = dict(default)
                        merged.update(data)
                        return merged
        except Exception:
            pass
        return dict(default)

    @staticmethod
    def _save_json(path: str, data: Dict):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def configure(self, params: Dict) -> Dict:
        changed = False
        for key in ("host", "token", "default_visibility"):
            if key in params and params[key] is not None:
                value = str(params[key]).strip()
                if key == "host":
                    value = value.replace("https://", "").replace("http://", "").strip("/")
                if value != self.config.get(key):
                    self.config[key] = value
                    changed = True
        if changed:
            if "token" in params or "host" in params:
                self.config["bot_marked"] = False  # 換賬號/實例需重新標註
            self._save_json(_CONFIG_FILE, self.config)
        # 連線驗證
        if self.config.get("token"):
            me = self._api("i")
            if me.get("ok"):
                username = me["data"].get("username", "")
                return {"success": True, "message": f"配置成功，已連接 @{username}@{self.config['host']}",
                        "bot_marked": self.config.get("bot_marked", False)}
            return {"success": False, "message": f"配置已保存但連線失敗：{me.get('error')}"}
        return {"success": True, "message": "配置已保存（未設 token，僅可只讀）"}

    def status(self) -> Dict:
        out = {
            "success": True,
            "host": self.config.get("host"),
            "has_token": bool(self.config.get("token")),
            "bot_marked": self.config.get("bot_marked", False),
            "default_visibility": self.config.get("default_visibility"),
        }
        if self.config.get("token"):
            me = self._api("i")
            if me.get("ok"):
                out["username"] = me["data"].get("username")
                out["remote_isBot"] = me["data"].get("isBot")
            else:
                out["connect_error"] = me.get("error")
        return out

    # ---------- API 基礎 ----------
    def _api(self, endpoint: str, payload: Optional[Dict] = None, timeout: int = 15) -> Dict:
        host = self.config.get("host") or _DEFAULT_HOST
        body = dict(payload or {})
        token = self.config.get("token")
        if token:
            body["i"] = token
        try:
            resp = self._session.post(f"https://{host}/api/{endpoint}", json=body, timeout=timeout)
            if resp.status_code == 204:
                return {"ok": True, "data": {}}
            data = resp.json()
            if resp.status_code >= 400:
                err = data.get("error", {})
                return {"ok": False, "error": err.get("message") or str(err) or f"HTTP {resp.status_code}"}
            return {"ok": True, "data": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- 機器人標註 ----------
    def set_bot(self) -> Dict:
        if not self.config.get("token"):
            return {"success": False, "error": "未配置 token"}
        res = self._api("i/update", {"isBot": True})
        if res.get("ok"):
            self.config["bot_marked"] = True
            self._save_json(_CONFIG_FILE, self.config)
            return {"success": True, "message": "賬號已標註為機器人（isBot=true）"}
        return {"success": False, "error": res.get("error")}

    # ---------- 發文 / 回覆 ----------
    def post(self, text: str, visibility: str = None, reply_id: str = None, cw: str = None) -> Dict:
        text = (text or "").strip()
        if not text:
            return {"success": False, "error": "內容為空"}
        if not self.config.get("token"):
            return {"success": False, "error": "未配置 token"}
        ok, hits = _filter_check(text)
        if not ok:
            return {"success": False, "error": f"內容被過濾器攔截（命中 {len(hits)} 個敏感詞），未發送"}
        if len(text) > _MAX_NOTE_LEN:
            text = text[: _MAX_NOTE_LEN - 1] + "…"
        payload = {"text": text, "visibility": visibility or self.config.get("default_visibility") or _DEFAULT_VISIBILITY}
        if reply_id:
            payload["replyId"] = reply_id
        if cw:
            payload["cw"] = cw
        res = self._api("notes/create", payload)
        if res.get("ok"):
            note = res["data"].get("createdNote", {})
            return {"success": True, "note_id": note.get("id"), "host": self.config.get("host"),
                    "url": f"https://{self.config.get('host')}/notes/{note.get('id')}" if note.get("id") else None}
        return {"success": False, "error": res.get("error")}

    # ---------- 點讚 / 反應 ----------
    def react(self, note_id: str, reaction: str = "👍") -> Dict:
        """給帖子點讚/加反應。note_id 必填，reaction 預設 👍"""
        if not self.config.get("token"):
            return {"success": False, "error": "未配置 token"}
        if not note_id:
            return {"success": False, "error": "缺少 note_id"}
        res = self._api("notes/reactions/create", {"noteId": note_id, "reaction": reaction})
        if res.get("ok"):
            return {"success": True, "note_id": note_id, "reaction": reaction}
        return {"success": False, "error": res.get("error")}

    # ---------- 提及 / 時間線 ----------
    def mentions(self, limit: int = 10) -> Dict:
        if not self.config.get("token"):
            return {"success": False, "error": "未配置 token"}
        res = self._api("notes/mentions", {"limit": max(1, min(int(limit), 30))})
        if not res.get("ok"):
            return {"success": False, "error": res.get("error")}
        notes = res["data"] if isinstance(res["data"], list) else []
        items = [{
            "id": n.get("id"),
            "text": n.get("text", "")[:500],
            "user": (n.get("user") or {}).get("username"),
            "createdAt": n.get("createdAt"),
        } for n in notes]
        if items:
            self.state["last_mention_id"] = items[0]["id"]
            self._save_json(_STATE_FILE, self.state)
        return {"success": True, "mentions": items}

    def timeline(self, kind: str = "local", limit: int = 10) -> Dict:
        endpoint = {"local": "notes/local-timeline", "home": "notes/timeline",
                    "global": "notes/global-timeline"}.get(kind, "notes/local-timeline")
        res = self._api(endpoint, {"limit": max(1, min(int(limit), 30))})
        if not res.get("ok"):
            return {"success": False, "error": res.get("error")}
        notes = res["data"] if isinstance(res["data"], list) else []
        return {"success": True, "notes": [{
            "id": n.get("id"),
            "text": (n.get("text") or "")[:300],
            "user": (n.get("user") or {}).get("username"),
            "createdAt": n.get("createdAt"),
        } for n in notes]}


_bot = None
_bot_lock = threading.Lock()


def _get_bot() -> MisskeyBot:
    global _bot
    with _bot_lock:
        if _bot is None:
            _bot = MisskeyBot()
    return _bot


def execute(input_data: Any) -> Dict:
    if isinstance(input_data, dict):
        action = str(input_data.get("action", "status")).strip().lower()
        params = input_data.get("params") or {}
        if not isinstance(params, dict):
            params = {}
    else:
        return {"success": False, "error": "輸入需為 {'action':..., 'params':{...}}"}

    bot = _get_bot()
    if action == "configure":
        return bot.configure(params)
    if action == "status":
        return bot.status()
    if action == "set_bot":
        return bot.set_bot()
    if action == "post":
        return bot.post(params.get("text", ""), visibility=params.get("visibility"), cw=params.get("cw"))
    if action == "reply":
        if not params.get("reply_id"):
            return {"success": False, "error": "缺少 reply_id"}
        return bot.post(params.get("text", ""), reply_id=params.get("reply_id"), cw=params.get("cw"))
    if action == "mentions":
        return bot.mentions(params.get("limit", 10))
    if action == "timeline":
        return bot.timeline(params.get("kind", "local"), params.get("limit", 10))
    if action == "react":
        return bot.react(params.get("note_id", ""), params.get("reaction", "👍"))
    return {"success": False, "error": f"未知動作: {action}"}
