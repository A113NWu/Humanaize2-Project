from datetime import datetime, timedelta
import threading
import time
from typing import Optional


def check_silence_and_decide(memory, threshold_seconds=60):
    """
    如果使用者長時間未回覆，則返回一個更智慧的自主思考建議，而不是直接問候。
    """
    if not memory.get("messages"):
        return None

    last_user = None
    for msg in reversed(memory["messages"]):
        if msg.get("role") == "user":
            last_user = msg
            break

    if last_user is None:
        return None

    try:
        last_time = datetime.fromisoformat(last_user.get("time"))
    except Exception:
        return None

    now = datetime.now()
    if (now - last_time) > timedelta(seconds=threshold_seconds):
        return {
            "action": "AUTO_THINK",
            "message": "Conversation paused. The AI is reviewing context and considering the next action.",
            "confidence": 0.9
        }
    return None


class AutonomousEngine:
    def __init__(self, memory, callback=None, interval_seconds=60, auto_break_silence=True):
        self.memory = memory
        self.callback = callback
        self.interval_seconds = interval_seconds
        self.auto_break_silence = auto_break_silence
        self.running = False
        self._thread = None
        self._last_user_time = None

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def on_user_message(self):
        self._last_user_time = datetime.now()

    def _run(self):
        while self.running:
            try:
                if not self.auto_break_silence:
                    time.sleep(self.interval_seconds)
                    continue

                decision = check_silence_and_decide(self.memory)
                if decision and self.callback:
                    self.callback({"type": "autonomous_decision", "decision": decision})
            except Exception:
                pass
            time.sleep(self.interval_seconds)
