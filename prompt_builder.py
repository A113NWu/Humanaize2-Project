from memory import build_history_string

def build_prompt(
    personality_context,
    memory,
    user_input,
    emotion=None
):

    history = build_history_string(memory)

    emotion_text = "neutral"

    if emotion:
        emotion_text = emotion.get("dominant", "neutral")

    return f"""
{personality_context}

Current user emotion: {emotion_text}

Conversation History:
{history}

User: {user_input}
Assistant:
"""