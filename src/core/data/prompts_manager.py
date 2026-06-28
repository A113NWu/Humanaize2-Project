# -*- coding: utf-8 -*-
"""
提示词管理器 - 从 txt 文件加载所有提示词
"""
import os
from typing import Optional

# 提示词文件路径
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# 提示词文件映射
PROMPT_FILES = {
    "should_answer_user": "should_answer_user.txt",
    "should_use_gan": "should_use_gan.txt",
    "should_reconsider": "should_reconsider.txt",
    "should_proactively_speak": "should_proactively_speak.txt",
    "choose_response_topic": "choose_response_topic.txt",
    "break_silence": "break_silence.txt",
    "chat": "chat.txt",
    "agent": "agent_prompt.txt",  # 在 data 目录下
    # GAN 相关
    "gan_decide": "gan_decide.txt",
    "gan_topic": "gan_topic.txt",
    "gan_argument_a": "gan_argument_a.txt",
    "gan_argument_b": "gan_argument_b.txt",
    "gan_synthesis": "gan_synthesis.txt",
}


def _get_prompts_dir():
    """获取提示词目录"""
    return os.path.join(os.path.dirname(__file__), "prompts")


def _get_data_dir():
    """获取 data 目录"""
    return os.path.dirname(__file__)


def load_prompt(prompt_name: str) -> str:
    """
    加载提示词
    
    Args:
        prompt_name: 提示词名称
        
    Returns:
        提示词内容
    """
    if prompt_name not in PROMPT_FILES:
        return ""
    
    filename = PROMPT_FILES[prompt_name]
    
    # 判断文件路径
    if prompt_name == "agent":
        # agent_prompt.txt 在 data 目录下
        filepath = os.path.join(_get_data_dir(), filename)
    else:
        filepath = os.path.join(_get_prompts_dir(), filename)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Failed to load prompt {prompt_name}: {e}")
        return ""


# ==================== 通用提示词加载函数 ====================

def load_should_answer_user_prompt(user_text: str) -> str:
    """加载判断是否回答用户的提示词"""
    template = load_prompt("should_answer_user")
    return template.format(user_text=user_text)


def load_should_use_gan_prompt(user_text: str, context: str = "") -> str:
    """加载判断是否使用 GAN 的提示词"""
    template = load_prompt("should_use_gan")
    return template.format(user_text=user_text, context=context)


def load_should_reconsider_prompt(context: str) -> str:
    """加载判断是否需要重新考虑的提示词"""
    template = load_prompt("should_reconsider")
    return template.format(context=context)


def load_should_proactively_speak_prompt(gan_topic: str, gan_synthesis: str, context: str) -> str:
    """加载判断是否主动说话的提示词"""
    template = load_prompt("should_proactively_speak")
    return template.format(gan_topic=gan_topic, gan_synthesis=gan_synthesis, context=context)


def load_choose_response_topic_prompt(user_text: str, user_topic: str, gan_topic: str, gan_synthesis: str, similarity: float) -> str:
    """加载选择回复主题的提示词"""
    template = load_prompt("choose_response_topic")
    return template.format(
        user_text=user_text,
        user_topic=user_topic or "无",
        gan_topic=gan_topic or "无",
        gan_synthesis=gan_synthesis or "无",
        similarity=similarity
    )


def load_break_silence_prompt() -> str:
    """加载打破沉默的提示词"""
    return load_prompt("break_silence")


def load_chat_prompt() -> str:
    """加载聊天提示词"""
    return load_prompt("chat")


def load_agent_prompt() -> str:
    """加载 agent 提示词"""
    return load_prompt("agent")


# ==================== GAN 相关提示词加载函数 ====================

def load_gan_decide_prompt(user_text: str) -> str:
    """加载 GAN 决策提示词"""
    template = load_prompt("gan_decide")
    return template.format(user_text=user_text)


def load_gan_topic_prompt(user_topic: str = "") -> str:
    """加载 GAN 话题生成提示词"""
    template = load_prompt("gan_topic")
    return template.format(user_topic=user_topic)


def load_gan_argument_a_prompt(topic: str) -> str:
    """加载 GAN 正方论点提示词"""
    template = load_prompt("gan_argument_a")
    return template.format(topic=topic)


def load_gan_argument_b_prompt(topic: str, argument_a: str, stop_marker: str = "DONE") -> str:
    """加载 GAN 反方论点提示词"""
    template = load_prompt("gan_argument_b")
    return template.format(topic=topic, argument_a=argument_a, stop_marker=stop_marker)


def load_gan_synthesis_prompt(topic: str, argument_a: str) -> str:
    """加载 GAN 综合提示词"""
    template = load_prompt("gan_synthesis")
    return template.format(topic=topic, argument_a=argument_a)
