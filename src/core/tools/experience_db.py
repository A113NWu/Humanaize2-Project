"""
經驗數據庫（輕量本地向量庫）

Aize 在溝通中主動把「思考方式、判斷策略、見聞」存進來，側重思考方式。
向量化用哈希 n-gram（md5 穩定哈希，無外部依賴、跨進程一致）+ 餘弦相似度。
新經驗與庫中某條足夠相似時直接覆蓋舊經驗（保留 id、強度 +1），
保證庫裡沉澱的永遠是最新的思考方式。
"""

import os
import re
import json
import time
import math
import hashlib
import threading

_DIM = 512
_OVERWRITE_THRESHOLD = 0.72   # 相似度 >= 此值視為同一條經驗，新覆蓋舊
_SEARCH_MIN_SCORE = 0.25      # 低於此相似度不檢索
_MAX_ENTRIES = 500

_KIND_LABELS = {"thinking": "思考方式", "observation": "見聞", "fact": "事實"}


def _normalize(text):
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(text or "").lower())


def _vectorize(text):
    """字符 uni/bi/tri-gram 哈希到固定維度的稀疏向量，L2 歸一化。"""
    t = _normalize(text)
    vec = {}
    if not t:
        return vec
    grams = list(t)
    grams += [t[i:i + 2] for i in range(len(t) - 1)]
    grams += [t[i:i + 3] for i in range(len(t) - 2)]
    for g in grams:
        h = int.from_bytes(hashlib.md5(g.encode("utf-8")).digest()[:4], "little") % _DIM
        vec[h] = vec.get(h, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {str(k): v / norm for k, v in vec.items()}


def _cosine(a, b):
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


class ExperienceDB:
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
        return os.path.join(base, "experience_db.json")

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

    # ---------- 寫入（相似即覆蓋） ----------

    def save(self, text, kind="thinking", tags=None):
        text = str(text or "").strip()
        if not text:
            return {"success": False, "error": "empty text"}
        kind = kind if kind in _KIND_LABELS else "thinking"
        vec = _vectorize(text)
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            best, best_score = None, 0.0
            for e in self.entries:
                s = _cosine(vec, e.get("vec") or {})
                if s > best_score:
                    best, best_score = e, s

            if best is not None and best_score >= _OVERWRITE_THRESHOLD:
                best["text"] = text
                best["kind"] = kind
                best["tags"] = sorted(set(best.get("tags") or []) | set(tags or []))
                best["vec"] = vec
                best["updated_at"] = now
                best["strength"] = min(int(best.get("strength", 1)) + 1, 9)
                self._save_file()
                return {"success": True, "action": "overwritten",
                        "id": best["id"], "similarity": round(best_score, 3)}

            entry = {"id": self._next_id, "kind": kind, "text": text,
                     "tags": list(tags or []), "vec": vec,
                     "created_at": now, "updated_at": now, "strength": 1}
            self._next_id += 1
            self.entries.append(entry)
            self._evict_if_needed()
            self._save_file()
            return {"success": True, "action": "created",
                    "id": entry["id"], "similarity": round(best_score, 3)}

    def _evict_if_needed(self):
        if len(self.entries) <= _MAX_ENTRIES:
            return

        def score(e):
            recency = 0.0
            try:
                ts = time.mktime(time.strptime(e.get("updated_at", "2000-01-01 00:00:00"),
                                               "%Y-%m-%d %H:%M:%S"))
                recency = max(0.0, 30.0 - (time.time() - ts) / 86400.0) / 30.0
            except Exception:
                pass
            return float(e.get("strength", 1)) + recency

        self.entries.sort(key=score, reverse=True)
        del self.entries[_MAX_ENTRIES - (_MAX_ENTRIES // 10):]

    # ---------- 檢索 ----------

    def search(self, query, top_k=3, min_score=_SEARCH_MIN_SCORE, kinds=None):
        vec = _vectorize(query)
        if not vec:
            return []
        with self._lock:
            scored = []
            for e in self.entries:
                if kinds and e.get("kind") not in kinds:
                    continue
                s = _cosine(vec, e.get("vec") or {})
                if s >= min_score:
                    scored.append((s, e))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [{"id": e["id"], "kind": e.get("kind"), "text": e.get("text"),
                     "tags": e.get("tags") or [], "score": round(s, 3)}
                    for s, e in scored[:top_k]]

    def format_for_prompt(self, query, top_k=3):
        hits = self.search(query, top_k=top_k)
        if not hits:
            return ""
        return "\n".join(
            f"- （{_KIND_LABELS.get(h['kind'], h['kind'])}）{h['text']}" for h in hits)

    def list_all(self, limit=50):
        with self._lock:
            items = sorted(self.entries, key=lambda e: e.get("updated_at", ""), reverse=True)
            return [{"id": e["id"], "kind": e.get("kind"), "text": e.get("text"),
                     "tags": e.get("tags") or [], "strength": e.get("strength", 1),
                     "updated_at": e.get("updated_at", "")} for e in items[:limit]]

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
            return {"success": True, "action": "forgotten", "id": entry_id}


_instance = None
_instance_lock = threading.Lock()


def get_experience_db():
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ExperienceDB()
    return _instance
