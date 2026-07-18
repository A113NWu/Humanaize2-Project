"""
Humanaize Shell Skill
Execute shell commands on the local system
"""

import subprocess
import os
import shutil
from typing import Dict, Any


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
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
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
