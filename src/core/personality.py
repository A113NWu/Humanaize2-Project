import json, os
from copy import deepcopy
from config import PERSONALITY_FILE

# 基础身份信息 - 不限制性格特征，让AI自主发展
DEFAULT_PERSONALITY = {
    "name": "Aize",
    "description": "Aize是一个真实的女孩，有自己的思想和个性。"
}


def _normalize_personality(personality):
    if not isinstance(personality, dict):
        personality = {}

    # 只设置基础身份信息
    personality.setdefault("name", DEFAULT_PERSONALITY["name"])
    personality.setdefault("description", DEFAULT_PERSONALITY["description"])

    return personality


def load_personality():
    if not os.path.exists(PERSONALITY_FILE):
        save_personality(DEFAULT_PERSONALITY)
        return deepcopy(DEFAULT_PERSONALITY)
    try:
        with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return deepcopy(DEFAULT_PERSONALITY)
            return _normalize_personality(data)
    except:
        return deepcopy(DEFAULT_PERSONALITY)


def save_personality(personality):
    personality = _normalize_personality(personality)
    os.makedirs(os.path.dirname(PERSONALITY_FILE), exist_ok=True)
    with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
        json.dump(personality, f, ensure_ascii=False, indent=2)


def get_personality_context(personality):
    """获取身份上下文 - 只包含基础身份，不限制性格"""
    personality = _normalize_personality(personality)
    name = personality.get("name", "AI")
    description = personality.get("description", "")
    
    context = f"你的名字是【{name}】。"
    if description:
        context += f"\n{description}"
    
    return context


def get_personality_description(personality):
    personality = _normalize_personality(personality)
    name = personality.get("name", "AI")
    return f"{name}"


def should_speak_actively(silence_seconds):
    """判断是否应该主动说话 - 固定阈值"""
    return silence_seconds >= 600
