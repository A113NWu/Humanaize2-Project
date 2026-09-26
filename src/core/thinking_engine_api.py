"""
ThinkingEngine API Server - OpenAI兼容接口

为AstrBot等外部服务提供OpenAI兼容的API，让消息经过ThinkingEngine的完整思考流程。
QQ-bot和客户端共用同样的处理函数和逻辑。

启动方式：
    python thinking_engine_api.py --port 8082

AstrBot配置：
    provider_source.api_base = "http://127.0.0.1:8082/v1"
"""

import json
import time
import uuid
import threading
import os
import sys
import re
import traceback
import collections
import hashlib
import secrets
try:
    from http.server import ThreadingHTTPServer as HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from queue import Queue, Empty

# 添加路径
core_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, core_dir)
src_dir = os.path.dirname(core_dir)
sys.path.insert(0, src_dir)
project_root = os.path.dirname(src_dir)
sys.path.insert(0, project_root)

try:
    from tools.logger import get_logger
    logger = get_logger()
except ModuleNotFoundError:
    try:
        from core.tools.logger import get_logger
        logger = get_logger()
    except ModuleNotFoundError:
        import logging
        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

try:
    from version import get_version
except ModuleNotFoundError:
    from core.version import get_version

try:
    from app_paths import get_settings_path
except ModuleNotFoundError:
    from core.app_paths import get_settings_path

# llama-server 實際加載的模型名緩存（狀態頁輪詢用；llama-server 掛掉時 60s 內沿用）
_LLAMA_MODEL_CACHE = {"name": "", "ts": 0.0}

# Dashboard 登錄會話（進程內存，重啟需重新登錄）：token -> 過期時間戳
_SESSIONS = {}
_AUTH_TTL_SECONDS = 7 * 24 * 3600

