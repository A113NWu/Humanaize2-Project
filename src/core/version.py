# -*- coding: utf-8 -*-
"""
Humanaize 2.0 版本管理模块
统一管理版本号，从version.json读取
"""

import json
import os

# 版本信息缓存
_version_cache = None

def get_version() -> str:
    """
    从version.json获取当前版本号
    
    Returns:
        str: 版本号字符串，如 "2.2.3"
    """
    global _version_cache
    
    if _version_cache is not None:
        return _version_cache
    
    # 查找version.json的多个可能位置
    possible_paths = [
        # 项目根目录
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "version.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "version.json"),
        # 安装目录
        "/usr/share/humanaize2/config/version.json",
        "/usr/local/share/humanaize2/config/version.json",
        # 当前目录
        os.path.join(os.path.dirname(__file__), "version.json"),
        os.path.join(os.path.dirname(__file__), "..", "version.json"),
    ]
    
    for version_file in possible_paths:
        if os.path.exists(version_file):
            try:
                with open(version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _version_cache = data.get("version", "2.2.3")
                    return _version_cache
            except Exception:
                continue
    
    # 如果都找不到，返回默认值
    _version_cache = "2.2.3"
    return _version_cache

def get_version_info() -> dict:
    """
    获取完整的版本信息
    
    Returns:
        dict: 包含version、last_updated、release_notes等字段的字典
    """
    # 查找version.json的多个可能位置
    possible_paths = [
        # 项目根目录
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "version.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "version.json"),
        # 安装目录
        "/usr/share/humanaize2/config/version.json",
        "/usr/local/share/humanaize2/config/version.json",
        # 当前目录
        os.path.join(os.path.dirname(__file__), "version.json"),
        os.path.join(os.path.dirname(__file__), "..", "version.json"),
    ]
    
    default_info = {
        "version": "2.2.3",
        "last_updated": "2026-06-16T00:00:00.000000",
        "release_notes": "v2.2.3"
    }
    
    for version_file in possible_paths:
        if os.path.exists(version_file):
            try:
                with open(version_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    
    return default_info

def get_user_agent() -> str:
    """
    获取用于HTTP请求的User-Agent字符串
    
    Returns:
        str: User-Agent字符串，如 "Humanaize2-Update-Checker/2.2.3"
    """
    return f"Humanaize2/{get_version()}"

def get_update_checker_agent() -> str:
    """
    获取更新检查器的User-Agent
    
    Returns:
        str: User-Agent字符串
    """
    return f"Humanaize2-Update-Checker/{get_version()}"

def get_downloader_agent() -> str:
    """
    获取下载器的User-Agent
    
    Returns:
        str: User-Agent字符串
    """
    return f"Humanaize2-Downloader/{get_version()}"

def get_model_downloader_agent() -> str:
    """
    获取模型下载器的User-Agent
    
    Returns:
        str: User-Agent字符串
    """
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
