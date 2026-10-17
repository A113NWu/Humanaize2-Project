"""
Humanaize Memory Skill

操作 Aize 的向量記憶庫：需要回憶時主動搜索，而不是把全部記憶疊進上下文。
日常對話會自動索引；這個技能用於主動檢索、手動保存、查看與遺忘。
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


def _get_db():
    _ensure_src_path()
    try:
        from tools.memory_db import get_memory_db
    except ImportError:
        from core.tools.memory_db import get_memory_db
    return get_memory_db()


def execute(input_data: Any) -> Dict:
    """
    Actions:
      search  - 用問題檢索相關記憶  {action, query, top_k?}
      save    - 手動保存一條記憶    {action, content, role?, kind?}
      list    - 最近記憶列表        {action, limit?}
      forget  - 按 id 遺忘          {action, id}
      status  - 記憶庫狀態
    """
    if isinstance(input_data, dict):
        action = input_data.get("action", "search")
    else:
        action = "search"
        input_data = {"query": str(input_data)}

    try:
        db = _get_db()
    except Exception as e:
        return {"success": False, "error": f"memory db unavailable: {e}"}

    if action == "search":
        query = str(input_data.get("query", ""))
        top_k = int(input_data.get("top_k", input_data.get("limit", 5)))
        hits = db.search(query, top_k=top_k)
        return {"success": True, "results": hits, "count": len(hits)}

    if action == "save":
        content = str(input_data.get("content", "") or input_data.get("query", ""))
        role = str(input_data.get("role", "note"))
        kind = str(input_data.get("kind", "note"))
        return db.add(role, content, kind=kind)

    if action == "list":
        limit = int(input_data.get("limit", 20))
        items = db.list_all(limit=limit)
        return {"success": True, "items": items, "count": len(items)}

    if action == "forget":
        return db.forget(input_data.get("id"))

    if action == "status":
        return {"success": True, "entries": len(db.entries), "path": db.path}

    return {"success": False, "error": f"Unknown action: {action}"}
