from llm import chat

def generate_with_emotion_feedback(prompt, emotion_monitor=None):
    """
    生成回复并根据情绪反馈后处理（可扩展）
    """
    response = chat(prompt)
    adaptation = None
    if emotion_monitor:
        adaptation = emotion_monitor()
    return response, adaptation
