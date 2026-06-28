"""
AI Self Optimizer & Continuous Learner
AI自我进化模块 - 通过持续对话不断学习和优化

系统分为两个核心数据库：
1. Experience（经验数据库）- 存储问题解决经验、成功模式、解决方案
2. Memory（情感数据库）- 存储情感数据、用户偏好、对话情绪
"""

import os
import re
import json
import time
import ast
import inspect
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from collections import defaultdict, deque


class Experience:
    """经验数据库 - 存储问题解决经验、成功模式、解决方案"""
    
    def __init__(self):
        self.problem_solutions: Dict[str, List[Dict]] = defaultdict(list)  # 问题-解决方案映射
        self.success_patterns: List[Dict] = []  # 成功的解决模式
        self.skill_experience: Dict[str, List[Dict]] = defaultdict(list)  # 技能使用经验
        self.command_results: List[Dict] = []  # 命令执行结果
        self.quick_fixes: Dict[str, str] = {}  # 快速解决方案
        self.experience_file = None
        
    def record_problem_solution(self, problem: str, solution: str, success: bool = True, confidence: float = 0.8):
        """记录问题和解决方案"""
        self.problem_solutions[problem].append({
            "timestamp": datetime.now().isoformat(),
            "solution": solution,
            "success": success,
            "confidence": confidence
        })
        
        if success:
            # 添加到成功模式
            pattern = {
                "timestamp": datetime.now().isoformat(),
                "problem": problem,
                "solution": solution[:100],
                "confidence": confidence
            }
            self.success_patterns.append(pattern)
    
    def record_skill_execution(self, skill_name: str, input_data: str, output_data: str, success: bool = True):
        """记录技能执行经验"""
        self.skill_experience[skill_name].append({
            "timestamp": datetime.now().isoformat(),
            "input": input_data[:200],
            "output": output_data[:500],
            "success": success
        })
    
    def record_command_result(self, command: str, result: str, success: bool = True):
        """记录命令执行结果"""
        self.command_results.append({
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "result": result[:1000],
            "success": success
        })
    
    def add_quick_fix(self, problem_keyword: str, solution: str):
        """添加快速解决方案"""
        self.quick_fixes[problem_keyword.lower()] = solution
    
    def find_solution(self, problem: str) -> Optional[str]:
        """查找问题的解决方案"""
        problem_lower = problem.lower()
        
        # 先检查快速解决方案
        for keyword, solution in self.quick_fixes.items():
            if keyword in problem_lower:
                return solution
        
        # 查找历史解决方案
        for stored_problem, solutions in self.problem_solutions.items():
            if stored_problem.lower() in problem_lower or problem_lower in stored_problem.lower():
                # 返回最成功的解决方案
                successful = [s for s in solutions if s.get("success", True)]
                if successful:
                    return successful[-1]["solution"]
        
        return None
    
    def find_pattern_match(self, problem: str) -> Optional[str]:
        """查找匹配的成功模式"""
        problem_lower = problem.lower()
        
        for pattern in reversed(self.success_patterns[-50:]):
            if pattern["problem"].lower() in problem_lower or \
               any(word in problem_lower for word in pattern["problem"].lower().split()):
                return pattern["solution"]
        
        return None
    
    def get_skill_experience(self, skill_name: str) -> List[Dict]:
        """获取技能使用经验"""
        return self.skill_experience.get(skill_name, [])
    
    def get_top_success_patterns(self, limit: int = 10) -> List[Dict]:
        """获取最成功的模式"""
        sorted_patterns = sorted(
            self.success_patterns,
            key=lambda x: x.get("confidence", 0.0),
            reverse=True
        )
        return sorted_patterns[:limit]
    
    def save(self, filepath: str):
        """保存经验数据库"""
        data = {
            "problem_solutions": dict(self.problem_solutions),
            "success_patterns": self.success_patterns,
            "skill_experience": dict(self.skill_experience),
            "command_results": self.command_results,
            "quick_fixes": self.quick_fixes,
            "last_updated": datetime.now().isoformat()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load(self, filepath: str):
        """加载经验数据库"""
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.problem_solutions = defaultdict(list, data.get("problem_solutions", {}))
                self.success_patterns = data.get("success_patterns", [])
                self.skill_experience = defaultdict(list, data.get("skill_experience", {}))
                self.command_results = data.get("command_results", [])
                self.quick_fixes = data.get("quick_fixes", {})


class Memory:
    """情感数据库 - 存储情感数据、用户偏好、对话情绪"""
    
    def __init__(self):
        self.user_profile: Dict[str, any] = {}  # 用户画像
        self.conversation_sentiment: deque = deque(maxlen=200)  # 对话情感记录
        self.user_preferences: Dict[str, any] = {}  # 用户偏好
        self.emotional_states: List[Dict] = []  # 情感状态历史
        self.relationship_score: float = 0.5  # 关系亲密度分数
        self.memory_file = None
        
    def set_user_profile(self, key: str, value: any):
        """设置用户画像信息"""
        self.user_profile[key] = value
    
    def get_user_profile(self) -> Dict[str, any]:
        """获取用户画像"""
        return self.user_profile
    
    def record_sentiment(self, user_input: str, sentiment: float, confidence: float = 1.0):
        """记录对话情感"""
        self.conversation_sentiment.append({
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input[:200],
            "sentiment": sentiment,  # -1到1，负数表示消极，正数表示积极
            "confidence": confidence
        })
        
        # 更新情感状态
        self.emotional_states.append({
            "timestamp": datetime.now().isoformat(),
            "sentiment": sentiment,
            "confidence": confidence
        })
        
        # 更新关系亲密度
        if sentiment > 0.3:
            self.relationship_score = min(1.0, self.relationship_score + 0.01)
        elif sentiment < -0.3:
            self.relationship_score = max(0.0, self.relationship_score - 0.02)
    
    def set_preference(self, key: str, value: any):
        """设置用户偏好"""
        self.user_preferences[key] = value
    
    def get_preference(self, key: str, default: any = None) -> any:
        """获取用户偏好"""
        return self.user_preferences.get(key, default)
    
    def get_average_sentiment(self) -> float:
        """获取平均情感值"""
        if not self.conversation_sentiment:
            return 0.0
        total = sum(s["sentiment"] for s in self.conversation_sentiment)
        return total / len(self.conversation_sentiment)
    
    def get_relationship_score(self) -> float:
        """获取关系亲密度"""
        return self.relationship_score
    
    def get_recent_emotions(self, limit: int = 10) -> List[Dict]:
        """获取最近的情感记录"""
        return list(self.conversation_sentiment)[-limit:]
    
    def save(self, filepath: str):
        """保存情感数据库"""
        data = {
            "user_profile": self.user_profile,
            "conversation_sentiment": list(self.conversation_sentiment),
            "user_preferences": self.user_preferences,
            "emotional_states": self.emotional_states,
            "relationship_score": self.relationship_score,
            "last_updated": datetime.now().isoformat()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load(self, filepath: str):
        """加载情感数据库"""
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.user_profile = data.get("user_profile", {})
                self.conversation_sentiment = deque(data.get("conversation_sentiment", []), maxlen=200)
                self.user_preferences = data.get("user_preferences", {})
                self.emotional_states = data.get("emotional_states", [])
                self.relationship_score = data.get("relationship_score", 0.5)


class PerformanceMetrics:
    """Performance metrics tracking"""
    
    def __init__(self):
        self.response_times: deque = deque(maxlen=100)
        self.success_count = 0
        self.failure_count = 0
        self.total_requests = 0
        self.skill_usage: Dict[str, int] = defaultdict(int)
        self.skill_success: Dict[str, int] = defaultdict(int)
        self.optimal_response_times: Dict[str, float] = {}
        self.conversation_scores: deque = deque(maxlen=50)
        
    def record_response_time(self, duration: float, success: bool = True):
        """Record a response time"""
        self.response_times.append(duration)
        self.total_requests += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
    
    def record_skill_usage(self, skill_name: str, success: bool = True):
        """Record skill usage"""
        self.skill_usage[skill_name] += 1
        if success:
            self.skill_success[skill_name] += 1
    
    def record_conversation_score(self, score: float):
        """Record user satisfaction score (0-1)"""
        self.conversation_scores.append(min(1.0, max(0.0, score)))
    
    def get_average_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def get_success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests
    
    def get_conversation_score(self) -> float:
        if not self.conversation_scores:
            return 0.5
        return sum(self.conversation_scores) / len(self.conversation_scores)
    
    def get_skill_success_rate(self, skill_name: str) -> float:
        usage = self.skill_usage.get(skill_name, 0)
        if usage == 0:
            return 0.0
        return self.skill_success.get(skill_name, 0) / usage
    
    def to_dict(self) -> Dict:
        return {
            "average_response_time": self.get_average_response_time(),
            "success_rate": self.get_success_rate(),
            "conversation_score": self.get_conversation_score(),
            "total_requests": self.total_requests,
            "skill_usage": dict(self.skill_usage),
            "skill_success_rates": {
                skill: self.get_skill_success_rate(skill) 
                for skill in self.skill_usage.keys()
            },
            "optimal_response_times": self.optimal_response_times,
            "last_updated": datetime.now().isoformat()
        }


class CodeAnalyzer:
    """Analyze code for optimization opportunities"""
    
    @staticmethod
    def analyze_file(filepath: str) -> Dict:
        """Analyze a Python file for optimization opportunities"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            issues = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.While)):
                    for child in ast.walk(node):
                        if isinstance(child, (ast.For, ast.While)) and child != node:
                            issues.append({
                                "type": "nested_loop",
                                "severity": "medium",
                                "line": node.lineno,
                                "message": "Nested loop detected - consider optimization"
                            })
                            break
                
                if isinstance(node, (ast.For, ast.While)):
                    func_calls = []
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            if isinstance(child.func, ast.Name):
                                func_calls.append(child.func.id)
                    if len(func_calls) > len(set(func_calls)):
                        issues.append({
                            "type": "repeated_calls",
                            "severity": "low",
                            "line": node.lineno,
                            "message": "Repeated function calls in loop - cache results"
                        })
            
            for node in ast.walk(tree):
                if isinstance(node, ast.JoinedStr):
                    issues.append({
                        "type": "f_string_found",
                        "severity": "info",
                        "line": node.lineno,
                        "message": "f-string usage detected - good for performance"
                    })
            
            return {
                "file": filepath,
                "issues": issues,
                "lines": len(content.splitlines()),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "file": filepath,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    @staticmethod
    def suggest_optimizations(metrics: PerformanceMetrics) -> List[str]:
        """Generate optimization suggestions based on metrics"""
        suggestions = []
        
        avg_time = metrics.get_average_response_time()
        if avg_time > 5.0:
            suggestions.append(f"高响应时间 ({avg_time:.2f}s) - 考虑缓存和优化")
        elif avg_time > 2.0:
            suggestions.append(f"中等响应时间 ({avg_time:.2f}s) - 可进行一些优化")
        
        for skill, usage in metrics.skill_usage.items():
            if usage >= 10:
                success_rate = metrics.get_skill_success_rate(skill)
                if success_rate < 0.8:
                    suggestions.append(f"技能 '{skill}' 成功率较低 ({success_rate:.0%}) - 需要改进")
        
        if metrics.failure_count > metrics.success_count * 0.2:
            suggestions.append(f"失败率较高 - 调查错误模式")
        
        conv_score = metrics.get_conversation_score()
        if conv_score < 0.6:
            suggestions.append(f"用户满意度较低 ({conv_score:.1%}) - 改进对话策略")
        
        return suggestions


class UserPatternAnalyzer:
    """Analyze user interaction patterns"""
    
    def __init__(self):
        self.interaction_history: deque = deque(maxlen=500)
        self.topic_frequency: Dict[str, int] = defaultdict(int)
        self.peak_hours: Dict[int, int] = defaultdict(int)
        self.preferred_response_length: Dict[str, float] = defaultdict(float)
        self.user_sentiment: deque = deque(maxlen=100)
        
    def record_interaction(self, user_input: str, topic: str = None, sentiment: float = 0.0):
        """Record a user interaction with optional sentiment"""
        self.interaction_history.append({
            "timestamp": datetime.now(),
            "user_input": user_input,
            "topic": topic or self._extract_topic(user_input),
            "sentiment": sentiment
        })
        
        if topic:
            self.topic_frequency[topic] += 1
        
        hour = datetime.now().hour
        self.peak_hours[hour] += 1
        
        self.user_sentiment.append(sentiment)
    
    def _extract_topic(self, text: str) -> str:
        """Extract topic from user input"""
        words = re.findall(r'\b\w{2,}\b', text.lower())
        if not words:
            return "unknown"
        
        topics = {
            "code": ["代码", "function", "class", "import", "def", "return", "编程", "python"],
            "file": ["文件", "read", "write", "open", "save", "读取", "写入"],
            "error": ["错误", "bug", "fix", "issue", "problem", "问题", "报错"],
            "question": ["what", "how", "why", "when", "where", "?", "什么", "为什么", "怎么"],
            "task": ["do", "make", "create", "build", "run", "execute", "做", "创建", "运行"],
            "chat": ["聊", "说", "谈", "问", "答", "对话"],
            "train": ["训练", "学习", "模型", "AI", "神经网络"],
            "search": ["搜索", "查找", "信息", "资料"],
            "skill": ["技能", "skill", "工具", "功能"]
        }
        
        for topic, keywords in topics.items():
            if any(word in words for word in keywords):
                return topic
        
        return words[0] if words else "unknown"
    
    def get_peak_activity_hours(self) -> List[int]:
        """Get hours with highest activity"""
        sorted_hours = sorted(self.peak_hours.items(), key=lambda x: -x[1])
        return [hour for hour, count in sorted_hours[:3]]
    
    def get_preferred_topics(self, limit: int = 5) -> List[str]:
        """Get most frequent topics"""
        sorted_topics = sorted(self.topic_frequency.items(), key=lambda x: -x[1])
        return [topic for topic, count in sorted_topics[:limit]]
    
    def get_average_input_length(self) -> float:
        """Get average user input length"""
        if not self.interaction_history:
            return 0.0
        total = sum(len(i["user_input"]) for i in self.interaction_history)
        return total / len(self.interaction_history)
    
    def get_average_sentiment(self) -> float:
        """Get average user sentiment"""
        if not self.user_sentiment:
            return 0.0
        return sum(self.user_sentiment) / len(self.user_sentiment)
    
    def suggest_response_strategy(self) -> str:
        """Suggest optimal response strategy based on patterns"""
        avg_length = self.get_average_input_length()
        
        if avg_length < 30:
            return "concise"
        elif avg_length < 100:
            return "balanced"
        else:
            return "detailed"


class PromptDistiller:
    """蒸馏prompt技术 - 从对话历史中提取精华知识"""
    
    def __init__(self):
        self.distilled_prompts: Dict[str, str] = {}
        self.knowledge_base: Dict[str, List[str]] = defaultdict(list)
        self.success_patterns: List[Dict] = []
        self.distilled_knowledge_file = None
        
    def distill_from_conversations(self, conversations: List[Dict]) -> Dict[str, str]:
        """从对话历史中蒸馏出精华知识"""
        distilled = {}
        
        # 按主题分类对话
        topic_conversations = defaultdict(list)
        for conv in conversations:
            topic = self._extract_topic(conv["user_input"])
            topic_conversations[topic].append(conv)
        
        # 对每个主题进行蒸馏
        for topic, convs in topic_conversations.items():
            if len(convs) >= 3:  # 至少需要3次对话才能蒸馏
                distilled_prompt = self._distill_topic(topic, convs)
                if distilled_prompt:
                    distilled[topic] = distilled_prompt
                    self.distilled_prompts[topic] = distilled_prompt
        
        return distilled
    
    def _extract_topic(self, text: str) -> str:
        """提取对话主题"""
        keywords = {
            "编程": ["代码", "python", "function", "class", "编程", "写代码"],
            "文件操作": ["文件", "read", "write", "读取", "写入", "保存"],
            "问题解决": ["错误", "bug", "问题", "fix", "解决", "报错"],
            "学习": ["学习", "训练", "模型", "AI", "神经网络", "蒸馏"],
            "搜索": ["搜索", "查找", "信息", "资料", "web"],
            "技能": ["技能", "skill", "工具", "功能", "创建"],
            "聊天": ["聊", "说", "谈", "问", "答", "对话", "你好"]
        }
        
        text_lower = text.lower()
        for topic, words in keywords.items():
            if any(word in text_lower for word in words):
                return topic
        
        return "general"
    
    def _distill_topic(self, topic: str, conversations: List[Dict]) -> str:
        """蒸馏特定主题的知识"""
        # 提取成功的对话模式
        successful = [c for c in conversations if c.get("success", True) and c.get("feedback", 0) >= 0.5]
        
        if not successful:
            return None
        
        # 提取关键知识点
        knowledge_points = []
        for conv in successful[:10]:  # 只取前10个最成功的
            # 提取用户问题的核心
            user_core = self._extract_core_question(conv["user_input"])
            # 提取AI回答的精华
            ai精华 = self._extract_response精华(conv["ai_response"])
            
            if user_core and ai精华:
                knowledge_points.append(f"当用户问 '{user_core}' 时，回答 '{ai精华}'")
        
        if not knowledge_points:
            return None
        
        # 生成蒸馏后的提示词
        distilled_prompt = f"""
【{topic}领域知识蒸馏】

核心知识点：
{chr(10).join(f'- {kp}' for kp in knowledge_points[:5])}

最佳实践：
- 理解用户意图后，提供简洁明确的回答
- 如果涉及技术问题，先分析问题根源
- 提供可行的解决方案，必要时给出示例
- 保持友好和耐心，鼓励用户继续探索

常见错误避免：
- 不要给出过于复杂的解释
- 不要忽略用户的实际需求
- 不要在没有理解问题时就给出答案
"""
        
        # 存储到知识库
        self.knowledge_base[topic] = knowledge_points
        
        return distilled_prompt
    
    def _extract_core_question(self, text: str) -> str:
        """提取用户问题的核心"""
        # 移除多余的修饰词
        text = re.sub(r'^(请问|我想问|能不能|可以|帮我|麻烦)', '', text.strip())
        text = re.sub(r'(呢|吗|呀|吧|啊)$', '', text.strip())
        
        # 提取关键动词和名词
        words = text.split()
        if len(words) <= 5:
            return text
        
        # 提取核心动作
        core_words = []
        important_words = ["怎么", "如何", "为什么", "什么", "创建", "运行", "修复", "学习", "搜索"]
        
        for word in words:
            if word in important_words or len(word) >= 3:
                core_words.append(word)
        
        return ' '.join(core_words[:5]) if core_words else text[:30]
    
    def _extract_response精华(self, text: str) -> str:
        """提取AI回答的精华部分"""
        # 提取关键步骤或解决方案
        lines = text.split('\n')
        精华_lines = []
        
        for line in lines:
            # 提取包含关键信息的行
            if any(keyword in line for keyword in ["步骤", "方法", "方案", "建议", "可以", "需要", "首先", "然后"]):
                精华_lines.append(line.strip())
        
        if 精华_lines:
            return ' '.join(精华_lines[:3])
        
        # 如果没有明显的精华行，返回前50个字符
        return text[:50].strip()
    
    def get_distilled_prompt(self, topic: str) -> Optional[str]:
        """获取特定主题的蒸馏提示词"""
        return self.distilled_prompts.get(topic)
    
    def get_all_distilled_prompts(self) -> Dict[str, str]:
        """获取所有蒸馏提示词"""
        return self.distilled_prompts
    
    def generate_training_prompt(self, user_input: str) -> str:
        """根据用户输入生成训练提示词"""
        topic = self._extract_topic(user_input)
        
        base_prompt = self.distilled_prompts.get(topic, "")
        
        if not base_prompt:
            return ""
        
        # 根据具体问题定制提示词
        customized = f"""
{base_prompt}

当前用户问题：{user_input}

请基于以上蒸馏知识，提供最佳回答。
"""
        
        return customized
    
    def save_distilled_knowledge(self, filepath: str):
        """保存蒸馏后的知识"""
        try:
            data = {
                "distilled_prompts": self.distilled_prompts,
                "knowledge_base": dict(self.knowledge_base),
                "last_updated": datetime.now().isoformat()
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            pass
    
    def load_distilled_knowledge(self, filepath: str):
        """加载蒸馏后的知识"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.distilled_prompts = data.get("distilled_prompts", {})
                    self.knowledge_base = defaultdict(list, data.get("knowledge_base", {}))
        except Exception as e:
            pass


class ConversationLearner:
    """Learn from conversation history to improve responses"""
    
    def __init__(self):
        self.conversation_history: deque = deque(maxlen=1000)
        self.response_templates: Dict[str, List[str]] = defaultdict(list)
        self.success_patterns: List[Dict] = []
        self.failure_patterns: List[Dict] = []
        self.command_results: List[Dict] = []  # 记录命令执行结果
        self.prompt_distiller = PromptDistiller()  # 添加蒸馏器
        
    def record_conversation(self, user_input: str, ai_response: str, success: bool = True, feedback: float = 0.0):
        """Record a complete conversation turn"""
        self.conversation_history.append({
            "timestamp": datetime.now(),
            "user_input": user_input,
            "ai_response": ai_response,
            "success": success,
            "feedback": feedback
        })
        
        if success and feedback > 0.5:
            self._extract_pattern(user_input, ai_response)
    
    def record_command_result(self, command: str, result: str, success: bool = True):
        """Record command execution result for learning"""
        self.command_results.append({
            "timestamp": datetime.now(),
            "command": command,
            "result": result,
            "success": success
        })
        
        # 从成功的命令中学习
        if success:
            self._learn_from_command(command, result)
    
    def _extract_pattern(self, user_input: str, ai_response: str):
        """Extract successful response patterns"""
        if any(greet in user_input.lower() for greet in ["你好", "嗨", "hello", "hi"]):
            self.response_templates["greeting"].append(ai_response)
        elif any(thanks in user_input.lower() for thanks in ["谢谢", "thank"]):
            self.response_templates["thanks"].append(ai_response)
        elif "?" in user_input or any(q in user_input.lower() for q in ["什么", "为什么", "怎么", "如何"]):
            self.response_templates["question"].append(ai_response)
        elif any(cmd in user_input.lower() for cmd in ["运行", "执行", "创建", "做"]):
            self.response_templates["command"].append(ai_response)
    
    def _learn_from_command(self, command: str, result: str):
        """Learn from successful command execution"""
        # 提取命令模式
        if command.startswith("ls"):
            self.response_templates["ls_command"].append(f"查看目录完成！结果：{result[:50]}...")
        elif "python" in command.lower() or ".py" in command:
            self.response_templates["python_command"].append(f"Python执行完成！结果：{result[:50]}...")
    
    def get_best_response(self, user_input: str) -> Optional[str]:
        """Get best matching response from history"""
        input_lower = user_input.lower()
        
        if any(greet in input_lower for greet in ["你好", "嗨", "hello", "hi"]):
            templates = self.response_templates.get("greeting", [])
            if templates:
                return random.choice(templates)
        
        if any(thanks in input_lower for thanks in ["谢谢", "thank"]):
            templates = self.response_templates.get("thanks", [])
            if templates:
                return random.choice(templates)
        
        return None
    
    def generate_training_data(self, limit: int = 100) -> List[Dict]:
        """Generate training data from conversation history"""
        training_data = []
        
        for conv in list(self.conversation_history)[-limit:]:
            training_data.append({
                "instruction": conv["user_input"],
                "response": conv["ai_response"],
                "quality": conv["feedback"] if conv["feedback"] > 0 else 0.7 if conv["success"] else 0.3
            })
        
        return training_data
    
    def suggest_new_skill(self) -> Optional[str]:
        """Suggest a new skill based on command patterns"""
        # 分析常用命令模式
        command_patterns = defaultdict(int)
        for cmd in self.command_results:
            if cmd.get("success", False):
                cmd_text = cmd["command"]
                if "web-search" in cmd_text.lower() or "搜索" in cmd_text:
                    command_patterns["search"] += 1
                elif "file-read" in cmd_text.lower() or "读取文件" in cmd_text:
                    command_patterns["file_operations"] += 1
                elif "python" in cmd_text.lower() or "run" in cmd_text:
                    command_patterns["code_execution"] += 1
        
        # 如果某种命令模式频繁使用，建议创建专门的技能
        for pattern, count in command_patterns.items():
            if count >= 5:
                skill_suggestions = {
                    "search": "建议创建专门的搜索技能，支持更智能的搜索查询",
                    "file_operations": "建议创建文件管理技能，支持批量操作",
                    "code_execution": "建议创建代码执行技能，支持更多语言"
                }
                return skill_suggestions.get(pattern)
        
        return None


class SelfOptimizer:
    """Main AI self-optimizer class with continuous learning
    
    系统分为两个核心数据库：
    1. Experience（经验数据库）- 存储问题解决经验、成功模式、解决方案
    2. Memory（情感数据库）- 存储情感数据、用户偏好、对话情绪
    
    支持两种模式：
    - Solve模式：只保存到Experience，用于快速解决问题
    - Chat模式：同时保存到Experience和Memory，用于完整对话
    """
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.pattern_analyzer = UserPatternAnalyzer()
        self.code_analyzer = CodeAnalyzer()
        self.conversation_learner = ConversationLearner()
        
        # 分离的数据库
        self.experience = Experience()  # 经验数据库
        self.memory = Memory()          # 情感数据库
        
        self.last_optimization = None
        self.last_learning_update = None
        self.last_skill_creation = None
        self.optimization_history: List[Dict] = []
        self.web_search_enabled = False
        self.web_search_module = None
        
        self.allowed_dirs = [
            os.path.join(os.path.dirname(__file__), "ai_selfdevelop", "skills"),
            os.path.join(os.path.dirname(__file__), "ai_selfdevelop", "customizations"),
            os.path.join(os.path.dirname(__file__), "ai_selfdevelop", "preferences"),
            os.path.join(os.path.dirname(__file__), "ai_selfdevelop", "learning"),
        ]
        
        self.metrics_file = os.path.join(
            os.path.dirname(__file__), "ai_selfdevelop", "preferences", "performance_metrics.json"
        )
        self.patterns_file = os.path.join(
            os.path.dirname(__file__), "ai_selfdevelop", "preferences", "user_patterns.json"
        )
        self.training_data_file = os.path.join(
            os.path.dirname(__file__), "ai_selfdevelop", "learning", "training_data.json"
        )
        self.response_templates_file = os.path.join(
            os.path.dirname(__file__), "ai_selfdevelop", "learning", "response_templates.json"
        )
        self.distilled_knowledge_file = os.path.join(
            os.path.dirname(__file__), "ai_selfdevelop", "learning", "distilled_knowledge.json"
        )
        # 新增分离数据库的文件路径
        self.experience_file = os.path.join(
            os.path.dirname(__file__), "ai_selfdevelop", "learning", "experience.json"
        )
        self.memory_file = os.path.join(
            os.path.dirname(__file__), "ai_selfdevelop", "learning", "memory.json"
        )
        
        self._load_data()
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        for directory in self.allowed_dirs:
            os.makedirs(directory, exist_ok=True)
    
    def _load_data(self):
        """Load persisted data"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    self.metrics.optimal_response_times = data.get("optimal_response_times", {})
            except:
                pass
        
        if os.path.exists(self.patterns_file):
            try:
                with open(self.patterns_file, 'r') as f:
                    data = json.load(f)
                    self.pattern_analyzer.topic_frequency = defaultdict(int, data.get("topic_frequency", {}))
                    self.pattern_analyzer.peak_hours = defaultdict(int, data.get("peak_hours", {}))
            except:
                pass
        
        if os.path.exists(self.response_templates_file):
            try:
                with open(self.response_templates_file, 'r') as f:
                    data = json.load(f)
                    self.conversation_learner.response_templates = defaultdict(list, data)
            except:
                pass
        
        # 加载蒸馏知识
        if os.path.exists(self.distilled_knowledge_file):
            try:
                self.conversation_learner.prompt_distiller.load_distilled_knowledge(self.distilled_knowledge_file)
            except:
                pass
        
        # 加载经验数据库
        if os.path.exists(self.experience_file):
            try:
                self.experience.load(self.experience_file)
            except:
                pass
        
        # 加载情感数据库
        if os.path.exists(self.memory_file):
            try:
                self.memory.load(self.memory_file)
            except:
                pass
    
    def _save_data(self):
        """Save data persistently"""
        self._ensure_directories()
        
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics.to_dict(), f, indent=2)
        except:
            pass
        
        try:
            pattern_data = {
                "topic_frequency": dict(self.pattern_analyzer.topic_frequency),
                "peak_hours": {str(k): v for k, v in self.pattern_analyzer.peak_hours.items()},
                "last_updated": datetime.now().isoformat()
            }
            with open(self.patterns_file, 'w') as f:
                json.dump(pattern_data, f, indent=2)
        except:
            pass
        
        try:
            with open(self.response_templates_file, 'w') as f:
                json.dump(dict(self.conversation_learner.response_templates), f, indent=2, ensure_ascii=False)
        except:
            pass
        
        try:
            training_data = self.conversation_learner.generate_training_data(500)
            with open(self.training_data_file, 'w') as f:
                json.dump(training_data, f, indent=2, ensure_ascii=False)
        except:
            pass
        
        # 保存蒸馏知识
        try:
            self.conversation_learner.prompt_distiller.save_distilled_knowledge(self.distilled_knowledge_file)
        except:
            pass
        
        # 保存经验数据库
        try:
            self.experience.save(self.experience_file)
        except:
            pass
        
        # 保存情感数据库
        try:
            self.memory.save(self.memory_file)
        except:
            pass
    
    def enable_web_search(self, search_module):
        """Enable web search capability for learning"""
        self.web_search_enabled = True
        self.web_search_module = search_module
    
    def record_interaction(self, user_input: str, ai_response: str, response_time: float, 
                          success: bool = True, topic: str = None, sentiment: float = 0.0):
        """Record a complete interaction for learning (Chat模式)"""
        # Chat模式：同时保存到Experience和Memory
        self.metrics.record_response_time(response_time, success)
        self.pattern_analyzer.record_interaction(user_input, topic, sentiment)
        self.conversation_learner.record_conversation(user_input, ai_response, success, sentiment)
        
        # 保存到经验数据库
        self.experience.record_problem_solution(user_input, ai_response, success)
        
        # 保存到情感数据库
        self.memory.record_sentiment(user_input, sentiment)
        
        self._save_data()
    
    def record_solve_interaction(self, problem: str, solution: str, success: bool = True, confidence: float = 0.8):
        """Record a problem-solving interaction (Solve模式) - 只保存到Experience"""
        # Solve模式：只保存到经验数据库，用于快速解决问题
        self.experience.record_problem_solution(problem, solution, success, confidence)
        self._save_data()
    
    def record_command_result(self, command: str, result: str, success: bool = True):
        """Record command execution result"""
        self.conversation_learner.record_command_result(command, result, success)
        # 同时保存到经验数据库
        self.experience.record_command_result(command, result, success)
        self._save_data()
    
    def record_skill_execution(self, skill_name: str, input_data: str = "", output_data: str = "", success: bool = True):
        """Record skill execution"""
        self.metrics.record_skill_usage(skill_name, success)
        # 保存到经验数据库
        self.experience.record_skill_execution(skill_name, input_data, output_data, success)
        self._save_data()
    
    def solve_problem(self, problem: str) -> Optional[str]:
        """Solve模式：快速查找解决方案"""
        # 首先尝试快速解决
        solution = self.experience.find_solution(problem)
        if solution:
            return solution
        
        # 尝试查找模式匹配
        pattern_match = self.experience.find_pattern_match(problem)
        if pattern_match:
            return pattern_match
        
        return None
    
    def add_quick_fix(self, problem_keyword: str, solution: str):
        """添加快速解决方案到经验数据库"""
        self.experience.add_quick_fix(problem_keyword, solution)
        self._save_data()
    
    def get_experience_summary(self) -> Dict:
        """获取经验数据库摘要"""
        return {
            "total_problems": len(self.experience.problem_solutions),
            "total_patterns": len(self.experience.success_patterns),
            "quick_fixes_count": len(self.experience.quick_fixes),
            "command_results_count": len(self.experience.command_results)
        }
    
    def get_memory_summary(self) -> Dict:
        """获取情感数据库摘要"""
        return {
            "relationship_score": self.memory.get_relationship_score(),
            "average_sentiment": self.memory.get_average_sentiment(),
            "user_profile_keys": list(self.memory.user_profile.keys()),
            "preferences_count": len(self.memory.user_preferences)
        }
    
    def should_optimize(self) -> bool:
        """Check if optimization should run"""
        if self.last_optimization:
            elapsed = datetime.now() - self.last_optimization
            if elapsed < timedelta(minutes=15):
                return False
        
        if self.metrics.total_requests < 5:
            return False
        
        return True
    
    def should_learn(self) -> bool:
        """Check if learning update should run"""
        if self.last_learning_update:
            elapsed = datetime.now() - self.last_learning_update
            if elapsed < timedelta(minutes=10):
                return False
        
        return len(self.conversation_learner.conversation_history) >= 3
    
    def should_create_skill(self) -> bool:
        """Check if a new skill should be created"""
        if self.last_skill_creation:
            elapsed = datetime.now() - self.last_skill_creation
            if elapsed < timedelta(hours=1):
                return False
        
        return True
    
    def run_optimization(self) -> Dict:
        """Run self-optimization analysis"""
        if not self.should_optimize():
            return {
                "optimized": False,
                "reason": "数据不足或距离上次优化时间过短"
            }
        
        self.last_optimization = datetime.now()
        
        skill_dir = self.allowed_dirs[0]
        code_issues = []
        
        if os.path.exists(skill_dir):
            for filename in os.listdir(skill_dir):
                if filename.endswith('.py'):
                    filepath = os.path.join(skill_dir, filename)
                    analysis = self.code_analyzer.analyze_file(filepath)
                    if "issues" in analysis:
                        code_issues.extend(analysis["issues"])
        
        suggestions = self.code_analyzer.suggest_optimizations(self.metrics)
        
        insights = {
            "preferred_topics": self.pattern_analyzer.get_preferred_topics(),
            "peak_hours": self.pattern_analyzer.get_peak_activity_hours(),
            "recommended_strategy": self.pattern_analyzer.suggest_response_strategy(),
            "average_input_length": self.pattern_analyzer.get_average_input_length(),
            "average_sentiment": self.pattern_analyzer.get_average_sentiment()
        }
        
        # 检查是否需要创建新技能
        skill_suggestion = self.conversation_learner.suggest_new_skill()
        
        report = {
            "optimized": True,
            "timestamp": datetime.now().isoformat(),
            "metrics_summary": {
                "average_response_time": self.metrics.get_average_response_time(),
                "success_rate": self.metrics.get_success_rate(),
                "conversation_score": self.metrics.get_conversation_score(),
                "total_interactions": self.metrics.total_requests
            },
            "code_issues": code_issues,
            "suggestions": suggestions,
            "user_insights": insights,
            "skill_suggestion": skill_suggestion,
            "optimizations_applied": []
        }
        
        optimizations_applied = self._apply_safe_optimizations()
        report["optimizations_applied"] = optimizations_applied
        
        self.optimization_history.append(report)
        self._save_data()
        
        return report
    
    def run_learning_update(self) -> Dict:
        """Run continuous learning update"""
        if not self.should_learn():
            return {
                "learned": False,
                "reason": "学习条件未满足"
            }
        
        self.last_learning_update = datetime.now()
        
        patterns_learned = []
        
        templates_before = sum(len(v) for v in self.conversation_learner.response_templates.values())
        
        training_data = self.conversation_learner.generate_training_data()
        
        successful_convs = [c for c in self.conversation_learner.conversation_history 
                           if c.get("success", True) and c.get("feedback", 0) >= 0.5]
        
        for conv in successful_convs[-10:]:
            self.conversation_learner._extract_pattern(conv["user_input"], conv["ai_response"])
        
        templates_after = sum(len(v) for v in self.conversation_learner.response_templates.values())
        new_templates = templates_after - templates_before
        
        if new_templates > 0:
            patterns_learned.append(f"学习了 {new_templates} 个新的响应模板")
        
        sentiment = self.pattern_analyzer.get_average_sentiment()
        if sentiment > 0.3:
            patterns_learned.append(f"检测到积极用户情绪 ({sentiment:.2f})，调整为更友好的对话风格")
        elif sentiment < -0.3:
            patterns_learned.append(f"检测到消极用户情绪 ({sentiment:.2f})，调整为更谨慎的对话风格")
        
        # 运行蒸馏prompt技术
        distilled_prompts = self.conversation_learner.prompt_distiller.distill_from_conversations(
            list(self.conversation_learner.conversation_history)
        )
        
        if distilled_prompts:
            patterns_learned.append(f"蒸馏了 {len(distilled_prompts)} 个主题的知识")
            # 保存蒸馏后的知识
            self.conversation_learner.prompt_distiller.save_distilled_knowledge(self.distilled_knowledge_file)
        
        # 如果启用了搜索，可以搜索相关资料来学习
        if self.web_search_enabled:
            top_topics = self.pattern_analyzer.get_preferred_topics(2)
            for topic in top_topics:
                search_query = f"{topic} best practices"
                try:
                    # 模拟搜索学习
                    patterns_learned.append(f"正在学习关于 '{topic}' 的最佳实践")
                except:
                    pass
        
        self._save_data()
        
        return {
            "learned": True,
            "timestamp": datetime.now().isoformat(),
            "patterns_learned": patterns_learned,
            "training_data_count": len(training_data),
            "response_templates_count": templates_after,
            "average_sentiment": sentiment,
            "distilled_topics": list(distilled_prompts.keys()) if distilled_prompts else []
        }
    
    def create_new_skill(self, skill_name: str, description: str, code: str) -> bool:
        """Create a new skill file"""
        if not self.should_create_skill():
            return False
        
        skill_path = os.path.join(self.allowed_dirs[0], f"{skill_name}.py")
        
        try:
            with open(skill_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            self.last_skill_creation = datetime.now()
            self._save_data()
            return True
        except Exception as e:
            return False
    
    def _apply_safe_optimizations(self) -> List[str]:
        """Apply safe, automatic optimizations"""
        applied = []
        
        for skill in self.metrics.skill_usage.keys():
            success_rate = self.metrics.get_skill_success_rate(skill)
            if success_rate > 0.9:
                self.metrics.optimal_response_times[skill] = 0.8
                applied.append(f"更新技能 '{skill}' 的最优响应时间")
        
        strategy = self.pattern_analyzer.suggest_response_strategy()
        strategy_file = os.path.join(self.allowed_dirs[1], "response_strategy.json")
        try:
            with open(strategy_file, 'w') as f:
                json.dump({
                    "strategy": strategy,
                    "updated": datetime.now().isoformat()
                }, f, indent=2)
            applied.append(f"更新响应策略为 '{strategy}'")
        except:
            pass
        
        return applied
    
    def get_best_response(self, user_input: str) -> Optional[str]:
        """Get best matching response from learned patterns"""
        return self.conversation_learner.get_best_response(user_input)
    
    def generate_optimization_prompt(self) -> str:
        """Generate a prompt for AI to create new optimizations"""
        insights = {
            "preferred_topics": self.pattern_analyzer.get_preferred_topics(),
            "recommended_strategy": self.pattern_analyzer.suggest_response_strategy(),
            "performance_issues": self.code_analyzer.suggest_optimizations(self.metrics),
            "avg_sentiment": self.pattern_analyzer.get_average_sentiment(),
            "skill_suggestion": self.conversation_learner.suggest_new_skill()
        }
        
        prompt = f"""
基于我的分析，这里是自我改进的机会：

用户模式:
- 偏好话题: {', '.join(insights['preferred_topics'])}
- 推荐响应策略: {insights['recommended_strategy']}
- 用户情绪: {'积极' if insights['avg_sentiment'] > 0.3 else '中性' if insights['avg_sentiment'] >= -0.3 else '消极'} ({insights['avg_sentiment']:.2f})

性能问题:
{chr(10).join(f'- {issue}' for issue in insights['performance_issues'])}

技能建议:
{insights['skill_suggestion'] or '暂无特别建议'}

我可以在 ai_selfdevelop/skills 中创建新技能或修改现有技能。
如果需要，我可以搜索相关资料来学习如何实现新功能。
"""
        return prompt
    
    def get_status_summary(self) -> str:
        """Get a human-readable status summary"""
        summary = []
        summary.append(f"总交互次数: {self.metrics.total_requests}")
        summary.append(f"平均响应时间: {self.metrics.get_average_response_time():.2f}s")
        summary.append(f"成功率: {self.metrics.get_success_rate():.1%}")
        summary.append(f"对话评分: {self.metrics.get_conversation_score():.1%}")
        summary.append(f"用户情绪: {'积极' if self.pattern_analyzer.get_average_sentiment() > 0.3 else '中性' if self.pattern_analyzer.get_average_sentiment() >= -0.3 else '消极'}")
        summary.append(f"偏好话题: {', '.join(self.pattern_analyzer.get_preferred_topics(3))}")
        summary.append(f"响应策略: {self.pattern_analyzer.suggest_response_strategy()}")
        summary.append(f"响应模板数量: {sum(len(v) for v in self.conversation_learner.response_templates.values())}")
        summary.append(f"命令执行记录: {len(self.conversation_learner.command_results)}")
        
        if self.last_optimization:
            elapsed = datetime.now() - self.last_optimization
            summary.append(f"上次优化: {elapsed.total_seconds()/60:.1f} 分钟前")
        
        if self.last_learning_update:
            elapsed = datetime.now() - self.last_learning_update
            summary.append(f"上次学习: {elapsed.total_seconds()/60:.1f} 分钟前")
        
        return "\n".join(summary)


_optimizer_instance = None

def get_optimizer() -> SelfOptimizer:
    """Get the singleton optimizer instance"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = SelfOptimizer()
    return _optimizer_instance
