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
import subprocess
try:
    from http.server import ThreadingHTTPServer as HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
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
    "mcp-client": {"list_servers", "list_tools", "ping", "refresh", "status"},
}


# ---------------------------------------------------------------------------
# 技能配置界面 / 配置讀寫 / 後台服務（通用機制）
#
# Skill 在 SKILL.md metadata 裡聲明即可接入 Dashboard 技能配置區：
#   config_ui: config_ui.html          → GET /api/skills/{name}/config_ui（iframe 嵌入）
#   config_file: config.json           → GET/POST /api/skills/{name}/config（POST 為深合併）
#   config_secret_fields: [a.b]        → 讀取時脫敏為 "configured"，寫入空值/"configured" 不覆蓋
#   service: {command: "node bot.js"}  → GET/POST /api/skills/{name}/service（start/stop/status）
# ---------------------------------------------------------------------------

# 進程級技能服務註冊表：skill_name -> {"proc": Popen, "started_at": ts, "log": path}
_SKILL_SERVICES = {}


def _get_skill_by_name(name: str):
    """按名字取技能（交由 SkillsManager 的大小寫不敏感查詢）。"""
    return _get_skills_manager().get_skill(name)


def _skill_subpath(root: str, rel: str):
    """把技能目錄相對路徑解析為絕對路徑；越界（../ 等）返回 None。"""
    if not root or not rel or os.path.isabs(rel):
        return None
    full = os.path.realpath(os.path.join(root, rel))
    real_root = os.path.realpath(root)
    if full != real_root and full.startswith(real_root + os.sep):
        return full
    return None


def _get_secret_path(secret: str):
    """脱敏点路径拆段；拒绝数组下标等复杂路径，支持 '*' 通配一層鍵。"""
    parts = [p for p in str(secret).split(".") if p and (p.isidentifier() or p == "*")]
    return parts or None


def _mask_secrets(node, parts):
    if not parts or not isinstance(node, dict):
        return
    key = parts[0]
    if key == "*":
        for child in list(node.keys()):
            _mask_secrets(node, [child] + parts[1:])
        return
    if key not in node:
        return
    if len(parts) == 1:
        if node[key] not in (None, ""):
            node[key] = "configured"
        return
    _mask_secrets(node[key], parts[1:])


def _is_secret_path(path: str, secret_dotted) -> bool:
    """判斷併合中的點路徑是否命中秘密字段（支持 '*' 通配）。"""
    if path in secret_dotted:
        return True
    pk = path.split(".")
    for secret in secret_dotted:
        if "*" not in secret:
            continue
        sk = secret.split(".")
        if len(sk) == len(pk) and all(a == "*" or a == b for a, b in zip(sk, pk)):
            return True
    return False


def _merge_config(dst: dict, patch: dict, secret_dotted, prefix=""):
    """深合併補丁到配置；秘密字段寫入空值或 'configured' 視為不修改。"""
    for key, value in patch.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _merge_config(dst[key], value, secret_dotted, path + ".")
            continue
        if _is_secret_path(path, secret_dotted) and (value in (None, "", "configured")):
            continue  # 留空 / 脫敏佔位符 → 保留原值
        dst[key] = value


def _service_record(name: str):
    rec = _SKILL_SERVICES.get(name)
    if rec:
        proc = rec["proc"]
        if proc.poll() is not None:  # 已退出，清掉失效記錄
            try:
                rec.get("log_handle") and rec["log_handle"].close()
            except Exception:
                pass
            _SKILL_SERVICES.pop(name, None)
            return None
    return rec


def _service_running(name: str) -> bool:
    return _service_record(name) is not None


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


def build_context_from_memory(memory, max_messages=20):
    """从memory构建上下文"""
    if not memory:
        return ""

    messages = memory.get("messages", [])[-max_messages:]
    context = "Recent conversation:"
    for msg in messages:
        role = msg.get("role", "").capitalize()
        source = msg.get("source", "")
        # 放宽截断：单条 500 字符，保留更多上下文细节
        content = msg.get("content", "")[:500]

        if source == "user":
            context += f"\n[用户] {content}"
        elif source == "ai_autonomous":
            context += f"\n[Aize主动] {content}"
        elif source == "ai_response":
            context += f"\n[Aize回复] {content}"
        else:
            context += f"\n{role}: {content}"

    # 長期記憶檢索（按最近一句用戶輸入）
    query = ""
    for msg in reversed(messages):
        if msg.get("source") == "user":
            query = msg.get("content", "")
            break
    if query:
        for importer, getter in (
            ("tools.memory_db", "get_memory_db"),
            ("tools.experience_db", "get_experience_db"),
            ("tools.emotion_db", "get_emotion_db"),
        ):
            try:
                module = __import__(importer, fromlist=[getter])
                block = getattr(module, getter)().format_for_prompt(query)
                if block:
                    context += "\n" + block
            except Exception:
                pass
    # 短期記憶（10 分鐘窗口）
    try:
        from memory.short_term import format_for_prompt as _st_block
        block = _st_block()
        if block:
            context += "\n" + block
    except Exception:
        pass
    return context


_BUSY_LABELS = {
    "break_silence": "正在主動找你聊天",
    "reflection": "正在自我反思",
    "gan": "正在內部推演",
    "chat": "正在回覆上一條消息",
    "chat_with_gan_decision": "正在回覆上一條消息",
    "chat_stream": "正在回覆上一條消息",
}


def _decide_busy_reply(user_text, busy_kind):
    """用戶在 Aize 忙於自主任務時插話：由她決定「先做完再說」還是「立刻回答」。

    返回 (choice, reason)，choice 為 "finish_first" 或 "answer_now"。
    決策失敗時默認立刻回答，保證用戶不會被卡住。
    """
    prompt = (
        "你是 Aize。你現在" + _BUSY_LABELS.get(busy_kind, f"正在處理 {busy_kind}") + "，"
        f"這時主人發來一條新消息：{user_text}\n\n"
        "你要决定怎麼做：\n"
        "A. finish_first —— 先把眼前的事做完，之後再以「主動找主人說話」的方式回覆這條消息；\n"
        "B. answer_now —— 立刻放下手上的事，直接回覆主人。\n"
        "只輸出 JSON：{\"choice\":\"finish_first\"或\"answer_now\",\"reason\":\"一句話理由\"}"
    )
    try:
        from llm import chat as _llm_chat
        reply = _llm_chat(prompt, max_tokens=120, temperature=0.1,
                          timeout=25, max_retries=1)
        if "finish_first" in (reply or "").lower():
            return "finish_first", (reply or "").strip()
        return "answer_now", (reply or "").strip()
    except Exception as e:
        logger.warning(f"[Chat] busy-decision failed, answering now: {e}")
        return "answer_now", f"decision error: {e}"


class ResponseCollector:
    """响应收集器 - 收集ThinkingEngine的回调响应
    支持流式和同步两种模式，在最后一个块后等待一段时间没有新消息则认为任务完成"""
    
    def __init__(self, timeout=600, completion_wait=300, first_chunk_wait=600):
        """非流式生成在 CPU 上可能 60-90 秒後才返回唯一的一個 chunk，
        首塊等待必須遠大於 chunk 間隔，否則會在生成完成前誤判為空回覆。
        低配機器（RAM 不足換頁）上 prompt 評估可達 3 分鐘以上，因此
        總超時與首塊等待都取 10 分鐘。
        completion_wait 僅作兜底：worker 正常結束時會發送 task_done 信號，
        collector 收到後立即完成；只有 worker 意外掛死時才靠靜默超時兜底。
        閉環模式下 followup 的 LLM 生成可達 2-3 分鐘（寫長文檔/複雜推理），
        靜默兜底取 300 秒避免把「正在思考下一步」誤判為任務完成而截斷回覆。
        同時 internal_thought / command_start / command_result 都會刷新
        計時器——只要 worker 還在產出任何事件，就不該被當成掛死。"""
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
            # 思考片段也刷新計時器：worker 還在思考就說明活著，
            # 不該因「90 秒沒正文 chunk」就誤判任務完成。
            self._last_chunk_time = time.time()
            self._queue.put({"type": "thought", "content": thought, "thought_type": thought_type})
        elif response.get("type") == "gan_complete":
            pass
        elif response.get("type") == "command_start":
            self._last_chunk_time = time.time()
            self._queue.put({"type": "command_start", "message": response.get("message", "")})
        elif response.get("type") == "command_result":
            self._last_chunk_time = time.time()
            self._queue.put({"type": "command_result", "output": response.get("output", "")})
        elif response.get("type") == "task_done":
            # worker 確認任務結束——排入隊列尾部，保證先按 FIFO 消費完
            # 所有已產出內容再結束，不會截斷最後的總結
            self._queue.put({"type": "task_done"})
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
                    msg = self._queue.get(timeout=0.5)
                except Empty:
                    continue
                if msg.get("type") == "task_done":
                    # 任務真正結束：FIFO 保證此前所有 chunk 已被消費
                    self._finished = True
                    return {"type": "done"}
                return msg
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


# ============================================================
# 進程級對話時間線（內存，不落盤）
# ------------------------------------------------------------
# 實時流式對話把事件分成「思考行 / 命令區塊 / 回覆正文」三類渲染，
# 但持久化的 memory.json 只保存混合後的純文本 content。網頁刷新時
# /api/chat/history 只能拿回純文本，導致思考框/命令框全部錯位成
# AI 原話。這裡按輪次保存結構化事件，供刷新後原樣重建。
# 進程重啟即消失（與思考框的臨時性質一致），最多保留 60 輪。
# ============================================================
_CHAT_TIMELINE = collections.deque(maxlen=60)
_CHAT_TIMELINE_LOCK = threading.Lock()

# 正在生成中的那一輪（id + 上次落盤時間），刷新頁面後仍可從時間線看到
_PENDING_TURN = {"id": None, "at": 0.0}
_CHAT_TIMELINE_FILE = None


def _timeline_file_path():
    """時間線落盤路徑（與記憶庫同目錄），刷新/重啟後排版與用量都還在。"""
    global _CHAT_TIMELINE_FILE
    if _CHAT_TIMELINE_FILE:
        return _CHAT_TIMELINE_FILE
    base = None
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["app_data_dir"])
            base = m.app_data_dir()
            break
        except Exception:
            continue
    if not base:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(base, exist_ok=True)
    _CHAT_TIMELINE_FILE = os.path.join(base, "chat_timeline.json")
    return _CHAT_TIMELINE_FILE


