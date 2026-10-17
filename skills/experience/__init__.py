"""experience 技能：Aize 的經驗數據庫入口（save / search / list / forget）。"""
import os
import sys


def _db():
    here = os.path.dirname(os.path.abspath(__file__))          # skills/experience
    proj = os.path.dirname(os.path.dirname(here))              # 項目根目錄
    for p in (os.path.join(proj, "src"), os.path.join(proj, "src", "core")):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    try:
        from core.tools.experience_db import get_experience_db
    except ImportError:
        from tools.experience_db import get_experience_db
    return get_experience_db()


def execute(input_data):
    data = input_data if isinstance(input_data, dict) else {}
    action = str(data.get("action", "")).strip().lower()
    params = data.get("params") if isinstance(data.get("params"), dict) else data
    db = _db()

    if action == "save":
        return db.save(params.get("text", ""),
                       kind=params.get("kind", "thinking"),
                       tags=params.get("tags"))
    if action == "search":
        try:
            top_k = int(params.get("top_k", 3) or 3)
        except (TypeError, ValueError):
            top_k = 3
        return {"success": True, "results": db.search(params.get("query", ""), top_k=top_k)}
    if action == "list":
        return {"success": True, "entries": db.list_all()}
    if action == "forget":
        return db.forget(params.get("id"))
    return {"success": False, "error": f"unknown action: {action}（可用 save/search/list/forget）"}
