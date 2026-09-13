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
