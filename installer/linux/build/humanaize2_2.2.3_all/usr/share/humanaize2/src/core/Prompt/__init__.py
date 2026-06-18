# -*- coding: utf-8 -*-
"""
Prompt 模块索引文件
统一管理所有 Prompt
"""

from .chat_prompt import *
from .solve_prompt import *
from .skill_prompt import *

__all__ = [
    # chat_prompt
    'get_chat_prompt',
    'get_system_prompt',
    
    # solve_prompt
    'get_task_list_prompt',
    'get_task_execution_prompt',
    'get_summary_prompt',
    
    # skill_prompt
    'get_skills_prompt',
    'get_skill_execution_prompt',
]