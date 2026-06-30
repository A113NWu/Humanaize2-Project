# -*- coding: utf-8 -*-
"""
Humanaize 2.0 Solve Mode Prompt - 使用 Lovable 2.0 格式
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.prompts_manager import (
    load_solve_main_prompt,
    load_solve_task_list_prompt,
    load_solve_task_execution_prompt,
    load_solve_summary_prompt
)


def get_task_list_prompt(problem: str, reference_files: list = None) -> str:
    """
    获取生成任务列表的 prompt (Lovable格式)
    
    Args:
        problem: 待解决的问题
        reference_files: 参考文件列表
        
    Returns:
        Lovable格式的任务列表生成 prompt
    """
    references = ', '.join(reference_files) if reference_files else '无'
    return load_solve_task_list_prompt(problem, references)

def get_task_execution_prompt(problem: str, task_title: str, task_description: str, hsn_context: str = "") -> str:
    """
    获取执行单个任务的 prompt (Lovable格式)
    
    Args:
        problem: 原始问题
        task_title: 任务标题
        task_description: 任务描述
        hsn_context: HSN协作上下文
        
    Returns:
        Lovable格式的任务执行 prompt
    """
    hsn_section = f"""
## HSN 协作信息

{hsn_context}

你可以利用这些协作信息来加速任务执行。
""" if hsn_context else ""
    return load_solve_task_execution_prompt(problem, task_title, task_description, hsn_section)

def get_summary_prompt(problem: str, results_text: str) -> str:
    """
    获取生成总结的 prompt (Lovable格式)
    
    Args:
        problem: 原始问题
        results_text: 任务执行结果
        
    Returns:
        Lovable格式的总结生成 prompt
    """
    return load_solve_summary_prompt(problem, results_text)
