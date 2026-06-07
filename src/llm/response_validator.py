BAD_PATTERNS = [
    "请问你要知道了吗",
    "我是人工智能机器人",
    "作为AI",
    "AI语言模型"
]

def validate_response(text):

    if not text:
        return False

    if len(text.strip()) < 2:
        return False

    for pattern in BAD_PATTERNS:
        if pattern in text:
            return False

    return True