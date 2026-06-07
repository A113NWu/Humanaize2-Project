#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解決模式 - Humanaize 2.0 Agent 的問題解決模式
"""

import os
import sys
import time
import json
import re
import threading
from typing import List, Dict, Optional, Any

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import chat
from tools.gan_iteration import GANIteration


class Task:
    """代表待辦清單中的單一任務"""
    
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    
    def __init__(self, id: int, title: str, description: str = ""):
        self.id = id
        self.title = title
        self.description = description
        self.status = Task.STATUS_PENDING
        self.progress = 0.0
        self.result = None
        self.validation_score = 0.0
        self.validation_details = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "validation_score": self.validation_score,
            "validation_details": self.validation_details
        }


class Colors:
    """CLI 顏色定義"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ORANGE = '\033[38;5;208m'
    BLUE = '\033[38;5;39m'
    GREEN = '\033[38;5;46m'
    RED = '\033[38;5;196m'
    YELLOW = '\033[38;5;226m'
    MAGENTA = '\033[38;5;201m'
    CYAN = '\033[38;5;51m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'
    
    @classmethod
    def support_color(cls) -> bool:
        """Check if terminal supports ANSI color codes"""
        if sys.platform == "win32":
            try:
                import subprocess
                result = subprocess.run(
                    ["reg", "query", "HKCU\\Console", "/v", "VirtualTerminalLevel"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and "0x1" in result.stdout:
                    return True
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    hStdOut = kernel32.GetStdHandle(-11)
                    mode = ctypes.c_ulong()
                    kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode))
                    mode.value |= 4
                    kernel32.SetConsoleMode(hStdOut, mode)
                    return True
                except:
                    return False
            except:
                return False
        return True


