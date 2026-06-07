from llm import chat

def reflect_on_conversation(conversation_text):
    prompt = f"""
Reflect on this conversation.

Generate:
1. observations
2. emotional analysis
3. relationship changes
4. long-term implications

Conversation:
{conversation_text}

Reflection:
"""

    return chat(prompt)
