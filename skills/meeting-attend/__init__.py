"""
會議旁聽技能：Aize 接入線上會議（騰訊會議等）的語音

捕獲系統音頻（WASAPI loopback 優先，麥克風兜底）→ 語音轉寫
→ 定期生成會議摘要推送到聊天中樞。
  start   {action:"start"}                      開始旁聽
  stop    {action:"stop"}                       停止旁聽
  status  {action:"status"}                     查看狀態與最新摘要
  summary {action:"summary"}                    立即生成一次摘要
  transcript {action:"transcript", limit?:50}   取最近逐字稿
"""

import os
import sys
from typing import Any, Dict


def _ensure_src_path():
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(here))
    for p in (os.path.join(project_root, "src"),
              os.path.join(project_root, "src", "core")):
        if p not in sys.path and os.path.isdir(p):
            sys.path.insert(0, p)


def _get_listener():
    _ensure_src_path()
    try:
        from voice.meeting_listener import get_meeting_listener
    except ImportError:
        from core.voice.meeting_listener import get_meeting_listener
    return get_meeting_listener()


def execute(input_data: Any) -> Dict:
    if not isinstance(input_data, dict):
        return {"success": False, "error": "input must be an object with 'action'"}
    action = input_data.get("action", "status")
    try:
        ml = _get_listener()
        if action == "start":
            r = ml.start()
            r["success"] = True
            return r
        if action == "stop":
            r = ml.stop()
            r["success"] = True
            return r
        if action == "status":
            return {"success": True, "meeting": ml.status()}
        if action == "summary":
            r = ml.summarize_now()
            r["success"] = bool(r.get("ok"))
            return r
        if action == "transcript":
            limit = int(input_data.get("limit", 50) or 50)
            return {"success": True, **ml.transcript(limit=max(1, min(limit, 3000)))}
        return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
