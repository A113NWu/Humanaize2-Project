from llm import chat

def generate_with_emotion_feedback(prompt, emotion_monitor=None):
    """
    生成回應並根據情緒回饋進行後處理（可擴充）
    """
    response = chat(prompt)
    adaptation = None
    if emotion_monitor:
        adaptation = emotion_monitor()
    return response, adaptation
