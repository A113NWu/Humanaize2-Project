# -*- coding: utf-8 -*-
"""
Humanaize 2.0 - Enhanced GAN Mode
Two-phase execution: Planning + Step-by-step execution with supervision
"""

import os
import sys
import json
import re
import threading
import time
import platform

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import chat
from data.prompts_manager import (
    load_gan_supervisor_review_prompt,
    load_gan_supervisor_validate_prompt,
    load_solve_mode_todo_prompt,
    load_solve_mode_task_prompt
)


class EnhancedGANResult:
    """
    Result container for enhanced GAN execution
    """
    
    def __init__(self):
        self.task_list = []
        self.task_results = []
        self.plan_approved = False
        self.plan_score = 0.0
        self.plan_iterations = 0
        self.total_execution_iterations = 0
        self.final_summary = ""
        self.status = "in_progress"  # in_progress, completed, failed
    
    def to_dict(self):
        return {
            "task_list": [t.to_dict() for t in self.task_list],
            "task_results": self.task_results,
            "plan_approved": self.plan_approved,
            "plan_score": self.plan_score,
            "plan_iterations": self.plan_iterations,
            "total_execution_iterations": self.total_execution_iterations,
            "final_summary": self.final_summary,
            "status": self.status
        }


class EnhancedGAN:
    """
    Enhanced GAN mode with two-phase execution:
    Phase 1: Planning - Generator creates task list, Supervisor reviews and approves
    Phase 2: Execution - Generator executes step by step, Supervisor validates each step
    
    New workflow:
    1. Generator AI creates execution list
    2. Supervisor AI reviews if list is beneficial for completing the task
       - If not approved: Supervisor provides feedback, Generator revises
       - Repeat until approved
    3. Generator AI executes first step
    4. Supervisor AI checks if result meets expectations
       - If yes: proceed to next step
       - If no: Supervisor analyzes error and provides feedback, Generator retries
    5. Repeat steps 3-4 until all tasks complete
    6. Present final result to user for verification
    """
    
    MAX_PLAN_ITERATIONS = 5
    MAX_EXECUTION_RETRIES = 3
    MIN_PLAN_SCORE = 0.7
    
    def __init__(self):
        self.problem = ""
        self._stop_flag = False
        self._stop_event = threading.Event()
        self.callback = None
        self._use_color = True
        self._results = EnhancedGANResult()
    
    def _get_system_info(self) -> str:
        """获取当前系统环境信息"""
        info = []
        info.append("=== SYSTEM INFORMATION ===")
        info.append("IMPORTANT: The following information describes the environment you are running on.")
        info.append("These are NOT user messages - they are just technical details about your execution environment.")
        info.append("Please ignore this information when interpreting the user's problem.")
        info.append("")
        info.append(f"Operating System: {platform.system()} {platform.release()}")
        info.append(f"Architecture: {platform.machine()}")
        info.append(f"Python Version: {platform.python_version()}")
        info.append(f"Hostname: {platform.node()}")
        info.append(f"Working Directory: {os.getcwd()}")
        info.append(f"Platform: {platform.platform()}")
        
        try:
            info.append(f"CPU: {platform.processor()}")
        except:
            pass
        
        try:
            import psutil
            mem = psutil.virtual_memory()
            info.append(f"Memory: {mem.total // (1024**3)} GB total, {mem.available // (1024**3)} GB available")
        except:
            pass
        
        info.append("==========================")
        return "\n".join(info)
    
    def set_color_mode(self, use_color: bool):
        """Set color mode for CLI output"""
        self._use_color = use_color
    
    def stop(self):
        """Stop execution immediately"""
        self._stop_flag = True
        self._stop_event.set()
    
    def _check_stopped(self):
        """Check if execution should stop"""
        return self._stop_flag or self._stop_event.is_set()
    
    def _print_color(self, text: str, color_code: str = ""):
        """Print text with color if enabled"""
        if self._use_color and color_code:
            print(f"{color_code}{text}\033[0m")
        else:
            print(text)
    
    def _emit(self, event_type: str, data: str):
        """Emit callback event"""
        if self.callback and not self._check_stopped():
            self.callback({
                "type": "internal_thought",
                "thought": f"[Enhanced GAN - {event_type.replace('_', ' ').title()}] {data}",
                "thought_type": f"gan_{event_type}"
            })
    
    def _safe_call(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Safe LLM call with stop check"""
        if self._check_stopped():
            return ""
        
        try:
            result = chat(prompt, max_tokens=max_tokens, temperature=temperature)
            return result.strip() if result else ""
        except Exception as e:
            self._print_color(f"LLM call failed: {e}", "\033[38;5;196m")
            return ""
    
    def _parse_task_list(self, response: str):
        """Parse LLM response into task list"""
        tasks = []
        
        if not response or not response.strip():
            return tasks
        
        try:
            # 清理响应
            cleaned = response.strip()
            cleaned = re.sub(r'```json\s*', '', cleaned)
            cleaned = re.sub(r'```\s*', '', cleaned)
            cleaned = re.sub(r'\s*```', '', cleaned)
            cleaned = re.sub(r'<thinking>[\s\S]*?</thinking>', '', cleaned)
            cleaned = re.sub(r'<think>[\s\S]*?</think>', '', cleaned)
            
            # 尝试直接解析
            try:
                data = json.loads(cleaned)
                if isinstance(data, list):
                    for idx, item in enumerate(data, 1):
                        if isinstance(item, dict):
                            tasks.append({
                                "id": item.get('id', idx),
                                "title": item.get('title', f"Task {idx}"),
                                "description": item.get('description', "")
                            })
                    if tasks:
                        return tasks
            except (json.JSONDecodeError, ValueError):
                pass
            
            # 正则匹配 JSON 数组
            json_match = re.search(r'\[[\s\S]*\]', cleaned)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if isinstance(data, list):
                        for idx, item in enumerate(data, 1):
                            if isinstance(item, dict):
                                tasks.append({
                                    "id": item.get('id', idx),
                                    "title": item.get('title', f"Task {idx}"),
                                    "description": item.get('description', "")
                                })
                        if tasks:
                            return tasks
                except (json.JSONDecodeError, ValueError):
                    pass
            
            # 从截断的 JSON 中提取完整的任务对象
            object_pattern = re.compile(r'\{\s*"id"\s*:\s*\d+\s*,\s*"title"\s*:\s*"([^"]*)"\s*,\s*"description"\s*:\s*"([^"]*)"\s*\}')
            for match in object_pattern.finditer(cleaned):
                tasks.append({
                    "id": len(tasks) + 1,
                    "title": match.group(1) or f"Task {len(tasks) + 1}",
                    "description": match.group(2)
                })
            if tasks:
                return tasks
            
            # 更宽松的 JSON 对象提取
            loose_pattern = re.compile(r'"id"\s*:\s*(\d+)[^}]*?"title"\s*:\s*"([^"]*)"[^}]*?"description"\s*:\s*"([^"]*)"')
            for match in loose_pattern.finditer(cleaned):
                task_id = int(match.group(1))
                task_title = match.group(2) or f"Task {task_id}"
                task_desc = match.group(3)
                tasks.append({
                    "id": task_id,
                    "title": task_title,
                    "description": task_desc
                })
            if tasks:
                return tasks
            
            # 编号列表解析
            lines = response.split('\n')
            task_pattern = re.compile(r'^[\s]*[\d]+[\.\)][\s]+(.+)')
            for line in lines:
                match = task_pattern.match(line.strip())
                if match:
                    title = match.group(1).strip()
                    title = re.sub(r'^\*\*(.+?)\*\*$', r'\1', title)
                    if title and len(title) > 2:
                        tasks.append({
                            "id": len(tasks) + 1,
                            "title": title,
                            "description": ""
                        })
        except Exception as e:
            self._print_color(f"Failed to parse task list: {e}", "\033[38;5;196m")
        
        return tasks
    
    def _parse_supervisor_response(self, response: str) -> dict:
        """Parse supervisor AI response"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            self._print_color(f"Failed to parse supervisor response: {e}", "\033[38;5;196m")
        
        return {"approved": False, "passed": False, "score": 0.0, "feedback": "", "reason": "", "error_analysis": "", "suggestion": ""}
    
    def _check_llm_server(self, max_wait: int = 60) -> bool:
        """Check if LLM server is available, wait if needed"""
        try:
            from tools.tools import check_llm_server
            import time
            
            if check_llm_server():
                self._print_color("LLM server is available", "\033[38;5;46m")
                return True
            
            self._print_color("LLM server not available, waiting...", "\033[38;5;208m")
            
            for attempt in range(max_wait):
                time.sleep(1)
                if check_llm_server():
                    self._print_color("LLM server started successfully", "\033[38;5;46m")
                    return True
                
                if (attempt + 1) % 10 == 0:
                    self._print_color(f"Waiting for LLM server... ({attempt + 1}/{max_wait}s)", "\033[38;5;208m")
            
            self._print_color(f"LLM server failed to start within {max_wait} seconds", "\033[38;5;196m")
            return False
            
        except Exception as e:
            self._print_color(f"Failed to check LLM server: {str(e)}", "\033[38;5;196m")
            return False
    
    def phase1_plan(self, problem: str) -> bool:
        """
        Phase 1: Planning phase
        Generator creates task list, Supervisor reviews and approves
        """
        self.problem = problem
        self._results.plan_iterations = 0
        
        self._print_color("\n" + "="*70, "\033[38;5;39m")
        self._print_color("PHASE 1: Planning - Task List Generation & Review", "\033[38;5;39m")
        self._print_color("="*70 + "\n", "\033[38;5;39m")
        
        for iteration in range(self.MAX_PLAN_ITERATIONS):
            if self._check_stopped():
                break
            
            self._results.plan_iterations = iteration + 1
            
            self._print_color(f"\n--- Plan Iteration {iteration + 1}/{self.MAX_PLAN_ITERATIONS} ---", "\033[38;5;208m")
            
            if iteration == 0:
                self._print_color("Generator AI: Creating initial task list...", "\033[38;5;46m")
            else:
                self._print_color("Generator AI: Revising task list based on supervisor feedback...", "\033[38;5;46m")
            
            system_info = self._get_system_info()
            prompt = system_info + "\n\n" + load_solve_mode_todo_prompt(problem, [], False)
            if iteration > 0 and hasattr(self, '_last_plan_feedback'):
                prompt += f"\n\nPrevious feedback for revision:\n{self._last_plan_feedback}"
            
            response = self._safe_call(prompt, max_tokens=500, temperature=0.7)
            
            if not response:
                self._print_color("Generator AI failed to generate task list", "\033[38;5;196m")
                continue
            
            task_list = self._parse_task_list(response)
            
            if not task_list:
                self._print_color("Failed to parse task list", "\033[38;5;196m")
                continue
            
            self._print_color(f"\nGenerated {len(task_list)} tasks:", "\033[38;5;46m")
            for task in task_list:
                self._print_color(f"  [{task['id']}] {task['title']}", "\033[38;5;75m")
            
            self._print_color("\nSupervisor AI: Reviewing task list...", "\033[38;5;201m")
            
            task_list_text = json.dumps(task_list, indent=2, ensure_ascii=False)
            supervisor_prompt = load_gan_supervisor_review_prompt(problem, task_list_text)
            
            supervisor_response = self._safe_call(supervisor_prompt, max_tokens=500, temperature=0.3)
            
            if not supervisor_response:
                self._print_color("Supervisor AI failed to respond", "\033[38;5;196m")
                continue
            
            review_result = self._parse_supervisor_response(supervisor_response)
            approved = review_result.get("approved", False)
            score = review_result.get("score", 0.0)
            feedback = review_result.get("feedback", "")
            suggested_changes = review_result.get("suggested_changes", [])
            
            self._print_color(f"\nSupervisor Review Result:", "\033[38;5;201m")
            self._print_color(f"  Approved: {'YES' if approved else 'NO'}", "\033[38;5;46m" if approved else "\033[38;5;196m")
            self._print_color(f"  Score: {score:.2f}/1.0", "\033[38;5;75m")
            if feedback:
                self._print_color(f"  Feedback: {feedback[:200]}...", "\033[38;5;226m")
            if suggested_changes:
                self._print_color(f"  Suggested changes: {', '.join(suggested_changes[:3])}", "\033[38;5;226m")
            
            if approved and score >= self.MIN_PLAN_SCORE:
                self._print_color("\n✓ Task list approved by Supervisor!", "\033[38;5;46m")
                self._results.task_list = task_list
                self._results.plan_approved = True
                self._results.plan_score = score
                return True
            
            self._last_plan_feedback = feedback
            self._print_color("\nTask list needs revision, generating new list...", "\033[38;5;226m")
        
        self._print_color("\n✗ Failed to get approved task list after maximum iterations", "\033[38;5;196m")
        return False
    
    def phase2_execute(self) -> bool:
        """
        Phase 2: Execution phase
        Execute each task step by step with supervisor validation
        """
        if not self._results.task_list:
            self._print_color("No task list to execute", "\033[38;5;196m")
            return False
        
        self._print_color("\n" + "="*70, "\033[38;5;39m")
        self._print_color("PHASE 2: Execution - Step-by-step with Validation", "\033[38;5;39m")
        self._print_color("="*70 + "\n", "\033[38;5;39m")
        
        completed_tasks = []
        
        for task_idx, task in enumerate(self._results.task_list):
            if self._check_stopped():
                break
            
            self._print_color(f"\n{'─'*70}", "\033[38;5;244m")
            self._print_color(f"Task {task['id']}: {task['title']}", "\033[38;5;39m")
            self._print_color(f"Description: {task['description'][:100]}...", "\033[38;5;244m")
            
            retries = 0
            execution_result = None
            
            while retries < self.MAX_EXECUTION_RETRIES:
                if self._check_stopped():
                    break
                
                self._print_color(f"\n  Attempt {retries + 1}/{self.MAX_EXECUTION_RETRIES}", "\033[38;5;208m")
                
                self._print_color("  Generator AI: Executing task...", "\033[38;5;46m")
                
                previous_tasks_text = "\n".join(
                    f"- Task {t['id']}: {t['title']}" for t in completed_tasks
                ) if completed_tasks else "None"
                
                system_info = self._get_system_info()
                prompt = system_info + "\n\n" + load_solve_mode_task_prompt(
                    task['title'],
                    task['description'],
                    self.problem,
                    f"Previous tasks completed:\n{previous_tasks_text}"
                )
                
                if retries > 0 and hasattr(self, '_last_validation_feedback'):
                    prompt += f"\n\nPrevious validation feedback:\n{self._last_validation_feedback}"
                
                execution_result = self._safe_call(prompt, max_tokens=500, temperature=0.7)
                
                if not execution_result:
                    self._print_color("  Generator AI failed to execute", "\033[38;5;196m")
                    retries += 1
                    continue
                
                self._results.total_execution_iterations += 1
                
                self._print_color(f"\n  Execution Result:\n  {execution_result[:200]}...", "\033[38;5;75m")
                
                self._print_color("\n  Supervisor AI: Validating result...", "\033[38;5;201m")
                
                supervisor_prompt = load_gan_supervisor_validate_prompt(
                    self.problem,
                    task['id'],
                    task['title'],
                    task['description'],
                    previous_tasks_text,
                    execution_result
                )
                
                supervisor_response = self._safe_call(supervisor_prompt, max_tokens=500, temperature=0.3)
                
                if not supervisor_response:
                    self._print_color("  Supervisor AI failed to validate", "\033[38;5;196m")
                    retries += 1
                    continue
                
                validation_result = self._parse_supervisor_response(supervisor_response)
                passed = validation_result.get("passed", False)
                score = validation_result.get("score", 0.0)
                reason = validation_result.get("reason", "")
                error_analysis = validation_result.get("error_analysis", "")
                suggestion = validation_result.get("suggestion", "")
                
                self._print_color(f"\n  Validation Result:", "\033[38;5;201m")
                self._print_color(f"    Passed: {'YES' if passed else 'NO'}", "\033[38;5;46m" if passed else "\033[38;5;196m")
                self._print_color(f"    Score: {score:.2f}/1.0", "\033[38;5;75m")
                if reason:
                    self._print_color(f"    Reason: {reason[:150]}...", "\033[38;5;226m")
                
                if passed:
                    self._print_color("  ✓ Task validated successfully!", "\033[38;5;46m")
                    completed_tasks.append(task)
                    
                    task_result = {
                        "task_id": task['id'],
                        "task_title": task['title'],
                        "result": execution_result,
                        "validation_score": score,
                        "retry_count": retries
                    }
                    self._results.task_results.append(task_result)
                    break
                
                self._print_color("  ✗ Task validation failed", "\033[38;5;196m")
                if error_analysis:
                    self._print_color(f"    Error Analysis: {error_analysis[:150]}...", "\033[38;5;226m")
                if suggestion:
                    self._print_color(f"    Suggestion: {suggestion[:150]}...", "\033[38;5;226m")
                
                self._last_validation_feedback = error_analysis + "\n" + suggestion
                retries += 1
            
            if retries >= self.MAX_EXECUTION_RETRIES:
                self._print_color(f"\n  ✗ Failed to complete task after {self.MAX_EXECUTION_RETRIES} attempts", "\033[38;5;196m")
                task_result = {
                    "task_id": task['id'],
                    "task_title": task['title'],
                    "result": execution_result or "Failed",
                    "validation_score": 0.0,
                    "retry_count": retries
                }
                self._results.task_results.append(task_result)
        
        self._results.status = "completed" if len(completed_tasks) == len(self._results.task_list) else "partial"
        return True
    
    def generate_final_summary(self) -> str:
        """Generate final summary of all task results"""
        self._print_color("\n" + "="*70, "\033[38;5;39m")
        self._print_color("FINAL SUMMARY & USER VERIFICATION", "\033[38;5;39m")
        self._print_color("="*70 + "\n", "\033[38;5;39m")
        
        self._print_color(f"Problem: {self.problem}", "\033[38;5;75m")
        self._print_color(f"\nPlan iterations: {self._results.plan_iterations}", "\033[38;5;244m")
        self._print_color(f"Plan score: {self._results.plan_score:.2f}/1.0", "\033[38;5;244m")
        self._print_color(f"Execution iterations: {self._results.total_execution_iterations}", "\033[38;5;244m")
        
        self._print_color(f"\nTotal tasks: {len(self._results.task_list)}", "\033[38;5;75m")
        completed_count = sum(1 for r in self._results.task_results if r.get("validation_score", 0) > 0)
        self._print_color(f"Completed tasks: {completed_count}", "\033[38;5;46m")
        
        if self._results.task_results:
            avg_score = sum(r.get("validation_score", 0) for r in self._results.task_results) / len(self._results.task_results)
            self._print_color(f"Average validation score: {avg_score:.2f}/1.0", "\033[38;5;75m")
        
        self._print_color("\n--- Task Results Summary ---", "\033[38;5;201m")
        for result in self._results.task_results:
            status_icon = "✓" if result.get("validation_score", 0) > 0 else "✗"
            color = "\033[38;5;46m" if result.get("validation_score", 0) > 0 else "\033[38;5;196m"
            self._print_color(f"{status_icon} [{result['task_id']}] {result['task_title']}", color)
            self._print_color(f"    Score: {result['validation_score']:.2f} | Retries: {result['retry_count']}", "\033[38;5;244m")
        
        self._print_color("\n--- Verification Required ---", "\033[38;5;208m")
        self._print_color("Please review the above results and provide feedback.", "\033[38;5;244m")
        
        self._results.final_summary = f"Problem: {self.problem}\n\n" \
            f"Tasks completed: {completed_count}/{len(self._results.task_list)}\n" \
            f"Average validation score: {avg_score:.2f}/1.0"
        
        return self._results.final_summary
    
    def run(self, problem: str) -> EnhancedGANResult:
        """Run the complete enhanced GAN workflow"""
        self._results = EnhancedGANResult()
        
        self._print_color("\n" + "="*70, "\033[38;5;39m")
        self._print_color("ENHANCED GAN MODE - Two-Phase Execution", "\033[38;5;39m")
        self._print_color("="*70 + "\n", "\033[38;5;39m")
        
        self._print_color(f"Problem: {problem}", "\033[38;5;75m")
        
        if not self._check_llm_server():
            self._results.status = "failed"
            self._results.error = "LLM server is not available"
            return self._results
        
        if not self.phase1_plan(problem):
            self._results.status = "failed"
            return self._results
        
        if not self.phase2_execute():
            return self._results
        
        self.generate_final_summary()
        
        return self._results


# ==================== Test ====================

if __name__ == "__main__":
    print("Testing Enhanced GAN Mode...")
    
    enhanced_gan = EnhancedGAN()
    enhanced_gan.set_color_mode(True)
    
    problem = "How can we improve customer satisfaction for an e-commerce website?"
    
    try:
        result = enhanced_gan.run(problem)
        print(f"\nFinal status: {result.status}")
        print(f"Plan approved: {result.plan_approved}")
        print(f"Plan score: {result.plan_score}")
        print(f"Task results: {len(result.task_results)}")
    except KeyboardInterrupt:
        enhanced_gan.stop()
        print("\nExecution interrupted by user")