def _timeline_load():
    try:
        with open(_timeline_file_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        for turn in (data.get("turns") or [])[-_CHAT_TIMELINE.maxlen:]:
            if isinstance(turn, dict) and turn.get("items"):
                _CHAT_TIMELINE.append(turn)
    except Exception:
        pass


def _timeline_save():
    try:
        with open(_timeline_file_path(), "w", encoding="utf-8") as f:
            json.dump({"turns": list(_CHAT_TIMELINE)}, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[Timeline] save failed: {e}")


def _clean_timeline_items(items):
    """壓縮時間線：去掉空塊，相鄰同類事件合併。"""
    clean_items = []
    for it in items:
        c = (it.get("c") or "")
        if not c:
            continue
        # 相鄰同類事件合併（token chunk / 同類思考幀）
        if clean_items and clean_items[-1].get("k") == it.get("k") \
                and clean_items[-1].get("t", "") == it.get("t", ""):
            clean_items[-1]["c"] += c
        else:
            clean_items.append({"k": it.get("k"), "t": it.get("t", ""), "c": c})
    return clean_items


def _timeline_attachment_list(attachments):
    if not attachments:
        return None
    return [
        {"name": str(a.get("name", ""))[:120],
         "is_image": bool(a.get("is_image"))}
        for a in attachments if isinstance(a, dict)
    ]


def _timeline_drop_pending_locked(pending_id=None):
    """移除尚未完成的 pending 輪次（調用方需持有 _CHAT_TIMELINE_LOCK）。
    指定 pending_id 時只處理該輪，避免中斷/並發時誤刪新一輪的 pending 記錄。"""
    current_id = _PENDING_TURN.get("id")
    if not current_id:
        return
    if pending_id is not None and pending_id != current_id:
        return
    for turn in list(_CHAT_TIMELINE):
        if turn.get("id") == current_id:
            try:
                _CHAT_TIMELINE.remove(turn)
            except ValueError:
                pass
    _PENDING_TURN["id"] = None


def _timeline_begin_turn(user_text, display_user=None, attachments=None):
    """收到使用者訊息就先落盤一個 pending 輪次。

    以前只有回覆完成才寫時間線，刷新頁面時正在生成的那一輪直接消失。
    現在先把這一輪（含附件）記下來，回覆內容邊生成邊更新，
    完成後由 _timeline_add_turn 用正式輪次替換。
    """
    if not (user_text or "").strip() and not attachments:
        return None
    turn_id = uuid.uuid4().hex[:12]
    turn = {
        "id": turn_id,
        "user": user_text or "",
        "display_user": (display_user if display_user is not None else (user_text or "")),
        "items": [],
        "ts": int(time.time()),
        "pending": True,
    }
    attach_list = _timeline_attachment_list(attachments)
    if attach_list:
        turn["attachments"] = attach_list
    with _CHAT_TIMELINE_LOCK:
        _timeline_drop_pending_locked()
        _CHAT_TIMELINE.append(turn)
        _timeline_save()
    _PENDING_TURN["id"] = turn_id
    _PENDING_TURN["at"] = 0.0
    return turn_id


def _timeline_update_pending(items):
    """把正在生成的內容寫進 pending 輪次（最多每秒落盤一次）。"""
    pending_id = _PENDING_TURN.get("id")
    if not pending_id:
        return
    now = time.time()
    if now - _PENDING_TURN.get("at", 0.0) < 1.0:
        return
    _PENDING_TURN["at"] = now
    clean_items = _clean_timeline_items(items)
    with _CHAT_TIMELINE_LOCK:
        for turn in _CHAT_TIMELINE:
            if turn.get("id") == pending_id:
                turn["items"] = clean_items
                break
        _timeline_save()


def _timeline_add_turn(user_text, items, usage=None, display_user=None, attachments=None,
                       pending_id=None):
    """記錄一輪對話。items: [{k: text|thought|cmd_start|cmd_result, t: str, c: str}]
    usage/attachments/display_user 一起落盤，刷新後用量腳註、附件名和技能框都能重建。"""
    # 壓縮：去掉空塊；正文合併後若整輪無內容則不記錄
    clean_items = _clean_timeline_items(items)
    if not (user_text or "").strip() and not clean_items:
        return
    turn = {
        "user": user_text or "",
        "display_user": (display_user if display_user is not None else (user_text or "")),
        "items": clean_items,
        "ts": int(time.time()),
    }
    if usage:
        turn["usage"] = usage
    attach_list = _timeline_attachment_list(attachments)
    if attach_list:
        turn["attachments"] = attach_list
    with _CHAT_TIMELINE_LOCK:
        # 該輪若先前以 pending 形式記過，先移除，避免刷新後出現重複兩條
        _timeline_drop_pending_locked(pending_id)
        _CHAT_TIMELINE.append(turn)
        _timeline_save()


def _timeline_snapshot():
    with _CHAT_TIMELINE_LOCK:
        return list(_CHAT_TIMELINE)


_timeline_load()


EMPTY_REPLY_ERROR = "錯誤：AI 沒有產生任何有效內容"

# fix1：Aize 拒絕回覆時客戶端唯一可見的內容
REFUSAL_TEXT = "Aize不想回答你的问题"

_THOUGHT_BLOCK_RE = re.compile(
    r"(?:^|\n)\s*THOUGHT\s*[:：]\s*(.*?)(?=\n\s*RESPONSE\s*[:：]|\Z)", re.S | re.I)
_RESPONSE_BLOCK_RE = re.compile(
    r"(?:^|\n)\s*RESPONSE\s*[:：]\s*(.*)\Z", re.S | re.I)
_MOTION_TAG_RE = re.compile(
    r"\[\s*motion\s*:\s*[A-Za-z]+\s*(?::\s*\d+\s*)?\]", re.I)


def _split_thought_response(content):
    """把記憶庫裡的原始回覆拆成 (thought, reply)。

    歷史接口直接讀 memory.json，裡面保存的是模型原文（含 THOUGHT:/RESPONSE:
    標籤）。不清洗就返回，網頁刷新後會把整段標籤原樣顯示出來。
    """
    text = content or ""
    m_thought = _THOUGHT_BLOCK_RE.search(text)
    m_reply = _RESPONSE_BLOCK_RE.search(text)
    if m_reply:
        reply = m_reply.group(1)
        thought = m_thought.group(1) if m_thought else text[:m_reply.start()]
    else:
        reply = text
        thought = m_thought.group(1) if m_thought else ""
        if m_thought:
            reply = text[:m_thought.start()] + text[m_thought.end():]
    reply = _MOTION_TAG_RE.sub("", reply).strip()
    thought = _MOTION_TAG_RE.sub("", thought).strip()
    return thought, reply


def _topic_switch_reply(raw_decision):
    """從 should_answer 判定結果裡取出 switch_topic 的自發台詞。"""
    try:
        data = json.loads(raw_decision) if raw_decision else {}
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    if str(data.get("decision", "")).strip().lower() != "switch_topic":
        return ""
    return str(data.get("reply") or "").strip()[:300]


# 中斷判斷子 Agent 的系統提示：判斷是否打斷，並安排後續話題走向。
_INTERRUPT_JUDGE_SYSTEM = """你是對話調度判斷器。使用者（主人）正在和 AI 助手對話，AI 還在輸出回覆時，主人又發來一條新消息。
你的任務有兩步：
1. 判斷是否應該中斷 AI 當前的輸出，先回答主人的新消息 interrupt。
   應該中斷（true）：
   - 新消息提出了不同的問題、改變了要求、或包含糾正/否定（如「不是」「停」「算了」「不對」「等一下」）
   - 新消息有時效性、很緊急，或補充了會改變答案的關鍵信息
   - 當前回覆已經明顯跑題或答非所問
   不該中斷（false）：
   - 新消息只是補充說明、延續同一話題，等當前回覆說完就能解決
   - 新消息是對當前回覆的期待（如「繼續」「然後呢」「說下去」）
2. 判斷新消息是不是對原問題的「補充」merge。
   - merge=true：新消息在補充原問題的條件、細節、背景，或是修正/澄清（如「呃，其實是…」「等一下，我是說…」「還有，它要…」），
     應該把它和原問題合併成一個請求一起回答。
   - merge=false：新消息是獨立的新問題或新話題。
3. 決定後續安排 post_action：
   - "resume_prev"：先回答新消息，答完再回到剛才被打斷的話題繼續做
   - "drop_prev"：先回答新消息，剛才的話題不用再提
   - "decline_switch"：新消息不值得現在切換，先把手上的回覆做完，再告訴主人「暫且不換話題」
   選 decline_switch 時 interrupt 必須是 false；merge=true 時 interrupt 必須是 true、post_action 填 "drop_prev"
   （因為合併後的請求已包含原問題，不需要再單獨續接）。其餘情況按第 1 步的判斷填 interrupt。
只輸出一個 JSON，不要任何其他文字：{"interrupt": true 或 false, "merge": true 或 false, "post_action": "resume_prev"/"drop_prev"/"decline_switch", "reason": "20字以內的原因"}"""


def _judge_chat_interrupt(question: str, partial: str, new_text: str) -> dict:
    """子 Agent：判斷新消息要不要打斷當前回覆，以及之後是否回到原話題。

    返回 {"interrupt": bool, "post_action": str, "reason": str,
          "source": "judge"|"fallback"}。
    判斷器本身失敗時默認中斷——主人新發的消息優先，避免被 409 卡住。
    """
    judge_input = (
        f"【AI 正在回答的問題】\n{(question or '(未知)')[:300]}\n\n"
        f"【AI 已經說出的內容】\n{(partial or '(還沒開始說)')[-600:]}\n\n"
        f"【主人新發的消息】\n{new_text[:500]}\n\n只輸出 JSON。"
    )
    try:
        from llm import chat
        raw = (chat(judge_input, max_tokens=240, temperature=0.1, timeout=10,
                    max_retries=0, system=_INTERRUPT_JUDGE_SYSTEM) or "").strip()
        m = re.search(r'"interrupt"\s*:\s*(true|false)', raw, re.I)
        if m:
            interrupt = m.group(1).lower() == "true"
        else:
            low = raw.lower()
            interrupt = ("yes" in low) or ("中斷" in raw) or ("中断" in raw)
        mm = re.search(r'"merge"\s*:\s*(true|false)', raw, re.I)
        merge = mm.group(1).lower() == "true" if mm else False
        pm = re.search(r'"post_action"\s*:\s*"(resume_prev|drop_prev|decline_switch)"', raw, re.I)
        post_action = pm.group(1).lower() if pm else ("drop_prev" if interrupt else "decline_switch")
        if merge:
            # 合併成一個請求：一定要先停下當前輸出，原問題已包含在合併內容裡
            interrupt = True
            post_action = "drop_prev"
        elif post_action == "decline_switch":
            interrupt = False
        rm = re.search(r'"reason"\s*:\s*"([^"]{0,80})"', raw)
        reason = rm.group(1) if rm else ("子 Agent 判定中斷" if interrupt else "子 Agent 判定不中斷")
        return {"interrupt": interrupt, "merge": merge, "post_action": post_action,
                "reason": reason, "source": "judge"}
    except Exception as e:
        logger.warning(f"[Chat] interrupt judge failed: {e}")
        return {"interrupt": True, "merge": False, "post_action": "drop_prev",
                "reason": f"判斷器失敗，默認中斷: {e}", "source": "fallback"}


class ThinkingEngineAPIHandler(BaseHTTPRequestHandler):
    """OpenAI兼容的API处理器"""

    # 聊天互斥鎖：ThinkingEngine 只有一個 worker，任務串行處理。
    # 若允許第二個聊天請求進入，它的 collector 會熱頂替引擎的全局 on_response，
    # 從而把前一個任務正在生成的內容串給新客戶端（且新任務的回答無人接收）。
    _chat_lock = threading.Lock()

    # 中斷判斷：主聊天請求進行中時，新請求可先問子 Agent「要不要打斷」。
    # 這裡保存當前回合的取消事件、原問題與已輸出內容，供 /api/chat/interrupt 讀取。
    _active_chat_lock = threading.Lock()
    _active_chat = None

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
            # 客戶端提前斷開時 self.command / self.path 可能未設置，安全取值
            method = getattr(self, 'command', '?')
            path = getattr(self, 'path', '?')
            logger.info(f"[HTTP] finish method={method} path={path} duration_ms={duration_ms:.1f}")
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
    _AUTH_EXEMPT_PATHS = ("/api/login", "/health", "/live2d",
                          "/api/live2d/poll", "/api/live2d/command",
                          "/api/live2d/chat", "/api/live2d/pose",
                          "/api/live2d/mocap/start", "/api/live2d/mocap/stop",
                          "/api/live2d/mocap/status", "/api/live2d/mocap/preview",
                          "/api/live2d/mocap/recalibrate", "/Selfuse_Capture",
                          "/Selfuse_Capture/", "/api/tts")
    # OBS 瀏覽源無法登錄，Live2D 頁面資源與攝像頭背景圖免登錄（仍受局域網門禁限制）
    _AUTH_EXEMPT_PREFIXES = ("/live2d/", "/asset/")

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
        if (path in self._AUTH_EXEMPT_PATHS
                or path.startswith(self._AUTH_EXEMPT_PREFIXES)
                or not self._auth_required()):
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
        elif parsed.path == '/api/chat/history':
            self._handle_chat_history()
        elif parsed.path == '/api/prompt':
            self._handle_get_prompt()
        elif parsed.path == '/api/chat/timeline':
            self._handle_chat_timeline()
        elif parsed.path == '/api/voice/capabilities':
            self._handle_voice_capabilities()
        elif parsed.path == '/api/events':
            self._handle_event_stream()
        elif parsed.path == '/api/web_search':
            self._handle_web_search(parsed)
        elif parsed.path == '/api/skills':
            self._handle_list_skills()
        elif parsed.path.startswith('/api/skills/'):
            self._route_skill_api_get(parsed.path)
        elif parsed.path == '/live2d':
            self._send_static_file("live2d/index.html", "text/html; charset=utf-8")
        elif parsed.path.startswith('/live2d/'):
            self._handle_live2d_static(parsed.path)
        elif parsed.path == '/api/live2d/poll':
            self._handle_live2d_poll(parsed)
        elif parsed.path == '/api/live2d/pose':
            self._handle_live2d_pose_stream()
        elif parsed.path == '/api/live2d/mocap/status':
            self._send_json(self._mocap().status())
        elif parsed.path == '/api/live2d/mocap/preview':
            self._handle_mocap_preview()
        elif parsed.path in ('/Selfuse_Capture', '/Selfuse_Capture/'):
            self._send_static_file("Selfuse_Capture/index.html", "text/html; charset=utf-8")
        elif parsed.path == '/api/phone/poll':
            self._handle_phone_poll(parsed)
        elif parsed.path.startswith('/api/meeting/'):
            self._handle_meeting_get(parsed, parsed.path.rsplit('/', 1)[-1])
        elif parsed.path == '/api/phone/status':
            try:
                self._send_json(self._phone_hub().status())
            except Exception as e:
                self._send_error(f"phone status failed: {e}", 500)
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
        elif parsed.path.startswith('/asset/'):
            self._handle_root_asset(parsed.path)
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
        elif parsed.path == '/api/chat/interrupt':
            self._handle_chat_interrupt()
        elif parsed.path == '/api/settings':
            self._handle_save_settings()
        elif parsed.path == '/api/prompt':
            self._handle_save_prompt()
        elif parsed.path == '/api/login':
            self._handle_login()
        elif parsed.path == '/api/logout':
            self._handle_logout()
        elif parsed.path == '/api/tts':
            self._handle_tts()
        elif parsed.path == '/api/skills/toggle':
            self._handle_skill_toggle()
        elif parsed.path == '/api/skills/reload':
            self._handle_skills_reload()
        elif parsed.path == '/api/skills/execute':
            self._handle_skill_execute()
        elif parsed.path.startswith('/api/skills/'):
            self._route_skill_api_post(parsed.path)
        elif parsed.path == '/api/upload':
            self._handle_upload()
        elif parsed.path == '/api/live2d/command':
            self._handle_live2d_command()
        elif parsed.path == '/api/live2d/chat':
            self._handle_live2d_chat()
        elif parsed.path in ('/api/live2d/mocap/start', '/api/live2d/mocap/stop',
                             '/api/live2d/mocap/recalibrate'):
            mc = self._mocap()
            if parsed.path.endswith('start'):
                self._send_json(mc.start())
            elif parsed.path.endswith('stop'):
                self._send_json(mc.stop())
            else:
                self._send_json(mc.recalibrate())
        elif parsed.path == '/api/phone/result':
            self._handle_phone_result()
        elif parsed.path == '/api/phone/command':
            self._handle_phone_command()
        else:
            self._send_error("Not found", 404)

    # ---------- Live2D ----------

    _LIVE2D_MIME = {
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".png": "image/png",
        ".moc3": "application/octet-stream",
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
    }

    def _handle_live2d_static(self, url_path):
        """本地化的 Live2D 資源（庫與模型），不再依賴外網 CDN。"""
        rel = url_path[len("/live2d/"):].replace("\\", "/").lstrip("/")
        if not rel or ".." in rel.split("/"):
            self._send_error("invalid path", 400)
            return
        ext = os.path.splitext(rel)[1].lower()
        self._send_static_file("live2d/" + rel, self._LIVE2D_MIME.get(ext, "application/octet-stream"))

    _ROOT_ASSET_MIME = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }

    def _handle_root_asset(self, url_path):
        """項目根目錄 Assets/ 下的圖片資源（如虛擬攝像頭背景 Camera_bkg.png）。"""
        rel = url_path[len("/asset/"):].replace("\\", "/").lstrip("/")
        if not rel or ".." in rel.split("/") or "/" in rel:
            self._send_error("invalid path", 400)
            return
        ext = os.path.splitext(rel)[1].lower()
        mime = self._ROOT_ASSET_MIME.get(ext)
        if not mime:
            self._send_error("Not found", 404)
            return
        roots = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(meipass)
        if getattr(sys, "frozen", False):
            roots.append(os.path.dirname(os.path.abspath(sys.executable)))
        roots.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        for root in roots:
            path = os.path.join(root, "Assets", rel)
            if os.path.isfile(path):
                self._send_file_path(path, mime)
                return
        self._send_error("Not found", 404)

    @staticmethod
    def _live2d_hub():
        try:
            from tools.live2d_hub import get_live2d_hub
        except ImportError:
            from core.tools.live2d_hub import get_live2d_hub
        return get_live2d_hub()

    def _handle_live2d_poll(self, parsed):
        try:
            from urllib.parse import parse_qs
            since = parse_qs(parsed.query or "").get("since", ["0"])[0]
        except Exception:
            since = "0"
        try:
            hub = self._live2d_hub()
            self._send_json({"commands": hub.poll_commands(since),
                             "status": hub.status()})
        except Exception as e:
            self._send_error(f"live2d poll failed: {e}", 500)

    def _handle_live2d_command(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except Exception as e:
            self._send_error(f"Invalid JSON body: {e}")
            return
        if not isinstance(body, dict) or not body.get("type"):
            self._send_error("command object with 'type' is required", 400)
            return
        try:
            cmd_id = self._live2d_hub().push_command(body)
            self._send_json({"success": True, "id": cmd_id})
        except Exception as e:
            self._send_error(f"live2d command failed: {e}", 500)

    def _handle_live2d_chat(self):
        """Live2D 頁面/外部聊天源送來的消息：走引擎生成回復，
        回復同時推 speak 命令給 Live2D 頁面朗讀，並以 JSON 返回文本。"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except Exception as e:
            self._send_error(f"Invalid JSON body: {e}")
            return

        text = (body.get("text") or "").strip() if isinstance(body, dict) else ""
        user = (body.get("user") or "live2d").strip() if isinstance(body, dict) else "live2d"
        if not text:
            self._send_error("text is required", 400)
            return

        state = ThinkingEngineState()
        thinking_engine = state.get_thinking_engine()
        memory = state.get_memory()
        personality = state.get_personality()
        if not thinking_engine:
            self._send_error("ThinkingEngine not available", 503)
            return
        try:
            thinking_engine.pause_idle()
        except Exception:
            pass

        if not self._chat_lock.acquire(blocking=False):
            self._send_error("AI 正在思考中，請稍後再試", 409)
            return

        try:
            # 與 /api/chat 相同的 system 塊拼裝（精簡版：不跑拒答決策線程，
            # Live2D 場景下彈幕/會議消息需要穩定回復）
            personality_prompt = ""
            if personality:
                personality_prompt = getattr(personality, 'description', '') or str(personality)
            system_block_parts = []
            try:
                from data.prompts_manager import load_system_prompt, load_agent_prompt
            except ImportError:
                from core.data.prompts_manager import load_system_prompt, load_agent_prompt
            for loader in (load_system_prompt, load_agent_prompt):
                try:
                    t = (loader() or "").strip()
                    if t:
                        system_block_parts.append(t)
                except Exception:
                    pass
            # 人格描述不再单独拼接：統一由 persona_block 注入（見下方），
            # 避免多處人格互相衝突。

            try:
                try:
                    from core.persona import persona_block
                except ImportError:
                    from persona import persona_block
                _persona_text = persona_block("chat", memory)
                if _persona_text:
                    system_block_parts.append(_persona_text)
            except Exception:
                pass
            try:
                _recent_ctx = build_context_from_memory(memory, max_messages=12)
                if _recent_ctx:
                    system_block_parts.append(_recent_ctx)
            except Exception:
                pass
            if os.name == "nt":
                system_block_parts.append(
                    "【運行環境】Windows。shell 技能由 cmd.exe 執行，不是 PowerShell/bash。"
                    "臨時目錄用 %TEMP%；禁止 /tmp、/Skills、$env:TEMP、New-Item；"
                    "下載用 curl.exe，解壓用 tar -xf（失敗再用 powershell -Command Expand-Archive），寫入前先 mkdir。")
            else:
                system_block_parts.append(
                    "【運行環境】Linux。shell 技能由 /bin/sh 執行，臨時目錄用 /tmp，解壓用 unzip 或 tar。")
            _skills_text = _get_skills_prompt_cached()
            if _skills_text:
                system_block_parts.append(_skills_text)

            messages = [{"role": "user", "content": text}]
            full_prompt = build_prompt_from_messages(messages, "\n\n".join(system_block_parts))

            if memory is not None:
                try:
                    from memory import add as _mem_add, save_memory as _mem_save
                    _mem_add(memory, "user", f"[{user}] {text}", source="live2d")
                    _mem_save(memory)
                except Exception:
                    pass

            collector = ResponseCollector(timeout=300)
            original_on_response = thinking_engine.on_response
            thinking_engine.on_response = collector.callback

            reply = ""
            try:
                thinking_engine.queue_chat_task(
                    full_prompt,
                    memory=memory,
                    user_text=text,
                    personality=personality,
                    use_gan_decision=False,
                )
                while True:
                    chunk = collector.get_chunk()
                    if chunk["type"] == "chunk":
                        reply += chunk["content"]
                    elif chunk["type"] == "done":
                        break
                    elif chunk["type"] == "error":
                        reply = reply or f"錯誤: {chunk['content']}"
                        break
                    elif chunk["type"] == "timeout":
                        reply = reply or "抱歉，我剛才走神了～"
                        break
                collector.set_finished()
            finally:
                thinking_engine.on_response = original_on_response

            reply = clean_reply(reply) if reply else ""
            if not reply:
                self._send_error("empty reply", 502)
                return

            if memory is not None:
                try:
                    from memory import add as _mem_add, save_memory as _mem_save
                    _mem_add(memory, "assistant", reply, source="live2d")
                    _mem_save(memory)
                except Exception:
                    pass

            # 推 speak 命令：Live2D 頁面輪詢拿到後 TTS 朗讀 + 唇形
            try:
                self._live2d_hub().push_command({"type": "speak", "text": reply})
            except Exception:
                pass

            self._send_json({"success": True, "reply": reply})
        except Exception as e:
            logger.error(f"[Live2D] chat error: {e}\n{traceback.format_exc()}")
            self._send_error(f"live2d chat failed: {e}", 500)
        finally:
            try:
                self._chat_lock.release()
            except RuntimeError:
                pass

    # ---------- 手機命令通道（安卓客戶端 × Shizuku） ----------

    @staticmethod
    def _phone_hub():
        try:
            from tools.phone_hub import get_phone_hub
        except ImportError:
            from core.tools.phone_hub import get_phone_hub
        return get_phone_hub()

    @staticmethod
    def _mocap():
        try:
            from voice.mocap import get_motion_capture
        except ImportError:
            from core.voice.mocap import get_motion_capture
        return get_motion_capture()

    def _handle_live2d_pose_stream(self):
        """SSE：以 30fps 推送面部動作捕捉姿態，供 Live2D 頁面實時套用。"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        mc = self._mocap()
        try:
            while True:
                pose = mc.get_pose()
                self.wfile.write(f"data: {json.dumps(pose)}\n\n".encode('utf-8'))
                self.wfile.flush()
                time.sleep(1.0 / 30)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _handle_mocap_preview(self):
        """MJPEG 推流：帶人臉框與姿態數值的鏡像預覽，供 Selfuse_Capture 頁面顯示。"""
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        mc = self._mocap()
        try:
            while True:
                jpg = mc.get_jpeg()
                if jpg:
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n'
                                     b'Content-Length: ' + str(len(jpg)).encode() + b'\r\n\r\n')
                    self.wfile.write(jpg)
                    self.wfile.write(b'\r\n')
                    self.wfile.flush()
                time.sleep(1.0 / 15)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    @staticmethod
    def _meeting():
        try:
            from voice.meeting_listener import get_meeting_listener
        except ImportError:
            from core.voice.meeting_listener import get_meeting_listener
        return get_meeting_listener()

    def _handle_meeting_get(self, parsed, action):
        """會議旁聽控制：/api/meeting/start|stop|status|transcript|summary"""
        ml = self._meeting()
        try:
            if action == "start":
                self._send_json(ml.start())
            elif action == "stop":
                self._send_json(ml.stop())
            elif action == "status":
                self._send_json(ml.status())
            elif action == "summary":
                self._send_json(ml.summarize_now())
            elif action == "transcript":
                qs = parse_qs(parsed.query or "")
                limit = int(qs.get("limit", ["500"])[0] or 500)
                self._send_json(ml.transcript(limit=max(1, min(limit, 3000))))
            else:
                self._send_error("Not found", 404)
        except Exception as e:
            self._send_error(f"meeting {action} failed: {e}", 500)


    def _handle_phone_poll(self, parsed):
        """手機端輪詢待執行命令。"""
        try:
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query or "")
            since = qs.get("since", ["0"])[0]
            device = qs.get("device", [""])[0]
        except Exception:
            since, device = "0", ""
        try:
            hub = self._phone_hub()
            self._send_json({"commands": hub.poll_commands(since, device),
                             "status": hub.status()})
        except Exception as e:
            self._send_error(f"phone poll failed: {e}", 500)

    def _handle_phone_result(self):
        """手機端回傳命令執行結果。"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except Exception as e:
            self._send_error(f"Invalid JSON body: {e}")
            return
        cmd_id = body.get("id") if isinstance(body, dict) else None
        result = body.get("result") if isinstance(body, dict) else None
        if cmd_id is None or not isinstance(result, dict):
            self._send_error("body must contain 'id' and 'result' object", 400)
            return
        try:
            ok = self._phone_hub().post_result(cmd_id, result)
            self._send_json({"success": bool(ok)})
        except Exception as e:
            self._send_error(f"phone result failed: {e}", 500)

    def _handle_phone_command(self):
        """本機測試/外部下發命令給手機（與 phone-shell 技能同通道）。"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except Exception as e:
            self._send_error(f"Invalid JSON body: {e}")
            return
        command = str(body.get("command", "")).strip() if isinstance(body, dict) else ""
        if not command:
            self._send_error("command is required", 400)
            return
        try:
            hub = self._phone_hub()
            cmd_id = hub.push_command(command, body.get("timeout", 30))
            wait = float(body.get("wait", 0) or 0)
            if wait > 0:
                result = hub.wait_result(cmd_id, min(wait, 120))
                self._send_json({"success": True, "id": cmd_id, "result": result})
            else:
                self._send_json({"success": True, "id": cmd_id})
        except Exception as e:
            self._send_error(f"phone command failed: {e}", 500)

    # 聊天附件大小不限（用戶要求移除 20MB 上限）
    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def _uploads_dir(self):
        """聊天上傳文件的持久目錄（與 memory 同級數據目錄下）。"""
        try:
            from app_paths import app_data_dir
        except ImportError:
            from core.app_paths import app_data_dir
        target = os.path.join(app_data_dir(), "uploads")
        os.makedirs(target, exist_ok=True)
        return target

    @staticmethod
    def _sanitize_upload_name(name: str) -> str:
        """只保留安全文件名字符，防止路徑穿越與怪字符。"""
        base = os.path.basename(name or "").strip().replace(" ", "_")
        base = re.sub(r'[^\w.\-一-鿿]', "_", base)
        return base[:80] or "file"

    def _handle_upload(self):
        """接收聊天附件（multipart/form-data），落盤到 uploads 目錄。

        返回 [{"name","path","mime","size","is_image"}]，path 為絕對路徑，
        後續 /api/chat 的 attachments 引用該路徑（僅允許 uploads 目錄內）。"""
        content_type = self.headers.get('Content-Type', '')
        match = re.match(r'multipart/form-data;\s*boundary=(.+)', content_type)
        if not match:
            self._send_error("Content-Type must be multipart/form-data")
            return
        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            content_length = 0
        if content_length <= 0:
            self._send_error("Empty upload body")
            return

        boundary = match.group(1).strip().strip('"').encode('utf-8')
        body = self.rfile.read(content_length)

        files = []
        for part in body.split(b'--' + boundary):
            part = part.strip(b'\r\n')
            if not part or part == b'--':
                continue
            header_blob, sep, payload = part.partition(b'\r\n\r\n')
            if not sep:
                continue
            headers_text = header_blob.decode('utf-8', errors='replace')
            disposition = re.search(r'Content-Disposition:[^\n]*filename="([^"]*)"', headers_text, re.I)
            if not disposition:
                continue
            filename = self._sanitize_upload_name(disposition.group(1))
            mime_match = re.search(r'Content-Type:\s*([^\r\n]+)', headers_text, re.I)
            mime = (mime_match.group(1).strip() if mime_match else '') or 'application/octet-stream'
            # part 末尾的 \r\n 屬於分隔符結構，不屬於文件內容
            if payload.endswith(b'\r\n'):
                payload = payload[:-2]

            ext = os.path.splitext(filename)[1].lower()
            is_image = mime.startswith('image/') or ext in self._IMAGE_EXTS
            stamp = time.strftime('%Y%m%d_%H%M%S')
            stored_name = f"{stamp}_{uuid.uuid4().hex[:6]}_{filename}"
            stored_path = os.path.join(self._uploads_dir(), stored_name)
            try:
                with open(stored_path, 'wb') as out:
                    out.write(payload)
            except OSError as e:
                self._send_error(f"Failed to save file: {e}", 500)
                return
            files.append({
                "name": filename,
                "path": stored_path,
                "mime": mime,
                "size": len(payload),
                "is_image": is_image,
            })
            logger.info(f"[Upload] saved {filename} ({len(payload)} bytes, mime={mime}, image={is_image})")

        if not files:
            self._send_error("No file found in upload body")
            return
        self._send_json({"status": "ok", "files": files})

    def _validate_attachment(self, item):
        """校驗前端回傳的附件引用：必須位於 uploads 目錄內且文件存在。"""
        if not isinstance(item, dict):
            return None
        path = str(item.get('path', '') or '')
        if not path:
            return None
        uploads = os.path.realpath(self._uploads_dir())
        real = os.path.realpath(path)
        if not real.startswith(uploads + os.sep) or not os.path.isfile(real):
            return None
        mime = str(item.get('mime', '') or '')
        ext = os.path.splitext(real)[1].lower()
        return {
            "name": self._sanitize_upload_name(str(item.get('name', '') or os.path.basename(real))),
            "path": real,
            "mime": mime,
            "is_image": bool(item.get('is_image')) or mime.startswith('image/') or ext in self._IMAGE_EXTS,
        }

    def _build_attachment_context(self, attachments, user_text: str) -> str:
        """把上傳附件轉成注入聊天的上下文段落。

        圖片：有視覺模型時直接調 vision 模型分析，結果餵給對話；
        其他文件（或視覺不可用時）：引導 Aize 結合文件類型與用戶需求
        自己寫代碼閉環分析（走正常聊天的技能 followup 循環）。"""
        blocks = []
        for att in attachments:
            att = self._validate_attachment(att)
            if not att:
                continue
            name, path, mime = att["name"], att["path"], att["mime"]
            need = (user_text or "").strip() or "分析这个文件并告诉我重点内容"

            if att["is_image"]:
                description = None
                try:
                    from llm import chat_with_image
                    publish_engine_event({"type": "internal_thought",
                                          "thought": f"[Upload] 正在用视觉模型分析图片 {name}…",
                                          "thought_type": "skill"})
                    description = chat_with_image(
                        f"用户上传了一张图片。用户需求：{need}\n"
                        f"请先详细描述图片内容，再结合用户需求给出回应要点。",
                        path, mime)
                except Exception as e:
                    logger.warning(f"[Upload] vision analysis failed: {e}")
                    description = f"[vision error] {e}"
                if description and not str(description).startswith("[vision error]"):
                    blocks.append(
                        f"【用户上传的图片「{name}」】\n"
                        f"视觉模型分析结果：\n{description}\n"
                        f"请结合以上图片内容和我的需求，用你平时的语气回复我。")
                    continue
                # 視覺不可用/失敗 → 降級為代碼分析（如提取尺寸、EXIF、OCR 等）
                reason = "未配置视觉模型（可在设置中启用 OpenAI API 并配置视觉模型）" \
                    if description is None else f"视觉模型调用失败（{str(description)[:120]}）"
                blocks.append(
                    f"【用户上传的图片「{name}」】\n"
                    f"- 类型：{mime}\n- 已保存到本机路径：{path}\n"
                    f"- 注意：{reason}，无法直接「看」图。\n"
                    f"用户需求：{need}\n"
                    f"请自己编写并执行代码（用 shell 技能运行 Python 脚本）尽可能分析这个图片文件"
                    f"（尺寸、格式、EXIF、颜色分布、OCR 文字等），执行结果返回后继续下一步，"
                    f"直到得出能给出的结论，再用自然语言总结给我，并如实说明哪些部分无法确认。")
                continue

            blocks.append(
                f"【用户上传的文件「{name}」，需要你分析】\n"
                f"- 类型：{mime}\n- 已保存到本机路径：{path}\n"
                f"- 大小：{os.path.getsize(path)} 字节\n"
                f"用户需求：{need}\n"
                f"请结合文件类型和用户需求，自己编写并执行代码来解析和分析这个文件"
                f"（文本类可用 file-read 分块读取；二进制/文档/压缩包等用 shell 技能运行 Python 脚本处理），"
                f"执行结果返回后继续下一步，直到得出完整结论，最后用自然语言把分析结果总结给我。"
                f"文件可能很大，不要试图一次性全部读入。")
        return "\n\n".join(blocks)

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

    def _handle_chat_history(self):
        """fix5：返回持久化聊天記錄（memory.json 中的對話消息）。
        網頁啟動時加載渲染；局域網設備連同一後端即可看到相同歷史。"""
        memory = ThinkingEngineState().get_memory() or {}
        items = []
        for msg in memory.get("messages", [])[-100:]:
            source = msg.get("source", "")
            role = msg.get("role", "")
            if role == "user" or source == "user":
                out_role = "user"
            elif role == "assistant" or source in ("ai_response", "ai_autonomous"):
                out_role = "assistant"
            else:
                continue
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if out_role == "assistant":
                thought, reply = _split_thought_response(content)
                if not reply:
                    reply, thought = thought, ""
                entry = {"role": "assistant", "content": reply, "time": msg.get("time", "")}
                if thought:
                    entry["thought"] = thought
                items.append(entry)
            else:
                items.append({"role": "user", "content": content, "time": msg.get("time", "")})
        self._send_json({"messages": items})

    def _handle_chat_timeline(self):
        """返回進程級結構化對話時間線（思考/命令/正文分離），
        供網頁刷新後原樣重建思考框與技能輸出框。"""
        self._send_json({"turns": _timeline_snapshot()})

    def _agent_prompt_path(self):
        """用戶可編輯的人設提示詞文件路徑（打包態為 exe 旁 Prompt/）"""
        try:
            from app_paths import prompts_dir
        except ImportError:
            from core.app_paths import prompts_dir
        return os.path.join(prompts_dir(), "agent_prompt.txt")

    def _handle_get_prompt(self):
        """讀取當前生效的人設提示詞，供網頁設置頁直接編輯"""
        path = self._agent_prompt_path()
        content = ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            pass
        # 首行版本標記只用於升級比對，不展示給用戶
        content = re.sub(r"\A\s*@@PROMPT_VER:\d+@@[^\n]*\n?", "", content, count=1)
        self._send_json({"ok": True, "content": content, "path": path})

    def _handle_save_prompt(self):
        """保存人設提示詞；保留版本標記，保存後下一句回覆立即生效"""
        data = self._read_json_body() or {}
        content = data.get("content")
        if not isinstance(content, str) or not content.strip():
            self._send_json({"ok": False, "error": "提示詞不能為空"}, status=400)
            return
        path = self._agent_prompt_path()
        marker = ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                first = f.readline(64)
            m = re.match(r"\s*(@@PROMPT_VER:\d+@@)", first)
            if m:
                marker = m.group(1) + "\n"
        except OSError:
            pass
        body = content.lstrip("\ufeff").strip()
        # 用戶若把標記一起貼進來，先去掉，避免重複
        body = re.sub(r"\A@@PROMPT_VER:\d+@@[^\n]*\n?", "", body, count=1)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(marker + body + "\n")
        except OSError as exc:
            self._send_json({"ok": False, "error": f"寫入失敗：{exc}"}, status=500)
            return
        self._send_json({"ok": True, "path": path})

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
            "model_path": "", "openai_enabled": False, "openai_api_key": "", "openai_base_url": "https://api.openai.com/v1", "openai_model": "gpt-4o-mini", "vision_model": "", "gan_enabled": True, "auto_break_silence": True,
            "skills_prompt": "", "llm_server_url": "http://127.0.0.1:8080",
            "max_tokens": 256, "temperature": 0.7, "guard_enabled": False,
            "guard_auto_start": False, "guard_interval": 5, "guard_firewall": True,
            "guard_network_monitor": True, "guard_system_monitor": True,
            "counter_measure_enabled": True, "counter_lab_mode": False,
            "counter_max_warnings": 2, "counter_cooldown": 300,
            "allow_lan_access": False, "web_auth_username": "", "web_auth_password_hash": "",
            "live2d_enabled": True, "animation_speed": "1.5",
            "tts_enabled": False
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
        default_voice = "zf_001"
        try:
            from voice.kokoro_tts import model_dir  # noqa: F401
            tts_available = bool(model_dir())
        except Exception:
            try:
                from core.voice.kokoro_tts import model_dir  # noqa: F401
                tts_available = bool(model_dir())
            except Exception:
                tts_available = False
        if not tts_available:
            try:
                import edge_tts  # noqa: F401
                tts_available = True
                default_voice = "zh-CN-XiaoxiaoNeural"
            except Exception:
                tts_available = False
        self._send_json({
            "tts_available": tts_available,
            "default_voice": default_voice,
            "stt": "webspeech",
        })

    def _handle_web_search(self, parsed):
        """聯網模塊搜索端點：復用 tools.web_search.WebSearch（DuckDuckGo + 代理配置）。

        供 mc-bot 等技能調用，例如 /api/web_search?q=minecraft%20小木屋&max=5。
        返回 {"query": "...", "results": [{"title","snippet","url","source"}]}。
        """
        qs = parse_qs(parsed.query)
        query = (qs.get('q') or [''])[0].strip()
        if not query:
            self._send_error("query param 'q' is required")
            return
        try:
            max_results = int((qs.get('max') or ['5'])[0])
        except ValueError:
            max_results = 5
        max_results = max(1, min(max_results, 10))
        try:
            from tools.web_search import WebSearch
        except ImportError:
            from core.tools.web_search import WebSearch
        try:
            results = WebSearch().search(query, max_results=max_results) or []
        except Exception as e:
            logger.warning(f"[WebSearch] search failed: {e}")
            results = []
        self._send_json({"query": query, "results": results})

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

    @staticmethod
    def _skill_payload(skill):
        """技能序列化：標記是否有獨立配置界面 / 可啟停服務（metadata 聲明 + 文件實際存在）。"""
        meta = skill.metadata or {}
        has_config_ui = bool(
            meta.get("config_ui")
            and _skill_subpath(skill.skill_dir, meta["config_ui"])
            and os.path.isfile(_skill_subpath(skill.skill_dir, meta["config_ui"]))
        )
        has_service = bool((meta.get("service") or {}).get("command"))
        builtin = bool(meta.get("builtin")) or skill.name.lower() in ("memory-search",)
        return {
            "name": skill.name,
            "description": (skill.description or "")[:300],
            "enabled": bool(skill.enabled),
            "builtin": builtin,
            "can_disable": not builtin,
            "can_delete": not builtin,
            "executable": bool(skill.executor),
            "has_config_ui": has_config_ui,
            "has_service": has_service,
            "service_running": _service_running(skill.name) if has_service else False,
        }

    def _handle_list_skills(self):
        """返回技能清單（名稱/說明/是否啟用/是否有執行器），不回傳任何密鑰。"""
        try:
            manager = _get_skills_manager()
            skills = [self._skill_payload(skill) for skill in manager.get_all_skills()]
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
            if not enabled and manager._is_builtin_skill(name):
                self._send_error(f"「{name}」是系統內置技能，無法關閉", 403)
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
                "skills": [self._skill_payload(skill) for skill in
                           sorted(manager.get_all_skills(),
                                  key=lambda item: item.name.lower())],
            })
        except (OSError, ValueError, json.JSONDecodeError) as e:
            self._send_error(f"Invalid request: {e}")

    def _handle_skills_reload(self):
        """重新掃描 skills 目錄：新增/刪除技能後不必重啟進程。"""
        try:
            manager = _get_skills_manager()
            count = manager.reload_skills()
            _invalidate_skills_prompt_cache()
            logger.info(f"[Skills] reloaded, total={count}")
            self._send_json({
                "status": "ok",
                "count": count,
                "skills": [self._skill_payload(skill) for skill in
                           sorted(manager.get_all_skills(),
                                  key=lambda item: item.name.lower())],
                "all_enabled": bool(manager.skills_config.get("all_enabled", True)),
            })
        except Exception as e:
            logger.error(f"[Skills] reload failed: {e}\n{traceback.format_exc()}")
            self._send_error(f"重新扫描技能失败: {e}", 500)

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
            elif name == "mcp-client":
                server = str(params.get("server", "")).strip()
                if server:
                    clean_params["server"] = server

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

    # ------------------------------------------------------------------
    # 技能子路由：/api/skills/{name}/config_ui|config|service|logs
    # 通用機制，凡在 SKILL.md metadata 聲明了對應能力的技能都可使用。
    # ------------------------------------------------------------------

    _SKILL_SUB_ACTIONS_GET = ("config_ui", "config", "service", "logs")
    _SKILL_SUB_ACTIONS_POST = ("config", "service")

    def _split_skill_subpath(self, path: str, allowed):
        """/api/skills/{name}/{action} → (name, action)；不合法返回 (None, None)。"""
        rest = path[len("/api/skills/"):]
        name, sep, action = rest.partition("/")
        name = name.strip()
        action = action.strip().lower()
        if not name or not sep or action not in allowed:
            return None, None
        return name, action

    def _route_skill_api_get(self, path: str):
        name, action = self._split_skill_subpath(path, self._SKILL_SUB_ACTIONS_GET)
        if not name:
            self._send_error("Not found", 404)
            return
        if action == "config_ui":
            self._handle_skill_config_ui(name)
        elif action == "config":
            self._handle_skill_config_get(name)
        elif action == "service":
            self._handle_skill_service_status(name)
        elif action == "logs":
            self._handle_skill_logs(name)

    def _route_skill_api_post(self, path: str):
        name, action = self._split_skill_subpath(path, self._SKILL_SUB_ACTIONS_POST)
        if not name:
            self._send_error("Not found", 404)
            return
        if action == "config":
            self._handle_skill_config_post(name)
        elif action == "service":
            self._handle_skill_service_control(name)

    def _resolve_skill(self, name: str):
        """取技能實例；失敗時已自行回應，返回 None。"""
        skill = _get_skill_by_name(name)
        if not skill or not skill.skill_dir:
            self._send_error(f"未找到技能: {name}", 404)
            return None
        return skill

    def _handle_skill_config_ui(self, name: str):
        """返回技能自帶的配置界面 HTML（供 Dashboard iframe 嵌入）。"""
        skill = self._resolve_skill(name)
        if not skill:
            return
        rel = (skill.metadata or {}).get("config_ui")
        path = _skill_subpath(skill.skill_dir, rel) if rel else None
        if not path or not os.path.isfile(path):
            self._send_error("该技能没有配置界面", 404)
            return
        self._send_file_path(path, "text/html; charset=utf-8")

    def _skill_config_file(self, skill):
        """技能聲明的配置文件絕對路徑；未聲明或越界返回 None。"""
        rel = (skill.metadata or {}).get("config_file")
        return _skill_subpath(skill.skill_dir, rel) if rel else None

    def _skill_secret_paths(self, skill):
        """脫敏點路徑集合（如 {"aize.password"}），僅接受標識符路徑。"""
        raw = (skill.metadata or {}).get("config_secret_fields") or []
        paths = set()
        for item in raw:
            parts = _get_secret_path(item)
            if parts:
                paths.add(".".join(parts))
        return paths

    def _handle_skill_config_get(self, name: str):
        """讀取技能配置文件（JSON），秘密字段脫敏為 'configured'。"""
        skill = self._resolve_skill(name)
        if not skill:
            return
        path = self._skill_config_file(skill)
        if not path:
            self._send_error("该技能未声明配置文件", 404)
            return
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            else:
                config = {}
            if not isinstance(config, dict):
                self._send_error("配置文件不是 JSON 对象", 500)
                return
            for dotted in self._skill_secret_paths(skill):
                _mask_secrets(config, dotted.split("."))
            self._send_json({"config": config})
        except (OSError, ValueError, json.JSONDecodeError) as e:
            self._send_error(f"读取配置失败: {e}", 500)

    def _handle_skill_config_post(self, name: str):
        """深合併寫入技能配置；秘密字段留空/'configured' 不覆蓋原值。"""
        skill = self._resolve_skill(name)
        if not skill:
            return
        path = self._skill_config_file(skill)
        if not path:
            self._send_error("该技能未声明配置文件", 404)
            return
        try:
            body = self._read_json_body()
        except (ValueError, json.JSONDecodeError) as e:
            self._send_error(f"Invalid request: {e}", 400)
            return
        patch = body.get("config")
        if not isinstance(patch, dict):
            self._send_error("config 必须是 JSON 对象", 400)
            return
        try:
            config = {}
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if not isinstance(config, dict):
                    config = {}
            _merge_config(config, patch, self._skill_secret_paths(skill))
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, path)
            logger.info(f"[Skills] config saved name={name} file={path}")
            self._send_json({"status": "ok", "message": "配置已保存"})
        except OSError as e:
            self._send_error(f"保存配置失败: {e}", 500)

    # ---------------------------- 技能服務啟停 ----------------------------

    def _skill_service_command(self, skill):
        svc = (skill.metadata or {}).get("service") or {}
        command = svc.get("command")
        if not isinstance(command, str) or not command.strip():
            return None
        return command.strip()

    def _handle_skill_service_status(self, name: str):
        skill = self._resolve_skill(name)
        if not skill:
            return
        if not self._skill_service_command(skill):
            self._send_error("该技能未声明服务", 404)
            return
        rec = _service_record(skill.name)
        payload = {"running": bool(rec)}
        if rec:
            payload["pid"] = rec["proc"].pid
            payload["uptime_sec"] = int(time.time() - rec["started_at"])
        self._send_json(payload)

    def _handle_skill_service_control(self, name: str):
        """啟停技能後台服務：{"action": "start"|"stop"|"restart"}。"""
        skill = self._resolve_skill(name)
        if not skill:
            return
        command = self._skill_service_command(skill)
        if not command:
            self._send_error("该技能未声明服务", 404)
            return
        try:
            body = self._read_json_body()
        except (ValueError, json.JSONDecodeError) as e:
            self._send_error(f"Invalid request: {e}", 400)
            return
        action = str(body.get("action", "")).strip().lower()
        if action not in ("start", "stop", "restart"):
            self._send_error("action 必须是 start/stop/restart", 400)
            return
        if action in ("stop", "restart"):
            self._stop_skill_service(skill.name)
        if action in ("start", "restart"):
            if not self._start_skill_service(skill, command):
                return  # 已自行回應錯誤
        self._send_json({
            "status": "ok",
            "running": _service_running(skill.name),
            "message": {"start": "服务已启动", "stop": "服务已停止", "restart": "服务已重启"}[action],
        })

    def _start_skill_service(self, skill, command: str) -> bool:
        """spawn 技能服務進程；日誌落到技能目錄 logs/service.log。失敗時已回應。"""
        if _service_record(skill.name):
            self._send_json({"status": "ok", "running": True, "message": "服务已在运行"})
            return False
        logs_dir = os.path.join(skill.skill_dir, "logs")
        try:
            os.makedirs(logs_dir, exist_ok=True)
            log_path = os.path.join(logs_dir, "service.log")
            log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
            log_handle.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} 启动 {command} =====\n")
            proc = subprocess.Popen(
                command,
                cwd=skill.skill_dir,
                shell=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except OSError as e:
            self._send_error(f"启动失败: {e}", 500)
            return False
        _SKILL_SERVICES[skill.name] = {
            "proc": proc,
            "started_at": time.time(),
            "log": log_path,
            "log_handle": log_handle,
        }
        logger.info(f"[Skills] service started name={skill.name} pid={proc.pid}")
        return True

    def _stop_skill_service(self, name: str):
        rec = _service_record(name)
        if not rec:
            return
        proc = rec["proc"]
        try:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        except Exception as e:
            logger.warning(f"[Skills] service stop failed name={name}: {e}")
        finally:
            try:
                rec.get("log_handle") and rec["log_handle"].close()
            except Exception:
                pass
            _SKILL_SERVICES.pop(name, None)
        logger.info(f"[Skills] service stopped name={name}")

    def _handle_skill_logs(self, name: str):
        """返回技能服務日誌末尾 100 行。"""
        skill = self._resolve_skill(name)
        if not skill:
            return
        if not self._skill_service_command(skill):
            self._send_error("该技能未声明服务", 404)
            return
        rec = _SKILL_SERVICES.get(skill.name)
        log_path = (rec or {}).get("log") or os.path.join(skill.skill_dir, "logs", "service.log")
        try:
            if not os.path.isfile(log_path):
                self._send_json({"lines": []})
                return
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()[-100:]
            self._send_json({"lines": lines})
        except OSError as e:
            self._send_error(f"读取日志失败: {e}", 500)

    def _handle_tts(self):
        """將文本合成為語音音頻（預設 Kokoro 本地神經 TTS，返回 audio/wav）。

        請求體: {"text": "...", "voice"?: "zf_001"}
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

    def _handle_chat_interrupt(self):
        """新消息到達時由子 Agent 判斷是否打斷當前回覆。

        請求：{"text": "主人新發的消息"}
        響應：{"interrupt": bool, "reason": str, "idle": bool}
        判定打斷時只 set 取消事件，實際的新問題由客戶端在同一個回合結束後重發。
        """
        try:
            body = self._read_json_body()
        except Exception as e:
            self._send_error(f"Invalid JSON body: {e}")
            return
        new_text = str(body.get("text", "")).strip()
        with self._active_chat_lock:
            active = dict(type(self)._active_chat) if type(self)._active_chat else None
        if not active:
            self._send_json({"interrupt": True, "merge": False, "idle": True,
                             "post_action": "drop_prev", "prev_question": "",
                             "reason": "no_active_chat"})
            return
        if not new_text:
            self._send_json({"interrupt": False, "merge": False, "idle": False, "reason": "empty_text"})
            return
        verdict = _judge_chat_interrupt(
            active.get("question", ""), active.get("partial", ""), new_text)
        if verdict["interrupt"]:
            ev = active.get("cancel")
            if ev is not None:
                ev.set()
            with self._active_chat_lock:
                if type(self)._active_chat:
                    type(self)._active_chat["interrupted"] = True
            logger.info(f"[Chat] interrupt requested: {verdict.get('reason')} new_text={new_text[:60]}")
        self._send_json({**verdict, "idle": False, "prev_question": active.get("question", ""),
                         "partial": str(active.get("partial") or "")[-600:]})

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
        # 本回合臨時系統指令（如「先拒絕換話題再繼續」），只進 system 塊，不寫入記憶
        system_hint = (body.get('system_hint') or '').strip()

        logger.info(
            f"[Chat] parsed path={urlparse(self.path).path} messages={len(messages)} "
            f"stream={stream} max_tokens={max_tokens} temperature={temperature}"
        )

        if not messages:
            self._send_error("messages is required")
            return

        # MC-Bot 乾淨通道：brain.js 標記 source=mc-bot 的請求不透過主程序的
        # prompt 拼裝/GAN/拒答/聯網搜索，只疊加人設與記憶後原樣透傳 messages。
        if body.get('source') == 'mc-bot':
            self._handle_mc_bot_chat(messages, max_tokens, temperature)
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
        # 時間線只存主人真正打的字（附件上下文/視覺描述不進聊天氣泡）
        display_user_text = (user_text or "").strip()

        # 上傳附件分流：圖片→視覺模型分析；其他文件→引導 Aize 寫代碼閉環分析。
        # 在佔用 _chat_lock 之前完成（視覺調用是外部 HTTP，不阻塞其他聊天排隊）。
        attachments = body.get('attachments') or []
        if isinstance(attachments, list) and attachments:
            try:
                attachment_context = self._build_attachment_context(attachments, user_text)
            except Exception as e:
                logger.warning(f"[Chat] attachment handling failed: {e}")
                attachment_context = ""
            if attachment_context:
                user_text = (user_text or "").strip()
                user_text = (user_text + "\n\n" + attachment_context) if user_text else attachment_context
                # 同步改寫最後一條 user 消息，讓 prompt 構建與記憶落盤都帶上附件上下文
                for msg in reversed(messages):
                    if msg.get('role') == 'user':
                        msg['content'] = user_text
                        break

        # 构建完整prompt（記憶不再自動附加，模型需要時自己調用 memory-search）
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
        # 人格描述不再单独拼接：統一由 persona_block 注入（見下方），
        # 避免多處人格（personality.json / agent_prompt / 各 prompt 文件）互相衝突。
        # 角色扮演人設（agent_prompt.txt）放進 system 塊：放在這裡模型才會
        # 真正入戲；走 MAIN/OTHER 三明治組裝時會被嵌套 prompt 稀釋/衝突
        try:
            from data.prompts_manager import load_agent_prompt
        except ImportError:
            from core.data.prompts_manager import load_agent_prompt
        _agent_prompt_text = (load_agent_prompt() or "").strip()
        if _agent_prompt_text:
            system_block_parts.append(_agent_prompt_text)
        # Aize 统一人格块：必须追加在「用户自定义提示词」之后
        try:
            try:
                from core.persona import persona_block
            except ImportError:
                from persona import persona_block
            _persona_text = persona_block("chat", memory)
            if _persona_text:
                system_block_parts.append(_persona_text)
        except Exception as e:
            logger.warning(f"[Chat] persona block failed: {e}")
        # 近期對話短窗口：多步任務（下載/安裝/排錯）需要知道前幾句做到哪，
        # 否則她會忘任務、只會空泛答應。更早的內容仍靠 memory-search 按需檢索。
        try:
            _recent_ctx = build_context_from_memory(memory, max_messages=12)
            if _recent_ctx:
                system_block_parts.append(_recent_ctx)
        except Exception as e:
            logger.warning(f"[Chat] recent context build failed: {e}")
        if system_hint:
            system_block_parts.append(system_hint[:2000])
        # 系統資訊：每次調用技能前先讓她知道 OS / shell 差異，避免拿 Linux 寫法在 Windows 上跑
        if os.name == "nt":
            system_block_parts.append(
                "【運行環境】Windows。shell 技能由 cmd.exe 執行，不是 PowerShell/bash。"
                "臨時目錄用 %TEMP%；禁止 /tmp、/Skills、$env:TEMP、New-Item；"
                "下載用 curl.exe，解壓用 tar -xf（失敗再用 powershell -Command Expand-Archive），寫入前先 mkdir。")
        else:
            system_block_parts.append(
                "【運行環境】Linux。shell 技能由 /bin/sh 執行，臨時目錄用 /tmp，解壓用 unzip 或 tar。")
        # 運行時實際可用的技能清單（安裝目錄 skills/ 下已啟用的技能），
        # 讓模型知道「什麼時候該用、具體叫什麼名字」，而不是只記得 JSON 格式
        _skills_text = _get_skills_prompt_cached()
        if _skills_text:
            system_block_parts.append(_skills_text)
        full_prompt = build_prompt_from_messages(messages, "\n\n".join(system_block_parts))

        logger.info(
            f"[Chat] dispatch user_text_length={len(user_text)} prompt_length={len(full_prompt)} "
            f"memory_available={bool(memory)} personality_available={bool(personality)} stream={stream}"
        )

        # 用戶在她忙於自主任務（主動開口/反思等）時插話：
        # 由 Aize 自己決定「先做完再說」還是「立刻回答」。
        # 選「先做完」時立刻回 ACK 並關閉本輪 SSE，避免手機端一直卡在加載；
        # 真正回覆走 break_silence 通道，作為主動消息推送。
        _busy_kind = None
        try:
            _busy_kind = thinking_engine.is_busy()
        except Exception:
            _busy_kind = None
        if _busy_kind and _busy_kind not in ("chat", "chat_stream", "chat_with_gan_decision") and user_text:
            _choice, _reason = _decide_busy_reply(user_text, _busy_kind)
            if _choice == "finish_first":
                logger.info(f"[Chat] busy({_busy_kind}) -> finish_first: {str(_reason)[:120]}")
                try:
                    if memory is not None:
                        from memory import add as _mem_add2, save_memory as _mem_save2
                        _mem_add2(memory, "user", user_text, source="user")
                        _mem_save2(memory)
                except Exception as e:
                    logger.warning(f"[Chat] busy persist failed: {e}")
                try:
                    # 只記下主人的話，不回任何提示；回覆留給之後的主動消息
                    _timeline_add_turn(user_text, [])
                except Exception:
                    pass
                # 當前任務完成後，接上主人的話主動回覆
                thinking_engine.queue_break_silence_task(
                    f"主人剛才說：{user_text}\n"
                    "你當時正忙，現在任務已完成，"
                    "主動接上這條消息，直接回覆主人，一兩句話。",
                    memory=memory)
                if stream:
                    self._send_empty_stream()
                else:
                    self._send_empty_json()
                return

        # 單 worker 串行：上一個聊天還在生成時直接禮貌拒絕，避免 collector 互相頂替
        if not self._chat_lock.acquire(blocking=False):
            logger.warning("[Chat] rejected: another chat task is still being processed")
            self._send_error("AI 正在思考中，請等待當前回覆完成後再發送", 409)
            return

        # fix2：web/API 路徑此前從不把用戶消息寫入記憶，導致上下文總是丟失。
        # 在 dispatch 前記錄並立即落盤，讓後續請求的 build_context_from_memory 能看到。
        if memory is not None and user_text:
            try:
                from memory import add as _mem_add, save_memory as _mem_save
                _mem_add(memory, "user", user_text, source="user")
                _mem_save(memory)
                # 学习主人习惯：识别「我要上课了」等缺席表述，并结算上次间隔
                try:
                    try:
                        from core.persona import note_user_message
                    except ImportError:
                        from persona import note_user_message
                    note_user_message(memory, user_text)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"[Chat] failed to persist user message to memory: {e}")

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

        # fix1：雙線程拒答機制——一個線程照常生成回覆，另一個線程並行判斷
        # 「要不要回覆」，並結合最近上下文決定「繼續剛才的話題還是回答新話題」。
        # 判定不回覆則掐斷生成線程，客戶端只看到「Aize不想回答你的问题」。
        cancel_event = threading.Event()
        thinking_engine._chat_cancel_event = cancel_event
        # 登記當前回合：/api/chat/interrupt 需要原問題、已輸出內容與取消事件
        with self._active_chat_lock:
            type(self)._active_chat = {
                "cancel": cancel_event,
                "question": user_text,
                "partial": "",
                "started": time.time(),
            }
        decision_holder = {}
        decision_done = threading.Event()

        def _run_answer_decision():
            try:
                ctx = build_context_from_memory(memory, max_messages=10) if memory else ""
                decision_holder['result'] = thinking_engine._should_answer_user_sync(user_text, ctx)
            except Exception as e:
                logger.error(f"[Chat] answer-decision error: {e}")
                decision_holder['result'] = (True, f"Error: {e} (defaulting to answer)")
            finally:
                decision_done.set()

        def _resolve_answer_decision():
            """等待決策結果；15 秒兜底默認回覆，避免決策卡死阻塞整個聊天。"""
            if not decision_done.wait(timeout=15):
                logger.warning("[Chat] answer-decision timed out after 15s, defaulting to answer")
                return True, "decision timeout, defaulting to answer"
            return decision_holder.get('result', (True, "no result, defaulting to answer"))

        # 先啟動決策線程再排生成任務：本地單槽推理時決策請求先佔住模型，
        # 生成排在後面，拒答時可以真正把生成擋在開始之前
        decision_thread = threading.Thread(target=_run_answer_decision, daemon=True)
        decision_thread.start()

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
                should_answer, decision_reason = _resolve_answer_decision()
                publish_engine_event({"type": "internal_thought",
                                      "thought": f"[Answer Decision] {'回覆' if should_answer else '不回覆'}：{str(decision_reason)[:120]}",
                                      "thought_type": "gan_decision"})
                if not should_answer:
                    cancel_event.set()
                    switch_reply = _topic_switch_reply(decision_reason)
                    logger.info(f"[Chat] refused to answer: {str(decision_reason)[:200]}")
                    self._send_refusal_stream(switch_reply or None)
                else:
                    self._handle_stream_response(collector, state, user_text=user_text,
                                                 prompt_chars=len(full_prompt),
                                                 display_user=display_user_text,
                                                 attachments=attachments)
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
                should_answer, decision_reason = _resolve_answer_decision()
                publish_engine_event({"type": "internal_thought",
                                      "thought": f"[Answer Decision] {'回覆' if should_answer else '不回覆'}：{str(decision_reason)[:120]}",
                                      "thought_type": "gan_decision"})
                if not should_answer:
                    cancel_event.set()
                    switch_reply = _topic_switch_reply(decision_reason)
                    logger.info(f"[Chat] refused to answer: {str(decision_reason)[:200]}")
                    self._send_refusal_json(switch_reply or None)
                else:
                    self._handle_sync_response(collector, user_text, memory, state)
        finally:
            # 恢复原始回调并清理本轮取消标记
            thinking_engine.on_response = original_on_response
            try:
                thinking_engine._chat_cancel_event = None
            except Exception:
                pass
            # 回合結束：清空中斷登記，之後的新消息直接正常發送
            with self._active_chat_lock:
                type(self)._active_chat = None
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

    def _handle_mc_bot_chat(self, messages, max_tokens, temperature):
        """MC-Bot 乾淨通道：brain.js 的 messages 原樣透傳給模型。

        只疊加兩樣東西（作為額外 system 消息放在最前）：
          1. agent_prompt.txt 人設
          2. 記憶上下文（build_context_from_memory）
        其他一律保持純淨：不疊加 system_prompt.txt、技能清單、GAN 決策、
        拒答線程、聯網搜索，也不把遊戲狀態寫入主記憶。
        """
        system_parts = []
        try:
            from data.prompts_manager import load_agent_prompt
        except ImportError:
            from core.data.prompts_manager import load_agent_prompt
        try:
            agent_prompt = (load_agent_prompt() or "").strip()
            if agent_prompt:
                system_parts.append(agent_prompt)
        except Exception as e:
            logger.warning(f"[MC-Bot] load agent_prompt failed: {e}")
        try:
            memory = ThinkingEngineState().get_memory()
            context = build_context_from_memory(memory) if memory else ""
            if context:
                system_parts.append(context)
        except Exception as e:
            logger.warning(f"[MC-Bot] build memory context failed: {e}")

        out_messages = list(messages)
        if system_parts:
            out_messages.insert(0, {"role": "system", "content": "\n\n".join(system_parts)})

        try:
            from llm.llm import _provider_settings, create_session, _strip_think_blocks
        except ImportError:
            from core.llm.llm import _provider_settings, create_session, _strip_think_blocks
        provider = _provider_settings()
        if not provider:
            self._send_error("MC-Bot 通道需要啟用雲端模型 API", 503)
            return

        payload = {
            "model": provider["model"],
            "messages": out_messages,
            "max_tokens": max_tokens or 300,
            "temperature": temperature if isinstance(temperature, (int, float)) else 0.7,
        }
        logger.info(f"[MC-Bot] passthrough messages={len(out_messages)} max_tokens={payload['max_tokens']}")
        session = create_session()
        try:
            resp = session.post(
                f"{provider['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            content = _strip_think_blocks(content)
        except Exception as e:
            logger.error(f"[MC-Bot] LLM request failed: {e}")
            self._send_error(f"LLM request failed: {e}", 502)
            return
        finally:
            session.close()

        self._send_json({
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": provider["model"],
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop"
            }],
            "usage": data.get("usage", {})
        })

    def _send_refusal_stream(self, text=None):
        """拒答（流式）：默認只發一條「Aize不想回答你的问题」；切換話題時發她自發的台詞。"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        chunk = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "thinking-engine",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": text or REFUSAL_TEXT},
                    "finish_reason": "stop"
                }
            ]
        }
        try:
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except BrokenPipeError:
            pass

    def _send_refusal_json(self, text=None):
        """拒答（同步）：OpenAI 格式，默認拒答語；切換話題時發自發台詞。"""
        self._send_json({
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "thinking-engine",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text or REFUSAL_TEXT},
                    "finish_reason": "stop"
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        })

    def _send_empty_stream(self):
        """靜默結束本輪（Aize 先忙手頭的事，稍後以主動消息回覆）。"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except BrokenPipeError:
            pass

    def _send_empty_json(self):
        """靜默結束本輪（同步版）。"""
        self._send_json({
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "thinking-engine",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        })

    def _handle_sync_response(self, collector, user_text, memory, state):
        """处理同步（非流式）响应 - 通过ResponseCollector收集ThinkingEngine的响应"""
        try:
            # 等待响应完成（最多等待collector的timeout）
            full_reply = ""
            tl_items = []
            pending_turn_id = _timeline_begin_turn(user_text)
            while True:
                chunk = collector.get_chunk()
                if chunk["type"] == "chunk":
                    full_reply += chunk["content"]
                    tl_items.append({"k": "text", "t": "", "c": chunk["content"]})
                elif chunk["type"] == "thought":
                    tl_items.append({"k": "thought", "t": chunk.get("thought_type", ""), "c": chunk.get("content", "")})
                elif chunk["type"] in ("command_start", "command_result"):
                    tl_items.append({"k": chunk["type"], "t": "", "c": chunk.get("message") or chunk.get("output") or ""})
                elif chunk["type"] == "done":
                    # 任务完成，退出循环
                    break
                elif chunk["type"] == "error":
                    full_reply = f"错误: {chunk['content']}"
                    tl_items.append({"k": "text", "t": "", "c": full_reply})
                    break
                elif chunk["type"] == "timeout":
                    full_reply = "抱歉，我刚才走神了～能再说一遍吗？😊"
                    tl_items.append({"k": "text", "t": "", "c": full_reply})
                    break

            # 标记完成
            collector.set_finished()
            _timeline_add_turn(user_text, tl_items, pending_id=pending_turn_id)

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

    def _handle_stream_response(self, collector, state, user_text="", prompt_chars=0,
                                display_user="", attachments=None):
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
        t_start = time.time()

        # 每次回覆至少觸發一個動作：模型偶爾漏發 [motion:] 時，形象也不會一動不動
        # 動作依當下主導情緒挑選（不再用 created % 9 亂抽），低落時寧可先不動
        try:
            from tools.live2d_hub import get_live2d_hub
            from tools.motion_policy import pick_reply_motion
            _motion = pick_reply_motion()
            if _motion:
                get_live2d_hub().push_command(_motion)
        except Exception:
            pass

        # 結構化事件時間線：刷新頁面後原樣重建思考框/命令輸出框
        # 先把這一輪寫成 pending，生成過程中持續更新，刷新不會再丟失
        tl_items = []
        pending_turn_id = _timeline_begin_turn(user_text, display_user=display_user,
                                               attachments=attachments)
        turn_usage = None

        try:
            # 累积完整回复用于清理和UI更新
            full_reply = ""
            
            # 从ResponseCollector获取流式响应
            while True:
                chunk = collector.get_chunk()
                
                if chunk["type"] == "chunk":
                    content = chunk["content"]
                    full_reply += content
                    tl_items.append({"k": "text", "t": "", "c": content})
                    _timeline_update_pending(tl_items)
                    # 供中斷判斷子 Agent 參考「已經說到哪」
                    with self._active_chat_lock:
                        if type(self)._active_chat:
                            type(self)._active_chat["partial"] = full_reply[-1500:]

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
                        # 客戶端被新消息打斷而斷線時，同步取消生成，讓引擎盡快釋放聊天鎖
                        try:
                            engine = state.get_thinking_engine() if state is not None else None
                            ev = getattr(engine, "_chat_cancel_event", None)
                            if ev is not None:
                                ev.set()
                        except Exception:
                            pass
                        break
                        
                elif chunk["type"] == "thought":
                    thought_content = chunk["content"]
                    thought_type = chunk.get("thought_type", "")
                    tl_items.append({"k": "thought", "t": thought_type, "c": thought_content})
                    _timeline_update_pending(tl_items)
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
                    cmd_content = chunk.get("message") or chunk.get("output") or ""
                    tl_items.append({"k": chunk["type"], "t": "", "c": cmd_content})
                    _timeline_update_pending(tl_items)
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
                                    "content": cmd_content
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
                    tl_items.append({"k": "text", "t": "", "c": error_content})
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
                        tl_items.append({"k": "text", "t": "", "c": error_content})
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
                    tl_items.append({"k": "text", "t": "", "c": timeout_content})
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
            # 用量統計：跟最後一個 chunk 一起下發，前端據此顯示「完成」標誌
            final_chunk["usage"] = {
                "prompt_chars": int(prompt_chars or 0),
                "completion_chars": len(full_reply or ""),
                "prompt_tokens_est": max(1, int((prompt_chars or 0) / 1.6)) if prompt_chars else 0,
                "completion_tokens_est": max(1, int(len(full_reply or "") / 1.6)) if full_reply else 0,
                "elapsed": round(time.time() - t_start, 1),
            }
            try:
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode('utf-8'))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except BrokenPipeError:
                pass

            # 标记完成
            collector.set_finished()

            # 保存本輪結構化時間線（刷新頁面後重建思考框/命令框/用量/附件名）
            # 統一在 finally 中落盤，避免客戶端斷線時跳過
            turn_usage = final_chunk.get("usage")

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
            except Exception:
                pass
        finally:
            # 無論成功、出錯還是客戶端斷線，都把這一輪定稿，pending 不會殘留
            try:
                _timeline_add_turn(user_text, tl_items, usage=turn_usage,
                                   display_user=display_user, attachments=attachments,
                                   pending_id=pending_turn_id)
            except Exception as e:
                logger.warning(f"[Timeline] finalize failed: {e}")


class ThinkingEngineAPIServer:
    """ThinkingEngine API服务器"""

    def __init__(self, host='127.0.0.1', port=8082):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        """启动API服务器（在后台线程中）。

        Windows 上首選端口可能被其他軟件獨占綁定——典型如 QQNT 啟動時隨機
        占用 8082，此時操作系統返回 WinError 10013（WSAEACCES）而非端口占用的
        10048；端口落在系統保留段（netsh excludedportrange）時同樣如此。
        因此首選端口綁定失敗時自動向後探測空閒端口，調用方統一通過
        server.port 讀取實際端口，托盤菜單與瀏覽器打開的 URL 自動跟隨。
        """
        if self.running:
            return

        requested_port = self.port
        last_error = None
        bound_server = None
        bound_port = None
        # 最多向後探測 20 個端口。
        # 注意：Windows 上若其他程序占用的是 0.0.0.0:port 而本機綁 127.0.0.1，
        # 系統允許共存且 loopback 請求按「最長匹配」優先到達本服務，屬正常情形；
        # 只有綁定真正失敗（0.0.0.0 衝突 10013/10048、保留端口段等）才順延。
        for candidate in range(requested_port, requested_port + 20):
            try:
                bound_server = HTTPServer((self.host, candidate), ThinkingEngineAPIHandler)
                bound_port = candidate
                break
            except OSError as exc:
                # 10013=被安全策略/獨占綁定/保留端口段攔截；10048=端口已占用
                last_error = exc
                logger.warning(
                    f"端口 {candidate} 無法綁定"
                    f"（{getattr(exc, 'winerror', exc.__class__.__name__)}: {exc}），嘗試下一個端口..."
                )

        if bound_server is None:
            raise OSError(
                f"端口 {requested_port}~{requested_port + 19} 均無法綁定，"
                f"請檢查端口占用或防火牆策略。最後一個錯誤: {last_error}"
            )

        if bound_port != requested_port:
            logger.warning(
                f"首選端口 {requested_port} 被占用或被系統攔截，"
                f"Humanaize2 已自動改用端口 {bound_port}"
            )

        self.server = bound_server
        self.port = bound_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="ThinkingEngineAPI")
        self.thread.start()
        self.running = True
        logger.info(f"ThinkingEngine API server started on http://{self.host}:{self.port}")

        # 後台預熱技能管理器：首次掃描需導入全部技能模塊（可達十幾秒），
        # 放啟動線程做掉，用戶首次打開「技能管理」分頁時即點即顯
        def _prewarm_skills():
            try:
                _get_skills_manager().get_all_skills()
            except Exception as e:
                logger.warning(f"[Skills] prewarm failed: {e}")
        threading.Thread(target=_prewarm_skills, daemon=True,
                         name="SkillsPrewarm").start()

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

    server = ThinkingEngineAPIServer(args.host, args.port)
    server.start()

    actual_port = server.port
    if actual_port != args.port:
        print(f"[WARN] Port {args.port} unavailable, fallback to {actual_port}")
    print(f"Starting ThinkingEngine API server on http://{args.host}:{actual_port}")
    print(f"OpenAI-compatible endpoint: http://{args.host}:{actual_port}/v1/chat/completions")
    print(f"Models list: http://{args.host}:{actual_port}/v1/models")
    print(f"Health check: http://{args.host}:{actual_port}/health")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
