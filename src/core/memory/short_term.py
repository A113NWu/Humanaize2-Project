# -*- coding: utf-8 -*-
"""短期記憶：按話題保存，直接進上下文。

規則：
- 每輪對話、以及社交平台收到的消息，先寫進短期記憶，下一輪對話立刻能讀到。
- 話題由 Aize 自己判斷：她說換話題就開新話題，否則歸入當前話題。
- 最多保留 10 個話題；出現第 11 個時，最老的那個話題整段忘掉。
- 每條內容 24 小時後遺忘。
- 回合結束 3 秒後由 Aize 判斷是否寫入長期記憶；寫入就從短期移除，
  沒寫入就留著，等 24 小時自然忘記。

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

RETENTION_SECONDS = 24 * 3600   # 短期記憶保留 24 小時
MAX_TOPICS = 10                 # 最多 10 個話題，超過忘掉最老的
DECIDE_DELAY = 3                # 回合結束後幾秒讓 Aize 判斷
RETRY_DELAY = 120               # 判斷失敗後重試間隔

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


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _migrate_legacy(data: dict) -> dict:
    """舊格式（扁平 entries + 10 分鐘窗口）→ 話題結構，只保留還沒過期的。"""
    now = time.time()
    topics = []
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "pending" or entry.get("expires_at", 0) <= now:
            continue
        ts = float(entry.get("ts") or now)
        item = {
            "id": entry.get("id") or _new_id(),
            "source": "chat",
            "speaker": "主人",
            "user": entry.get("user", ""),
            "ai": entry.get("ai", ""),
            "ts": ts,
            "expires_at": ts + RETENTION_SECONDS,
            "status": "pending",
            "decided": False,
            "next_decide_at": now + DECIDE_DELAY,
        }
        if topics and ts - topics[-1]["updated_at"] <= 30 * 60:
            topics[-1]["entries"].append(item)
            topics[-1]["updated_at"] = ts
        else:
            topics.append({"id": _new_id(), "title": "（舊對話）", "created_at": ts,
                           "updated_at": ts, "entries": [item]})
    return {"topics": topics[-MAX_TOPICS:], "last_topic_id": topics[-1]["id"] if topics[-MAX_TOPICS:] else ""}


def _normalize(data) -> dict:
    if not isinstance(data, dict):
        return {"topics": [], "last_topic_id": ""}
    if isinstance(data.get("entries"), list) and not isinstance(data.get("topics"), list):
        return _migrate_legacy(data)
    topics = []
    for topic in data.get("topics") or []:
        if not isinstance(topic, dict):
            continue
        entries = [e for e in (topic.get("entries") or []) if isinstance(e, dict)]
        if not entries:
            continue
        topics.append({
            "id": topic.get("id") or _new_id(),
            "title": str(topic.get("title") or ""),
            "created_at": float(topic.get("created_at") or entries[0].get("ts") or time.time()),
            "updated_at": float(topic.get("updated_at") or entries[-1].get("ts") or time.time()),
            "entries": entries,
        })
    return {"topics": topics, "last_topic_id": str(data.get("last_topic_id") or "")}


def _load() -> dict:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            return _normalize(json.load(f))
    except Exception:
        return {"topics": [], "last_topic_id": ""}


def _save(data: dict) -> None:
    try:
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _find_entry(data: dict, entry_id: str):
    for topic in data.get("topics") or []:
        for entry in topic.get("entries") or []:
            if entry.get("id") == entry_id:
                return topic, entry
    return None, None


def _prune(data: dict, now=None) -> bool:
    """清掉過期內容、空話題，並保證話題數不超過上限。返回是否有改動。"""
    now = now or time.time()
    before = json.dumps(data, sort_keys=True, ensure_ascii=False) if data else ""
    topics = []
    for topic in data.get("topics") or []:
        entries = [e for e in (topic.get("entries") or []) if float(e.get("expires_at") or 0) > now]
        if entries:
            topic["entries"] = entries
            topics.append(topic)
    if len(topics) > MAX_TOPICS:
        topics = topics[-MAX_TOPICS:]   # 話題按時間順序排列，砍掉最老的
    data["topics"] = topics
    if data.get("last_topic_id") not in {t.get("id") for t in topics}:
        data["last_topic_id"] = topics[-1]["id"] if topics else ""
    return json.dumps(data, sort_keys=True, ensure_ascii=False) != before


def _ensure_topic(data: dict, title="") -> dict:
    last_id = data.get("last_topic_id")
    for topic in data.get("topics") or []:
        if topic.get("id") == last_id:
            return topic
    topic = {"id": _new_id(), "title": title, "created_at": time.time(),
             "updated_at": time.time(), "entries": []}
    data.setdefault("topics", []).append(topic)
    data["last_topic_id"] = topic["id"]
    return topic


def record_turn(user_text: str, ai_text: str = "", source: str = "chat", speaker: str = "主人") -> dict:
    """把一輪對話 / 一條收到的消息寫進短期記憶（話題先歸到當前話題）。"""
    user_text = str(user_text or "").strip()
    if not user_text:
        return {}
    now = time.time()
    entry = {
        "id": _new_id(),
        "source": str(source or "chat"),
        "speaker": str(speaker or "主人"),
        "user": user_text[:800],
        "ai": str(ai_text or "")[:800],
        "ts": now,
        "expires_at": now + RETENTION_SECONDS,
        "status": "pending",
        "decided": False,
        "next_decide_at": now + DECIDE_DELAY,
    }
    with _LOCK:
        data = _load()
        topic = _ensure_topic(data)
        # 同一輪可能因多路徑寫入被記錄多次，120 秒內「問+答」完全相同才去重
        ai_snapshot = str(ai_text or "")[:800]
        if any(e.get("speaker") == entry["speaker"] and e.get("user") == user_text[:800]
               and e.get("ai") == ai_snapshot and now - float(e.get("ts") or 0) < 120
               for e in topic.get("entries") or []):
            return {}
        topic["entries"].append(entry)
        topic["updated_at"] = now
        _prune(data, now)
        _save(data)
    _ensure_janitor()
    return entry


def attach_ai(entry_id: str, ai_text: str) -> None:
    """社交消息回了之後，把她說的那句補進同一條短期記憶。"""
    text = str(ai_text or "").strip()
    if not text:
        return
    with _LOCK:
        data = _load()
        _, entry = _find_entry(data, entry_id)
        if entry is not None:
            entry["ai"] = text[:800]
            _save(data)


def pending_entries() -> list:
    """當前還記得的全部短期記憶（按時間順序）。"""
    now = time.time()
    data = _load()
    items = []
    for topic in data.get("topics") or []:
        for entry in topic.get("entries") or []:
            if float(entry.get("expires_at") or 0) > now:
                items.append(entry)
    return items


def format_for_prompt(limit: int = 0, max_chars: int = 2000) -> str:
    """給對話上下文用的短期記憶塊；空的時候返回空字串。"""
    now = time.time()
    data = _load()
    topics = []
    for topic in data.get("topics") or []:
        entries = [e for e in (topic.get("entries") or [])
                   if float(e.get("expires_at") or 0) > now]
        if entries:
            topics.append((topic, entries))
    if not topics:
        return ""

    # 從最新話題往前裝，超出字數就只保留較新的話題（內容仍在檔案裡，等 24h 或話題上限淘汰）
    blocks = []
    used = 0
    for topic, entries in reversed(topics):
        lines = [f"## 話題：{topic.get('title') or '（未命名）'}"]
        for entry in entries:
            lines.append(f"- {entry.get('speaker') or '主人'}：{str(entry.get('user') or '')[:120]}")
            if entry.get("ai"):
                lines.append(f"  Aize：{str(entry['ai'])[:120]}")
        block = "\n".join(lines)
        if used + len(block) > max_chars and blocks:
            break
        blocks.insert(0, block)
        used += len(block)
    return "[短期記憶｜按話題保存，最多 10 個；每條 24 小時後遺忘]\n" + "\n".join(blocks)


def _parse_json(text: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _decide(entry: dict, topic_title: str) -> dict:
    """讓 Aize 自己判斷：這是不是新話題 + 是否值得進長期記憶。"""
    try:
        try:
            from llm.llm import chat
        except ImportError:
            from llm import chat
        speaker = entry.get("speaker") or "主人"
        prompt = (
            "你是 Aize。以下是你剛剛經歷的一輪內容，它只存在短期記憶裡，24 小時後就會忘記。\n"
            f"當前話題：{topic_title or '（還沒命名）'}\n\n"
            f"{speaker}：{entry.get('user', '')}\n"
            + (f"Aize：{entry.get('ai', '')}\n" if entry.get("ai") else "")
            + "\n請判斷兩件事，只輸出一個 JSON：\n"
            "1) same_topic：這輪內容和【當前話題】是不是同一件事；不是就給 topic 一個新的短標題（10 字內）。\n"
            "2) store：是否值得長期記住，選擇要存入的資料庫（可多選，不需要就空陣列）：\n"
            "   - memory：關於對方的事實、喜好、習慣、計劃\n"
            "   - experience：可複用的做法、教訓、原則\n"
            "   - emotion：這段文字對應的人類情感（供你學習情感）\n"
            '{"same_topic": true, "topic": "話題短標題", "store": ["memory"], '
            '"summary": "一句話摘要", "emotion": "joy|sadness|anger|fear|surprise|love|tired|calm|gratitude", "intensity": 0.6}'
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


def _drop(data: dict, entry_id: str) -> None:
    for topic in data.get("topics") or []:
        topic["entries"] = [e for e in (topic.get("entries") or []) if e.get("id") != entry_id]
    data["topics"] = [t for t in (data.get("topics") or []) if t.get("entries")]


def _move_to_new_topic(data: dict, entry: dict, title: str) -> None:
    """這一輪換了話題：把她從舊話題搬到一個新話題裡。"""
    for topic in data.get("topics") or []:
        topic["entries"] = [e for e in (topic.get("entries") or []) if e.get("id") != entry.get("id")]
    data["topics"] = [t for t in (data.get("topics") or []) if t.get("entries")]
    topic = {"id": _new_id(), "title": title or "新話題", "created_at": entry.get("ts") or time.time(),
             "updated_at": entry.get("ts") or time.time(), "entries": [entry]}
    data.setdefault("topics", []).append(topic)
    data["last_topic_id"] = topic["id"]


def _process(entry_id: str) -> None:
    data = _load()
    topic, entry = _find_entry(data, entry_id)
    if entry is None or entry.get("status") != "pending":
        return
    if float(entry.get("expires_at") or 0) <= time.time():
        with _LOCK:
            data = _load()
            _drop(data, entry_id)
            _save(data)
        return

    decision = _decide(entry, topic.get("title") if topic else "")
    if not decision:
        # 判斷失敗：保留，稍後重試（仍受 24 小時限制）
        with _LOCK:
            data = _load()
            _, entry = _find_entry(data, entry_id)
            if entry is not None:
                entry["next_decide_at"] = time.time() + RETRY_DELAY
                _save(data)
        return

    written = _commit(entry, decision)
    with _LOCK:
        data = _load()
        topic, entry = _find_entry(data, entry_id)
        if entry is None:
            return
        # 話題判定：她說換了就搬去新話題；第一次判斷時順手給當前話題起名
        same = decision.get("same_topic", True)
        title = str(decision.get("topic") or "").strip()[:20]
        if same is False:
            _move_to_new_topic(data, entry, title)
        elif topic and title and not topic.get("title"):
            topic["title"] = title
        if written:
            _drop(data, entry_id)
        else:
            entry["status"] = "kept"
            entry["decided"] = True
            entry["store"] = []
        _prune(data)
        _save(data)


def _janitor() -> None:
    while True:
        try:
            now = time.time()
            data = _load()
            due = []
            for topic in data.get("topics") or []:
                for entry in topic.get("entries") or []:
                    if entry.get("status") != "pending":
                        continue
                    if float(entry.get("expires_at") or 0) <= now:
                        continue
                    if now >= float(entry.get("next_decide_at") or 0):
                        due.append(entry["id"])
            changed = _prune(data, now)
            if changed:
                with _LOCK:
                    current = _load()
                    _prune(current, now)
                    _save(current)
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
