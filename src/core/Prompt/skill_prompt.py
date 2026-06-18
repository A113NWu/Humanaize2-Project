# -*- coding: utf-8 -*-
"""
技能系统相关的 Prompt
"""

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
        return ""

    prompts = {
        "en": """## Available Skills

You can use the following skills:

""",
        "zh": """## 可用技能

你可以使用以下技能：

""",
        "zh-TW": """## 可用技能

你可以使用以下技能：

""",
    }

    prompt = prompts.get(language, prompts["zh"])

    for skill in skills_list:
        prompt += f"- {skill['name']}: {skill['description']}\n"

    prompt += """
使用技能时，请输出JSON格式：{"skill": "技能名称", "input": "输入内容"}
不要添加其他文字，只输出JSON。
"""

    return prompt

def get_skill_execution_prompt(skill_name: str, skill_description: str) -> str:
    """
    获取技能执行的提示信息
    
    Args:
        skill_name: 技能名称
        skill_description: 技能描述
        
    Returns:
        技能执行提示
    """
    return f"""
正在执行技能: {skill_name}
描述: {skill_description}

请等待执行结果...
"""