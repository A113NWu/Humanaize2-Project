"""
Prompt Builder - 使用统一的 Prompt 模块
"""

from memory import build_history_string
from Prompt import get_chat_prompt

def build_prompt(
    personality_context,
    memory,
    user_input,
    emotion=None
):
    """
    构建对话 Prompt
    
    Args:
        personality_context: 个性上下文
        memory: 记忆对象
        user_input: 用户输入
        emotion: 用户情绪
        
    Returns:
        格式化的 Prompt 字符串
    """
    history = build_history_string(memory)
    emotion_text = emotion.get("dominant", "neutral") if emotion else "neutral"
    
    return get_chat_prompt(personality_context, emotion_text).format(
        history=history,
        user_input=user_input
    )