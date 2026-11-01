# -*- coding: utf-8 -*-
"""长期任务与截止时间：让 Aize 记住要做很久的事，并自己安排「做一会、休息一会」。

数据文件：data/long_tasks.json
- tasks: 任务列表（标题/描述/截止时间/进度/下一步/下次继续时间/状态）
- rest: 全局休息窗口（休息期间空闲引擎完全停工，到点自动醒来）
"""
import json
import os
import threading
from datetime import datetime, timedelta

_LOCK = threading.RLock()
_STORE = None

_STATUS_ACTIVE = "active"
_STATUS_DONE = "done"
_STATUS_CANCELLED = "cancelled"


def _data_dir():
    base = None
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["app_data_dir"])
            base = m.app_data_dir()
            break
        except Exception:
            continue
    if not base:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _path():
    return os.path.join(_data_dir(), "long_tasks.json")


def _now():
    return datetime.now()


def _parse_dt(value):
    """接受 '2026-11-03 18:00' / ISO / datetime，返回 datetime 或 None。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("年", "-").replace("月", "-").replace("日", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S") if dt else None


def _minutes_until(dt):
    if not dt:
        return None
    return int((dt - _now()).total_seconds() // 60)


class LongTaskStore:
    def __init__(self, path=None):
        self.path = path or _path()
        self.tasks = []
        self.rest_state = {"until": None, "reason": ""}
        self._next_id = 1
        self._load()

    # ------------------------------------------------------------ storage
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.tasks = data.get("tasks", []) if isinstance(data, dict) else []
            self.rest_state = data.get("rest", {"until": None, "reason": ""}) or {"until": None, "reason": ""}
            self._next_id = int(data.get("next_id", len(self.tasks) + 1))
        except Exception:
            self.tasks, self.rest_state, self._next_id = [], {"until": None, "reason": ""}, 1

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"next_id": self._next_id, "tasks": self.tasks, "rest": self.rest_state},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _find(self, task_id):
        for t in self.tasks:
            if str(t.get("id")) == str(task_id):
                return t
        return None

    # ------------------------------------------------------------ tasks
    def create(self, title, detail="", deadline=None, next_step="", next_work_at=None):
        title = str(title or "").strip()
        if not title:
            return {"success": False, "error": "title 不能为空"}
        with _LOCK:
            tid = self._next_id
            self._next_id += 1
            now = _now()
            task = {
                "id": tid,
                "title": title,
                "detail": str(detail or "").strip(),
                "deadline": _iso(_parse_dt(deadline)),
                "progress": "",
                "next_step": str(next_step or "").strip(),
                "status": _STATUS_ACTIVE,
                "created_at": _iso(now),
                "updated_at": _iso(now),
                "next_work_at": _iso(_parse_dt(next_work_at) or now),
                "log": [],
            }
            self.tasks.append(task)
            self._save()
        return {"success": True, "task": task}

    def list_tasks(self, include_done=False):
        with _LOCK:
            if include_done:
                return list(self.tasks)
            return [t for t in self.tasks if t.get("status") == _STATUS_ACTIVE]

    def get(self, task_id):
        return self._find(task_id)

    def update(self, task_id, **fields):
        with _LOCK:
            t = self._find(task_id)
            if not t:
                return {"success": False, "error": f"任务 {task_id} 不存在"}
            for key in ("title", "detail", "progress", "next_step", "status"):
                if key in fields and fields[key] is not None:
                    t[key] = str(fields[key]).strip()
            if "deadline" in fields:
                t["deadline"] = _iso(_parse_dt(fields["deadline"]))
            if "next_work_at" in fields:
                t["next_work_at"] = _iso(_parse_dt(fields["next_work_at"]))
            if "next_minutes" in fields and fields["next_minutes"]:
                try:
                    t["next_work_at"] = _iso(_now() + timedelta(minutes=int(fields["next_minutes"])))
                except Exception:
                    pass
            t["updated_at"] = _iso(_now())
            note = str(fields.get("note") or "").strip()
            if note:
                t.setdefault("log", []).append({"time": _iso(_now()), "text": note})
                t["log"] = t["log"][-50:]
            self._save()
            return {"success": True, "task": t}

    def complete(self, task_id, note=""):
        return self.update(task_id, status=_STATUS_DONE, note=note or "任务完成")

    # ------------------------------------------------------------ rest
    def rest_until(self):
        with _LOCK:
            return _parse_dt((self.rest_state or {}).get("until"))

    def is_resting(self):
        ru = self.rest_until()
        return bool(ru and _now() < ru)

    def rest(self, minutes=None, until=None, reason=""):
        """安排一次休息：期间空闲引擎完全停工，到点自动醒。"""
        target = _parse_dt(until)
        if not target and minutes:
            try:
                target = _now() + timedelta(minutes=max(1, int(minutes)))
            except Exception:
                target = None
        if not target:
            return {"success": False, "error": "需要 minutes 或 until"}
        with _LOCK:
            self.rest_state = {"until": _iso(target), "reason": str(reason or "").strip()}
            self._save()
        return {"success": True, "rest": self.rest_state}

    def wake(self):
        with _LOCK:
            self.rest_state = {"until": None, "reason": ""}
            for t in self.tasks:
                if t.get("status") == _STATUS_ACTIVE:
                    t["next_work_at"] = _iso(_now())
            self._save()
        return {"success": True}

    # ------------------------------------------------------------ queries
    def due_tasks(self):
        """到达「下次继续」时间的任务。"""
        now = _now()
        out = []
        with _LOCK:
            for t in self.tasks:
                if t.get("status") != _STATUS_ACTIVE:
                    continue
                nw = _parse_dt(t.get("next_work_at"))
                if nw is None or nw <= now:
                    out.append(t)
        return out

    def reminder_text(self, max_tasks=3):
        """给提示词/上下文用的一行行任务摘要。"""
        lines = []
        now = _now()
        with _LOCK:
            for t in self.tasks:
                if t.get("status") != _STATUS_ACTIVE:
                    continue
                dl = _parse_dt(t.get("deadline"))
                if dl:
                    mins = _minutes_until(dl)
                    if mins is not None and mins < 0:
                        due = f"已逾期 {-mins} 分钟"
                    elif mins is not None and mins < 24 * 60:
                        due = f"还剩 {mins} 分钟"
                    else:
                        due = f"还剩 {mins // 60} 小时" if mins is not None else ""
                    due_text = f"｜截止 {dl.strftime('%m-%d %H:%M')}（{due}）"
                else:
                    due_text = "｜未设截止时间"
                parts = [f"#{t.get('id')} {t.get('title')}{due_text}"]
                if t.get("progress"):
                    parts.append(f"进度：{t['progress']}")
                if t.get("next_step"):
                    parts.append(f"下一步：{t['next_step']}")
                lines.append("　".join(parts))
                if len(lines) >= max_tasks:
                    break
        return "\n".join(lines)


def get_task_store():
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = LongTaskStore()
        return _STORE
