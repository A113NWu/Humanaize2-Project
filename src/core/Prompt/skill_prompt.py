# -*- coding: utf-8 -*-
"""
Humanaize 2.0 技能系统 Prompt - 使用 Lovable 2.0 格式
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.prompts_manager import (
    load_skill_main_prompt,
    load_skill_list_prompt,
    load_skill_execution_prompt
)


def get_skills_prompt(skills_list: list, language: str = "zh") -> str:
    """
    获取技能列表的 prompt
    
    Args:
        skills_list: 技能列表，每个技能包含 name 和 description
        language: 语言（zh/en/zh-TW）
        
    Returns:
        格式化的技能提示 prompt
    """
    if not skills_list:
        return "目前没有可用的技能。"

    skills_text = ""
    for skill in skills_list:
        skills_text += f"- **{skill['name']}**: {skill['description']}\n"

    return load_skill_list_prompt(skills_text)

def get_skills_prompt_advanced(skills_list: list, language: str = "zh", user_request: str = "") -> str:
    """
    获取技能列表的 prompt (Lovable格式)
    
    Args:
        skills_list: 技能列表
        language: 语言
        user_request: 用户请求
        
    Returns:
        Lovable格式的技能提示
    """
    skills_list_formatted = "\n".join([
        f"- **{skill['name']}**: {skill['description']}"
        for skill in skills_list
    ]) if skills_list else "无"

    skills_count = len(skills_list) if skills_list else 0
    
    lang_map = {
        "en": "English",
        "zh": "简体中文",
        "zh-TW": "繁體中文"
    }
    
    return load_skill_main_prompt(
        skills_list=skills_list_formatted,
        skills_list_formatted=skills_list_formatted,
        skills_count=skills_count,
        language=lang_map.get(language, "简体中文"),
        user_request=user_request or "（未指定）"
    )


def get_skill_execution_prompt(skill_name: str, skill_description: str) -> str:
    """
    获取技能执行的提示信息
    
    Args:
        skill_name: 技能名称
        skill_description: 技能描述
        
    Returns:
        技能执行提示
    """
    return load_skill_execution_prompt(skill_name, skill_description)
