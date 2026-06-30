import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import chat
from data.prompts_manager import load_memory_summarizer_prompt

def summarize_memory(messages):
    joined = "\n".join(messages[-50:])
    prompt = load_memory_summarizer_prompt(joined)
    return chat(prompt)
