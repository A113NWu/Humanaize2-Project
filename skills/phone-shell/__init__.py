"""
手機 Shell 技能：Aize 遠程在安卓手機上執行 shell 命令

手機端 Aize Companion 通過 Shizuku 取得 shell 級權限，
輪詢本中樞取命令、執行後回傳結果。
  run     {action:"run", command:"...", timeout?:30, wait?:true} 下發並等結果
  status  {action:"status"} 查看手機是否在線
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


def _get_hub():
    _ensure_src_path()
    try:
        from tools.phone_hub import get_phone_hub
    except ImportError:
        from core.tools.phone_hub import get_phone_hub
    return get_phone_hub()


def execute(input_data: Any) -> Dict:
    if isinstance(input_data, dict):
        action = input_data.get("action", "status")
    else:
        return {"success": False, "error": "input must be an object with 'action'"}

    if action == "status":
        try:
            return {"success": True, "phone": _get_hub().status()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    if action == "run":
        command = str(input_data.get("command", "")).strip()
        if not command:
            return {"success": False, "error": "command is required"}
        timeout = int(input_data.get("timeout", 30) or 30)
        wait = bool(input_data.get("wait", True))

        hub = _get_hub()
        status = hub.status()
        if not status.get("online"):
            return {"success": False,
                    "error": "手機不在線（Aize Companion 未連接或未開啟遠程命令）",
                    "phone": status}

        cmd_id = hub.push_command(command, timeout)
        if not cmd_id:
            return {"success": False, "error": "failed to queue command"}
        if not wait:
            return {"success": True, "id": cmd_id,
                    "message": "命令已下發（未等待結果）"}

        # 手機輪詢間隔 + 執行時間，寬限一點
        result = hub.wait_result(cmd_id, timeout + 30)
        if result is None:
            return {"success": False, "id": cmd_id,
                    "error": f"等待手機執行結果超時（{timeout + 30}s）"}
        return {
            "success": bool(result.get("success")),
            "id": cmd_id,
            "exit_code": result.get("exit_code"),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "error": result.get("error"),
            "duration_ms": result.get("duration_ms"),
        }

    return {"success": False, "error": f"Unknown action: {action}"}
