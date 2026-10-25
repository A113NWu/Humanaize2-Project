# -*- coding: utf-8 -*-
"""
Prompt 模块索引文件
统一管理所有 Prompt
"""

from .chat_prompt import (
    get_chat_prompt,
    get_system_prompt,
    get_break_silence_prompt,
)
from .solve_prompt import (
    get_task_list_prompt,
    get_task_execution_prompt,
    get_summary_prompt,
)
from .skill_prompt import (
    get_skills_prompt,
    get_skills_prompt_advanced,
    get_skill_execution_prompt,
)

__all__ = [
    # chat_prompt
    'get_chat_prompt',
    'get_system_prompt',
    'get_break_silence_prompt',

    # solve_prompt
    'get_task_list_prompt',
    'get_task_execution_prompt',
    'get_summary_prompt',

    # skill_prompt
    'get_skills_prompt',
    'get_skills_prompt_advanced',
    'get_skill_execution_prompt',
]
