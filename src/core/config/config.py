LLAMA_SERVER = "http://127.0.0.1:8080"
LLAMA_SERVER_URL = f"{LLAMA_SERVER}/completion"
MODEL_NAME = "gemma-4-E4B-it-ultra-uncensored-heretic-Q8_0.gguf"
MAX_TOKENS = 512
TEMPERATURE = 0.7
TOP_P = 0.9

UI_WIDTH = 1200
UI_HEIGHT = 900

MEMORY_FILE = "data/memory.json"
PERSONALITY_FILE = "data/personality.json"
THOUGHTS_FILE = "data/thoughts.json"
DECISIONS_FILE = "data/decisions.json"
EVOLUTION_FILE = "data/evolution.json"

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
