import os

try:
    from app_paths import app_data_dir
except ImportError:
    from core.app_paths import app_data_dir

LLAMA_SERVER = "http://127.0.0.1:8080"
LLAMA_SERVER_URL = f"{LLAMA_SERVER}/completion"
MODEL_NAME = "tinyllama.gguf"
MAX_TOKENS = 512
TEMPERATURE = 0.7
TOP_P = 0.9

UI_WIDTH = 1200
UI_HEIGHT = 900

# 打包態必須落在 exe 旁持久目錄；__file__ 相對路徑在 onefile 下指向
# 臨時解包目錄（進程退出即刪），會導致記憶/人格等狀態「重啟失憶」。
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = app_data_dir()

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
