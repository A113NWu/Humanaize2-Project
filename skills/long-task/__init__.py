#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""长期任务技能：记录带截止时间的任务，安排「做一会、休息一会」。"""

import os
import sys
from typing import Any, Dict

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src", "core"))

try:
    from tools.long_tasks import get_task_store
except ImportError:
    get_task_store = None


def _store():
    if get_task_store is None:
        return None
    return get_task_store()


def execute(input_data: Any) -> Dict[str, Any]:
    store = _store()
    if store is None:
        return {"success": False, "error": "长期任务模块不可用"}
    if not isinstance(input_data, dict):
        return {"success": False, "error": "input 必须是对象"}

    params = input_data.get("params") if isinstance(input_data.get("params"), dict) else {}
    merged = dict(params)
    merged.update({k: v for k, v in input_data.items() if k != "params"})
    action = str(merged.get("action") or merged.get("command") or "list").strip().lower()

    if action == "create":
        return store.create(
            merged.get("title") or merged.get("name"),
            detail=merged.get("detail") or merged.get("description") or "",
            deadline=merged.get("deadline"),
            next_step=merged.get("next_step") or "",
        )

    if action in ("list", "show"):
        tasks = store.list_tasks(include_done=bool(merged.get("include_done")))
        return {
            "success": True,
            "tasks": tasks,
            "resting_until": (store.rest_state or {}).get("until"),
            "summary": store.reminder_text(max_tasks=5),
        }

    if action in ("update", "progress"):
        return store.update(
            merged.get("id") or merged.get("task_id"),
            progress=merged.get("progress"),
            next_step=merged.get("next_step"),
            deadline=merged.get("deadline"),
            next_minutes=merged.get("next_minutes"),
            note=merged.get("note"),
        )

    if action in ("done", "complete"):
        return store.complete(merged.get("id") or merged.get("task_id"),
                              note=merged.get("note") or "")

    if action in ("rest", "pause", "break"):
        return store.rest(minutes=merged.get("minutes") or 30,
                          until=merged.get("until"),
                          reason=merged.get("reason") or "")

    if action in ("wake", "resume"):
        return store.wake()

    return {"success": False, "error": f"未知 action：{action}"}
