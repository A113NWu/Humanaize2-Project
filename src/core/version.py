# -*- coding: utf-8 -*-
"""
Humanaize 2.0 版本管理模块
统一管理版本号，从 config/version.json 读取。

查找順序（開發態/打包態均適用）：
  1. 打包後可執行文件同目錄的 config/version.json（綠色版/安裝目錄，可被用戶更新）
  2. PyInstaller onefile 解包目錄 _MEIPASS/config/version.json（安裝包內置）
  3. 項目倉庫 config/version.json（開發態）
  4. Linux 系统目录 / 当前目录兜底
"""

import json
import os
import sys

# 版本信息缓存
_version_cache = None

# 找不到任何 version.json 时的兜底版本（发布前随版本號一併更新）
FALLBACK_VERSION = "2.3.2"


def _candidate_paths():
    """返回所有可能的 version.json 路徑（按優先級排序）"""
    here = os.path.dirname(os.path.abspath(__file__))
    paths = []

    # 打包態：可執行文件同目錄（便於用戶/更新器替換）
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        paths.append(os.path.join(exe_dir, "config", "version.json"))

    # 打包態：onefile 解包目錄
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        paths.append(os.path.join(meipass, "config", "version.json"))

    # 開發態：項目根目錄（src/core/version.py 向上三级）
    paths.append(os.path.join(here, "..", "..", "..", "config", "version.json"))
    paths.append(os.path.join(here, "..", "..", "config", "version.json"))

    # Linux 安装目录
    paths.append("/usr/share/humanaize2/config/version.json")
    paths.append("/usr/local/share/humanaize2/config/version.json")

    # 模块同目录兜底
    paths.append(os.path.join(here, "version.json"))
    paths.append(os.path.join(here, "..", "version.json"))
    return paths


def _load_version_json():
    """讀取第一個可用的 version.json，返回 dict；全部失敗返回 None"""
    for version_file in _candidate_paths():
        try:
            if not os.path.exists(version_file):
                continue
            with open(version_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return None


def get_version() -> str:
    """
    从version.json获取当前版本号

    Returns:
        str: 版本号字符串，如 "2.3.0"
    """
    global _version_cache

    if _version_cache is not None:
        return _version_cache

    data = _load_version_json()
    if isinstance(data, dict):
        _version_cache = str(data.get("version") or FALLBACK_VERSION)
    else:
        _version_cache = FALLBACK_VERSION
    return _version_cache


def get_version_info() -> dict:
    """
    获取完整的版本信息

    Returns:
        dict: 包含version、last_updated、release_notes等字段的字典
    """
    data = _load_version_json()
    if isinstance(data, dict) and data.get("version"):
        return data

    return {
        "version": FALLBACK_VERSION,
        "last_updated": "",
        "release_notes": f"v{FALLBACK_VERSION}",
    }


def get_user_agent() -> str:
    """
    获取用于HTTP请求的User-Agent字符串

    Returns:
        str: User-Agent字符串，如 "Humanaize2/2.3.0"
    """
    return f"Humanaize2/{get_version()}"


def get_update_checker_agent() -> str:
    """获取更新检查器的User-Agent"""
    return f"Humanaize2-Update-Checker/{get_version()}"


def get_downloader_agent() -> str:
    """获取下载器的User-Agent"""
    return f"Humanaize2-Downloader/{get_version()}"


def get_model_downloader_agent() -> str:
    """获取模型下载器的User-Agent"""
    return f"Humanaize2-Model-Downloader/{get_version()}"


# 清除版本缓存（用于测试或重新加载）
def clear_cache():
    """清除版本信息缓存"""
    global _version_cache
    _version_cache = None


# 如果需要立即获取版本，可以在这里打印
if __name__ == "__main__":
    print(f"当前版本: {get_version()}")
    print(f"版本信息: {get_version_info()}")
    print(f"User-Agent: {get_user_agent()}")
