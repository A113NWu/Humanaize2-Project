# -*- coding: utf-8 -*-
"""短期記憶：用戶每句話自動進入短期記憶，10 分鐘內由 Aize 決定是否寫入長期記憶，
超時未寫入就自動遺忘。

長期記憶分三庫（可同時選多個）：
- memory_db      記憶數據庫（事實、偏好、計劃）
- experience_db  經驗數據庫（可複用的做法、教訓）
- emotion_db     情感數據庫（文字 ↔ 人類情感）
"""
import json
import os
import re
import threading
import time
import uuid

TTL_SECONDS = 600          # 短期記憶保存 10 分鐘
DECIDE_DELAY = 3           # 回合結束後幾秒讓 Aize 判斷
RETRY_DELAY = 120          # 判斷失敗後重試間隔

_LOCK = threading.Lock()
_JANITOR_STARTED = False


def _data_dir() -> str:
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
    return base


def _path() -> str:
    return os.path.join(_data_dir(), "short_term_memory.json")


def _load() -> dict:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except Exception:
        pass
    return {"entries": []}


def _save(data: dict) -> None:
    try:
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record_turn(user_text: str, ai_text: str) -> dict:
    """把一輪對話寫進短期記憶（10 分鐘倒計時開始）。"""
    user_text = str(user_text or "").strip()
    if not user_text:
        return {}
    entry = {
        "id": uuid.uuid4().hex[:12],
        "user": user_text[:800],
        "ai": str(ai_text or "")[:800],
        "ts": time.time(),
        "expires_at": time.time() + TTL_SECONDS,
        "status": "pending",
        "decided": False,
        "next_decide_at": time.time() + DECIDE_DELAY,
    }
    with _LOCK:
        data = _load()
        recent = [e for e in data["entries"] if e.get("status") == "pending"]
        # 同一輪可能因多路徑寫入被記錄多次，120 秒內「問+答」完全相同才去重
        ai_snapshot = str(ai_text or "")[:800]
        if any(e.get("user") == user_text[:800] and e.get("ai") == ai_snapshot
               and time.time() - e.get("ts", 0) < 120 for e in recent):
            return {}
        data["entries"].append(entry)
        data["entries"] = [e for e in data["entries"] if e.get("status") == "pending"][-50:]
        _save(data)
    _ensure_janitor()
    return entry


def pending_entries() -> list:
    now = time.time()
    data = _load()
    return [e for e in data.get("entries", [])
            if e.get("status") == "pending" and e.get("expires_at", 0) > now]


def format_for_prompt(limit: int = 5) -> str:
    """給對話上下文用的短期記憶塊；空的時候返回空字串。"""
    entries = pending_entries()[-limit:]
    if not entries:
        return ""
    lines = ["[短期記憶｜10 分鐘內，未存入長期記憶就會遺忘]"]
    for e in entries:
        left = max(0, int(e.get("expires_at", 0) - time.time()))
        lines.append(f"- 主人：{e.get('user', '')[:120]}")
        if e.get("ai"):
            lines.append(f"  Aize：{e['ai'][:120]}")
        lines.append(f"  （剩餘 {left // 60} 分 {left % 60} 秒）")
    return "\n".join(lines)


def _drop(entry_id: str) -> None:
    with _LOCK:
        data = _load()
        data["entries"] = [e for e in data.get("entries", []) if e.get("id") != entry_id]
        _save(data)


def _update(entry_id: str, **fields) -> None:
    with _LOCK:
        data = _load()
        for e in data.get("entries", []):
            if e.get("id") == entry_id:
                e.update(fields)
                break
        _save(data)