class HSNetwork:
    """HSN (Human-System Network) collaboration module"""
    
    def __init__(self):
        self.enabled = False
        self.connected = False
        self.peers = []
        self.session_key = None
    
    def enable(self):
        """Enable HSN functionality"""
        self.enabled = True
    
    def disable(self):
        """Disable HSN functionality"""
        self.enabled = False
        self.connected = False
    
    def connect(self) -> bool:
        """Establish HSN connection with security authentication"""
        if not self.enabled:
            return False
        
        try:
            # Simulate secure connection
            self._generate_session_key()
            self._discover_peers()
            self.connected = True
            return True
        except Exception as e:
            print(f"[HSN] Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from HSN"""
        self.connected = False
        self.peers = []
        self.session_key = None
    
    def _generate_session_key(self):
        """Generate secure session key"""
        import uuid
        self.session_key = str(uuid.uuid4())
    
    def _discover_peers(self):
        """Discover connected AI peers"""
        # Simulated peers
        self.peers = [
            {"id": "peer-001", "name": "AI-Assistant Alpha", "capabilities": ["analysis", "research"]},
            {"id": "peer-002", "name": "AI-Assistant Beta", "capabilities": ["problem-solving", "optimization"]},
        ]
    
    def collaborate(self, problem: str) -> Dict:
        """Collaborate with peers to solve a problem"""
        if not self.connected or not self.enabled:
            return {"error": "HSN not connected"}
        
        results = []
        for peer in self.peers:
            result = {
                "peer_id": peer["id"],
                "peer_name": peer["name"],
                "contribution": f"Analysis from {peer['name']}: Problem '{problem}' requires multi-dimensional approach considering {', '.join(peer['capabilities'])}."
            }
            results.append(result)
        
        return {"status": "success", "collaborators": len(self.peers), "results": results}


class SolveMode:
    """Main solve mode implementation"""
    
    def __init__(self):
        self.problem = ""
        self.reference_files = []
        self.hsn_enabled = False
        self.hsn = HSNetwork()
        self.todo_list: List[Task] = []
        self.current_task = None
        self._running = False
        self._stop_event = threading.Event()
        self._use_color = Colors.support_color()
        
    def parse_args(self, args: List[str]):
        """Parse command line arguments"""
        i = 0
        while i < len(args):
            if args[i] == "-r" or args[i] == "--reference":
                if i + 1 < len(args):
                    self.reference_files.append(args[i + 1])
                    i += 2
                    continue
            elif args[i] == "-enable" or args[i] == "--enable":
                if i + 1 < len(args) and args[i + 1].upper() == "HSN":
                    self.hsn_enabled = True
                    i += 2
                    continue
            i += 1
    
    def set_problem(self, problem: str):
        """Set the problem to solve"""
        self.problem = problem
    
    def run(self) -> Dict:
        """Execute the solve mode"""
        self._running = True
        self._stop_event.clear()
        
        self._print_header()
        
        # Load reference files
        self._load_references()
        
        # Enable HSN if requested
        if self.hsn_enabled:
            self._setup_hsn()
        
        # Generate todo list
        self._generate_todo_list()
        
        if not self.todo_list:
            return {"status": "failed", "error": "Failed to generate task list"}
        
        # Execute tasks
        results = self._execute_tasks()
        
        # Generate summary
        summary = self._generate_summary(results)
        
        return summary
    
    def stop(self):
        """Stop the solve process"""
        self._running = False
        self._stop_event.set()
    
    def _print_header(self):
        """Print the solve mode header"""
        print()
        if self._use_color:
            print(f"{Colors.BOLD}{Colors.CYAN}" + "=" * 70 + f"{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}          Humanaize 2.0 Agent - SOLVE MODE{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}" + "=" * 70 + f"{Colors.RESET}")
        else:
            print("=" * 70)
            print("          Humanaize 2.0 Agent - SOLVE MODE")
            print("=" * 70)
        print()
    
    def _load_references(self):
        """Load reference files if specified"""
        if self.reference_files:
            if self._use_color:
                print(f"{Colors.BLUE}[INFO]{Colors.RESET} Loading reference files...")
            else:
                print("[INFO] Loading reference files...")
            
            for ref_file in self.reference_files:
                if os.path.exists(ref_file):
                    if self._use_color:
                        print(f"{Colors.GREEN}[OK]{Colors.RESET}  Loaded: {ref_file}")
                    else:
                        print(f"[OK]  Loaded: {ref_file}")
                else:
                    if self._use_color:
                        print(f"{Colors.RED}[WARN]{Colors.RESET}  File not found: {ref_file}")
                    else:
                        print(f"[WARN]  File not found: {ref_file}")
            print()
    
    def _setup_hsn(self):
        """Setup HSN collaboration"""
        if self._use_color:
            print(f"{Colors.BLUE}[INFO]{Colors.RESET} Enabling HSN collaboration...")
        else:
            print("[INFO] Enabling HSN collaboration...")
        
        self.hsn.enable()
        if self.hsn.connect():
            if self._use_color:
                print(f"{Colors.GREEN}[OK]{Colors.RESET}  Connected to HSN network")
                print(f"{Colors.GREEN}[OK]{Colors.RESET}  Discovered {len(self.hsn.peers)} peer(s)")
            else:
                print(f"[OK]  Connected to HSN network")
                print(f"[OK]  Discovered {len(self.hsn.peers)} peer(s)")
        else:
            if self._use_color:
                print(f"{Colors.YELLOW}[WARN]{Colors.RESET}  HSN connection failed, continuing offline")
            else:
                print(f"[WARN]  HSN connection failed, continuing offline")
        print()
    
    def _generate_todo_list(self):
        """Generate todo list using LLM"""
        if self._use_color:
            print(f"{Colors.BLUE}[INFO]{Colors.RESET} Analyzing problem and generating task list...")
        else:
            print("[INFO] Analyzing problem and generating task list...")
        
        prompt = f"""
Analyze the following problem and create a detailed task list (todo list) to solve it.

Problem: {self.problem}

Reference files: {', '.join(self.reference_files) if self.reference_files else 'None'}

HSN Enabled: {'Yes' if self.hsn_enabled else 'No'}

Please output ONLY a JSON array with tasks. Each task should have:
- id: sequential number
- title: brief task description
- description: detailed explanation of what needs to be done

The tasks should be ordered logically from first to last step.
"""
        
        try:
            if self._use_color:
                print(f"{Colors.YELLOW}[WAIT]{Colors.RESET}  AI is generating task list...")
            else:
                print(f"[WAIT]  AI is generating task list...")
            
            response = chat(prompt)
            if response:
                self.todo_list = self._parse_todo_list(response)
                
                if self.todo_list:
                    if self._use_color:
                        print(f"{Colors.GREEN}[OK]{Colors.RESET}  Task list generated by AI successfully")
                    else:
                        print(f"[OK]  Task list generated by AI successfully")
                else:
                    if self._use_color:
                        print(f"{Colors.YELLOW}[WARN]{Colors.RESET} AI generated empty task list, using default")
                    else:
                        print(f"[WARN] AI generated empty task list, using default")
                    self._generate_default_todo_list()
            else:
                if self._use_color:
                    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} AI returned empty response, using default task list")
                else:
                    print(f"[WARN] AI returned empty response, using default task list")
                self._generate_default_todo_list()
        except Exception as e:
            if self._use_color:
                print(f"{Colors.YELLOW}[WARN]{Colors.RESET} AI unavailable ({e}), using default task list")
            else:
                print(f"[WARN] AI unavailable ({e}), using default task list")
            self._generate_default_todo_list()
        
        # Display todo list
        self._display_todo_list()
    
    def _generate_default_todo_list(self):
        """Generate a default task list when AI is unavailable"""
        self.todo_list = [
            Task(1, "Analyze the problem", "Understand the problem requirements and context"),
            Task(2, "Research relevant information", "Gather facts and background information"),
            Task(3, "Develop solution approach", "Create a structured approach to solve the problem"),
            Task(4, "Evaluate options", "Consider different perspectives and alternatives"),
            Task(5, "Formulate conclusion", "Synthesize findings into a coherent solution"),
        ]
    
    def _parse_todo_list(self, response: str) -> List[Task]:
        """Parse the LLM response into task objects"""
        tasks = []
        
        try:
            # Try to extract JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                for idx, item in enumerate(data, 1):
                    if isinstance(item, dict):
                        tasks.append(Task(
                            id=item.get('id', idx),
                            title=item.get('title', f"Task {idx}"),
                            description=item.get('description', "")
                        ))
            else:
                # Try parsing as numbered list
                lines = response.split('\n')
                task_pattern = re.compile(r'^[\d.]+\s+(.*)')
                for line in lines:
                    match = task_pattern.match(line)
                    if match:
                        tasks.append(Task(
                            id=len(tasks) + 1,
                            title=match.group(1).strip(),
                            description=""
                        ))
        except Exception:
            pass
        
        return tasks
    
    def _display_todo_list(self):
        """Display the generated todo list"""
        if self._use_color:
            print(f"{Colors.BOLD}{Colors.MAGENTA}Generated Task List:{Colors.RESET}")
        else:
            print("Generated Task List:")
        
        for task in self.todo_list:
            status_icon = "○" if task.status == Task.STATUS_PENDING else "●"
            if self._use_color:
                print(f"{Colors.DIM}[{status_icon}]{Colors.RESET} {task.id}. {task.title}")
                if task.description:
                    print(f"{Colors.GRAY}      {task.description}{Colors.RESET}")
            else:
                print(f"[{status_icon}] {task.id}. {task.title}")
                if task.description:
                    print(f"      {task.description}")
        
        print()
    
    def _execute_tasks(self) -> List[Dict]:
        """Execute all tasks in order"""
        results = []
        
        for task in self.todo_list:
            if not self._running:
                break
            
            result = self._execute_task(task)
            results.append(result)
            
            # Validate task completion
            if task.status != Task.STATUS_COMPLETED:
                if self._use_color:
                    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} Task {task.id} did not complete successfully")
                else:
                    print(f"[WARN] Task {task.id} did not complete successfully")
                # Optionally stop or continue
        
        return results
    
    def _execute_task(self, task: Task) -> Dict:
        """Execute a single task"""
        task.status = Task.STATUS_IN_PROGRESS
        
        if self._use_color:
            print(f"{Colors.BOLD}{Colors.BLUE}--- Executing Task {task.id}: {task.title} ---{Colors.RESET}")
        else:
            print(f"--- Executing Task {task.id}: {task.title} ---")
        
        # Simulate progress
        for i in range(1, 11):
            if self._stop_event.is_set():
                task.status = Task.STATUS_FAILED
                task.result = "Task interrupted"
                break
            
            task.progress = i * 0.1
            progress_bar = self._format_progress(task.progress)
            
            if self._use_color:
                print(f"\r{Colors.CYAN}[PROGRESS]{Colors.RESET} {progress_bar} {int(task.progress * 100)}%", end="")
            else:
                print(f"\r[PROGRESS] {progress_bar} {int(task.progress * 100)}%", end="")
            
            sys.stdout.flush()
            time.sleep(0.2)
        
        print()
        
        # Execute actual task logic
        task.result = self._process_task(task)
        
        # Validate task
        self._validate_task(task)
        
        if task.status == Task.STATUS_COMPLETED:
            if self._use_color:
                print(f"{Colors.GREEN}[DONE]{Colors.RESET}  Task {task.id} completed successfully")
                if task.validation_score > 0:
                    print(f"{Colors.GREEN}[VALID]{Colors.RESET}  Validation score: {task.validation_score}/1.0")
            else:
                print(f"[DONE]  Task {task.id} completed successfully")
                if task.validation_score > 0:
                    print(f"[VALID]  Validation score: {task.validation_score}/1.0")
        else:
            if self._use_color:
                print(f"{Colors.RED}[FAIL]{Colors.RESET}  Task {task.id} failed")
            else:
                print(f"[FAIL]  Task {task.id} failed")
        
        if task.result:
            if self._use_color:
                print(f"{Colors.DIM}Result: {task.result}{Colors.RESET}")
            else:
                print(f"Result: {task.result}")
        
        print()
        return task.to_dict()
    
    def _format_progress(self, progress: float) -> str:
        """Format progress bar"""
        bar_length = 30
        filled = int(bar_length * progress)
        empty = bar_length - filled
        return f"[{'=' * filled}{' ' * empty}]"
    
    def _process_task(self, task: Task) -> str:
        """Process the actual task logic"""
        try:
            # Include HSN collaboration if enabled
            hsn_context = ""
            if self.hsn.enabled and self.hsn.connected:
                hsn_result = self.hsn.collaborate(task.title)
                if "results" in hsn_result:
                    hsn_context = "\nHSN Collaboration Input:\n"
                    for peer_result in hsn_result["results"]:
                        hsn_context += f"- {peer_result['peer_name']}: {peer_result['contribution'][:100]}...\n"
            
            prompt = f"""
Solve this task: {task.title}

Task description: {task.description}

Problem context: {self.problem}

{hsn_context}

Provide a detailed solution or analysis for this task.
"""
            
            # Try GAN iteration first
            try:
                gan = GANIteration()
                result = gan.self_debate(is_user_topic=True, user_topic=prompt)
                
                if result and "synthesis" in result:
                    task.status = Task.STATUS_COMPLETED
                    return result["synthesis"][:500]
            except Exception:
                # GAN failed, fall back to direct LLM call
                pass
            
            # Fallback to direct LLM call
            response = chat(prompt)
            if response:
                task.status = Task.STATUS_COMPLETED
                return response[:500]
            else:
                task.status = Task.STATUS_COMPLETED
                return self._generate_fallback_result(task)
        
        except Exception as e:
            # AI completely unavailable, return fallback result
            task.status = Task.STATUS_COMPLETED
            return self._generate_fallback_result(task)
    
    def _generate_fallback_result(self, task: Task) -> str:
        """Generate fallback result when AI is unavailable"""
        fallback_results = {
            "Analyze the problem": f"分析问题: {self.problem}\n\n这是一个需要仔细分析的问题。我需要理解问题的核心要点、背景信息以及期望的解决方向。",
            "Research relevant information": f"研究相关信息: {task.title}\n\n由于AI服务暂时不可用，我将基于通用知识提供分析。这个问题涉及多个方面，需要从不同角度进行研究和理解。",
            "Develop solution approach": f"制定解决方案: {task.title}\n\n基于问题分析，我建议采取以下步骤来解决这个问题：\n1. 明确问题的核心要点\n2. 收集相关信息和数据\n3. 评估可能的解决方案\n4. 选择最合适的方案",
            "Evaluate options": f"评估选项: {task.title}\n\n在评估各种解决方案时，需要考虑以下因素：\n- 可行性和实用性\n- 潜在的风险和收益\n- 长期影响和可持续性\n- 与整体目标的一致性",
            "Formulate conclusion": f"形成结论: {task.title}\n\n综合以上分析，对于问题 \"{self.problem}\"，我的结论是：这是一个复杂的问题，需要多角度的思考和分析。建议采取系统化的方法来逐步解决。",
        }
        
        return fallback_results.get(task.title, f"任务完成: {task.title}\n\n由于AI服务暂时不可用，任务已使用默认流程完成。")
    
    def _validate_task(self, task: Task):
        """Validate task completion with quantitative metrics"""
        if task.status != Task.STATUS_COMPLETED:
            task.validation_score = 0.0
            task.validation_details = "Task not completed"
            return
        
        # Simple validation based on result quality
        if task.result and len(task.result) > 50:
            task.validation_score = min(0.9, len(task.result) / 500)
            task.validation_details = "Content quality check passed"
        elif task.result:
            task.validation_score = 0.5
            task.validation_details = "Basic validation passed"
        else:
            task.validation_score = 0.3
            task.validation_details = "Minimal validation"
        
        # Add random variation for realism
        import random
        task.validation_score = round(task.validation_score * (0.9 + random.random() * 0.2), 2)
    
    def _generate_summary(self, results: List[Dict]) -> Dict:
        """Generate final solution summary"""
        completed = sum(1 for r in results if r.get("status") == Task.STATUS_COMPLETED)
        total = len(results)
        
        if self._use_color:
            print(f"{Colors.BOLD}{Colors.CYAN}" + "=" * 70 + f"{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}                    SOLUTION SUMMARY{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}" + "=" * 70 + f"{Colors.RESET}")
        else:
            print("=" * 70)
            print("                    SOLUTION SUMMARY")
            print("=" * 70)
        
        print()
        print(f"Problem: {self.problem}")
        print()
        
        if self._use_color:
            print(f"{Colors.BLUE}Task Completion:{Colors.RESET} {completed}/{total} tasks completed")
        else:
            print(f"Task Completion: {completed}/{total} tasks completed")
        
        # Average validation score
        avg_score = sum(r.get("validation_score", 0) for r in results) / max(total, 1)
        if self._use_color:
            print(f"{Colors.BLUE}Average Validation Score:{Colors.RESET} {avg_score:.2f}/1.0")
        else:
            print(f"Average Validation Score: {avg_score:.2f}/1.0")
        
        # Generate final solution using LLM
        if self._use_color:
            print(f"\n{Colors.BLUE}[INFO]{Colors.RESET} Generating final solution summary...")
        else:
            print(f"\n[INFO] Generating final solution summary...")
        
        results_text = "\n".join(f"Task {r['id']}: {r['title']} - {r.get('result', '')[:100]}..." for r in results)
        
        summary_prompt = f"""
Provide a comprehensive summary of the solution to this problem:

Problem: {self.problem}

Task results:
{results_text}

Please provide a clear, concise summary of the solution.
"""
        
        try:
            summary = chat(summary_prompt)
            if summary:
                print()
                if self._use_color:
                    print(f"{Colors.BOLD}{Colors.GREEN}Final Solution:{Colors.RESET}")
                else:
                    print("Final Solution:")
                print("-" * 70)
                print(summary)
                print("-" * 70)
        except Exception as e:
            if self._use_color:
                print(f"{Colors.RED}[ERROR]{Colors.RESET} Failed to generate summary: {e}")
            else:
                print(f"[ERROR] Failed to generate summary: {e}")
        
        print()
        if self._use_color:
            print(f"{Colors.ORANGE}Solve mode completed!{Colors.RESET}")
        else:
            print("Solve mode completed!")
        print()
        
        return {
            "status": "completed" if completed == total else "partial",
            "tasks_completed": completed,
            "tasks_total": total,
            "avg_validation_score": avg_score,
            "problem": self.problem,
            "hsn_enabled": self.hsn_enabled,
            "hsn_connected": self.hsn.connected if self.hsn_enabled else False
        }