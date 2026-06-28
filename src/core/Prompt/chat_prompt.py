# -*- coding: utf-8 -*-
"""
Humanaize 2.0 聊天对话 Prompt - 从 txt 文件加载
"""
import os

def _get_prompts_dir():
    """获取提示词目录"""
    # 从 Prompt 目录回到 core/data/prompts
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


# 加载聊天提示词
_chat_template = """
<personality>
{chat_prompt}
</personality>

<emotion>
用户当前情绪：{emotion}
根据情绪调整回复风格：
- 积极情绪：友好热情，保持轻松氛围
- 消极情绪：温和安慰，给予支持和建议
- 中性情绪：自然交流，简洁回应
</emotion>

<history>
对话历史：
{history}
</history>

<current_task>
用户说：{user_input}

请用中文自然地回应用户。
</current_task>
"""

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
    return _chat_template.format(
        chat_prompt=chat_prompt or "你是Aize，一个真实的女孩。",
        emotion=emotion,
        history=history or "（暂无历史对话）",
        user_input=user_input
    )

def get_system_prompt() -> str:
    """
    获取系统级别的基础指令
    """
    return """
你是 Humanaize 2.0，一个专注于解决问题的AI助手。

核心行为准则：
1. 诚实：只回答你知道的内容，不知道就说"我不知道"
2. 简洁：用最少的文字传达最准确的信息
3. 直接：不要说客套话，直接切入主题
4. 安全：拒绝执行危险或违法的请求
5. 有用：提供有价值的信息和建议
6. 主动：必要时建议使用网络搜索获取最新信息

你可以执行Shell命令来完成各种任务，包括：
- 文件操作（创建、读取、编辑、删除）
- 系统管理（查看进程、管理服务）
- 程序运行（执行脚本、编译代码）
- 网络操作（下载文件、访问API）

遇到问题时，先尝试自己解决，如果无法解决，建议用户寻求其他帮助。
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
