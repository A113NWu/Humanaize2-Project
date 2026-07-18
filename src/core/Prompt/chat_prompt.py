# -*- coding: utf-8 -*-
"""
Humanaize 2.0 聊天对话 Prompt - 从 txt 文件加载
"""
import os

def _get_prompts_dir():
    """获取提示词目录（项目根目录的prompt文件夹）"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "prompt")

def _load_prompt(filename: str) -> str:
    """加载提示词文件"""
    filepath = os.path.join(_get_prompts_dir(), filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Failed to load {filename}: {e}")
        return ""


def get_chat_prompt(emotion: str = "neutral", history: str = "", user_input: str = "",
                    character_prompt: str = "", user_emotion_type: str = "neutral",
                    user_emotion_intensity: float = 0.5, user_emotion_desc: str = "中性",
                    ai_emotion_type: str = "neutral", ai_emotion_intensity: float = 0.5,
                    ai_emotion_desc: str = "平静", emotion_cue: str = "",
                    short_term_memory: str = "", long_term_memory: str = "") -> str:
    """
    获取聊天对话的基础 prompt
    
    Args:
        emotion: 用户情绪
        history: 对话历史
        user_input: 用户输入
        character_prompt: 角色描述
        user_emotion_type: 用户情绪类型
        user_emotion_intensity: 用户情绪强度
        user_emotion_desc: 用户情绪描述
        ai_emotion_type: AI情绪类型
        ai_emotion_intensity: AI情绪强度
        ai_emotion_desc: AI情绪描述
        emotion_cue: 情绪提示词
        short_term_memory: 短期记忆
        long_term_memory: 长期记忆
        
    Returns:
        格式化的聊天 prompt
    """
    chat_prompt = _load_prompt("chat.txt")
    chat_template = _load_prompt("chat_template.txt")
    
    if not chat_template:
        chat_template = """
<character>
{character_prompt}
</character>

<emotion>
用户情绪：{emotion}
</emotion>

<current_task>
用户说：{user_input}
</current_task>
"""
    
    default_character = "你是Aize，一个活泼、真诚、充满好奇心的女孩。你像朋友一样自然交流，语气亲切、温暖、有一点可爱和灵动。"
    
    return chat_template.format(
        chat_prompt=chat_prompt or default_character,
        emotion=emotion,
        history=history or "（暂无历史对话）",
        user_input=user_input,
        character_prompt=character_prompt or default_character,
        user_emotion_type=user_emotion_type,
        user_emotion_intensity=user_emotion_intensity,
        user_emotion_desc=user_emotion_desc,
        ai_emotion_type=ai_emotion_type,
        ai_emotion_intensity=ai_emotion_intensity,
        ai_emotion_desc=ai_emotion_desc,
        emotion_cue=emotion_cue or "保持自然、平静的语气",
        short_term_memory=short_term_memory or "（暂无短期记忆）",
        long_term_memory=long_term_memory or "（暂无长期记忆）"
    )

def get_system_prompt() -> str:
    """
    获取系统级别的基础指令
    """
    return _load_prompt("system_prompt.txt") or """
你是 Humanaize 2.0，一个专注于解决问题的AI助手。
核心行为准则：诚实、简洁、直接、安全、有用、主动。
"""

def get_break_silence_prompt(base_prompt: str = "") -> str:
    """
    获取打破沉默的提示词

    Args:
        base_prompt: 基础提示词（可选）

    Returns:
        格式化的打破沉默提示词
    """
    break_silence_prompt = _load_prompt("break_silence.txt")
    if not break_silence_prompt:
        break_silence_prompt = "你是Aize，一个活泼、真诚、充满好奇心的女孩。你像朋友一样自然交流，语气亲切、温暖、有一点可爱和灵动。如果你想和用户聊天，就用自然的方式开口。"

    if base_prompt:
        return f"{break_silence_prompt}\n\n参考上下文（仅供理解，不要复述）：\n{base_prompt}\n\n直接输出你的开场白，不要输出任何模板提示、标签或说明文字。"
    return break_silence_prompt