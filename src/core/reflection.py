import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm import chat
from data.prompts_manager import load_reflection_prompt

def reflect_on_conversation(conversation_text):
    prompt = load_reflection_prompt(conversation_text)
    return chat(prompt)
