"""
统一回复清理模块 - 清理AI回复中的模板泄漏和格式标记

提供单一的清理入口，替换三处重复代码：
1. thinking_engine_api.py 的 clean_reply
2. thinking_engine.py 的 _clean_and_humanize_reply
3. gan_iteration.py 的 _create_synthesis 内联清理
"""

import re


def clean_reply(reply):
    """
    清理回复中的模板泄漏和格式标记
    
    Args:
        reply: 原始回复文本
        
    Returns:
        清理后的回复文本，如果清理后为空则返回空字符串
    """
    if not reply:
        return ""

    cleaned = str(reply)

    # 移除代码块标记
    cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
    cleaned = re.sub(r'`[^`]+`', '', cleaned)

    # 移除元数据和自我修正内容
    cleaned = re.sub(r'\*\([^)]*\)', '', cleaned)
    cleaned = re.sub(r'\*\*[^*]+\*\*', '', cleaned)
    cleaned = re.sub(r'\*[^*]+\*', '', cleaned)

    # 移除各种元数据标签
    cleaned = re.sub(r'(?i)self-correction[/\s]*refinement[^\n]*', '', cleaned)
    cleaned = re.sub(r'(?i)final desired output[^\n]*', '', cleaned)
    cleaned = re.sub(r'(?i)applying the rule[^\n]*', '', cleaned)
    cleaned = re.sub(r'(?i)result\s*:', '', cleaned)
    cleaned = re.sub(r'(?i)based on rules[^\n]*', '', cleaned)
    cleaned = re.sub(r'(?i)following the rules[^\n]*', '', cleaned)
    cleaned = re.sub(r'(?i)according to rules[^\n]*', '', cleaned)

    # 移除对话上下文泄漏内容
    cleaned = re.sub(r'(?i)recent\s+conversation\s*:\s*', '', cleaned)
    cleaned = re.sub(r'(?i)^user\s*:\s*', '', cleaned)
    cleaned = re.sub(r'(?i)^assistant\s*:\s*', '', cleaned)
    cleaned = re.sub(r'(?i)\nuser\s*:\s*', '\n', cleaned)
    cleaned = re.sub(r'(?i)\nassistant\s*:\s*', '\n', cleaned)

    # 移除模板分隔符和占位符
    cleaned = re.sub(r'-{3,}', '', cleaned)
    cleaned = re.sub(r'\*{3,}', '', cleaned)

    # 移除break_silence任务模板泄漏内容
    cleaned = re.sub(r'（请开始生成回复）', '', cleaned)
    cleaned = re.sub(r'(请开始生成回复)', '', cleaned)
    cleaned = re.sub(r'（开始生成回复）', '', cleaned)
    cleaned = re.sub(r'(开始生成回复)', '', cleaned)
    cleaned = re.sub(r'（假设没有对话上下文）', '', cleaned)
    cleaned = re.sub(r'(假设没有对话上下文)', '', cleaned)
    cleaned = re.sub(r'（假设这是第一次对话，没有上下文）', '', cleaned)
    cleaned = re.sub(r'(假设这是第一次对话，没有上下文)', '', cleaned)
    cleaned = re.sub(r'现在开始生成回复[：:]', '', cleaned)
    cleaned = re.sub(r'现在开始，没有上下文。', '', cleaned)
    cleaned = re.sub(r'现在，我没有上下文[，,]所以我要用一个自然的开场白。', '', cleaned)
    cleaned = re.sub(r'如果上下文是空的，就主动开启一个话题。', '', cleaned)
    cleaned = re.sub(r'现在开始你的回复。', '', cleaned)
    cleaned = re.sub(r'延续对话。', '', cleaned)

    # 移除任务模板标签
    cleaned = re.sub(r'\*\*当前任务是[：:][^\n]*\n?', '', cleaned)
    cleaned = re.sub(r'\*\*当前上下文[：:][^\n]*\n?', '', cleaned)
    cleaned = re.sub(r'\*\*你的回复[（(]Aize的风格[)）][：:][^\n]*\n?', '', cleaned)
    cleaned = re.sub(r'\*\*最终回复应该像这样[：:][^\n]*\n?', '', cleaned)
    cleaned = re.sub(r'\*\*最终生成回复[：:][^\n]*\n?', '', cleaned)
    cleaned = re.sub(r'\*\*请开始生成回复\*\*', '', cleaned)
    cleaned = re.sub(r'\*\*请根据本次的辩论话题生成论点和结论。\*\*', '', cleaned)
    cleaned = re.sub(r'\*\*请将您的[^\n]*输入给我[^\n]*\n?', '', cleaned)

    # 移除GAN模板泄漏
    cleaned = re.sub(r'请根据本次的辩论话题生成论点和结论[。.]?', '', cleaned)
    cleaned = re.sub(r'请将您的[^\n]*输入给我[^\n]*', '', cleaned)
    cleaned = re.sub(r'请提供你的用户问题[。.]?', '', cleaned)
    cleaned = re.sub(r'话题[：:]\s*[^\n]*', '', cleaned)
    cleaned = re.sub(r'讨论的论点[：:]\s*[^\n]*', '', cleaned)
    cleaned = re.sub(r'输入话题[：:]\s*[^\n]*', '', cleaned)
    cleaned = re.sub(r'输入论点[：:]\s*[^\n]*', '', cleaned)
    cleaned = re.sub(r'输出[：:]\s*', '', cleaned)
    cleaned = re.sub(r'示例[：:]?\s*[^\n]*', '', cleaned)

    # 清理多余的空白和换行
    cleaned = re.sub(r'\n+', '\n', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def validate_coherence(text, topic=""):
    """
    验证文本的一致性和相关性，检查是否存在模板泄漏
    
    Args:
        text: 要验证的文本
        topic: 参考话题（用于相关性检查）
        
    Returns:
        bool: True表示文本一致且相关，False表示存在问题
    """
    if not text:
        return False

    # 检查模板泄漏模式
    leak_patterns = [
        "请提供你的用户问题",
        "请开始生成回复",
        "现在开始生成回复",
        "假设没有对话上下文",
        "**当前任务是**",
        "**你的回复**",
        "Topic:",
        "Argument:",
        "Conclusion:",
        "请根据本次的辩论话题生成论点和结论",
        "请将您的",
        "输入给我",
        "输入话题",
        "输入论点",
        "输出：",
        "示例："
    ]

    for pattern in leak_patterns:
        if pattern in text:
            return False

    # 如果有话题，检查相关性
    if topic:
        topic_keywords = set(topic.lower().split())
        text_keywords = set(text.lower().split())

        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', 'that', 'this', 'is', 'are', 'and', 'or', 'but', 'not', 'the', 'a', 'an'}
        topic_keywords = topic_keywords - stop_words
        text_keywords = text_keywords - stop_words

        if topic_keywords:
            overlap = len(topic_keywords & text_keywords)
            if overlap >= 2:
                return True

            if len(text) >= 100 and '.' in text and ',' in text:
                return True

            return False

    return True


def clean_and_validate(reply, topic=""):
    """
    清理并验证回复
    
    Args:
        reply: 原始回复文本
        topic: 参考话题（用于一致性验证）
        
    Returns:
        (str, bool): (清理后的文本, 是否通过验证)
    """
    cleaned = clean_reply(reply)
    is_valid = validate_coherence(cleaned, topic)
    return cleaned, is_valid
