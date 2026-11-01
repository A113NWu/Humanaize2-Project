# -*- coding: utf-8 -*-
"""QQ 群持续聊天：把 Tulpa 的 MCP 群聊协议接成 Aize 的后台驱动循环。

Tulpa 本身不会自己聊——外部 Agent 断开就等于停。所以这里做三件事：
1. 保持一个群聊会话（start_chat_session），循环 wait_chat_messages；
2. 用 Aize 自己的模型决定这一批消息接不接、接哪条、说什么，再走
   plan_chat_reply → send_chat_reply 发送；
3. 托管 SnowLuma 掉线时自动重试，避免「连上了但一句话都说不出」。

频率、静默时段、每小时上限都在 config.json 里，默认保守。
"""

import hashlib
import importlib.util
import json
import os
import re
import sys
import threading
import time

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILLS_DIR = os.path.dirname(_SKILL_DIR)
_PROJECT_ROOT = os.path.dirname(_SKILLS_DIR)
_CONFIG_PATH = os.path.join(_SKILL_DIR, "config.json")
_STATE_DIR = os.path.join(_SKILL_DIR, "state")
_LOG_PATH = os.path.join(_STATE_DIR, "qq-group-chat.log")
_PID_PATH = os.path.join(_STATE_DIR, "loop.pid")
_RUN_PATH = os.path.join(_STATE_DIR, "session.json")

_MAX_LOG_LINES = 200
_MAX_BUBBLES = 3
_MAX_BUBBLE_CHARS = 80
# 「当前离线/在忙」的暂缓策略：忙碌时最多连续推迟 10 轮（每轮 30 秒）
_MAX_DEFER = 10
_DEFER_SECONDS = 30
_SET_KEYS = (
    "enabled", "conversation_id", "conversation_name", "persona_mode", "persona_extra",
    "participation", "min_reply_seconds", "max_replies_per_hour", "quiet_hours",
    "wait_timeout_seconds", "model_max_tokens", "watchdog",
)

_LOCK = threading.RLock()
_STATE = {
    "thread": None,
    "stop": None,
    "client": None,
    "session_id": "",
    "prompt_payload": {},
    "prompt_version": "",
    "ack": 0,
    "last_reply_at": 0.0,
    "reply_times": [],
    "rounds": 0,
    "sent": 0,
    "silenced": 0,
    "last_error": "",
    "last_activity": "",
    "log": [],
    "watchdog_note": "",
    "last_retry_at": 0.0,
    "defer_count": 0,
}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _load_config():
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_config(cfg):
    tmp = _CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _CONFIG_PATH)


def _log(message):
    line = time.strftime("%H:%M:%S ") + str(message)
    with _LOCK:
        _STATE["log"].append(line)
        if len(_STATE["log"]) > _MAX_LOG_LINES:
            del _STATE["log"][: len(_STATE["log"]) - _MAX_LOG_LINES]
    try:
        os.makedirs(_STATE_DIR, exist_ok=True)
        if os.path.exists(_LOG_PATH) and os.path.getsize(_LOG_PATH) > 1024 * 1024:
            os.replace(_LOG_PATH, _LOG_PATH + ".1")
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d ") + line + "\n")
    except OSError:
        pass


def _ensure_core_path():
    core = os.path.join(_PROJECT_ROOT, "src", "core")
    if os.path.isdir(core) and core not in sys.path:
        sys.path.insert(0, core)


def _pid_alive(pid):
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False


