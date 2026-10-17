"""
記憶向量數據庫

Aize 的長期記憶不再整段疊進上下文，而是逐條向量化存進這個庫；
需要回憶時才用當前問題檢索相關記憶注入提示詞。
人格記憶與 Skill 提示詞不走這裡——那些屬於常駐記憶，由人格數據庫管理。

向量化復用 experience_db 的哈希 n-gram 方案（無外部依賴、跨進程一致）。
"""

import os
import json
import time
import threading

from .experience_db import _vectorize, _cosine

_MAX_ENTRIES = 2000
_SEARCH_MIN_SCORE = 0.22
_MIN_CONTENT_LEN = 4      # 過短內容（嗯/好/ok）不值得進記憶庫


def _is_machine_content(content):
    """技能調用/命令回執等機器消息不進記憶庫（與 thinking_engine 的過濾一致）。"""
    c = str(content or "")
    return ('{"skill"' in c or "'skill'" in c or
            c.startswith("[Command executed") or
            c.startswith("Command output:") or
            c.startswith("[Skill]"))


class MemoryDB:
    def __init__(self, path=None):
        self._lock = threading.Lock()
        self.path = path or self._default_path()
        self.entries = []
        self._next_id = 1
        self._load()

    @staticmethod
    def _default_path():
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
        return os.path.join(base, "memory_db.json")

    # ---------- 持久化 ----------

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = data.get("entries", [])
            self._next_id = int(data.get("next_id", len(self.entries) + 1))
        except Exception:
            self.entries, self._next_id = [], 1

    def _save_file(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"next_id": self._next_id, "entries": self.entries},
                          f, ensure_ascii=False)
        except Exception:
            pass

    # ---------- 寫入 ----------

    def add(self, role, content, kind="chat", timestamp=None):
        """索引一條記憶。機器消息/過短內容直接跳過。"""
        content = str(content or "").strip()
        if len(content) < _MIN_CONTENT_LEN or _is_machine_content(content):
            return {"success": False, "error": "skipped"}
        vec = _vectorize(content)
        if not vec:
            return {"success": False, "error": "empty vector"}
        entry = {
            "id": self._next_id,
            "role": str(role or "user"),
            "kind": str(kind or "chat"),
            "content": content,
            "time": timestamp or time.strftime("%Y-%m-%d %H:%M:%S"),
            "vec": vec,
        }
        with self._lock:
            self._next_id += 1
            self.entries.append(entry)
            if len(self.entries) > _MAX_ENTRIES:
                del self.entries[:len(self.entries) - _MAX_ENTRIES]
            self._save_file()
        return {"success": True, "id": entry["id"]}

    # ---------- 檢索 ----------

    def search(self, query, top_k=5, min_score=_SEARCH_MIN_SCORE):
        vec = _vectorize(query)
        if not vec:
            return []
        with self._lock:
            scored = []
            for e in self.entries:
                s = _cosine(vec, e.get("vec") or {})
                if s >= min_score:
                    scored.append((s, e))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [{"id": e["id"], "role": e.get("role"), "kind": e.get("kind"),
                     "content": e.get("content"), "time": e.get("time"),
                     "score": round(s, 3)} for s, e in scored[:top_k]]

    def format_for_prompt(self, query, top_k=5):
        """返回可直接注入提示詞的記憶行；無命中返回空字串。"""
        hits = self.search(query, top_k=top_k)
        if not hits:
            return ""
        return "\n".join(f"{h['role']}: {h['content']}" for h in hits)

    def list_all(self, limit=50):
        with self._lock:
            items = self.entries[-limit:]
            return [{"id": e["id"], "role": e.get("role"), "kind": e.get("kind"),
                     "content": e.get("content"), "time": e.get("time")}
                    for e in reversed(items)]

    def forget(self, entry_id):
        try:
            entry_id = int(entry_id)
        except (TypeError, ValueError):
            return {"success": False, "error": "invalid id"}
        with self._lock:
            before = len(self.entries)
            self.entries = [e for e in self.entries if e.get("id") != entry_id]
            if len(self.entries) == before:
                return {"success": False, "error": f"id {entry_id} not found"}
            self._save_file()
            return {"success": True, "id": entry_id}

    # ---------- 遷移 ----------

    def backfill_from_memory(self, messages):
        """把舊 JSON 記憶一次性灌進向量庫（只用於升級遷移）。"""
        count = 0
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            r = self.add(m.get("role", "user"), m.get("content", ""),
                         timestamp=m.get("time"))
            if r.get("success"):
                count += 1
        return count


_instance = None
_instance_lock = threading.Lock()


def get_memory_db():
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MemoryDB()
    return _instance
