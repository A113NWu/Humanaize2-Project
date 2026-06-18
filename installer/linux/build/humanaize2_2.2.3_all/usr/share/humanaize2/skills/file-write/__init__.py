"""
Humanaize File Write Skill
Write content to files on the local filesystem
"""

import os
from typing import Dict, Any


def execute(input_data: Any) -> Dict:
    """
    Write content to a file

    Args:
        input_data: Either a dict with 'path' and 'content' keys, or just content with path specified

    Returns:
        Dict with success status and optional error message
    """
    if isinstance(input_data, dict):
        file_path = input_data.get("path", "")
        content = input_data.get("content", "")
        encoding = input_data.get("encoding", "utf-8")
        mode = input_data.get("mode", "w")
        create_dirs = input_data.get("create_dirs", True)
    else:
        return {
            "success": False,
            "error": "File write requires a dictionary with 'path' and 'content' keys"
        }

    if not file_path:
        return {
            "success": False,
            "error": "No file path provided"
        }

    if create_dirs:
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to create directory: {str(e)}"
                }

    try:
        with open(file_path, mode, encoding=encoding, errors='replace') as f:
            f.write(content)

        return {
            "success": True,
            "path": file_path,
            "size": len(content),
            "lines": len(content.splitlines())
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to write file: {str(e)}"
        }


def append(input_data: Any) -> Dict:
    """
    Append content to an existing file

    Args:
        input_data: Dict with 'path' and 'content' keys

    Returns:
        Dict with success status
    """
    if isinstance(input_data, dict):
        input_data["mode"] = "a"
        return execute(input_data)
    else:
        return {
            "success": False,
            "error": "Append requires a dictionary with 'path' and 'content' keys"
        }
