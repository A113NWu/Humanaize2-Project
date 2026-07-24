import os

LLAMA_SERVER = "http://127.0.0.1:8080"
LLAMA_SERVER_URL = f"{LLAMA_SERVER}/completion"
MODEL_NAME = "tinyllama.gguf"
MAX_TOKENS = 512
TEMPERATURE = 0.7
TOP_P = 0.9

UI_WIDTH = 1200
UI_HEIGHT = 900

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CONFIG_DIR)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
PERSONALITY_FILE = os.path.join(DATA_DIR, "personality.json")
THOUGHTS_FILE = os.path.join(DATA_DIR, "thoughts.json")
DECISIONS_FILE = os.path.join(DATA_DIR, "decisions.json")
EVOLUTION_FILE = os.path.join(DATA_DIR, "evolution.json")

MAX_MEMORY = 100
MAX_MEMORY_MESSAGES = MAX_MEMORY
MEMORY_SUMMARY_TRIGGER = 1000

DEFAULT_PERSONALITY = {
    "traits": {"curiosity": 0.7, "empathy": 0.5, "creativity": 0.6},
    "initial_prompt": "You are a friendly helpful AI."
}

SCREENSHOT_INTERVAL = 300  # seconds
REFLECTION_INTERVAL = 1800
AUTONOMOUS_CHECK_INTERVAL = 300
