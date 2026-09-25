"""
Humanaize Shell Skill
Execute shell commands on the local system
"""

import subprocess
import os
import sys
import locale
import shutil
from typing import Dict, Any


def _decode_output(raw: bytes) -> str:
    """解碼命令輸出。

    中文 Windows 的 cmd.exe 按系統 OEM 代碼頁輸出（CP950/CP936），
    舊代碼硬編碼 utf-8 導致「'cat' 不是內部或外部命令」整行亂碼。
    按「系統首選編碼 → utf-8」順序嘗試，均失敗時 replace 兜底。
    """
    if not raw:
        return ""
    candidates = []
    pref = locale.getpreferredencoding(False)
    if pref:
        candidates.append(pref)
    candidates += ["utf-8", "gbk", "cp950", "cp936"]
    seen = set()
    for enc in candidates:
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            text = raw.decode(enc)
            if "\ufffd" not in text:
                return text
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode(pref or "utf-8", errors="replace")


def execute(input_data: Any) -> Dict:
    """
    Execute a shell command and return the result

    Args:
        input_data: Either a string command or dict with 'command' key

    Returns:
        Dict with stdout, stderr, returncode, and success status
    """
    if isinstance(input_data, dict):
        command = input_data.get("command", "")
        cwd = input_data.get("cwd", None)
        timeout = input_data.get("timeout", 30)
    else:
        command = str(input_data)
        cwd = None
        timeout = 30

    if not command:
        return {
            "success": False,
            "error": "No command provided",
            "stdout": "",
            "stderr": ""
        }

    if not shutil.which("cmd") and os.name == 'nt':
        return {
            "success": False,
            "error": "cmd.exe not found",
            "stdout": "",
            "stderr": ""
        }

    try:
        shell = os.name == 'nt' or True
        result = subprocess.run(
            command,
            shell=shell,
            cwd=cwd,
            capture_output=True,
            timeout=timeout
        )
        stdout = _decode_output(result.stdout)
        stderr = _decode_output(result.stderr)

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "command": command
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds",
            "stdout": "",
            "stderr": "",
            "command": command
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
            "command": command
        }
