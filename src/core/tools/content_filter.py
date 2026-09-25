"""共享內容過濾器 —— 所有對外發佈內容（社交發文、回覆）與閒置思考產出
在公開/記錄前都應經過這裡檢查，防止不當言論流出。

詞表來源：純文字文件，每行一個詞，支援 # 註釋與空白行。
預設路徑：<應用數據目錄>/sensitive_words.txt（可由環境變數
HUMANAIZE_SENSITIVE_WORDS 覆蓋，方便日後替換成加密文件的解密載入器）。

日後加密接入點：只需改寫 _load_raw_lines()，先解密再按行返回即可，
check()/sanitize() 的調用方無需改動。
"""

import os
import re
import threading
import time

try:
    from app_paths import app_data_dir
except ImportError:
    try:
        from core.app_paths import app_data_dir
    except ImportError:
        app_data_dir = None

try:
    from logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

_WORDS = []           # 已編譯的小寫敏感詞列表
_MTIME = 0.0          # 詞表文件修改時間（熱更新用）
_LOADED_PATH = None
_LOCK = threading.Lock()


def _word_file_path() -> str:
    override = os.environ.get("HUMANAIZE_SENSITIVE_WORDS", "").strip()
    if override:
        return override
    base = app_data_dir() if callable(app_data_dir) else "data"
    return os.path.join(base, "sensitive_words.txt")


def _load_raw_lines(path: str):
    """讀取詞表原始行。日後文件加密時，在此先解密再 splitlines 即可。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read().splitlines()
    except OSError:
        return []


def _reload_if_needed():
    global _WORDS, _MTIME, _LOADED_PATH
    path = _word_file_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        with _LOCK:
            _WORDS, _MTIME, _LOADED_PATH = [], 0.0, path
        return
    if path == _LOADED_PATH and mtime == _MTIME:
        return
    with _LOCK:
        words = []
        for line in _load_raw_lines(path):
            w = line.strip()
            if w and not w.startswith("#"):
                words.append(w.lower())
        _WORDS = sorted(set(words), key=len, reverse=True)  # 長詞優先，避免子串誤判
        _MTIME, _LOADED_PATH = mtime, path
    logger.info(f"[ContentFilter] loaded {len(_WORDS)} sensitive words from {path}")


def check(text: str):
    """檢查文本是否含敏感詞。返回 (是否安全, 命中的詞列表)。"""
    if not text:
        return True, []
    _reload_if_needed()
    if not _WORDS:
        return True, []
    low = text.lower()
    hits = [w for w in _WORDS if w in low]
    return (not hits), hits


def sanitize(text: str, mask: str = "***") -> str:
    """把命中詞替換為 mask；原樣返回安全文本。"""
    ok, hits = check(text)
    if ok:
        return text
    out = text
    for w in hits:
        out = re.sub(re.escape(w), mask, out, flags=re.I)
    return out


def guard(text: str, context: str = "") -> str:
    """發佈前守衛：含敏感詞時記日誌並返回清理後文本（供思考/日誌場景使用）。"""
    ok, hits = check(text)
    if ok:
        return text
    logger.warning(f"[ContentFilter] blocked {len(hits)} sensitive word(s) in {context or 'content'}")
    return sanitize(text)
