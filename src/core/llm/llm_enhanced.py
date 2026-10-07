from llm import chat, chat_stream

def generate_with_emotion_feedback(prompt, emotion_monitor=None, max_tokens=None):
    """
    生成回應並根據情緒回饋進行後處理（可擴充）
    max_tokens: followup 輪可能需要生成長文檔內容（如寫 Word），
                顯式傳入以覆蓋 chat() 對雲端模型的 1024 默認上限。
    """
    kwargs = {}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    response = chat(prompt, **kwargs)
    adaptation = None
    if emotion_monitor:
        adaptation = emotion_monitor()
    return response, adaptation


def generate_with_emotion_feedback_stream(prompt, emotion_monitor=None, max_tokens=None):
    """
    流式生成回應並根據情緒回饋進行後處理
    返回生成器，逐token返回
    """
    kwargs = {}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    for token in chat_stream(prompt, **kwargs):
        yield token

    if emotion_monitor:
        emotion_monitor()
