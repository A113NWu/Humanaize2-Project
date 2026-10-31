# -*- coding: utf-8 -*-
"""情感數據庫：記錄「什麼文字對應人類的什麼情感」，供 Aize 學習與回憶。"""
import json
import os
import threading
import time

_MAX_ENTRIES = 500

_EMOTION_LABELS = {
    "joy": "開心/愉快", "sadness": "難過/失落", "anger": "生氣/不滿",
    "fear": "害怕/焦慮", "surprise": "驚訝", "love": "喜歡/依戀",
    "tired": "疲憊/無力", "calm": "平靜/安心", "shame": "羞愧/自責",
    "gratitude": "感謝/感動",
}


def format_emotion(label: str) -> str:
    return _EMOTION_LABELS.get(label, label or "未分類")


class EmotionDB:
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
        return os.path.join(base, "emotion_db.json")

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
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, text: str, emotion: str, intensity: float = 0.6, context: str = "") -> dict:
        text = str(text or "").strip()
        if not text:
            return {"success": False, "error": "empty text"}
        with self._lock:
            entry = {
                "id": self._next_id,
                "text": text[:300],
                "emotion": str(emotion or "calm"),
                "emotion_label": format_emotion(emotion),
                "intensity": max(0.0, min(1.0, float(intensity or 0.6))),
                "context": str(context or "")[:200],
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._next_id += 1
            self.entries.append(entry)
            if len(self.entries) > _MAX_ENTRIES:
                self.entries = self.entries[-_MAX_ENTRIES:]
            self._save_file()
        return {"success": True, "entry": entry}

    def _score(self, entry: dict, query: str) -> float:
        """輕量關鍵詞 / 情感標籤匹配，避免為情感庫引入額外模型開銷。"""
        if not query:
            return 0.0
        q = query.lower()
        text = entry.get("text", "").lower()
        hits = sum(1 for ch in set(q) if ch.strip() and ch in text)
        score = hits / max(1, len(set(q)))
        label = entry.get("emotion", "")
        if label and label in q:
            score += 0.3
        if entry.get("emotion_label", "") and entry["emotion_label"] in query:
            score += 0.2
        return score

    def search(self, query: str, top_k: int = 3) -> list:
        scored = [(self._score(e, query), e) for e in self.entries]
        scored = [s for s in scored if s[0] > 0.15]
        scored.sort(key=lambda x: (x[0], x[1].get("time", "")), reverse=True)
        return [e for _, e in scored[:top_k]]

    def format_for_prompt(self, query: str, top_k: int = 3) -> str:
        found = self.search(query, top_k=top_k)
        if not found:
            return ""
        lines = ["[情感數據庫]"]
        for e in found:
            lines.append(f"- 「{e['text']}」→ {e['emotion_label']}（強度 {e['intensity']:.2f}）")
        return "\n".join(lines)

    def list_all(self, limit: int = 50) -> list:
        return self.entries[-limit:]


_EMOTION_DB = None
_DB_LOCK = threading.Lock()


def get_emotion_db() -> EmotionDB:
    global _EMOTION_DB
    if _EMOTION_DB is None:
        with _DB_LOCK:
            if _EMOTION_DB is None:
                _EMOTION_DB = EmotionDB()
    return _EMOTION_DB