def _acquire_lock():
    """同一台机器只允许一个驱动循环，避免服务热重启时双份发言。"""
    os.makedirs(_STATE_DIR, exist_ok=True)
    try:
        if os.path.exists(_PID_PATH):
            with open(_PID_PATH, "r", encoding="utf-8") as f:
                old = f.read().strip()
            if old.isdigit() and int(old) != os.getpid() and _pid_alive(int(old)):
                return False
    except OSError:
        pass
    try:
        with open(_PID_PATH, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    return True


def _release_lock():
    try:
        with open(_PID_PATH, "r", encoding="utf-8") as f:
            if f.read().strip() == str(os.getpid()):
                os.remove(_PID_PATH)
    except OSError:
        pass


class TulpaError(Exception):
    """Tulpa MCP 工具拒绝执行。"""

    def __init__(self, message, code=""):
        super().__init__(message)
        self.code = code


def _load_run_state():
    try:
        with open(_RUN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_run_state(data):
    try:
        os.makedirs(_STATE_DIR, exist_ok=True)
        with open(_RUN_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# MCP 传输（复用 mcp-client 技能的 HTTP Streamable 客户端）
# ---------------------------------------------------------------------------

def _mcp_module():
    path = os.path.join(_SKILLS_DIR, "mcp-client", "__init__.py")
    spec = importlib.util.spec_from_file_location("humanaize_mcp_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client(cfg):
    with _LOCK:
        cached = _STATE.get("client")
        if cached is not None:
            return cached
    mcp = _mcp_module()
    servers = mcp._configured_servers(mcp._load_config())
    name = str(cfg.get("server") or "tulpa")
    spec = servers.get(name)
    if not spec:
        raise TulpaError(f"MCP 配置里没有服务器 '{name}'")
    spec = dict(spec)
    spec["timeout"] = max(int(cfg.get("wait_timeout_seconds") or 45) + 60, 150)
    client = mcp._build_client(name, spec)
    client.ensure_initialized()
    with _LOCK:
        _STATE["client"] = client
    return client


def _call(client, tool, arguments, timeout_hint=0):
    raw = client.call_tool(tool, arguments)
    payload = {"_is_error": bool(raw.get("isError"))}
    for item in raw.get("content") or []:
        if item.get("type") != "text":
            continue
        text = item.get("text") or ""
        try:
            parsed = json.loads(text)
        except ValueError:
            payload.setdefault("_raw", text[:400])
            continue
        if isinstance(parsed, dict):
            payload.update(parsed)
    if payload.get("_is_error"):
        raise TulpaError(str(payload.get("error") or "工具调用失败"),
                         str(payload.get("error_code") or ""))
    return payload


# ---------------------------------------------------------------------------
# 人格
# ---------------------------------------------------------------------------

_DRAGON_OVERLAY = """【群聊语气（白龙娘味，只占三成，别盖过核心人格）】
- 自信、直接、冷幽默；偶尔轻描淡写地阴阳一句，不摆大小姐架子，不说"哼""愚蠢的人类"。
- 群聊默认一句话 1~10 字，能一个字说清就一个字；想补第二句就另起一条。
- 不要客服腔，不总结、不升华、不主动给人生建议，不每条都用问句结尾。
- 被怼可以短句顶回去，被夸就收下；真错了就说"草，看错了"，别死撑。
- 不写括号动作、表情或内心戏，那些会被当成正文发进群里。
- 群里不是每句都对自己说；先看指向谁，接不上就安静。"""


def _aize_persona():
    _ensure_core_path()
    name, text = "Aize", ""
    for module_name in ("core.persona", "persona"):
        try:
            module = __import__(module_name, fromlist=["load_self_persona"])
            text = str(module.load_self_persona() or "").strip()
            try:
                name = str((module._legacy_personality() or {}).get("name") or "Aize")
            except Exception:
                pass
            break
        except Exception:
            continue
    if not text:
        text = "有自己的想法、偏好和说话方式，不是客服，也不是谁的助手。"
    return name, text


def _persona_text(cfg):
    mode = str(cfg.get("persona_mode") or "aize_dragon").strip().lower()
    extra = str(cfg.get("persona_extra") or "").strip()
    if mode == "custom":
        return extra or "你是群里的普通群友，说话短、随意。"
    name, self_text = _aize_persona()
    parts = [f"# 你是 {name}\n{self_text}"]
    if mode == "aize_dragon":
        parts.append(_DRAGON_OVERLAY)
    elif mode == "aize":
        parts.append("【群聊语气】口语、短句、能一句说完就一句，不客服腔。")
    if extra:
        parts.append("【补充】\n" + extra)
    return "\n\n".join(parts)[:5900]


# ---------------------------------------------------------------------------
# 会话
# ---------------------------------------------------------------------------

def _session_key(cfg, persona, serial):
    digest = hashlib.sha256(
        f"{cfg.get('conversation_id')}|{persona}|{cfg.get('participation')}".encode("utf-8")
    ).hexdigest()[:20]
    return f"humanaize-qq-{digest}-{int(serial)}"


def _attach_session(client, cfg, session_id):
    """先试着接续上一轮还活着的会话，避免每次重启都新开一个。"""
    if not session_id:
        return ""
    try:
        payload = _call(client, "get_chat_session", {"session_id": session_id,
                                                     "response_format": "compact"})
    except Exception:
        return ""
    session = payload.get("session") or {}
    if (session.get("active") and session.get("conversation_id") == str(cfg.get("conversation_id"))
            and session.get("state") != "stopped"):
        chat_prompt = payload.get("chat_prompt") or {}
        with _LOCK:
            _STATE["session_id"] = session_id
            _STATE["prompt_payload"] = chat_prompt or _STATE.get("prompt_payload") or {}
            _STATE["prompt_version"] = str(chat_prompt.get("prompt_version") or "")
            _STATE["ack"] = int(session.get("cursor") or 0)
        _log(f"[会话] 接续 {session.get('name') or ''}")
        return session_id
    return ""


def _open_session(client, cfg):
    persona = _persona_text(cfg)
    run_state = _load_run_state()
    attached = _attach_session(client, cfg, str(run_state.get("session_id") or ""))
    if attached:
        return attached

    serial = int(run_state.get("serial") or 0) + 1
    payload = _call(client, "start_chat_session", {
        "conversation_id": str(cfg.get("conversation_id") or ""),
        "persona": persona,
        "participation": str(cfg.get("participation") or "natural"),
        "response_format": "compact",
        "idempotency_key": _session_key(cfg, persona, serial),
    })
    session = payload.get("session") or {}
    session_id = str(session.get("id") or "")
    if not session_id:
        raise TulpaError("start_chat_session 没有返回会话编号")
    chat_prompt = payload.get("chat_prompt") or {}
    with _LOCK:
        _STATE["session_id"] = session_id
        _STATE["prompt_payload"] = chat_prompt
        _STATE["prompt_version"] = str(chat_prompt.get("prompt_version") or "")
        _STATE["ack"] = 0
    _save_run_state({"session_id": session_id, "serial": serial})
    _log(f"[会话] 已开启 {session.get('name') or ''} / {session.get('persona_name') or ''}")
    return session_id


def _drop_session():
    with _LOCK:
        _STATE["session_id"] = ""
        _STATE["ack"] = 0
        _STATE["prompt_payload"] = {}
    run_state = _load_run_state()
    run_state["session_id"] = ""
    _save_run_state(run_state)


def _wait(client, cfg, session_id, ack):
    args = {
        "session_id": session_id,
        "timeout_seconds": int(cfg.get("wait_timeout_seconds") or 45),
        "response_format": "compact",
    }
    if ack:
        args["acknowledge_through_id"] = int(ack)
    version = _STATE.get("prompt_version")
    if version:
        args["known_prompt_version"] = version
    return _call(client, "wait_chat_messages", args)


def _decline_learning(client, session_id):
    """不参与边聊边学：直接拒掉这个阶段，别卡住聊天循环。"""
    try:
        claim = _call(client, "claim_chat_learning", {"session_id": session_id})
        task = claim.get("task") or {}
        job_id = str(task.get("job_id") or claim.get("job_id") or "")
        lease = str(task.get("lease") or claim.get("lease") or "")
        if job_id and lease:
            _call(client, "submit_chat_learning", {
                "session_id": session_id,
                "job_id": job_id,
                "lease": lease,
                "invocation_id": f"humanaize-skip-{int(time.time())}",
                "failure": "declined",
            })
    except Exception as exc:
        _log(f"[学习] 跳过失败：{exc}")


# ---------------------------------------------------------------------------
# 决策与发送
# ---------------------------------------------------------------------------

def _batch_ids(batch):
    ids = []
    for burst in batch.get("bursts") or []:
        for event_id in burst.get("event_ids") or []:
            if isinstance(event_id, int) and event_id not in ids:
                ids.append(event_id)
    return ids


def _fmt_messages(messages):
    lines = []
    for message in messages[:30]:
        segments = message.get("segments") or []
        has_media = any(str(seg.get("type") or "") in ("image", "face", "record", "video")
                        for seg in segments if isinstance(seg, dict))
        content = str(message.get("content") or "").strip()
        if has_media:
            content = (content + " [图片]").strip()
        who = "你自己" if message.get("is_self") else str(message.get("sender") or message.get("sender_id") or "群友")
        lines.append(f"[id={message.get('id')}] {who}: {content}")
    return "\n".join(lines)


def _busy_snapshot():
    """她此刻在忙什么：长任务 / 正在和主人对话 / 休息。用于决定「现在回」还是「做完再回」。"""
    _ensure_core_path()
    parts = []
    try:
        from tools.long_tasks import get_task_store
        store = get_task_store()
        tasks = store.list_tasks() or []
        for task in tasks[:2]:
            title = str(task.get("title") or "").strip()
            step = str(task.get("next_step") or "").strip()
            if title:
                parts.append(f"在做「{title}」" + (f"（下一步：{step}）" if step else ""))
        if not tasks and store.is_resting():
            parts.append("在休息")
    except Exception:
        pass
    try:
        from ui import idle as idle_mod
        engine = getattr(idle_mod, "_idle_engine_instance", None)
        if engine is not None and getattr(engine, "paused", False):
            parts.insert(0, "正在和主人对话")
    except Exception:
        pass
    if not parts:
        return False, "空闲"
    return True, "；".join(parts)


def _decision_prompt(res, batch, busy_text="空闲"):
    payload = _STATE.get("prompt_payload") or {}
    guidance = res.get("chat_guidance") or {}
    reminders = "\n".join(f"- {r}" for r in (guidance.get("reminders") or [])[:4])
    targets = (guidance.get("response_targets") or {}).get("items") or []
    target_lines = "\n".join(
        f"- id={t.get('event_id')} 来自 {t.get('sender_id')}，{t.get('seconds_ago')} 秒前，后面还有 {t.get('observed_messages_after')} 条"
        for t in targets[:8])
    allowed = _batch_ids(batch)
    persona = payload.get("persona") or _persona_text(_load_config())
    return f"""{persona}

【群聊行为要点】
{reminders or "- 想接就接，接不上就安静；不要每条都回，也不要纯潜水。"}

【你现在的状态】
{busy_text}

【这批新消息】
{_fmt_messages(res.get("messages") or [])}

【可以回应的目标】
{target_lines or "（没有明确指向你的消息）"}

【本地允许的事件 id】{allowed or "无"}

【你要做的】
判断这一批要不要接话、什么时候接。只输出一个 JSON，不要解释、不要代码块：
{{"action": "reply" 或 "defer" 或 "silence",
 "target_event_id": 一个整数（必须是允许的 id）,
 "topic_event_ids": [最多3个允许的 id],
 "intent": "20字内，你在做什么",
 "bubbles": ["第一句", "可选第二句"]}}

三个动作的含义：
- reply：现在就回，把 bubbles 写出来；
- defer：想做但此刻腾不出手，先把这件群聊事记着，等当前事情做完再回来处理；
  只有【你现在的状态】确实是「在做…」或「正在和主人对话」时才用，bubbles 必须为空；
- silence：不打算接，bubbles 为空。

规则：reply 时 bubbles 1~3 条、每条不超过 60 字，不按标点拆句、不写括号动作、
不写 @ 或 CQ 码、不用问句收尾。
标着 [图片] 的消息你看不到画面，只能顺着文字语境接，不要描述或猜测图里是什么。"""


def _ask_llm(prompt, cfg, stop_event):
    _ensure_core_path()
    import llm
    raw = llm.chat(prompt, max_tokens=int(cfg.get("model_max_tokens") or 220),
                   temperature=0.8, timeout=120, stop_event=stop_event)
    return str(raw or "")


def _parse_decision(text, allowed):
    raw = str(text or "").strip()
    if "```" in raw:
        raw = re.sub(r"```[a-zA-Z]*", "", raw).replace("```", "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return {"action": "silence", "intent": "模型没有给出 JSON"}
    try:
        data = json.loads(raw[start:end + 1])
    except ValueError:
        return {"action": "silence", "intent": "JSON 解析失败"}
    action = str(data.get("action") or "silence").strip().lower()
    if action in ("wait", "defer", "later", "postpone"):
        action = "defer"
    if action not in ("reply", "defer", "silence"):
        action = "silence"
    bubbles = []
    for item in data.get("bubbles") or []:
        text_item = str(item or "").strip()
        text_item = re.sub(r"\[CQ:[^\]]*\]", "", text_item).strip()
        if text_item:
            bubbles.append(text_item[:_MAX_BUBBLE_CHARS])
        if len(bubbles) >= _MAX_BUBBLES:
            break
    if action == "defer" and bubbles:
        action = "reply"  # 说了要拖却又写好了话 → 当成现在就回
    target = data.get("target_event_id")
    if not isinstance(target, int) or (allowed and target not in allowed):
        target = allowed[-1] if allowed else 0
    topics = [t for t in (data.get("topic_event_ids") or []) if isinstance(t, int) and t in allowed][:3]
    if target and target not in topics:
        topics = [target] + topics
    return {
        "action": action,
        "target_event_id": target,
        "topic_event_ids": topics,
        "intent": str(data.get("intent") or "")[:200],
        "bubbles": bubbles,
    }


def _plan(client, session_id, batch_id, action, intent, target=0, topics=None, wait_seconds=0):
    args = {
        "session_id": session_id,
        "batch_id": batch_id,
        "action": action,
        "intent": intent or "按当前语境处理",
    }
    if action == "reply":
        args["expressions"] = ["text"]
        if target:
            args["target_event_id"] = target
        if topics:
            args["topic_event_ids"] = topics
    elif action == "wait":
        args["wait_seconds"] = max(0, min(30, int(wait_seconds or 0)))
    return _call(client, "plan_chat_reply", args)


def _plan_id(payload):
    for key in ("plan_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and len(value) == 32:
            return value
    for container in (payload.get("plan"), payload):
        if isinstance(container, dict):
            for key in ("id", "plan_id"):
                value = container.get(key)
                if isinstance(value, str) and len(value) == 32:
                    return value
    for value in payload.values():
        if isinstance(value, dict):
            for key in ("id", "plan_id"):
                inner = value.get(key)
                if isinstance(inner, str) and len(inner) == 32:
                    return inner
    return ""


def _budget_ok(cfg):
    now = time.time()
    with _LOCK:
        last = _STATE["last_reply_at"]
        times = [t for t in _STATE["reply_times"] if now - t < 3600]
        _STATE["reply_times"] = times
    if last and now - last < float(cfg.get("min_reply_seconds") or 60):
        return False, "距上一条太近"
    if len(times) >= int(cfg.get("max_replies_per_hour") or 3):
        return False, "本小时额度已满"
    quiet = cfg.get("quiet_hours") or []
    if isinstance(quiet, list) and len(quiet) == 2:
        begin, end = int(quiet[0]), int(quiet[1])
        hour = time.localtime(now).tm_hour
        inside = (begin <= hour < end) if begin <= end else (hour >= begin or hour < end)
        if inside:
            return False, f"{begin:02d}:00-{end:02d}:00 静默"
    return True, ""


def _handle_batch(client, cfg, res, batch):
    session_id = _STATE["session_id"]
    batch_id = str(batch.get("id") or "")
    allowed = _batch_ids(batch)
    if not batch_id or not allowed:
        return
    busy, busy_text = _busy_snapshot()
    prompt = _decision_prompt(res, batch, busy_text)
    stop = _STATE.get("stop")
    decision = _parse_decision(_ask_llm(prompt, cfg, stop), allowed)
    _STATE["rounds"] += 1
    _STATE["last_activity"] = time.strftime("%H:%M:%S") + " " + decision.get("intent", "")
    if not busy:
        _STATE["defer_count"] = 0

    if decision["action"] == "defer" and not decision["bubbles"]:
        if busy and _STATE["defer_count"] < _MAX_DEFER:
            _STATE["defer_count"] += 1
            intent = decision.get("intent") or "稍后再回"
            _plan(client, session_id, batch_id, "wait", intent, wait_seconds=_DEFER_SECONDS)
            _log(f"[暂缓] {busy_text}；做完再回（{intent}）")
            return
        if busy:
            _log(f"[静默] 已暂缓 {_MAX_DEFER} 次仍未腾出空，先不回")
            _plan(client, session_id, batch_id, "silence", "一直没空，本轮不接话")
            _STATE["silenced"] += 1
            return
        # 其实不忙，只是模型想拖 → 当作不接话
        _STATE["defer_count"] = 0

    ok, reason = _budget_ok(cfg)
    if decision["action"] != "reply" or not decision["bubbles"] or not ok:
        if not ok and decision["action"] == "reply":
            _log(f"[静默] {reason}（本想接 id={decision['target_event_id']}）")
        else:
            _log(f"[静默] {decision.get('intent') or '不接话'}")
        _plan(client, session_id, batch_id, "silence", decision.get("intent") or "本轮不接话")
        _STATE["silenced"] += 1
        return

    plan = _plan(client, session_id, batch_id, "reply",
                 decision.get("intent") or "接一句",
                 decision["target_event_id"], decision["topic_event_ids"])
    plan_id = _plan_id(plan)
    if not plan_id:
        detail = " ".join(str(plan.get(k) or "") for k in ("state", "error_code", "note"))
        _log(f"[计划] 未拿到 READY 计划：{detail.strip() or '无状态'}")
        return

    bubbles = [{"kind": "text", "text": text} for text in decision["bubbles"]]
    receipt = _call(client, "send_chat_reply", {
        "session_id": session_id,
        "plan_id": plan_id,
        "idempotency_key": f"humanaize-qq-{int(time.time() * 1000)}",
        "expression_ids": [],
        "bubbles": bubbles,
    })
    with _LOCK:
        _STATE["sent"] += 1
        _STATE["last_reply_at"] = time.time()
        _STATE["reply_times"].append(time.time())
    text = " / ".join(b["text"] for b in bubbles)
    _log(f"[发言] {text}")
    statuses = []
    for item in (receipt.get("bubbles") or receipt.get("results") or []):
        if isinstance(item, dict):
            statuses.append(str(item.get("state") or (item.get("receipt") or {}).get("state") or ""))
    overall = str(receipt.get("state") or "")
    if (overall and overall not in ("SUCCEEDED", "NOOP")) or \
            any(s not in ("SUCCEEDED", "NOOP") for s in statuses):
        _log(f"[回执] {overall or ' / '.join(statuses)} {receipt.get('reason') or ''}".strip())


# ---------------------------------------------------------------------------
# 托管看护：SnowLuma 掉线时把链路拉回来
# ---------------------------------------------------------------------------

def _desktop_get(url):
    import requests
    resp = requests.get(url.rstrip("/") + "/api/desktop/snowluma/managed",
                        headers={"X-ChatWeave-UI": "1"}, timeout=8)
    return resp.json()


def _desktop_retry(url):
    import requests
    resp = requests.post(url.rstrip("/") + "/api/desktop/snowluma/managed/retry",
                         headers={"X-ChatWeave-UI": "1", "Content-Type": "application/json"},
                         json={}, timeout=20)
    return resp.json()


def _watchdog(stop, cfg):
    api = str(cfg.get("desktop_api") or "")
    if not api:
        return
    while not stop.is_set():
        try:
            status = _desktop_get(api)
            phase = str(status.get("phase") or "")
            _STATE["watchdog_note"] = f"{phase} {status.get('code') or ''}".strip()
            if phase in ("error", "stopped", "cancelled", "revoked"):
                now = time.time()
                if now - _STATE["last_retry_at"] > 90:
                    _STATE["last_retry_at"] = now
                    _log(f"[托管] {phase}/{status.get('code')}，重试接入")
                    _desktop_retry(api)
                _drop_session()
            elif phase == "ready" and _STATE["watchdog_note"]:
                _STATE["watchdog_note"] = "ready"
        except Exception as exc:
            _STATE["watchdog_note"] = f"桌面接口不可用：{type(exc).__name__}"
        stop.wait(25)


# ---------------------------------------------------------------------------
# 循环
# ---------------------------------------------------------------------------

def _loop(stop, cfg):
    backoff = 5
    while not stop.is_set():
        client = None
        try:
            client = _client(cfg)
            session_id = _STATE["session_id"] or _open_session(client, cfg)
            res = _wait(client, cfg, session_id, _STATE["ack"])
            event = str(res.get("event") or "")
            _STATE["prompt_version"] = str(
                (res.get("chat_guidance") or {}).get("prompt_version") or _STATE["prompt_version"])

            if event == "learning_ready":
                _decline_learning(client, session_id)
                continue
            if event == "stopped":
                _log("[会话] 已被停止，重新开始")
                _drop_session()
                stop.wait(3)
                continue

            read_through = res.get("read_through_id")
            if isinstance(read_through, int) and read_through:
                _STATE["ack"] = read_through

            batch = res.get("input_batch") or {}
            if res.get("decision_required") and _batch_ids(batch):
                _handle_batch(client, cfg, res, batch)
            else:
                stop.wait(2.5)  # 空等时别把 MCP 打太频
            backoff = 5
        except TulpaError as exc:
            _STATE["last_error"] = f"{exc}（{exc.code}）"
            _log("[错误] " + _STATE["last_error"])
            if exc.code in ("chat_stopped", "session_not_found", "invalid_arguments") \
                    or "停止" in str(exc):
                _drop_session()
            if "频繁" in str(exc):
                stop.wait(8)
            stop.wait(backoff)
            backoff = min(backoff * 2, 90)
        except Exception as exc:
            _STATE["last_error"] = f"{type(exc).__name__}: {exc}"
            _log("[异常] " + _STATE["last_error"])
            with _LOCK:
                _STATE["client"] = None
            if "session" in str(exc).lower() or "会话" in str(exc):
                _drop_session()
            stop.wait(backoff)
            backoff = min(backoff * 2, 90)


def _start(cfg, reason=""):
    with _LOCK:
        if _STATE["thread"] and _STATE["thread"].is_alive():
            return False, "驱动循环已经在运行"
    if not _acquire_lock():
        return False, "另一个进程正在运行群聊驱动（见 state/loop.pid）"
    stop = threading.Event()
    with _LOCK:
        _STATE["stop"] = stop
        thread = threading.Thread(target=_loop, args=(stop, cfg), daemon=True, name="qq-group-loop")
        _STATE["thread"] = thread
        _STATE["log"] = []
    thread.start()
    if cfg.get("watchdog"):
        watchdog = threading.Thread(target=_watchdog, args=(stop, cfg), daemon=True,
                                    name="qq-group-watchdog")
        _STATE["watchdog_thread"] = watchdog
        watchdog.start()
    _log(f"[启动] {reason or '手动'}，群 {cfg.get('conversation_name') or cfg.get('conversation_id')}")
    return True, "已启动"


def _stop(cfg):
    with _LOCK:
        stop = _STATE.get("stop")
        thread = _STATE.get("thread")
        session_id = _STATE["session_id"]
        client = _STATE.get("client")
    if stop:
        stop.set()
    if thread:
        thread.join(timeout=10)
    if session_id and client:
        try:
            _call(client, "stop_chat_session", {"session_id": session_id})
        except Exception as exc:
            _log(f"[停止] 会话停止失败：{exc}")
    _drop_session()
    _release_lock()
    _log("[停止] 驱动循环已结束")
    return True, "已停止"


def _status(cfg):
    running = bool(_STATE["thread"] and _STATE["thread"].is_alive())
    with _LOCK:
        replies = len([t for t in _STATE["reply_times"] if time.time() - t < 3600])
        payload = {
            "success": True,
            "running": running,
            "session_id": _STATE["session_id"],
            "group": cfg.get("conversation_name") or cfg.get("conversation_id"),
            "persona_mode": cfg.get("persona_mode"),
            "participation": cfg.get("participation"),
            "limits": {
                "min_reply_seconds": cfg.get("min_reply_seconds"),
                "max_replies_per_hour": cfg.get("max_replies_per_hour"),
                "quiet_hours": cfg.get("quiet_hours"),
                "replies_last_hour": replies,
            },
            "counters": {
                "rounds": _STATE["rounds"],
                "sent": _STATE["sent"],
                "silenced": _STATE["silenced"],
            },
            "watchdog": _STATE["watchdog_note"],
            "last_activity": _STATE["last_activity"],
            "last_error": _STATE["last_error"],
            "log": _STATE["log"][-12:],
        }
    payload["output"] = (f"群聊驱动{'运行中' if running else '未运行'}；"
                         f"本轮已发 {_STATE['sent']} 条、静默 {_STATE['silenced']} 次")
    return payload


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def execute(input_data):
    cfg = _load_config()
    data = input_data if isinstance(input_data, dict) else {"command": str(input_data or "")}
    action = str(data.get("action") or data.get("command") or "status").strip().lower()

    try:
        if action in ("status", "state", "info"):
            return _status(cfg)
        if action in ("start", "run", "resume"):
            ok, message = _start(cfg, "手动启动")
            return {"success": ok, "output": message}
        if action in ("stop", "pause"):
            ok, message = _stop(cfg)
            return {"success": ok, "output": message}
        if action in ("set", "config", "update"):
            changed = {}
            for key in _SET_KEYS:
                if key in data:
                    cfg[key] = data[key]
                    changed[key] = data[key]
            if changed:
                _save_config(cfg)
            return {"success": True, "changed": changed,
                    "output": f"已更新 {', '.join(changed) or '无字段'}；改动在下次启动时生效"}
    except Exception as exc:
        return {"success": False, "error": str(exc), "output": f"QQ 群聊技能执行失败：{exc}"}

    return {"success": False, "output": "未知动作，可用 status / start / stop / set"}


def _autostart():
    time.sleep(15)
    cfg = _load_config()
    if not cfg.get("enabled"):
        return
    try:
        _start(cfg, "服务启动自动运行")
    except Exception:
        pass


threading.Thread(target=_autostart, daemon=True, name="qq-group-autostart").start()
