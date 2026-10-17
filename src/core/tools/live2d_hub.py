"""
Live2D 命令中樞（進程內單例）

Aize（經 live2d 技能）或 API 把命令推進來，Live2D 網頁輪詢取走執行：
  speak      {type:"speak", text}        讓模型說話（TTS + 唇形）
  motion     {type:"motion", group, index?} 播放動作組
  expression {type:"expression", name}   切換表情
  chat_in    {type:"chat_in", source, user, text} 外部聊天（彈幕/會議）進來，
             網頁收到後會轉 POST /api/live2d/chat 形成回復閉環

外部聊天源（彈幕插件等）調 ingest_chat() 即可，無需了解網頁細節。
"""

import time
import threading
from collections import deque

_MAX_BUFFER = 200


class Live2DHub:
    def __init__(self):
        self._lock = threading.Lock()
        self._commands = deque(maxlen=_MAX_BUFFER)
        self._next_id = 1
        self.started_at = time.time()

    # ---------- 命令 ----------

    def push_command(self, cmd):
        if not isinstance(cmd, dict) or not cmd.get("type"):
            return None
        with self._lock:
            cmd = dict(cmd)
            cmd["id"] = self._next_id
            cmd["ts"] = time.time()
            self._next_id += 1
            self._commands.append(cmd)
            return cmd["id"]

    def poll_commands(self, since_id=0):
        try:
            since_id = int(since_id or 0)
        except (TypeError, ValueError):
            since_id = 0
        with self._lock:
            return [c for c in self._commands if c.get("id", 0) > since_id]

    # ---------- 外部聊天入口 ----------

    def ingest_chat(self, source, user, text):
        text = str(text or "").strip()
        if not text:
            return None
        return self.push_command({
            "type": "chat_in",
            "source": str(source or "external"),
            "user": str(user or "anon"),
            "text": text,
        })

    # ---------- 狀態 ----------

    def status(self):
        with self._lock:
            return {
                "buffered_commands": len(self._commands),
                "next_id": self._next_id,
                "uptime_seconds": int(time.time() - self.started_at),
            }


_instance = None
_instance_lock = threading.Lock()


def get_live2d_hub():
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = Live2DHub()
    return _instance
