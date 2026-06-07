from llm import chat

def summarize_memory(messages):
    joined = "\n".join(messages[-50:])

    prompt = f"""
Summarize the important long-term information.

Focus on:
- user personality
- important events
- emotional patterns
- beliefs
- ongoing topics

Conversation:
{joined}

Summary:
"""

    return chat(prompt)
