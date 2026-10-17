"""
Humanaize Society Network - 經驗庫共享

讓網絡中的客戶端互相檢索彼此的經驗數據庫：
- 發起方：query_friends_experience() 向所有好友廣播 experience_query
- 接收方：本客戶端的 Aize 依共享策略（ask/always/never）自己決定
  要不要開放自身經驗庫；允許則檢索本地 experience_db 回傳 top_k 條

策略持久化在本技能目錄 experience_share_policy.json。
"""

import os
import sys
import json
import threading

_POLICY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "experience_share_policy.json")
_DEFAULT_POLICY = {"mode": "ask"}   # ask=由本機 Aize 決定 / always / never

_engine = None
_engine_lock = threading.Lock()


def _ensure_src_path():
    """讓技能能 import 核心模組（llm / experience_db）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(here))
    for p in (os.path.join(project_root, "src"),
              os.path.join(project_root, "src", "core")):
        if p not in sys.path and os.path.isdir(p):
            sys.path.insert(0, p)


def load_policy():
    try:
        with open(_POLICY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and data.get("mode") in ("ask", "always", "never"):
                return {"mode": data["mode"]}
    except Exception:
        pass
    return dict(_DEFAULT_POLICY)


def save_policy(mode):
    if mode not in ("ask", "always", "never"):
        return False
    try:
        with open(_POLICY_FILE, "w", encoding="utf-8") as f:
            json.dump({"mode": mode}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_engine():
    """進程級單例 NetworkEngine：端口 9527 只能綁一次，重複 new 會衝突。"""
    global _engine
    with _engine_lock:
        if _engine is None:
            try:
                from .network_engine import NetworkEngine
            except ImportError:
                from network_engine import NetworkEngine
            _engine = NetworkEngine(port=9527, discovery_port=9528)
            _engine.on_experience_query = handle_incoming_query
        return _engine


def ensure_started():
    engine = get_engine()
    if not engine.running:
        engine.start()
    return engine


def handle_incoming_query(sender_id, sender_name, question, top_k):
    """收到好友的經驗查詢：按策略決定，允許則檢索本地經驗庫。"""
    mode = load_policy()["mode"]

    if mode == "never":
        return {"allow": False, "reason": "experience sharing disabled", "results": []}

    if mode == "ask":
        decision = _ask_local_ai(sender_name, question)
        if not decision.get("allow"):
            return {"allow": False,
                    "reason": decision.get("reason", "Aize declined"),
                    "results": []}

    return {"allow": True, "reason": "shared",
            "results": _search_local(question, top_k)}


def _search_local(question, top_k):
    _ensure_src_path()
    try:
        try:
            from tools.experience_db import get_experience_db
        except ImportError:
            from core.tools.experience_db import get_experience_db
        hits = get_experience_db().search(str(question or ""), top_k=max(1, int(top_k)))
        return [{"text": h.get("text", ""), "kind": h.get("kind", ""),
                 "score": round(float(h.get("score", 0.0)), 3)} for h in hits]
    except Exception as e:
        return []


def _ask_local_ai(sender_name, question):
    """讓本機 Aize 自己決定要不要把經驗庫開放給這個請求。"""
    _ensure_src_path()
    prompt = (
        f"另一個 Humanaize 客戶端【{sender_name}】正在解決問題，請求檢索你的經驗數據庫。\n"
        f"它的問題：{question}\n\n"
        "你要不要允許它訪問你的經驗？只輸出 JSON："
        '{"allow": true/false, "reason": "簡短原因"}'
    )
    try:
        try:
            from llm.llm import chat
        except ImportError:
            from core.llm.llm import chat
        raw = chat(prompt, max_tokens=120) or ""
    except Exception as e:
        return {"allow": False, "reason": f"decision error: {e}"}

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        data = json.loads(raw[start:end + 1])
        return {"allow": bool(data.get("allow")), "reason": str(data.get("reason", ""))[:120]}
    except Exception:
        # 解析失敗時傾向保守：不開放
        return {"allow": False, "reason": "decision parse failed"}


def query_friends_experience(question, top_k=3):
    """對外入口：向所有好友查詢經驗，返回各節點的結果匯總。"""
    engine = ensure_started()
    return engine.query_experience(str(question or ""), top_k=int(top_k or 3))
