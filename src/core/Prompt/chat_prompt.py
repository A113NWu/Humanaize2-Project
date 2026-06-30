# -*- coding: utf-8 -*-
"""
Humanaize 2.0 聊天对话 Prompt - 从 txt 文件加载
"""
import os

def _get_prompts_dir():
    """获取提示词目录"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prompts")

def _load_prompt(filename: str) -> str:
    """加载提示词文件"""
    filepath = os.path.join(_get_prompts_dir(), filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Failed to load {filename}: {e}")
        return ""


def get_chat_prompt(emotion: str = "neutral", history: str = "", user_input: str = "") -> str:
    """
    获取聊天对话的基础 prompt
    
    Args:
        emotion: 用户情绪
        history: 对话历史
        user_input: 用户输入
        
    Returns:
        格式化的聊天 prompt
    """
    chat_prompt = _load_prompt("chat.txt")
    chat_template = _load_prompt("chat_template.txt")
    
    if not chat_template:
        chat_template = """
<personality>
{chat_prompt}
</personality>

<emotion>
用户当前情绪：{emotion}
</emotion>

<current_task>
用户说：{user_input}
</current_task>
"""
    
    return chat_template.format(
        chat_prompt=chat_prompt or "你是Aize，一个真实的女孩。",
        emotion=emotion,
        history=history or "（暂无历史对话）",
        user_input=user_input
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
        break_silence_prompt = "你是Aize，一个真实的女孩。如果你想和用户聊天，就用自然的方式开口。"
    
    if base_prompt:
        return break_silence_prompt + "\n\n" + base_prompt
    return break_silence_prompt