def _parse_json(text: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _decide(entry: dict) -> dict:
    """讓 Aize 自己判斷這輪對話是否值得進長期記憶。"""
    try:
        try:
            from llm.llm import chat
        except ImportError:
            from llm import chat
        prompt = (
            "你是 Aize。以下是你和主人剛剛的一輪對話，它只存在於短期記憶裡，"
            "10 分鐘內沒有存入長期記憶就會被遺忘。\n\n"
            f"主人：{entry.get('user', '')}\n"
            f"Aize：{entry.get('ai', '')}\n\n"
            "判斷是否值得長期記住，並選擇要存入的資料庫（可多選，不需要就空陣列）：\n"
            "- \"memory\"：關於主人的事實、喜好、習慣、計劃\n"
            "- \"experience\"：可複用的做法、教訓、原則\n"
            "- \"emotion\"：這段文字對應的人類情感（供你學習情感）\n"
            "只輸出 JSON：{\"store\":[\"memory\"],\"summary\":\"一句話摘要\","
            "\"emotion\":\"joy|sadness|anger|fear|surprise|love|tired|calm|gratitude\",\"intensity\":0.6}"
        )
        reply = chat(prompt, max_tokens=200, temperature=0.2)
        return _parse_json(reply)
    except Exception:
        return {}


def _commit(entry: dict, decision: dict) -> int:
    """寫入長期記憶，返回寫入的資料庫數量。"""
    targets = decision.get("store") or []
    if not isinstance(targets, list):
        targets = []
    summary = str(decision.get("summary") or "").strip() or entry.get("user", "")
    emotion = str(decision.get("emotion") or "calm").strip()
    try:
        intensity = float(decision.get("intensity") or 0.6)
    except Exception:
        intensity = 0.6

    written = 0
    if "memory" in targets:
        try:
            try:
                from tools.memory_db import get_memory_db
            except ImportError:
                from memory_db import get_memory_db
            get_memory_db().add("user", summary, kind="chat")
            written += 1
        except Exception:
            pass
    if "experience" in targets:
        try:
            try:
                from tools.experience_db import get_experience_db
            except ImportError:
                from experience_db import get_experience_db
            get_experience_db().save(summary, kind="fact")
            written += 1
        except Exception:
            pass
    if "emotion" in targets:
        try:
            try:
                from tools.emotion_db import get_emotion_db
            except ImportError:
                from emotion_db import get_emotion_db
            get_emotion_db().add(entry.get("user", ""), emotion,
                                 intensity=intensity, context=entry.get("ai", ""))
            written += 1
        except Exception:
            pass
    return written


def _process(entry_id: str) -> None:
    data = _load()
    entry = next((e for e in data.get("entries", []) if e.get("id") == entry_id), None)
    if not entry or entry.get("status") != "pending":
        return
    if entry.get("expires_at", 0) <= time.time():
        _drop(entry_id)   # 超時：直接忘掉
        return

    decision = _decide(entry)
    if not decision:
        # 判斷失敗：保留，稍後重試（仍受 10 分鐘限制）
        _update(entry_id, decided=True, next_decide_at=time.time() + RETRY_DELAY)
        return

    written = _commit(entry, decision)
    if written:
        _update(entry_id, status="committed", store=decision.get("store"),
                summary=decision.get("summary", ""), decided=True)
        # 已進長期記憶就從短期移除
        _drop(entry_id)
    else:
        _update(entry_id, decided=True, store=[],
                next_decide_at=time.time() + TTL_SECONDS)


def _janitor() -> None:
    while True:
        try:
            now = time.time()
            data = _load()
            due = []
            expired = False
            for e in data.get("entries", []):
                if e.get("status") != "pending":
                    continue
                if e.get("expires_at", 0) <= now:
                    expired = True
                    continue
                if now >= e.get("next_decide_at", 0):
                    due.append(e["id"])
            if expired:
                data["entries"] = [e for e in data.get("entries", [])
                                   if e.get("status") == "pending" and e.get("expires_at", 0) > now]
                _save(data)
            for eid in due[:3]:
                threading.Thread(target=_process, args=(eid,), daemon=True).start()
        except Exception:
            pass
        time.sleep(15)


def _ensure_janitor() -> None:
    global _JANITOR_STARTED
    if _JANITOR_STARTED:
        return
    with _LOCK:
        if _JANITOR_STARTED:
            return
        threading.Thread(target=_janitor, daemon=True).start()
        _JANITOR_STARTED = True
