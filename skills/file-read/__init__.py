"""
Humanaize File Read Skill
Read files from the local filesystem
"""

import os
from typing import Dict, Any, Optional


def execute(input_data: Any) -> Dict:
    """
    Read content from a file

    Args:
        input_data: Either a file path string or dict with 'path' key

    Returns:
        Dict with success status, content, and optional error message
    """
    if isinstance(input_data, dict):
        file_path = input_data.get("path", "")
        encoding = input_data.get("encoding", "utf-8")
        max_size = input_data.get("max_size", 1024 * 1024)
    else:
        file_path = str(input_data)
        encoding = "utf-8"
        max_size = 1024 * 1024

    if not file_path:
        return {
            "success": False,
            "error": "No file path provided",
            "content": ""
        }

    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"File not found: {file_path}",
            "content": ""
        }

    if not os.path.isfile(file_path):
        return {
            "success": False,
            "error": f"Path is not a file: {file_path}",
            "content": ""
        }

    file_size = os.path.getsize(file_path)
    if file_size > max_size:
        return {
            "success": False,
            "error": f"File too large ({file_size} bytes). Maximum allowed: {max_size} bytes",
            "content": ""
        }

    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read()

        return {
            "success": True,
            "content": content,
            "path": file_path,
            "size": file_size,
            "lines": len(content.splitlines())
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read file: {str(e)}",
            "content": ""
        }


def read_lines(file_path: str, start: int = 1, count: int = 100, encoding: str = "utf-8") -> Dict:
    """
    Read specific lines from a file

    Args:
        file_path: Path to the file
        start: Starting line number (1-indexed)
        count: Number of lines to read
        encoding: File encoding

    Returns:
        Dict with success status and lines content
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"File not found: {file_path}",
            "lines": []
        }

    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            lines = f.readlines()

        start_idx = max(0, start - 1)
        end_idx = min(len(lines), start_idx + count)

        return {
            "success": True,
            "lines": lines[start_idx:end_idx],
            "total_lines": len(lines),
            "start": start,
            "count": count
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "lines": []
        }
