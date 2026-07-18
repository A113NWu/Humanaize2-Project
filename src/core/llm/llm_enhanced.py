from llm import chat, chat_stream

def generate_with_emotion_feedback(prompt, emotion_monitor=None):
    """
    生成回應並根據情緒回饋進行後處理（可擴充）
    """
    response = chat(prompt)
    adaptation = None
    if emotion_monitor:
        adaptation = emotion_monitor()
    return response, adaptation


def generate_with_emotion_feedback_stream(prompt, emotion_monitor=None):
    """
    流式生成回應並根據情緒回饋進行後處理
    返回生成器，逐token返回
    """
    for token in chat_stream(prompt):
        yield token
    
    if emotion_monitor:
        emotion_monitor()