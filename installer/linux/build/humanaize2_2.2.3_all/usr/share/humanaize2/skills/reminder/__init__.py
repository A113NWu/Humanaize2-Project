"""
Humanaize Reminder Skill
Set and manage timed reminders
"""

import os
import json
import threading
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta


REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reminders.json")


class ReminderManager:
    """Manages active reminders"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._reminders: List[Dict] = []
        self._callbacks: Dict[str, callable] = {}
        self._monitor_thread = None
        self._running = False
        self._load_reminders()
        self._start_monitor()

    def _load_reminders(self):
        """Load reminders from file"""
        try:
            if os.path.exists(REMINDERS_FILE):
                with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
                    self._reminders = json.load(f)
        except Exception:
            self._reminders = []

    def _save_reminders(self):
        """Save reminders to file"""
        try:
            os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
            with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._reminders, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def _start_monitor(self):
        """Start reminder monitor thread"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self):
        """Monitor loop for checking reminders"""
        while self._running:
            now = datetime.now()
            triggered = []

            for i, reminder in enumerate(self._reminders):
                trigger_time = datetime.fromisoformat(reminder["trigger_at"])
                if now >= trigger_time:
                    triggered.append(i)
                    callback = self._callbacks.get(reminder["id"])
                    if callback:
                        try:
                            callback(reminder)
                        except Exception:
                            pass

            for i in reversed(triggered):
                self._reminders.pop(i)

            if triggered:
                self._save_reminders()

            time.sleep(1)

    def add_reminder(self, message: str, trigger_at: str = None, seconds: int = None) -> Dict:
        """Add a new reminder"""
        if trigger_at:
            try:
                trigger_time = datetime.fromisoformat(trigger_at)
            except ValueError:
                return {
                    "success": False,
                    "error": "Invalid datetime format. Use ISO format."
                }
        elif seconds:
            trigger_time = datetime.now() + timedelta(seconds=seconds)
        else:
            return {
                "success": False,
                "error": "Must provide either trigger_at or seconds"
            }

        reminder_id = f"reminder_{int(time.time() * 1000)}"
        reminder = {
            "id": reminder_id,
            "message": message,
            "trigger_at": trigger_time.isoformat(),
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }

        self._reminders.append(reminder)
        self._save_reminders()

        return {
            "success": True,
            "reminder": reminder,
            "message": f"Reminder set for {trigger_time.strftime('%Y-%m-%d %H:%M:%S')}"
        }

    def list_reminders(self) -> Dict:
        """List all pending reminders"""
        return {
            "success": True,
            "reminders": self._reminders,
            "count": len(self._reminders)
        }

    def cancel_reminder(self, reminder_id: str) -> Dict:
        """Cancel a reminder"""
        for i, reminder in enumerate(self._reminders):
            if reminder["id"] == reminder_id:
                self._reminders.pop(i)
                self._save_reminders()
                return {
                    "success": True,
                    "message": f"Reminder {reminder_id} cancelled"
                }

        return {
            "success": False,
            "error": f"Reminder {reminder_id} not found"
        }

    def register_callback(self, reminder_id: str, callback: callable):
        """Register callback for reminder trigger"""
        self._callbacks[reminder_id] = callback


_manager = None


def get_manager() -> ReminderManager:
    """Get reminder manager singleton"""
    global _manager
    if _manager is None:
        _manager = ReminderManager()
    return _manager


def execute(input_data: Any) -> Dict:
    """
    Execute reminder operation

    Args:
        input_data: Either a dict with action or a message string

    Returns:
        Dict with operation result
    """
    manager = get_manager()

    if isinstance(input_data, dict):
        action = input_data.get("action", "add")
        message = input_data.get("message", "")
        reminder_id = input_data.get("id", "")
        seconds = input_data.get("seconds")
        trigger_at = input_data.get("trigger_at")
    else:
        action = "add"
        message = str(input_data)
        reminder_id = ""
        seconds = None
        trigger_at = None

    if action == "add":
        if not message:
            return {
                "success": False,
                "error": "No reminder message provided"
            }
        return manager.add_reminder(message, trigger_at=trigger_at, seconds=seconds)

    elif action == "list":
        return manager.list_reminders()

    elif action == "cancel":
        if not reminder_id:
            return {
                "success": False,
                "error": "No reminder ID provided"
            }
        return manager.cancel_reminder(reminder_id)

    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}"
        }
