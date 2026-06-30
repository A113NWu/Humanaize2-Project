# -*- coding: utf-8 -*-
"""
提示词管理器 - 从 txt 文件加载所有提示词
"""
import os
from typing import Optional

def _get_project_root():
    """获取项目根目录"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

PROMPTS_DIR = os.path.join(_get_project_root(), "prompt")

# 提示词文件映射
PROMPT_FILES = {
    "should_answer_user": "should_answer_user.txt",
    "should_use_gan": "should_use_gan.txt",
    "should_reconsider": "should_reconsider.txt",
    "should_proactively_speak": "should_proactively_speak.txt",
    "choose_response_topic": "choose_response_topic.txt",
    "break_silence": "break_silence.txt",
    "chat": "chat.txt",
    "agent": "agent_prompt.txt",  # 在 data 目录下
    # 新增提示词
    "followup": "followup_prompt.txt",
    "web_search_prefix": "web_search_prefix.txt",
    "chat_template": "chat_template.txt",
    "system_prompt": "system_prompt.txt",
    "reflection": "reflection_prompt.txt",
    "memory_summarizer": "memory_summarizer_prompt.txt",
    "distillation": "distillation_prompt.txt",
    "distillation_customize": "distillation_customize_prompt.txt",
    "self_improvement": "self_improvement_prompt.txt",
    "solve_mode_todo": "solve_mode_todo_prompt.txt",
    "solve_mode_summary": "solve_mode_summary_prompt.txt",
    "solve_mode_task": "solve_mode_task_prompt.txt",
    # Skill 相关
    "skill_main": "skill_prompt_main.txt",
    "skill_list": "skill_list_prompt.txt",
    "skill_execution": "skill_execution_prompt.txt",
    # Solve Prompt 相关
    "solve_main": "solve_prompt_main.txt",
    "solve_task_list": "solve_task_list.txt",
    "solve_task_execution": "solve_task_execution.txt",
    "solve_summary": "solve_summary.txt",
    # GAN 相关
    "gan_decide": "gan_decide.txt",
    "gan_topic": "gan_topic.txt",
    "gan_argument_a": "gan_argument_a.txt",
    "gan_argument_b": "gan_argument_b.txt",
    "gan_synthesis": "gan_synthesis.txt",
}


def _get_prompts_dir():
    """获取提示词目录"""
    return PROMPTS_DIR


def _get_data_dir():
    """获取 data 目录"""
    return os.path.dirname(__file__)


def load_prompt(prompt_name: str) -> str:
    """
    加载提示词
    
    Args:
        prompt_name: 提示词名称
        
    Returns:
        提示词内容
    """
    if prompt_name not in PROMPT_FILES:
        return ""
    
    filename = PROMPT_FILES[prompt_name]
    filepath = os.path.join(_get_prompts_dir(), filename)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Failed to load prompt {prompt_name}: {e}")
        return ""


# ==================== 通用提示词加载函数 ====================

def load_should_answer_user_prompt(user_text: str) -> str:
    """加载判断是否回答用户的提示词"""
    template = load_prompt("should_answer_user")
    return template.format(user_text=user_text)


def load_should_use_gan_prompt(user_text: str, context: str = "") -> str:
    """加载判断是否使用 GAN 的提示词"""
    template = load_prompt("should_use_gan")
    return template.format(user_text=user_text, context=context)


def load_should_reconsider_prompt(context: str) -> str:
    """加载判断是否需要重新考虑的提示词"""
    template = load_prompt("should_reconsider")
    return template.format(context=context)


def load_should_proactively_speak_prompt(gan_topic: str, gan_synthesis: str, context: str) -> str:
    """加载判断是否主动说话的提示词"""
    template = load_prompt("should_proactively_speak")
    return template.format(gan_topic=gan_topic, gan_synthesis=gan_synthesis, context=context)


def load_choose_response_topic_prompt(user_text: str, user_topic: str, gan_topic: str, gan_synthesis: str, similarity: float) -> str:
    """加载选择回复主题的提示词"""
    template = load_prompt("choose_response_topic")
    return template.format(
        user_text=user_text,
        user_topic=user_topic or "无",
        gan_topic=gan_topic or "无",
        gan_synthesis=gan_synthesis or "无",
        similarity=similarity
    )


def load_break_silence_prompt() -> str:
    """加载打破沉默的提示词"""
    return load_prompt("break_silence")


def load_chat_prompt() -> str:
    """加载聊天提示词"""
    return load_prompt("chat")


def load_agent_prompt() -> str:
    """加载 agent 提示词"""
    return load_prompt("agent")


# ==================== GAN 相关提示词加载函数 ====================

def load_gan_decide_prompt(user_text: str) -> str:
    """加载 GAN 决策提示词"""
    template = load_prompt("gan_decide")
    return template.format(user_text=user_text)


def load_gan_topic_prompt(user_topic: str = "") -> str:
    """加载 GAN 话题生成提示词"""
    template = load_prompt("gan_topic")
    return template.format(user_topic=user_topic)


def load_gan_argument_a_prompt(topic: str) -> str:
    """加载 GAN 正方论点提示词"""
    template = load_prompt("gan_argument_a")
    return template.format(topic=topic)


def load_gan_argument_b_prompt(topic: str, argument_a: str, stop_marker: str = "DONE") -> str:
    """加载 GAN 反方论点提示词"""
    template = load_prompt("gan_argument_b")
    return template.format(topic=topic, argument_a=argument_a, stop_marker=stop_marker)


def load_gan_synthesis_prompt(topic: str, argument_a: str) -> str:
    """加载 GAN 综合提示词"""
    template = load_prompt("gan_synthesis")
    return template.format(topic=topic, argument_a=argument_a)


# ==================== 新增提示词加载函数 ====================

def load_followup_prompt(command_output: str, user_text: str) -> str:
    """加载命令执行后的跟进提示词"""
    template = load_prompt("followup")
    return template.format(command_output=command_output, user_text=user_text)


def load_web_search_prefix_prompt(search_summary: str) -> str:
    """加载网络搜索结果前缀提示词"""
    template = load_prompt("web_search_prefix")
    return template.format(search_summary=search_summary)


def load_chat_template_prompt() -> str:
    """加载聊天模板提示词"""
    return load_prompt("chat_template")


def load_system_prompt() -> str:
    """加载系统提示词"""
    return load_prompt("system_prompt")


def load_reflection_prompt(conversation_text: str) -> str:
    """加载对话反思提示词"""
    template = load_prompt("reflection")
    return template.format(conversation_text=conversation_text)


def load_memory_summarizer_prompt(conversation_text: str) -> str:
    """加载记忆摘要提示词"""
    template = load_prompt("memory_summarizer")
    return template.format(conversation_text=conversation_text)


def load_distillation_prompt(topic: str, knowledge_points: list) -> str:
    """加载知识蒸馏提示词"""
    template = load_prompt("distillation")
    return template.format(
        topic=topic,
        knowledge_points='\n'.join(f'- {kp}' for kp in knowledge_points[:5])
    )


def load_distillation_customize_prompt(base_prompt: str, user_input: str) -> str:
    """加载知识蒸馏定制提示词"""
    template = load_prompt("distillation_customize")
    return template.format(base_prompt=base_prompt, user_input=user_input)


def load_self_improvement_prompt(preferred_topics: str, recommended_strategy: str, 
                                  sentiment: str, sentiment_score: float, 
                                  performance_issues: list, skill_suggestion: str) -> str:
    """加载自我改进提示词"""
    template = load_prompt("self_improvement")
    return template.format(
        preferred_topics=preferred_topics,
        recommended_strategy=recommended_strategy,
        sentiment=sentiment,
        sentiment_score=f"{sentiment_score:.2f}",
        performance_issues='\n'.join(f'- {issue}' for issue in performance_issues),
        skill_suggestion=skill_suggestion or '暂无特别建议'
    )


def load_solve_mode_todo_prompt(problem: str, reference_files: list, hsn_enabled: bool) -> str:
    """加载Solve模式任务列表提示词"""
    template = load_prompt("solve_mode_todo")
    return template.format(
        problem=problem,
        reference_files=', '.join(reference_files) if reference_files else 'None',
        hsn_enabled='Yes' if hsn_enabled else 'No'
    )


def load_solve_mode_summary_prompt(problem: str, results_text: str) -> str:
    """加载Solve模式总结提示词"""
    template = load_prompt("solve_mode_summary")
    return template.format(problem=problem, results_text=results_text)


def load_solve_mode_task_prompt(task_title: str, task_description: str, problem: str, hsn_context: str = "") -> str:
    """加载Solve模式任务解决提示词"""
    template = load_prompt("solve_mode_task")
    return template.format(
        task_title=task_title,
        task_description=task_description,
        problem=problem,
        hsn_context=hsn_context
    )


def load_skill_main_prompt(skills_list: str, skills_list_formatted: str, skills_count: int, language: str, user_request: str = "") -> str:
    """加载技能主提示词"""
    template = load_prompt("skill_main")
    return template.format(
        skills_list=skills_list,
        skills_list_formatted=skills_list_formatted,
        skills_count=skills_count,
        language=language,
        user_request=user_request or "（未指定）"
    )


def load_skill_list_prompt(skills_text: str) -> str:
    """加载技能列表提示词"""
    template = load_prompt("skill_list")
    return template.format(skills_text=skills_text)


def load_skill_execution_prompt(skill_name: str, skill_description: str) -> str:
    """加载技能执行提示词"""
    template = load_prompt("skill_execution")
    return template.format(
        skill_name=skill_name,
        skill_description=skill_description
    )


def load_solve_main_prompt(problem: str, reference_files: str = "无", hsn_context: str = "") -> str:
    """加载Solve模式主提示词"""
    template = load_prompt("solve_main")
    return template.format(
        problem=problem,
        reference_files=reference_files,
        hsn_context=hsn_context
    )


def load_solve_task_list_prompt(problem: str, reference_files: str = "无") -> str:
    """加载任务列表生成提示词"""
    template = load_prompt("solve_task_list")
    return template.format(
        problem=problem,
        reference_files=reference_files
    )


def load_solve_task_execution_prompt(problem: str, task_title: str, task_description: str, hsn_section: str = "") -> str:
    """加载任务执行提示词"""
    template = load_prompt("solve_task_execution")
    return template.format(
        problem=problem,
        task_title=task_title,
        task_description=task_description,
        hsn_section=hsn_section
    )


def load_solve_summary_prompt(problem: str, results_text: str) -> str:
    """加载总结生成提示词"""
    template = load_prompt("solve_summary")
    return template.format(
        problem=problem,
        results_text=results_text
    )
