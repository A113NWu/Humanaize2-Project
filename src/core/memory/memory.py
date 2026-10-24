import json, os
from datetime import datetime

try:
    from core.config.config import MEMORY_FILE, MAX_MEMORY
except ImportError:
    from config.config import MEMORY_FILE, MAX_MEMORY

DEFAULT_MEMORY = {"messages": [], "summaries": [], "thoughts": [], "decisions": []}

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        save_memory(DEFAULT_MEMORY)
        return DEFAULT_MEMORY.copy()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return DEFAULT_MEMORY.copy()
            data.setdefault("messages", [])
            data.setdefault("summaries", [])
            data.setdefault("thoughts", [])
            data.setdefault("decisions", [])
            return data
    except:
        return DEFAULT_MEMORY.copy()

def save_memory(mem):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)

def add(mem, role, content, source=None):
    entry = {
        "role": role,
        "content": content,
        "time": datetime.now().isoformat(),
        "source": source or ("user" if role == "user" else "ai_response")
    }
    mem.setdefault("messages", []).append(entry)
    if len(mem["messages"]) > MAX_MEMORY:
        mem["messages"] = mem["messages"][-MAX_MEMORY:]
    # 同步索引進向量記憶庫（懶加載，失敗不影響主流程）
    try:
        try:
            from ..tools.memory_db import get_memory_db
        except ImportError:
            from tools.memory_db import get_memory_db
        get_memory_db().add(role, content, timestamp=entry["time"])
    except Exception:
        pass
    # 系統級經驗沉澱：每輪對話自動抽取偏好/思路，不再依賴 Skill
    if role in ("user", "assistant") and source not in ("system",):
        try:
            try:
                from ..tools.experience_db import capture_message
            except ImportError:
                from tools.experience_db import capture_message
            capture_message(role, content)
        except Exception:
            pass
    return mem  # 返回更新后的memory对象

def add_message(mem, role, content):
    return add(mem, role, content)

def add_decision(mem, decision, reason=None):
    if "decisions" not in mem or not isinstance(mem["decisions"], list):
        mem["decisions"] = []
    entry = {
        "decision": decision,
        "reason": reason,
        "time": datetime.now().isoformat()
    }
    mem["decisions"].append(entry)
    if len(mem["decisions"]) > MAX_MEMORY:
        mem["decisions"] = mem["decisions"][-MAX_MEMORY:]

def get_memory_stats(mem):
    return {
        "total_messages": len(mem.get("messages", [])),
        "total_thoughts": len(mem.get("thoughts", [])),
        "total_decisions": len(mem.get("decisions", [])),
    }

def add_thought(mem, thought, thought_type="internal"):
    if "thoughts" not in mem or not isinstance(mem["thoughts"], list):
        mem["thoughts"] = []
    entry = {
        "type": thought_type,
        "content": thought,
        "time": datetime.now().isoformat()
    }
    mem["thoughts"].append(entry)
    if len(mem["thoughts"]) > MAX_MEMORY:
        mem["thoughts"] = mem["thoughts"][-MAX_MEMORY:]

def build_history_string(mem):
    """從記憶體建構對話歷史字串"""
    messages = mem.get("messages", [])
    history = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history += f"{role}: {content}\n"
    return history.strip()
