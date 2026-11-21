"""社交通知收件匣（進程內共享）。

後台監聽器（Misskey 等）收到新消息時只負責 push 進來，不再自己決定回不回；
閒置思考 / 對話流程把待處理的消息取出來注入提示詞，由 Aize 自己猶豫、
掂量要不要回應。帶 TTL，過期消息不會一直被提起。
"""

import threading
import time

_TTL_SECONDS = 6 * 3600
_MAX_ITEMS = 20

_lock = threading.Lock()
_items = []  # [{"platform","kind","note_id","user","text","ts"}]


def _prune_locked():
    cutoff = time.time() - _TTL_SECONDS
    _items[:] = [it for it in _items if float(it.get("ts") or 0) >= cutoff]
    if len(_items) > _MAX_ITEMS:
        del _items[:len(_items) - _MAX_ITEMS]


def push(platform, kind, note_id, user, text, ttl_seconds=None):
    """放入一條新消息；同平台同 note_id 不重複。返回是否真的新增。"""
    note_id = str(note_id or "").strip()
    if not note_id:
        return False
    platform = str(platform or "misskey").strip() or "misskey"
    with _lock:
        _prune_locked()
        for it in _items:
            if it.get("platform") == platform and str(it.get("note_id")) == note_id:
                return False
        _items.append({
            "platform": platform,
            "kind": str(kind or "").strip() or "消息",
            "note_id": note_id,
            "user": str(user or "").strip() or "?",
            "text": str(text or "").strip(),
            "ts": time.time(),
        })
        _prune_locked()
    return True


def peek(limit=8):
    """看一眼待處理消息，不移除。"""
    with _lock:
        _prune_locked()
        return [dict(it) for it in _items[-limit:]]


def drain(limit=8):
    """取出待處理消息並從收件匣移除（消息已進入提示詞，不再重複提醒）。"""
    with _lock:
        _prune_locked()
        limit = max(1, int(limit or 1))
        taken = [dict(it) for it in _items[-limit:]]
        if taken:
            del _items[-limit:]
        return taken


def clear(items):
    """按 (platform, note_id) 移除指定消息（Aize 已經在思考裡掂量過）。"""
    ids = {(str(it.get("platform")), str(it.get("note_id"))) for it in (items or [])}
    if not ids:
        return
    with _lock:
        _items[:] = [it for it in _items
                     if (str(it.get("platform")), str(it.get("note_id"))) not in ids]


def format_block(items):
    """把待處理消息渲染成提示詞段落；沒有消息時返回空串。"""
    items = list(items or [])
    if not items:
        return ""
    lines = []
    for it in items:
        label = {"misskey": "Misskey"}.get(str(it.get("platform")), str(it.get("platform")))
        lines.append(f"- [{label}｜{it.get('kind')}｜note_id={it.get('note_id')}] "
                     f"@{it.get('user')}：{str(it.get('text') or '')[:200]}")
    return ("【社交平台的新消息】\n" + "\n".join(lines) +
            "\n這些是剛收到、還沒處理的消息。先自己掂量一下要不要回應："
            "想回就用 misskey-bot 技能回應，input 是 "
            '{"action":"reply","params":{"reply_id":"上面的 note_id","text":"回复内容"}}；'
            "只想點表情就用 "
            '{"action":"react","params":{"note_id":"上面的 note_id","reaction":"👍"}}；'
            "不想回就忽略，不用為了禮貌勉強自己，也不用向主人匯報。")
