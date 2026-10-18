"""應用持久化路徑的唯一來源。

歷史問題：ui_settings.json 的路徑在各模組中以 ``__file__`` 相對拼寫，
打包（frozen）後會解析進 ``sys._MEIPASS``——onefile 該目錄進程退出即刪，
onedir 對應 ``_internal`` 只讀緩存——導致網頁/GUI 保存的設置重啟後丟失，
且不同模組拼出的路徑並不一致（例如 thinking_engine 誤讀 core/data/）。

統一規則：
- 開發態：``<項目根>/src/core/ui/data/ui_settings.json``（歷史規範路徑）
- 打包態：``<exe 同目錄>/data/ui_settings.json``（與 cmd_config.json 同級，
  安裝目錄可寫）；若只讀則退回 ``~/.humanaize2/data/``
首次使用時自動把安裝包內置的默認設置複製到持久位置。
"""

import os
import re
import shutil
import sys

_SETTINGS_FILENAME = "ui_settings.json"


def _project_root() -> str:
    """本文件位於 <項目根>/src/core/app_paths.py，上溯三級即項目根。"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _is_writable_dir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, "._humanaize2_write_test")
        with open(probe, "w", encoding="utf-8"):
            pass
        os.remove(probe)
        return True
    except OSError:
        return False


def _frozen_data_dir() -> str:
    """打包態的可寫數據目錄：exe 旁 data/，只讀安裝退回 ~/.humanaize2/data。"""
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    install_data = os.path.join(exe_dir, "data")
    if _is_writable_dir(install_data):
        return install_data
    return os.path.join(os.path.expanduser("~"), ".humanaize2", "data")


def app_data_dir() -> str:
    """應用數據目錄（memory/personality 等運行時狀態）。

    開發態沿用項目根 data/；打包態為 exe 旁持久目錄——絕不能落進
    sys._MEIPASS（onefile 進程退出即刪，會造成「重啟失憶」）。
    """
    if getattr(sys, "frozen", False):
        return _frozen_data_dir()
    return os.path.join(_project_root(), "data")


def persistent_data_dir() -> str:
    """返回可持久讀寫的應用數據目錄（UI 設置所在）。

    開發態：``<項目根>/src/core/ui/data``（歷史規範路徑）
    打包態：與 app_data_dir 相同的 exe 旁持久目錄
    """
    if getattr(sys, "frozen", False):
        return _frozen_data_dir()
    return os.path.join(_project_root(), "src", "core", "ui", "data")


def _bundled_settings_candidates():
    """安裝包內置的默認設置可能位置（用於首次種植）。"""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "src", "core", "ui", "data", _SETTINGS_FILENAME))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "_internal", "src", "core", "ui", "data", _SETTINGS_FILENAME))
    return candidates


def get_settings_path() -> str:
    """取得 ui_settings.json 的持久路徑；文件不存在時用內置默認種植一份。"""
    data_dir = persistent_data_dir()
    target = os.path.join(data_dir, _SETTINGS_FILENAME)
    if not os.path.exists(target):
        for bundled in _bundled_settings_candidates():
            if bundled and os.path.isfile(bundled) and os.path.abspath(bundled) != os.path.abspath(target):
                try:
                    os.makedirs(data_dir, exist_ok=True)
                    shutil.copy2(bundled, target)
                    break
                except OSError:
                    continue
    return target


def _bundled_dirs(*rel_parts) -> list:
    """安裝包內同名資源目錄的候選位置（_MEIPASS 與 onedir _internal）。"""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, *rel_parts))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "_internal", *rel_parts))
    return [c for c in candidates if os.path.isdir(c)]


def _prompt_ver(path: str) -> int:
    """讀取種植文件首行的版本標記 @@PROMPT_VER:N@@，無標記視為 0（舊版種植）"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            first = f.readline(64)
        m = re.match(r"\s*@@PROMPT_VER:(\d+)@@", first)
        return int(m.group(1)) if m else 0
    except OSError:
        return 0


def seed_from_bundled(target_dir: str, bundled_dirs) -> int:
    """把捆綁目錄中的文件種植到 target_dir。

    規則：
    - 目標不存在 → 複製；
    - 目標已存在但捆綁版帶更高版本標記（@@PROMPT_VER:N@@ 首行）→
      先把舊文件備份為 <name>.user.bak（用戶若有自定義可找回），再覆蓋。
      這樣新版本附帶的提示詞更新能自動到達已安裝的用戶，而不會
      被「永不覆蓋」策略永久攔住（歷史 bug：Live2D motion 指令因此失傳）；
    - 其餘情況不動，保留用戶修改。

    返回新複製/更新的文件數。
    """
    copied = 0
    os.makedirs(target_dir, exist_ok=True)
    for src_dir in bundled_dirs:
        try:
            names = os.listdir(src_dir)
        except OSError:
            continue
        for name in names:
            src = os.path.join(src_dir, name)
            dst = os.path.join(target_dir, name)
            if not os.path.isfile(src):
                continue
            try:
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    copied += 1
                    continue
                src_ver = _prompt_ver(src)
                dst_ver = _prompt_ver(dst)
                if src_ver > dst_ver:
                    with open(src, "rb") as f:
                        src_bytes = f.read()
                    with open(dst, "rb") as f:
                        dst_bytes = f.read()
                    if src_bytes != dst_bytes:
                        try:
                            shutil.copy2(dst, os.path.join(target_dir, name + ".user.bak"))
                        except OSError:
                            pass
                        with open(dst, "wb") as f:
                            f.write(src_bytes)
                        copied += 1
            except OSError:
                pass
    return copied


def prompts_dir() -> str:
    """用戶可編輯的提示詞目錄。

    開發態：``<項目根>/prompt``（即源碼目錄本身）
    打包態：``<exe 同目錄>/Prompt``——首次運行把安裝包內置的默認提示詞
    種植進來，普通用戶即可直接編輯；刪除某文件時由調用方回退到捆綁默認。
    """
    if getattr(sys, "frozen", False):
        target = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "Prompt")
        seed_from_bundled(target, _bundled_dirs("prompt"))
        return target
    return os.path.join(_project_root(), "prompt")
