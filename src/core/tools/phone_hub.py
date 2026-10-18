"""
手機命令中樞（進程內單例）

PC 端 Aize（phone-shell 技能）把 shell 命令推進來，
安卓客戶端輪詢取走、用 Shizuku 執行後把結果 POST 回來：
  push_command(command, timeout)  → id
  poll_commands(since_id)         → 手機端拉取待執行命令
  post_result(id, result)         → 手機端回傳執行結果
  wait_result(id, timeout)        → 技能端阻塞等結果
"""

import time
import threading
from collections import deque

_MAX_BUFFER = 100
# 手機輪詢間隔約 3~5 秒，超過這個時間沒來輪詢就視為離線
_ONLINE_WINDOW_SEC = 20
# 結果保留時間，避免內存洩漏
_RESULT_TTL_SEC = 300


class PhoneHub:
    def __init__(self):
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._commands = deque(maxlen=_MAX_BUFFER)
        self._results = {}  # id -> (ts, result dict)
        self._next_id = 1
        self.started_at = time.time()
        self.last_poll_at = 0.0
        self.device_name = ""

    # ---------- 命令（PC → 手機） ----------

    def push_command(self, command, timeout_sec=30, work_dir=None):
        command = str(command or "").strip()
        if not command:
            return None
        with self._cond:
            cmd = {
                "id": self._next_id,
                "ts": time.time(),
                "type": "shell",
                "command": command,
                "timeout": int(timeout_sec or 30),
            }
            if work_dir:
                cmd["work_dir"] = str(work_dir)
            self._next_id += 1
            self._commands.append(cmd)
            return cmd["id"]

    def poll_commands(self, since_id=0, device_name=""):
        try:
            since_id = int(since_id or 0)
        except (TypeError, ValueError):
            since_id = 0
        with self._lock:
            self.last_poll_at = time.time()
            if device_name:
                self.device_name = str(device_name)[:64]
            return [c for c in self._commands if c.get("id", 0) > since_id]

    # ---------- 結果（手機 → PC） ----------

    def post_result(self, cmd_id, result):
        try:
            cmd_id = int(cmd_id)
        except (TypeError, ValueError):
            return False
        if not isinstance(result, dict):
            return False
        with self._cond:
            self._results[cmd_id] = (time.time(), dict(result))
            self._gc_results_locked()
            self._cond.notify_all()
            return True

    def wait_result(self, cmd_id, timeout_sec=None):
        """技能端阻塞等結果；超時返回 None。"""
        deadline = time.time() + float(timeout_sec or 60)
        with self._cond:
            while True:
                entry = self._results.get(cmd_id)
                if entry is not None:
                    return entry[1]
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._cond.wait(timeout=min(remaining, 1.0))

    def _gc_results_locked(self):
        now = time.time()
        expired = [k for k, (ts, _) in self._results.items()
                   if now - ts > _RESULT_TTL_SEC]
        for k in expired:
            self._results.pop(k, None)

    # ---------- 狀態 ----------

    def status(self):
        with self._lock:
            online = self.last_poll_at and (time.time() - self.last_poll_at) < _ONLINE_WINDOW_SEC
            return {
                "online": bool(online),
                "device_name": self.device_name,
                "last_poll_seconds_ago": int(time.time() - self.last_poll_at) if self.last_poll_at else None,
                "buffered_commands": len(self._commands),
                "pending_results": len(self._results),
            }


_instance = None
_instance_lock = threading.Lock()


def get_phone_hub():
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PhoneHub()
    return _instance
