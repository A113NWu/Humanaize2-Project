"""
Humanaize Memory Skill
Query and manage conversation memory
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "memory.json")


def _load_memory() -> Dict:
    """Load memory from file"""
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {"conversations": [], "facts": [], "preferences": {}}


def _save_memory(memory: Dict) -> bool:
    """Save memory to file"""
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


def execute(input_data: Any) -> Dict:
    """
    Execute memory operation

    Args:
        input_data: Either a string action or dict with 'action' key
            Actions: search, add, list, clear, stats

    Returns:
        Dict with operation result
    """
    if isinstance(input_data, dict):
        action = input_data.get("action", "search")
        query = input_data.get("query", "")
        data = input_data.get("data", {})
    else:
        action = "search"
        query = str(input_data)
        data = {}

    memory = _load_memory()

    if action == "search":
        return _search_memory(memory, query)
    elif action == "add":
        return _add_memory(memory, data)
    elif action == "list":
        return _list_memory(memory, data)
    elif action == "clear":
        return _clear_memory(memory)
    elif action == "stats":
        return _get_stats(memory)
    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}"
        }


def _search_memory(memory: Dict, query: str) -> Dict:
    """Search memory for matching entries"""
    if not query:
        return {
            "success": True,
            "results": [],
            "count": 0
        }

    query_lower = query.lower()
    results = []

    for conv in memory.get("conversations", []):
        if query_lower in conv.get("text", "").lower():
            results.append(conv)

    for fact in memory.get("facts", []):
        if query_lower in str(fact).lower():
            results.append(fact)

    return {
        "success": True,
        "results": results,
        "count": len(results),
        "query": query
    }


def _add_memory(memory: Dict, data: Dict) -> Dict:
    """Add new memory entry"""
    entry_type = data.get("type", "fact")
    content = data.get("content", "")

    if not content:
        return {
            "success": False,
            "error": "No content provided"
        }

    if entry_type == "conversation":
        memory.setdefault("conversations", []).append({
            "text": content,
            "timestamp": datetime.now().isoformat()
        })
    elif entry_type == "fact":
        memory.setdefault("facts", []).append({
            "fact": content,
            "timestamp": datetime.now().isoformat()
        })
    elif entry_type == "preference":
        key = data.get("key", "general")
        memory.setdefault("preferences", {})[key] = {
            "value": content,
            "timestamp": datetime.now().isoformat()
        }

    _save_memory(memory)

    return {
        "success": True,
        "message": f"Added {entry_type}: {content[:50]}..."
    }


def _list_memory(memory: Dict, data: Dict) -> Dict:
    """List memory entries"""
    entry_type = data.get("type", None)
    limit = data.get("limit", 50)

    if entry_type:
        items = memory.get(entry_type + "s", [])[-limit:]
    else:
        items = []
        for key in ["conversations", "facts"]:
            items.extend(memory.get(key, []))
        items = items[-limit:]

    return {
        "success": True,
        "items": items,
        "count": len(items)
    }


def _clear_memory(memory: Dict) -> Dict:
    """Clear all memory"""
    memory = {"conversations": [], "facts": [], "preferences": {}}
    _save_memory(memory)

    return {
        "success": True,
        "message": "Memory cleared"
    }


def _get_stats(memory: Dict) -> Dict:
    """Get memory statistics"""
    return {
        "success": True,
        "stats": {
            "conversations": len(memory.get("conversations", [])),
            "facts": len(memory.get("facts", [])),
            "preferences": len(memory.get("preferences", {}))
        }
    }
