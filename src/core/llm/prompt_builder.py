"""
Prompt Builder - 使用统一的 Prompt 模块
"""

from memory import build_history_string
from Prompt import get_chat_prompt


def build_prompt(
    memory,
    user_input,
    emotion=None
):
    """
    构建对话 Prompt
    
    Args:
        memory: 记忆对象
        user_input: 用户输入
        emotion: 用户情绪
        
    Returns:
        格式化的 Prompt 字符串
    """
    history = build_history_string(memory)
    emotion_text = emotion.get("dominant", "neutral") if emotion else "neutral"
    
    return get_chat_prompt(emotion_text, history, user_input)


def build_enhanced_prompt(
    memory,
    user_input,
    user_emotion=None,
    ai_emotion=None
):
    """
    构建增强版对话 Prompt（支持新模板）
    
    Args:
        memory: 记忆对象
        user_input: 用户输入
        user_emotion: 用户情绪分析结果
        ai_emotion: AI情绪状态
        
    Returns:
        格式化的 Prompt 字符串
    """
    if memory:
        history = build_history_string(memory)
    else:
        history = ""
    
    character_prompt = ""
    try:
        from tools.character_config import character_config
        prompt_data = character_config.get_prompt()
        if prompt_data and isinstance(prompt_data, dict):
            character_prompt = prompt_data.get("full", "")
    except ImportError:
        pass
    
    user_emotion_type = "neutral"
    user_emotion_intensity = 0.5
    user_emotion_desc = "中性"
    
    if user_emotion:
        user_emotion_type = user_emotion.get("dominant_emotion", "neutral")
        user_emotion_intensity = user_emotion.get("intensity", 0.5)
        user_emotion_desc = user_emotion.get("analysis", "中性")
    
    ai_emotion_type = "neutral"
    ai_emotion_intensity = 0.5
    ai_emotion_desc = "平静"
    emotion_cue = "保持自然、平静的语气"
    
    if ai_emotion:
        ai_emotion_type = ai_emotion.get("emotion_type", "neutral")
        ai_emotion_intensity = ai_emotion.get("intensity", 0.5)
        ai_emotion_desc = ai_emotion.get("display_name", "平静")
        
        try:
            from tools.emotion_engine import emotion_engine
            emotion_cue = emotion_engine.engine.get_emotion_cue()
        except ImportError:
            pass
    
    short_term_memory = ""
    long_term_memory = ""
    
    if memory:
        if hasattr(memory, 'short_term_memories'):
            short_term_memory = "\n".join([str(m) for m in memory.short_term_memories[-5:]])
        if hasattr(memory, 'long_term_memories'):
            long_term_memory = "\n".join([str(m) for m in memory.long_term_memories[-3:]])
    
    return get_chat_prompt(
        emotion=user_emotion_type,
        history=history,
        user_input=user_input,
        character_prompt=character_prompt,
        user_emotion_type=user_emotion_type,
        user_emotion_intensity=user_emotion_intensity,
        user_emotion_desc=user_emotion_desc,
        ai_emotion_type=ai_emotion_type,
        ai_emotion_intensity=ai_emotion_intensity,
        ai_emotion_desc=ai_emotion_desc,
        emotion_cue=emotion_cue,
        short_term_memory=short_term_memory,
        long_term_memory=long_term_memory
    )