# 未登錄訪問 / 時返回的內聯登錄頁
_LOGIN_PAGE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Humanaize 登录</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#141010;font-family:"Segoe UI",sans-serif}
.card{background:#1f1815;border:1px solid #3a2a1e;border-radius:14px;padding:36px 32px;width:300px;box-shadow:0 12px 40px rgba(0,0,0,.5)}
h1{margin:0 0 6px;font-size:20px;color:#ff8c3a}
p{margin:0 0 20px;font-size:12px;color:#a89888}
label{display:block;font-size:13px;color:#d8c8b8;margin-bottom:12px}
input{display:block;width:100%;box-sizing:border-box;margin-top:4px;padding:9px 10px;border-radius:8px;border:1px solid #4a382a;background:#171210;color:#f0e6da;font-size:14px}
input:focus{outline:none;border-color:#ff8c3a}
button{width:100%;margin-top:8px;padding:10px;border:0;border-radius:8px;background:#ff8c3a;color:#1a120c;font-size:15px;font-weight:600;cursor:pointer}
button:hover{background:#ffa05c}
#msg{min-height:16px;margin-top:10px;font-size:12px;color:#ff7a7a}
</style></head><body>
<div class="card"><h1>HUMANAIZE</h1><p>此面板已启用账户登录</p>
<form id="f"><label>账户名<input id="u" autocomplete="username" required></label>
<label>密码<input id="p" type="password" autocomplete="current-password" required></label>
<button type="submit">登录</button><div id="msg"></div></form></div>
<script>
document.getElementById('f').onsubmit=async e=>{e.preventDefault();
const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({username:document.getElementById('u').value,password:document.getElementById('p').value})});
if(r.ok){location.reload()}else{const d=await r.json().catch(()=>({}));
document.getElementById('msg').textContent=(d.error&&d.error.message)||'登录失败'}};
</script></body></html>"""

# 運行時技能清單緩存（Agent 初始化較重，全進程只構造一次）
_SKILLS_PROMPT_CACHE = {"text": None}


def _get_skills_prompt_cached() -> str:
    """獲取當前實際可用技能的說明文本（繁中），失敗返回空串。

    復用 /api/skills 的同一個進程級 SkillsManager（完整構造需導入全部
    技能模塊，可達十幾秒），避免 Agent("!") 再構造一份。
    """
    if _SKILLS_PROMPT_CACHE["text"] is not None:
        return _SKILLS_PROMPT_CACHE["text"]
    text = ""
    try:
        text = (_get_skills_manager().get_skills_prompt("zh-TW") or "").strip()
    except Exception as e:
        logger.warning(f"[Chat] failed to build skills prompt: {e}")
        text = ""
    _SKILLS_PROMPT_CACHE["text"] = text
    return text


def _invalidate_skills_prompt_cache():
    """技能啟用狀態變更後，讓下次聊天重新構造可用技能清單。"""
    _SKILLS_PROMPT_CACHE["text"] = None


# 運行時技能管理器實例（進程級緩存，與 Agent 內部使用同一個 skills 目錄）
_SKILLS_MANAGER_CACHE = {"mgr": None}


def _resolve_skills_dir():
    """技能目錄解析：打包態優先 exe 旁 skills/（安裝鋪設），
    開發態用項目根 skills/，與 Agent 的解析規則保持一致。"""
    if getattr(sys, "frozen", False):
        exe_skills = os.path.join(os.path.dirname(sys.executable), "skills")
        if os.path.isdir(exe_skills) and os.listdir(exe_skills):
            return exe_skills
    dev_skills = os.path.join(project_root, "skills")
    if os.path.isdir(dev_skills) and os.listdir(dev_skills):
        return dev_skills
    core_skills = os.path.join(core_dir, "skills")
    if os.path.isdir(core_skills) and os.listdir(core_skills):
        return core_skills
    return None


def _get_skills_manager():
    """獲取進程級 SkillsManager（構造較重，只做一次）。"""
    mgr = _SKILLS_MANAGER_CACHE["mgr"]
    if mgr is not None:
        return mgr
    try:
        from skills_manager import SkillsManager
    except ImportError:
        from core.tools.skills_manager import SkillsManager
    skills_dir = _resolve_skills_dir()
    mgr = SkillsManager(skills_dir) if skills_dir else SkillsManager()
    _SKILLS_MANAGER_CACHE["mgr"] = mgr
    return mgr


class IdleEventBus:
    """進程級事件匯流排：閒置引擎 / 對話中的思考事件 → 網頁 /api/events SSE。

    - 每個事件帶遞增 seq，訂閱端斷線重連可按 seq 去重
    - 保留最近 300 條環形緩衝，新連接（或重連）先補發歷史，再收實時事件
    - 訂閱者隊列滿時直接丟棄該訂閱者（慢客戶端不阻塞主流程）
    """

    def __init__(self, history_size=300):
        self._lock = threading.Lock()
        self._subscribers = set()
        self._recent = collections.deque(maxlen=history_size)
        self._seq = 0

    def publish(self, event: dict):
        if not isinstance(event, dict):
            return
        with self._lock:
            self._seq += 1
            event = dict(event)
            event["seq"] = self._seq
            self._recent.append(event)
            dead = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except Exception:
                    dead.append(queue)
            for queue in dead:
                self._subscribers.discard(queue)

    def subscribe(self):
        queue = Queue(maxsize=1000)
        with self._lock:
            self._subscribers.add(queue)
            recent = list(self._recent)
        return queue, recent

    def unsubscribe(self, queue):
        with self._lock:
            self._subscribers.discard(queue)


_idle_event_bus = IdleEventBus()


def classify_idle_thought_type(text: str, thought_type: str = "") -> str:
    """閒置引擎自身發出的思考沒有 thought_type，按前綴歸類以便網頁上色。
    GANIteration 轉發的事件本身帶有 gan_topic/gan_argument 等類型，原樣保留。"""
    ttype = (thought_type or "").strip()
    if ttype:
        return ttype
    head = (text or "").lstrip()
    if head.startswith("[Social"):
        return "social"
    if head.startswith("[Thinking Direction"):
        return "gan_topic"
    if head.startswith("[Self-thought]"):
        return "gan_synthesis"
    if head.startswith("[Idle Activity]"):
        return "gan"
    if head.startswith("[Self-Optimization") or head.startswith("[Auto-Optimization"):
        return "solve_mode"
    return "internal"


def _now_display():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def publish_engine_event(response):
    """把引擎回調字典正規化後推送給網頁事件匯流排。

    對應關係：
    - internal_thought    → thought（閒置思考 / GAN 辯論 / 決策日誌）
    - error               → error
    - autonomous_message  → autonomous（Aize 主動找主人說話）
    """
    if not isinstance(response, dict):
        return
    rtype = response.get("type")
    try:
        if rtype == "internal_thought":
            content = response.get("thought", "") or ""
            if not content:
                return
            _idle_event_bus.publish({
                "type": "thought",
                "thought_type": classify_idle_thought_type(content, response.get("thought_type", "")),
                "content": content,
                "time": _now_display(),
            })
        elif rtype == "error":
            _idle_event_bus.publish({
                "type": "error",
                "thought_type": "error",
                "content": response.get("error", "") or "",
                "time": _now_display(),
            })
        elif rtype == "autonomous_message":
            _idle_event_bus.publish({
                "type": "autonomous",
                "thought_type": "social",
                "content": response.get("message", "") or "",
                "time": _now_display(),
            })
    except Exception as e:
        logger.warning(f"[Events] publish failed: {e}")


# 網頁端允許顯式執行的技能白名單（shell 等高危技能不在此列，
# 它們只能由模型通過 JSON 協議調用）
_SKILL_EXECUTE_WHITELIST = {
    "misskey-bot": {"status", "configure", "set_bot"},
}


# 延迟导入llm模块，避免循环依赖
_generate_with_emotion_feedback = None
_generate_with_emotion_feedback_stream = None

def _get_llm_functions():
    """延迟获取LLM函数"""
    global _generate_with_emotion_feedback, _generate_with_emotion_feedback_stream
    if _generate_with_emotion_feedback is None:
        try:
            from llm.llm_enhanced import generate_with_emotion_feedback, generate_with_emotion_feedback_stream
            _generate_with_emotion_feedback = generate_with_emotion_feedback
            _generate_with_emotion_feedback_stream = generate_with_emotion_feedback_stream
        except ImportError as e:
            logger.error(f"Failed to import llm_enhanced: {e}")
            _generate_with_emotion_feedback = _fallback_generate
            _generate_with_emotion_feedback_stream = _fallback_generate_stream
    return _generate_with_emotion_feedback, _generate_with_emotion_feedback_stream


def _fallback_generate(prompt, emotion_monitor=None):
    """回退方案：直接调用llama-server"""
    import requests
    try:
        response = requests.post(
            "http://127.0.0.1:8080/completion",
            json={"prompt": prompt, "n_predict": 512, "temperature": 0.7, "top_p": 0.9, "ignore_eos": False},
            timeout=300
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("content", "") if isinstance(data, dict) else str(data)
        return text.strip(), None
    except Exception as e:
        logger.error(f"Fallback generate error: {e}")
        return f"[error] {e}", None


def _fallback_generate_stream(prompt, emotion_monitor=None):
    """回退方案：直接流式调用llama-server"""
    import requests
    try:
        response = requests.post(
            "http://127.0.0.1:8080/completion",
            json={"prompt": prompt, "n_predict": 512, "temperature": 0.7, "top_p": 0.9, "ignore_eos": False, "stream": True},
            timeout=300,
            stream=True
        )
        response.raise_for_status()
        for line in response.iter_lines(chunk_size=1024):
            if not line:
                continue
            line_str = line.decode('utf-8', errors='ignore').strip()
            if line_str.startswith('data:'):
                data_str = line_str[5:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        token = data.get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.error(f"Fallback stream error: {e}")
        yield f"[error] {e}"


class ThinkingEngineState:
    """共享状态 - 与GUI的ThinkingEngine交互"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._thinking_engine = None
                cls._instance._memory = None
                cls._instance._personality = None
                cls._instance._qq_ui_callback = None
        return cls._instance

    def set_thinking_engine(self, engine):
        self._thinking_engine = engine

    def get_thinking_engine(self):
        return self._thinking_engine

    def set_memory(self, memory):
        self._memory = memory

    def get_memory(self):
        return self._memory

    def set_personality(self, personality):
        self._personality = personality

    def get_personality(self):
        return self._personality

    def set_qq_ui_callback(self, callback):
        self._qq_ui_callback = callback

    def get_qq_ui_callback(self):
        return self._qq_ui_callback


from utils.reply_cleaner import clean_reply


def build_prompt_from_messages(messages, personality_prompt=""):
    """從OpenAI格式的messages構建prompt（按當前模型的對話模板渲染）"""
    try:
        from llm.chat_format import render_messages
    except ImportError:
        from core.llm.chat_format import render_messages
    return render_messages(messages, personality_prompt)


def build_context_from_memory(memory, max_messages=8):
    """从memory构建上下文"""
    if not memory:
        return ""

    messages = memory.get("messages", [])[-max_messages:]
    context = "Recent conversation:"
    for msg in messages:
        role = msg.get("role", "").capitalize()
        source = msg.get("source", "")
        content = msg.get("content", "")[:100]

        if source == "user":
            context += f"\n[用户] {content}"
        elif source == "ai_autonomous":
            context += f"\n[Aize主动] {content}"
        elif source == "ai_response":
            context += f"\n[Aize回复] {content}"
        else:
            context += f"\n{role}: {content}"
    return context


class ResponseCollector:
    """响应收集器 - 收集ThinkingEngine的回调响应
    支持流式和同步两种模式，在最后一个块后等待一段时间没有新消息则认为任务完成"""
    
    def __init__(self, timeout=600, completion_wait=5, first_chunk_wait=600):
        """非流式生成在 CPU 上可能 60-90 秒後才返回唯一的一個 chunk，
        首塊等待必須遠大於 chunk 間隔，否則會在生成完成前誤判為空回覆。
        低配機器（RAM 不足換頁）上 prompt 評估可達 3 分鐘以上，因此
        總超時與首塊等待都取 10 分鐘。"""
        self._queue = Queue()
        self._timeout = timeout
        self._completion_wait = completion_wait
        self._first_chunk_wait = first_chunk_wait
        self._full_reply = ""
        self._thoughts = []
        self._finished = False
        self._last_chunk_time = 0

    def callback(self, response):
        """ThinkingEngine回调函数"""
        if response.get("type") == "chat_response":
            reply = response.get("reply", "")
            self._full_reply += reply
            self._last_chunk_time = time.time()
            self._queue.put({"type": "chunk", "content": reply})
        elif response.get("type") == "internal_thought":
            thought = response.get("thought", "")
            thought_type = response.get("thought_type", "")
            self._thoughts.append(thought)
            logger.info(f"[ThinkingEngine] Internal thought: {thought[:100]}...")
            # 注意：思考片段不更新 _last_chunk_time——真正的 LLM 回覆可能
            # 在思考後數分鐘才到（慢機器），若按 5 秒靜默判完成會截斷回覆
            self._queue.put({"type": "thought", "content": thought, "thought_type": thought_type})
        elif response.get("type") == "gan_complete":
            pass
        elif response.get("type") == "command_start":
            self._last_chunk_time = time.time()
            self._queue.put({"type": "command_start", "message": response.get("message", "")})
        elif response.get("type") == "command_result":
            self._last_chunk_time = time.time()
            self._queue.put({"type": "command_result", "output": response.get("output", "")})
        elif response.get("type") == "error":
            self._queue.put({"type": "error", "content": response.get("error", "")})
            self._finished = True
    
    def get_chunk(self):
        """获取下一个响应块
        在最后一个块后等待_completion_wait秒，如果没有新消息则返回完成标记"""
        try:
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed >= self._timeout:
                    return {"type": "timeout"}
                
                # 检查是否已经有一段时间没有新消息了
                if self._last_chunk_time > 0:
                    time_since_last_chunk = time.time() - self._last_chunk_time
                    if time_since_last_chunk >= self._completion_wait:
                        return {"type": "done"}
                
                # 如果从未收到任何块，给慢的 CPU 推理留足首块时间
                if self._last_chunk_time == 0 and elapsed >= self._first_chunk_wait:
                    return {"type": "done"}
                
                # 尝试获取队列中的消息（非阻塞）
                try:
                    return self._queue.get(timeout=0.5)
                except Empty:
                    continue
        except Exception:
            return {"type": "timeout"}
    
    def is_finished(self):
        """检查是否已完成"""
        return self._finished
    
    def set_finished(self):
        """标记完成"""
        self._finished = True
    
    def get_full_reply(self):
        """获取完整回复"""
        return self._full_reply
    
    def get_thoughts(self):
        """获取思考内容"""
        return self._thoughts


EMPTY_REPLY_ERROR = "錯誤：AI 沒有產生任何有效內容"


class ThinkingEngineAPIHandler(BaseHTTPRequestHandler):
    """OpenAI兼容的API处理器"""

    # 聊天互斥鎖：ThinkingEngine 只有一個 worker，任務串行處理。
    # 若允許第二個聊天請求進入，它的 collector 會熱頂替引擎的全局 on_response，
    # 從而把前一個任務正在生成的內容串給新客戶端（且新任務的回答無人接收）。
    _chat_lock = threading.Lock()

    def log_message(self, format, *args):
        logger.info(f"[HTTP] client={self.client_address[0]} request={args[0]}")

    def _log_request(self, method, path):
        self._request_started_at = time.perf_counter()
        logger.info(
            f"[HTTP] start method={method} path={path} client={self.client_address[0]} "
            f"content_length={self.headers.get('Content-Length', '0')} "
            f"user_agent={self.headers.get('User-Agent', '-')[:120]}"
        )

    def finish(self):
        try:
            duration_ms = (time.perf_counter() - getattr(self, '_request_started_at', time.perf_counter())) * 1000
            logger.info(f"[HTTP] finish method={self.command} path={self.path} duration_ms={duration_ms:.1f}")
        finally:
            super().finish()

    def _send_json(self, data, status=200):
        """发送JSON响应"""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message, status=400):
        """发送错误响应"""
        self._send_json({"error": {"message": message, "type": "invalid_request_error"}}, status)

    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    # ---------- 訪問控制：局域網門禁 + 賬戶登錄 ----------
    _LOCAL_CLIENTS = ("127.0.0.1", "::1", "localhost")
    _AUTH_EXEMPT_PATHS = ("/api/login", "/health")

    def _lan_blocked(self) -> bool:
        """非本機來源且未開啟局域網訪問 → 拒絕（熱生效）。"""
        client_ip = (self.client_address[0] if self.client_address else "") or ""
        if client_ip in self._LOCAL_CLIENTS:
            return False
        return not bool(self._read_settings_raw().get("allow_lan_access"))

    def _auth_required(self) -> bool:
        settings = self._read_settings_raw()
        return bool(settings.get("web_auth_username") and settings.get("web_auth_password_hash"))

    def _session_valid(self) -> bool:
        token = ""
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "humanaize_session":
                token = value
                break
        if not token:
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:].strip()
        if not token:
            return False
        expiry = _SESSIONS.get(token)
        if expiry is None:
            return False
        if expiry < time.time():
            _SESSIONS.pop(token, None)
            return False
        return True

    def _access_granted(self, path: str) -> bool:
        """統一入口：先局域網門禁，再登錄認證。返回 False 時已自行回應。"""
        if self._lan_blocked():
            self._send_error("局域网访问未启用，仅本机可访问此面板", 403)
            return False
        if path in self._AUTH_EXEMPT_PATHS or not self._auth_required():
            return True
        if self._session_valid():
            return True
        if path == "/":
            self._send_login_page()
        else:
            self._send_error("未登录或会话已过期", 401)
        return False

    def _send_login_page(self):
        body = _LOGIN_PAGE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def _handle_login(self):
        """校驗賬密，成功則簽發會話 Cookie。"""
        try:
            body = self._read_json_body()
        except Exception:
            self._send_error("Invalid request", 400)
            return
        if not self._auth_required():
            self._send_json({"status": "ok", "auth_required": False})
            return
        settings = self._read_settings_raw()
        username = str(body.get("username", ""))
        password = str(body.get("password", ""))
        ok = (secrets.compare_digest(username, str(settings.get("web_auth_username") or ""))
              and self._verify_web_password(password, str(settings.get("web_auth_password_hash") or "")))
        if not ok:
            logger.info(f"[Auth] login failed for user={username!r} from {self.client_address[0]}")
            self._send_error("账户名或密码错误", 401)
            return
        token = secrets.token_urlsafe(32)
        _SESSIONS[token] = time.time() + _AUTH_TTL_SECONDS
        logger.info(f"[Auth] login success for user={username!r}")
        payload = json.dumps({"status": "ok"}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Set-Cookie',
                         f"humanaize_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={_AUTH_TTL_SECONDS}")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_logout(self):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "humanaize_session":
                _SESSIONS.pop(value, None)
        payload = json.dumps({"status": "ok"}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Set-Cookie', "humanaize_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        """处理GET请求"""
        parsed = urlparse(self.path)
        self._log_request("GET", parsed.path)
        if not self._access_granted(parsed.path):
            return

        if parsed.path == '/v1/models':
            self._handle_list_models()
        elif parsed.path == '/health':
            self._send_json({"status": "ok", "service": "thinking-engine-api"})
        elif parsed.path == '/api/settings':
            self._send_json(self._load_settings())
        elif parsed.path == '/api/status':
            self._send_json(self._status_payload())
        elif parsed.path == '/api/voice/capabilities':
            self._handle_voice_capabilities()
        elif parsed.path == '/api/events':
            self._handle_event_stream()
        elif parsed.path == '/api/skills':
            self._handle_list_skills()
        elif parsed.path == '/':
            self._send_static_file("index.html", "text/html; charset=utf-8")
        elif parsed.path == '/background':
            found = self._find_background_image()
            if found is None:
                self._send_error("Not found", 404)
            else:
                image_path, image_type = found
                self._send_file_path(image_path, image_type)
        elif parsed.path.startswith('/assets/'):
            asset_name = parsed.path.removeprefix('/assets/')
            asset_types = {"styles.css": "text/css; charset=utf-8", "app.js": "application/javascript; charset=utf-8"}
            if asset_name in asset_types:
                self._send_static_file(asset_name, asset_types[asset_name])
            else:
                self._send_error("Not found", 404)
        else:
            self._send_error("Not found", 404)

    def _send_static_file(self, file_name, content_type):
        """返回浏览器管理面板静态资源。

        优先级（与 _find_background_image 一致，支持热更新 web UI 不重建）：
        1. 打包态 exe 旁 web/（用户可修改）
        2. 开发态代码目录 web/
        3. PyInstaller _MEIPASS 内置副本（兜底）
        """
        roots = []
        if getattr(sys, "frozen", False):
            roots.append(os.path.dirname(os.path.abspath(sys.executable)))
        roots.append(os.path.dirname(__file__))
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(meipass)

        dashboard_path = None
        for root in roots:
            path = os.path.join(root, "web", file_name)
            if os.path.exists(path):
                dashboard_path = path
                break
        if not dashboard_path:
            self._send_error("Static file not found", 500)
            return
        self._send_file_path(dashboard_path, content_type)

    def _send_file_path(self, file_path, content_type):
        """按絕對路徑返回二進制文件內容"""
        try:
            with open(file_path, "rb") as static_file:
                body = static_file.read()
        except OSError:
            self._send_error("Static file not found", 500)
            return

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def _find_background_image(self):
        """查找網頁自定義背景圖 Assets/Background.{jpg,jpeg,png}。

        查找順序：打包後的安裝目錄（用戶放入圖片即可生效，無需重裝）
        → 開發態項目根目錄 → onefile 解包目錄（安裝包內置默認圖）。
        返回 (絕對路徑, MIME) 或 None。
        """
        roots = []
        if getattr(sys, "frozen", False):
            roots.append(os.path.dirname(os.path.abspath(sys.executable)))
        roots.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(meipass)

        candidates = (
            ("Background.jpg", "image/jpeg"),
            ("Background.jpeg", "image/jpeg"),
            ("Background.png", "image/png"),
        )
        seen = set()
        for root in roots:
            if not root or root in seen:
                continue
            seen.add(root)
            assets_dir = os.path.join(root, "Assets")
            for name, mime in candidates:
                image_path = os.path.join(assets_dir, name)
                if os.path.isfile(image_path):
                    return image_path, mime
        return None

    def do_POST(self):
        """处理POST请求"""
        parsed = urlparse(self.path)
        self._log_request("POST", parsed.path)
        if not self._access_granted(parsed.path):
            return

        if parsed.path in ('/api/chat', '/v1/chat/completions'):
            self._handle_chat_completions()
        elif parsed.path == '/api/settings':
            self._handle_save_settings()
        elif parsed.path == '/api/login':
            self._handle_login()
        elif parsed.path == '/api/logout':
            self._handle_logout()
        elif parsed.path == '/api/tts':
            self._handle_tts()
        elif parsed.path == '/api/skills/toggle':
            self._handle_skill_toggle()
        elif parsed.path == '/api/skills/execute':
            self._handle_skill_execute()
        else:
            self._send_error("Not found", 404)

    def _settings_path(self):
        return get_settings_path()

    def _active_llm_model(self, server_url):
        """向本地 llama-server 查詢實際加載的模型名（RAM 不足自動退回時與設置值不同）。

        查詢失敗時 60 秒內沿用最後一次成功結果，避免狀態頁輪詢被超時拖慢。
        """
        import time
        from urllib.request import urlopen

        now = time.time()
        try:
            with urlopen(server_url.rstrip("/") + "/v1/models", timeout=1.0) as resp:
                data = json.load(resp)
            name = str(((data.get("data") or [{}])[0]).get("id") or "").strip()
            if name:
                _LLAMA_MODEL_CACHE.update(name=name, ts=now)
            return name
        except Exception:
            if now - _LLAMA_MODEL_CACHE.get("ts", 0.0) < 60:
                return _LLAMA_MODEL_CACHE.get("name", "")
            return ""

    def _status_payload(self):
        memory = ThinkingEngineState().get_memory() or {}
        settings = self._load_settings()
        # 顯示實際生效的模型：OpenAI > llama-server 實際加載 > 自定義 model_path > 標籤
        if settings.get("openai_enabled") and settings.get("openai_api_key") == "configured":
            display_model = settings.get("openai_model", "openai")
        else:
            active = self._active_llm_model(str(settings.get("llm_server_url") or "http://127.0.0.1:8080"))
            if active:
                display_model = active
            else:
                custom_model = str(settings.get("model_path", "")).strip()
                display_model = os.path.basename(custom_model) if custom_model else settings.get("model_name", "local")
        return {
            "status": "ok",
            "version": get_version(),
            "model": display_model,
            "messages": memory.get("messages", [])[-100:],
            "thoughts": memory.get("thoughts", [])[-100:],
            "decisions": memory.get("decisions", [])[-100:],
        }

    def _settings_defaults(self):
        return {
            "language": "中文", "theme": "Liquid Glass", "model_name": "tinyllama",
            "model_path": "", "openai_enabled": False, "openai_api_key": "", "openai_base_url": "https://api.openai.com/v1", "openai_model": "gpt-4o-mini", "gan_enabled": True, "auto_break_silence": True,
            "skills_prompt": "", "llm_server_url": "http://127.0.0.1:8080",
            "max_tokens": 256, "temperature": 0.7, "guard_enabled": False,
            "guard_auto_start": False, "guard_interval": 5, "guard_firewall": True,
            "guard_network_monitor": True, "guard_system_monitor": True,
            "counter_measure_enabled": True, "counter_lab_mode": False,
            "counter_max_warnings": 2, "counter_cooldown": 300, "iot_auto_start": True,
            "iot_host": "0.0.0.0", "iot_port": 8765, "iot_scan_enabled": True,
            "iot_scan_interval": 30, "iot_discovered_devices": [],
            "allow_lan_access": False, "web_auth_username": "", "web_auth_password_hash": ""
        }

    def _read_settings_raw(self):
        """讀取持久設置（不脫敏），僅供內部邏輯/保存合併使用。"""
        settings = self._settings_defaults()
        try:
            with open(self._settings_path(), "r", encoding="utf-8") as settings_file:
                values = json.load(settings_file)
            if isinstance(values, dict):
                settings.update(values)
        except (OSError, ValueError):
            pass
        return settings

    def _load_settings(self):
        """對網頁返回的脫敏視圖（API key 只回 configured 佔位符；密碼 hash 不返回）。"""
        settings = self._read_settings_raw()
        if settings.get("openai_api_key"):
            settings["openai_api_key"] = "configured"
        settings["web_auth_enabled"] = bool(
            settings.get("web_auth_username") and settings.get("web_auth_password_hash"))
        settings.pop("web_auth_password_hash", None)
        return settings

    @staticmethod
    def _hash_web_password(password: str, salt: str = None) -> str:
        """salt$sha256(salt+password) 存儲格式；salt 為空時生成新 salt。"""
        salt = salt or secrets.token_hex(8)
        digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return f"{salt}${digest}"

    @staticmethod
    def _verify_web_password(password: str, stored: str) -> bool:
        try:
            salt, digest = stored.split("$", 1)
        except ValueError:
            return False
        candidate = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return secrets.compare_digest(candidate, digest)

    def _handle_save_settings(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            values = json.loads(self.rfile.read(content_length).decode('utf-8'))
            if not isinstance(values, dict):
                raise ValueError("settings must be an object")
            # 密碼不是持久 key，先取出單獨處理（「留空不修改」語義）
            new_password = str(values.pop("web_auth_password", "") or "")
            # 以磁盤上的原始設置（含真實 API key）為基準合併，避免脫敏佔位符覆蓋密鑰
            settings = self._read_settings_raw()
            allowed = set(settings)
            updates = {key: value for key, value in values.items() if key in allowed}
            if updates.get("openai_api_key") == "configured":
                updates.pop("openai_api_key")
            # 賬戶名被清空 → 關閉登錄（連同 hash 一起清掉）
            if "web_auth_username" in updates and not str(updates.get("web_auth_username") or "").strip():
                updates["web_auth_username"] = ""
                updates["web_auth_password_hash"] = ""
            elif new_password:
                updates["web_auth_password_hash"] = self._hash_web_password(new_password)
            model_path_changed = (
                "model_path" in updates
                and str(updates.get("model_path", "")).strip() != str(settings.get("model_path", "")).strip()
            )
            settings.update(updates)
            os.makedirs(os.path.dirname(self._settings_path()), exist_ok=True)
            with open(self._settings_path(), "w", encoding="utf-8") as settings_file:
                json.dump(settings, settings_file, ensure_ascii=False, indent=2)

            # GAN 開關熱生效：即時同步給正在運行的閒置引擎
            if "gan_enabled" in updates:
                try:
                    from ui import idle as idle_mod
                    inst = getattr(idle_mod, "_idle_engine_instance", None)
                    if inst is not None:
                        inst.gan_enabled = bool(updates.get("gan_enabled"))
                except Exception:
                    pass

            response = {"status": "ok", "settings": self._load_settings()}
            if model_path_changed and str(updates.get("model_path", "")).strip():
                # 模型路徑在 llama-server 啟動時消費，需重啟後端進程才能切換
                self._schedule_model_server_restart()
                response["restart_required"] = True
                response["message"] = "模型路徑已保存，正在重啟 LLM 服務…"
            self._send_json(response)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self._send_error(f"Invalid settings: {error}")

    def _schedule_model_server_restart(self):
        """後台強制重啟本地 llama-server，使新模型路徑生效。"""
        def _restart():
            try:
                try:
                    from main import _check_and_start_server
                except ImportError:
                    from core.main import _check_and_start_server
                _check_and_start_server(force_restart=True)
            except Exception as error:  # noqa: BLE001 - 後台線程需兜底
                logger.error(f"Failed to restart LLM server after model path change: {error}")

        threading.Thread(target=_restart, daemon=True).start()

    def _handle_voice_capabilities(self):
        """告知網頁端語音能力：TTS 引擎是否可用及默認音色。
        STT 使用瀏覽器內建 Web Speech API，由前端自行探測。"""
        tts_available = False
        default_voice = "zh-CN-XiaoxiaoNeural"
        try:
            import edge_tts  # noqa: F401
            tts_available = True
        except Exception:
            tts_available = False
        self._send_json({
            "tts_available": tts_available,
            "default_voice": default_voice,
            "stt": "webspeech",
        })

    def _handle_event_stream(self):
        """SSE 長連接：把閒置思考 / GAN 日誌 / 社交事件即時推給網頁 GAN 面板。

        連接建立時先補發緩衝中的最近事件（翻譯：刷新頁面也能看到本輪思考），
        之後每 20 秒髮一個 ping 保持連接；EventSource 斷線會自動重連，
        前端按 seq 去重，避免補發歷史造成重複行。
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        queue, recent = _idle_event_bus.subscribe()
        try:
            for event in recent:
                self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode('utf-8'))
            self.wfile.flush()
            while True:
                try:
                    event = queue.get(timeout=20)
                except Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        except Exception as e:
            logger.warning(f"[Events] stream closed: {e}")
        finally:
            _idle_event_bus.unsubscribe(queue)

    def _handle_list_skills(self):
        """返回技能清單（名稱/說明/是否啟用/是否有執行器），不回傳任何密鑰。"""
        try:
            manager = _get_skills_manager()
            skills = [{
                "name": skill.name,
                "description": (skill.description or "")[:300],
                "enabled": bool(skill.enabled),
                "executable": bool(skill.executor),
            } for skill in manager.get_all_skills()]
            skills.sort(key=lambda item: item["name"].lower())
            self._send_json({
                "skills": skills,
                "all_enabled": bool(manager.skills_config.get("all_enabled", True)),
            })
        except Exception as e:
            logger.error(f"[Skills] list failed: {e}\n{traceback.format_exc()}")
            self._send_error(f"读取技能列表失败: {e}", 500)

    def _read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        if not isinstance(body, dict):
            raise ValueError("request body must be a JSON object")
        return body

    def _handle_skill_toggle(self):
        """啟用/停用技能：{"name": "misskey-bot", "enabled": true}"""
        try:
            body = self._read_json_body()
            name = str(body.get("name", "")).strip()
            enabled = bool(body.get("enabled"))
            if not name:
                self._send_error("技能名称不能为空", 400)
                return
            manager = _get_skills_manager()
            if not manager.get_skill(name):
                self._send_error(f"未找到技能: {name}", 404)
                return
            if enabled:
                manager.enable_skill(name)
            else:
                manager.disable_skill(name)
            _invalidate_skills_prompt_cache()
            logger.info(f"[Skills] toggle name={name} enabled={enabled}")
            self._send_json({
                "status": "ok",
                "name": name,
                "enabled": enabled,
                "skills": [{
                    "name": skill.name,
                    "description": (skill.description or "")[:300],
                    "enabled": bool(skill.enabled),
                    "executable": bool(skill.executor),
                } for skill in sorted(manager.get_all_skills(),
                                      key=lambda item: item.name.lower())],
            })
        except (OSError, ValueError, json.JSONDecodeError) as e:
            self._send_error(f"Invalid request: {e}")

    def _handle_skill_execute(self):
        """執行白名單內的安全技能動作用於網頁配置（目前僅 misskey-bot）。

        請求體: {"name": "misskey-bot", "action": "configure", "params": {...}}
        Token 採「留空不修改」語義，且任何返回都不包含密鑰明文。
        """
        try:
            body = self._read_json_body()
            name = str(body.get("name", "")).strip()
            action = str(body.get("action", "")).strip().lower()
            params = body.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            allowed_actions = _SKILL_EXECUTE_WHITELIST.get(name)
            if not allowed_actions or action not in allowed_actions:
                self._send_error("不允许从网页执行该技能或动作", 403)
                return

            clean_params = {}
            if action == "configure":
                host = str(params.get("host", "")).strip()
                token = str(params.get("token", "")).strip()
                visibility = str(params.get("default_visibility", "")).strip()
                if host:
                    clean_params["host"] = host
                if visibility:
                    clean_params["default_visibility"] = visibility
                # 空串或脫敏佔位符都視為「不修改現有 token」
                if token and token != "configured":
                    clean_params["token"] = token

            manager = _get_skills_manager()
            result = manager.execute_skill(
                name, {"action": action, "params": clean_params}, language="zh-TW")
            if action in ("configure", "set_bot"):
                _invalidate_skills_prompt_cache()
            self._send_json({"status": "ok", "result": result})
        except (OSError, ValueError, json.JSONDecodeError) as e:
            self._send_error(f"Invalid request: {e}")
        except Exception as e:
            logger.error(f"[Skills] execute failed: {e}\n{traceback.format_exc()}")
            self._send_error(f"技能执行失败: {e}", 500)

    def _handle_tts(self):
        """將文本合成為語音音頻（預設 edge-tts，返回 audio/mpeg）。

        請求體: {"text": "...", "voice"?: "zh-CN-XiaoxiaoNeural"}
        網頁端按句調用，配合流式對話實現「AI 輸出多少就朗讀多少」。
        """
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except Exception as e:
            self._send_error(f"Invalid JSON body: {e}")
            return

        text = (body.get("text") or "").strip() if isinstance(body, dict) else ""
        voice = (body.get("voice") or "").strip() if isinstance(body, dict) else ""
        if not text:
            self._send_error("text is required", 400)
            return
        if len(text) > 4000:
            self._send_error("text too long (max 4000 chars per chunk)", 400)
            return

        try:
            try:
                from voice.tts_synthesizer import SynthesizeOptions, synthesize_speech, TTSError
            except ModuleNotFoundError:
                from core.voice.tts_synthesizer import SynthesizeOptions, synthesize_speech, TTSError

            result = synthesize_speech(SynthesizeOptions(text=text, voice=voice))
            audio = result.get("audio_bytes") or b""
            content_type = result.get("content_type") or "audio/mpeg"
            if not audio:
                self._send_error("TTS returned empty audio", 502)
                return

            logger.info(f"[TTS] provider={result.get('provider')} chars={len(text)} bytes={len(audio)}")
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(audio)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(audio)
        except Exception as e:
            status = getattr(e, "status", 500)
            logger.warning(f"[TTS] synthesis failed status={status} error={e}")
            self._send_error(f"TTS failed: {e}", status)

    def _handle_list_models(self):
        """返回可用模型列表"""
        models = [
            {
                "id": "thinking-engine",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "humanaize"
            },
            {
                "id": "aize-v2",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "humanaize"
            }
        ]
        self._send_json({"object": "list", "data": models})

    def _handle_chat_completions(self):
        """处理聊天完成请求 - OpenAI兼容格式
        QQ-bot和客户端共用同样的处理函数和逻辑，都通过ThinkingEngine队列处理"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_data = self.rfile.read(content_length)
            body = json.loads(body_data.decode('utf-8'))
        except Exception as e:
            logger.warning(f"[Chat] invalid request body size={content_length if 'content_length' in locals() else 0} error={e}")
            self._send_error(f"Invalid JSON body: {e}")
            return

        messages = body.get('messages', [])
        stream = body.get('stream', False)
        max_tokens = body.get('max_tokens', 512)
        temperature = body.get('temperature', 0.7)

        logger.info(
            f"[Chat] parsed path={urlparse(self.path).path} messages={len(messages)} "
            f"stream={stream} max_tokens={max_tokens} temperature={temperature}"
        )

        if not messages:
            self._send_error("messages is required")
            return

        # 获取共享状态
        state = ThinkingEngineState()
        thinking_engine = state.get_thinking_engine()
        memory = state.get_memory()
        personality = state.get_personality()

        # 必须有ThinkingEngine实例
        if not thinking_engine:
            logger.error("[Chat] rejected because ThinkingEngine is not initialized")
            self._send_error("ThinkingEngine not available", 503)
            return

        # 通知IdleEngine暂停（如果有），优先处理用户消息
        try:
            thinking_engine.pause_idle()
        except Exception:
            pass

        # 构建角色提示
        personality_prompt = ""
        if personality:
            personality_prompt = getattr(personality, 'description', '') or str(personality)

        # 从messages中提取用户输入
        user_text = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_text = msg.get('content', '')
                break

        # 构建完整prompt（系統/人格/記憶上下文統一進入模型的 system 塊，
        # 再按當前模型家族的對話模板渲染，避免特殊標記前混入裸文本）
        context = build_context_from_memory(memory) if memory else ""
        system_block_parts = []
        # 載入用戶可編輯的 system_prompt.txt（角色扮演/人設提示詞）。
        # 歷史 bug：load_system_prompt() 定義了但從未被調用，用戶改了
        # Prompt\system_prompt.txt 也不會生效；每次請求實時讀取，改完即生效。
        try:
            from data.prompts_manager import load_system_prompt
        except ImportError:
            from core.data.prompts_manager import load_system_prompt
        _system_prompt_text = (load_system_prompt() or "").strip()
        if _system_prompt_text:
            system_block_parts.append(_system_prompt_text)
        if personality_prompt:
            system_block_parts.append(personality_prompt)
        # 角色扮演人設（agent_prompt.txt）放進 system 塊：放在這裡模型才會
        # 真正入戲；走 MAIN/OTHER 三明治組裝時會被嵌套 prompt 稀釋/衝突
        try:
            from data.prompts_manager import load_agent_prompt
        except ImportError:
            from core.data.prompts_manager import load_agent_prompt
        _agent_prompt_text = (load_agent_prompt() or "").strip()
        if _agent_prompt_text:
            system_block_parts.append(_agent_prompt_text)
        # 運行時實際可用的技能清單（安裝目錄 skills/ 下已啟用的技能），
        # 讓模型知道「什麼時候該用、具體叫什麼名字」，而不是只記得 JSON 格式
        _skills_text = _get_skills_prompt_cached()
        if _skills_text:
            system_block_parts.append(_skills_text)
        if context:
            system_block_parts.append(context)
        full_prompt = build_prompt_from_messages(messages, "\n\n".join(system_block_parts))

        logger.info(
            f"[Chat] dispatch user_text_length={len(user_text)} prompt_length={len(full_prompt)} "
            f"memory_available={bool(memory)} personality_available={bool(personality)} stream={stream}"
        )

        # 單 worker 串行：上一個聊天還在生成時直接禮貌拒絕，避免 collector 互相頂替
        if not self._chat_lock.acquire(blocking=False):
            logger.warning("[Chat] rejected: another chat task is still being processed")
            self._send_error("AI 正在思考中，請等待當前回覆完成後再發送", 409)
            return

        # 创建响应收集器
        collector = ResponseCollector(timeout=300)

        # 保存原始on_response回调
        original_on_response = thinking_engine.on_response

        # 设置临时回调；同时把思考/错误事件桥接到全局事件汇流排，
        # 让网页 GAN 面板能实时看到本次对话的 GAN 决策与辩论日志
        def _bridged_callback(response):
            collector.callback(response)
            if isinstance(response, dict) and response.get("type") in (
                    "internal_thought", "error", "autonomous_message"):
                publish_engine_event(response)

        thinking_engine.on_response = _bridged_callback

        try:
            if stream:
                # 通过ThinkingEngine队列提交流式聊天任务
                thinking_engine.queue_chat_stream_task(
                    full_prompt,
                    memory=memory,
                    user_text=user_text,
                    target_info=None
                )
                logger.debug("[Chat] stream task queued")
                self._handle_stream_response(collector, state)
            else:
                # 通过ThinkingEngine队列提交聊天任务
                thinking_engine.queue_chat_task(
                    full_prompt,
                    memory=memory,
                    user_text=user_text,
                    personality=personality,
                    use_gan_decision=True
                )
                logger.debug("[Chat] sync task queued")
                self._handle_sync_response(collector, user_text, memory, state)
        finally:
            # 恢复原始回调
            thinking_engine.on_response = original_on_response
            # 对话结束：让闲置引擎继续暂停 60 秒后自动恢复，避免争抢本地推理
            try:
                from ui import idle as idle_mod
                inst = getattr(idle_mod, "_idle_engine_instance", None)
                if inst is not None and getattr(inst, "running", False):
                    inst.schedule_resume(60)
            except Exception:
                pass
            try:
                self._chat_lock.release()
            except RuntimeError:
                pass

    def _handle_sync_response(self, collector, user_text, memory, state):
        """处理同步（非流式）响应 - 通过ResponseCollector收集ThinkingEngine的响应"""
        try:
            # 等待响应完成（最多等待collector的timeout）
            full_reply = ""
            while True:
                chunk = collector.get_chunk()
                if chunk["type"] == "chunk":
                    full_reply += chunk["content"]
                elif chunk["type"] == "done":
                    # 任务完成，退出循环
                    break
                elif chunk["type"] == "error":
                    full_reply = f"错误: {chunk['content']}"
                    break
                elif chunk["type"] == "timeout":
                    full_reply = "抱歉，我刚才走神了～能再说一遍吗？😊"
                    break

            # 标记完成
            collector.set_finished()

            # 清理回复
            cleaned_reply = clean_reply(full_reply) if full_reply else ""

            if not cleaned_reply:
                raise ValueError(EMPTY_REPLY_ERROR)

            # 通知QQ UI更新（显示Aize发送的消息）
            qq_callback = state.get_qq_ui_callback()
            if qq_callback:
                try:
                    qq_callback({
                        'type': 'sent',
                        'from': 'Aize',
                        'target_id': 'QQ',
                        'message_type': 'private',
                        'message': cleaned_reply,
                        'timestamp': time.time()
                    })
                except Exception as e:
                    logger.error(f"[ThinkingEngine API] QQ UI callback error: {e}")

            # 构建OpenAI格式响应
            response = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "thinking-engine",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": cleaned_reply
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": len(cleaned_reply) // 4,
                    "total_tokens": len(cleaned_reply) // 4
                }
            }

            logger.info(f"[ThinkingEngine API] Sync response: '{cleaned_reply[:50]}...'")
            self._send_json(response)

        except Exception as e:
            logger.error(f"[Chat] sync response error type={type(e).__name__} error={e}\n{traceback.format_exc()}")
            error_message = str(e) if str(e) else "抱歉，AI 沒有產生任何有效內容。"
            self._send_json({
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "thinking-engine",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": error_message
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            })

    def _handle_stream_response(self, collector, state):
        """处理流式响应 - SSE格式
        通过ResponseCollector收集ThinkingEngine的响应，实现QQ-bot和客户端共用同样的处理逻辑"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        # 流結束（[DONE]）後必須關閉連接：keep-alive 會讓 curl/AstrBot 等
        # 客戶端在收到完整回覆後仍掛起等待，直到自身超時
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        chat_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())

        try:
            # 累积完整回复用于清理和UI更新
            full_reply = ""
            
            # 从ResponseCollector获取流式响应
            while True:
                chunk = collector.get_chunk()
                
                if chunk["type"] == "chunk":
                    content = chunk["content"]
                    full_reply += content

                    # 发送SSE块
                    sse_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": content},
                                "finish_reason": None
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(sse_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                        self.wfile.flush()
                    except BrokenPipeError:
                        logger.info("[ThinkingEngine API] Client disconnected")
                        break
                        
                elif chunk["type"] == "thought":
                    thought_content = chunk["content"]
                    thought_type = chunk.get("thought_type", "")
                    thought_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        # 前端依 thought/thought_type 把該幀渲染成彩色日誌行，而非回覆正文
                        "thought": True,
                        "thought_type": thought_type,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": thought_content},
                                "finish_reason": None
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(thought_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                        self.wfile.flush()
                    except BrokenPipeError:
                        pass
                        
                elif chunk["type"] in ("command_start", "command_result"):
                    # 技能執行事件：前端渲染成終端風格區塊，不混入回覆正文
                    cmd_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        "thought": True,
                        "thought_type": "skill",
                        "command_event": chunk["type"],
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "content": chunk.get("message") or chunk.get("output") or ""
                                },
                                "finish_reason": None
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(cmd_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                        self.wfile.flush()
                    except BrokenPipeError:
                        pass

                elif chunk["type"] == "error":
                    # 发送错误消息
                    error_content = f"错误: {chunk['content']}"
                    full_reply += error_content
                    error_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        "error": True,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": error_content},
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                    except BrokenPipeError:
                        pass
                    break
                    
                elif chunk["type"] == "done":
                    if not full_reply:
                        error_content = EMPTY_REPLY_ERROR
                        logger.warning("[ThinkingEngine API] Stream completed without any content; likely no LLM output was produced.")
                        error_chunk = {
                            "id": chat_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": "thinking-engine",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": error_content},
                                    "finish_reason": "stop"
                                }
                            ]
                        }
                        try:
                            self.wfile.write(f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                        except BrokenPipeError:
                            pass
                    else:
                        logger.info(f"[ThinkingEngine API] Task completed naturally with {len(full_reply)} chars of output")
                    break
                elif chunk["type"] == "timeout":
                    timeout_content = "錯誤：AI 回應超時，沒有產生有效內容"
                    full_reply += timeout_content
                    timeout_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "thinking-engine",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": timeout_content},
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    try:
                        self.wfile.write(f"data: {json.dumps(timeout_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                    except BrokenPipeError:
                        pass
                    break

            # 发送结束标记
            final_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "thinking-engine",
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }
                ]
            }
            try:
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except BrokenPipeError:
                pass

            # 标记完成
            collector.set_finished()

            # 通知QQ UI更新（显示Aize发送的消息）
            cleaned_reply = clean_reply(full_reply) if full_reply else ""
            if cleaned_reply:
                qq_callback = state.get_qq_ui_callback()
                if qq_callback:
                    try:
                        qq_callback({
                            'type': 'sent',
                            'from': 'Aize',
                            'target_id': 'QQ',
                            'message_type': 'private',
                            'message': cleaned_reply,
                            'timestamp': time.time()
                        })
                    except Exception as e:
                        logger.error(f"[ThinkingEngine API] QQ UI callback error: {e}")

            logger.info(f"[ThinkingEngine API] Stream response completed: '{full_reply[:50]}...'")

        except Exception as e:
            logger.error(f"[ThinkingEngine API] Stream error: {e}")
            error_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "thinking-engine",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "抱歉，我刚才走神了～能再说一遍吗？😊"},
                        "finish_reason": "stop"
                    }
                ]
            }
            try:
                self.wfile.write(f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except BrokenPipeError:
                pass


class ThinkingEngineAPIServer:
    """ThinkingEngine API服务器"""

    def __init__(self, host='127.0.0.1', port=8082):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        """启动API服务器（在后台线程中）"""
        if self.running:
            return

        self.server = HTTPServer((self.host, self.port), ThinkingEngineAPIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="ThinkingEngineAPI")
        self.thread.start()
        self.running = True
        logger.info(f"ThinkingEngine API server started on http://{self.host}:{self.port}")

    def stop(self):
        """停止API服务器"""
        if not self.running:
            return
        self.server.shutdown()
        self.server.server_close()
        self.running = False
        logger.info("ThinkingEngine API server stopped")

    def is_running(self):
        return self.running


# 全局实例
_api_server = None


def get_api_server():
    """获取API服务器全局实例"""
    global _api_server
    if _api_server is None:
        _api_server = ThinkingEngineAPIServer()
    return _api_server


def start_api_server(host='127.0.0.1', port=8082):
    """启动API服务器"""
    server = get_api_server()
    if not server.is_running():
        server.host = host
        server.port = port
        server.start()
    return server


def stop_api_server():
    """停止API服务器"""
    server = get_api_server()
    if server.is_running():
        server.stop()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='ThinkingEngine API Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind')
    parser.add_argument('--port', type=int, default=8082, help='Port to bind')
    args = parser.parse_args()

    print(f"Starting ThinkingEngine API server on http://{args.host}:{args.port}")
    print(f"OpenAI-compatible endpoint: http://{args.host}:{args.port}/v1/chat/completions")
    print(f"Models list: http://{args.host}:{args.port}/v1/models")
    print(f"Health check: http://{args.host}:{args.port}/health")

    server = ThinkingEngineAPIServer(args.host, args.port)
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
