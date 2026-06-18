# -*- coding: utf-8 -*-
"""
Solve Mode 相关的 Prompt
"""

def get_task_list_prompt(problem: str, reference_files: list = None) -> str:
    """
    获取生成任务列表的 prompt
    
    Args:
        problem: 待解决的问题
        reference_files: 参考文件列表
        
    Returns:
        格式化的任务列表生成 prompt
    """
    references = ', '.join(reference_files) if reference_files else '无'
    
    return f"""
我需要解决这个问题：{problem}

参考文件：{references}

请帮我生成一个任务列表来解决这个问题。

输出格式要求：
- 只输出JSON数组
- 每个任务包含：id(数字), title(简短标题), description(详细描述)
- 按执行顺序排列
- 任务数量不要超过5个

示例输出：
[
  {"id": 1, "title": "分析问题", "description": "理解问题的核心需求和背景"},
  {"id": 2, "title": "收集信息", "description": "收集相关资料和数据"}
]

请直接输出JSON，不要添加额外文字。
"""

def get_task_execution_prompt(problem: str, task_title: str, task_description: str, hsn_context: str = "") -> str:
    """
    获取执行单个任务的 prompt
    
    Args:
        problem: 原始问题
        task_title: 任务标题
        task_description: 任务描述
        hsn_context: HSN协作上下文
        
    Returns:
        格式化的任务执行 prompt
    """
    return f"""
问题: {problem}

当前任务: {task_title}
任务描述: {task_description}

{hsn_context}

请直接给出这个任务的解决方案或分析，不要超过300字。
"""

def get_summary_prompt(problem: str, results_text: str) -> str:
    """
    获取生成总结的 prompt
    
    Args:
        problem: 原始问题
        results_text: 任务执行结果
        
    Returns:
        格式化的总结生成 prompt
    """
    return f"""
问题: {problem}

任务执行结果:
{results_text}

请用中文给出一个简洁的总结，不超过300字。
"""