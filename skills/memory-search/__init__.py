"""記憶檢索技能：讓 Aize 按需搜尋長期記憶庫，而不是把記憶硬塞進上下文。"""


def execute(input_data):
    """搜尋記憶庫。

    input: {"query": "關鍵詞", "top_k": 5} 或直接給查詢字串
    output: {"success", "query", "count", "results", "text"}
    """
    if isinstance(input_data, dict):
        query = str(input_data.get("query") or input_data.get("q") or "").strip()
        try:
            top_k = int(input_data.get("top_k") or input_data.get("limit") or 5)
        except (TypeError, ValueError):
            top_k = 5
    else:
        query = str(input_data or "").strip()
        top_k = 5

    if not query:
        return {"success": False, "error": "缺少 query（要搜尋的關鍵詞）"}

    try:
        try:
            from tools.memory_db import get_memory_db
        except ImportError:
            from core.tools.memory_db import get_memory_db
        hits = get_memory_db().search(query, top_k=max(1, min(top_k, 10))) or []
    except Exception as e:
        return {"success": False, "error": f"記憶庫檢索失敗: {e}", "query": query}

    if not hits:
        return {"success": True, "query": query, "count": 0, "results": [],
                "text": "記憶庫裡沒有找到相關內容。"}

    lines = []
    for hit in hits:
        role = "主人" if hit.get("role") == "user" else "Aize"
        lines.append(f"[{hit.get('time', '')}] {role}：{hit.get('content', '')}")
    return {"success": True, "query": query, "count": len(hits),
            "results": hits, "text": "\n".join(lines)}
