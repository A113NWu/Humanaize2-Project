"""
AI Self Optimizer
AI self-improvement module for performance optimization and code enhancement.
Runs during GAN idle time to analyze patterns and optimize code.
"""

import os
import re
import json
import time
import ast
import inspect
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from collections import defaultdict, deque


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
    
    def get_average_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def get_success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests
    
    def get_skill_success_rate(self, skill_name: str) -> float:
        usage = self.skill_usage.get(skill_name, 0)
        if usage == 0:
            return 0.0
        return self.skill_success.get(skill_name, 0) / usage
    
    def to_dict(self) -> Dict:
        return {
            "average_response_time": self.get_average_response_time(),
            "success_rate": self.get_success_rate(),
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
            
            # Find optimization opportunities
            issues = []
            
            # Check for inefficient loops
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.While)):
                    # Check for nested loops
                    for child in ast.walk(node):
                        if isinstance(child, (ast.For, ast.While)) and child != node:
                            issues.append({
                                "type": "nested_loop",
                                "severity": "medium",
                                "line": node.lineno,
                                "message": "Nested loop detected - consider optimization"
                            })
                            break
                
                # Check for repeated function calls in loops
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
            
            # Check for inefficient string concatenation
            for node in ast.walk(tree):
                if isinstance(node, ast.JoinedStr):  # f-string
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
            suggestions.append(f"High average response time ({avg_time:.2f}s) - consider caching and optimization")
        elif avg_time > 2.0:
            suggestions.append(f"Moderate response time ({avg_time:.2f}s) - some optimization possible")
        
        # Analyze skill performance
        for skill, usage in metrics.skill_usage.items():
            if usage >= 10:  # Only for frequently used skills
                success_rate = metrics.get_skill_success_rate(skill)
                if success_rate < 0.8:
                    suggestions.append(f"Skill '{skill}' has low success rate ({success_rate:.0%}) - review implementation")
        
        if metrics.failure_count > metrics.success_count * 0.2:
            suggestions.append(f"High failure rate - investigate error patterns")
        
        return suggestions


class UserPatternAnalyzer:
    """Analyze user interaction patterns"""
    
    def __init__(self):
        self.interaction_history: deque = deque(maxlen=500)
        self.topic_frequency: Dict[str, int] = defaultdict(int)
        self.peak_hours: Dict[int, int] = defaultdict(int)
        self.preferred_response_length: Dict[str, float] = defaultdict(float)
        
    def record_interaction(self, user_input: str, topic: str = None):
        """Record a user interaction"""
        self.interaction_history.append({
            "timestamp": datetime.now(),
            "user_input": user_input,
            "topic": topic or self._extract_topic(user_input)
        })
        
        if topic:
            self.topic_frequency[topic] += 1
        
        hour = datetime.now().hour
        self.peak_hours[hour] += 1
    
    def _extract_topic(self, text: str) -> str:
        """Extract topic from user input (simple implementation)"""
        words = re.findall(r'\b\w{4,}\b', text.lower())
        if not words:
            return "unknown"
        
        # Common topic keywords
        topics = {
            "code": ["code", "function", "class", "import", "def", "return"],
            "file": ["file", "read", "write", "open", "save"],
            "error": ["error", "bug", "fix", "issue", "problem"],
            "question": ["what", "how", "why", "when", "where", "?"],
            "task": ["do", "make", "create", "build", "run", "execute"]
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
    
    def suggest_response_strategy(self) -> str:
        """Suggest optimal response strategy based on patterns"""
        avg_length = self.get_average_input_length()
        
        if avg_length < 30:
            return "concise"  # Short inputs prefer quick, concise responses
        elif avg_length < 100:
            return "balanced"  # Medium inputs prefer balanced responses
        else:
            return "detailed"  # Long inputs prefer detailed responses


class SelfOptimizer:
    """Main AI self-optimizer class"""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.pattern_analyzer = UserPatternAnalyzer()
        self.code_analyzer = CodeAnalyzer()
        self.last_optimization = None
        self.optimization_history: List[Dict] = []
        
        # Directories AI can modify (only ai_selfdevelop directory)
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
        
        self._load_data()
    
    def _load_data(self):
        """Load persisted data"""
        # Load performance metrics
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    self.metrics.optimal_response_times = data.get("optimal_response_times", {})
            except:
                pass
        
        # Load user patterns
        if os.path.exists(self.patterns_file):
            try:
                with open(self.patterns_file, 'r') as f:
                    data = json.load(f)
                    self.pattern_analyzer.topic_frequency = defaultdict(int, data.get("topic_frequency", {}))
                    self.pattern_analyzer.peak_hours = defaultdict(int, data.get("peak_hours", {}))
            except:
                pass
    
    def _save_data(self):
        """Save data persistently"""
        # Ensure directories exist
        for directory in self.allowed_dirs:
            os.makedirs(directory, exist_ok=True)
        
        # Save performance metrics
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics.to_dict(), f, indent=2)
        except:
            pass
        
        # Save user patterns
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
    
    def record_interaction(self, user_input: str, response_time: float, success: bool = True, topic: str = None):
        """Record a complete interaction for learning"""
        self.metrics.record_response_time(response_time, success)
        self.pattern_analyzer.record_interaction(user_input, topic)
        self._save_data()
    
    def record_skill_execution(self, skill_name: str, success: bool = True):
        """Record skill execution"""
        self.metrics.record_skill_usage(skill_name, success)
        self._save_data()
    
    def should_optimize(self) -> bool:
        """Check if optimization should run (during GAN idle time)"""
        # Don't optimize too frequently
        if self.last_optimization:
            elapsed = datetime.now() - self.last_optimization
            if elapsed < timedelta(minutes=30):
                return False
        
        # Check if we have enough data
        if self.metrics.total_requests < 10:
            return False
        
        return True
    
    def run_optimization(self) -> Dict:
        """Run self-optimization analysis and generate recommendations"""
        if not self.should_optimize():
            return {
                "optimized": False,
                "reason": "Not enough data or too soon since last optimization"
            }
        
        self.last_optimization = datetime.now()
        
        # Analyze code for optimization opportunities
        skill_dir = self.allowed_dirs[0]  # ai_selfdevelop/skills
        code_issues = []
        
        if os.path.exists(skill_dir):
            for filename in os.listdir(skill_dir):
                if filename.endswith('.py'):
                    filepath = os.path.join(skill_dir, filename)
                    analysis = self.code_analyzer.analyze_file(filepath)
                    if "issues" in analysis:
                        code_issues.extend(analysis["issues"])
        
        # Generate suggestions
        suggestions = self.code_analyzer.suggest_optimizations(self.metrics)
        
        # Get user behavior insights
        insights = {
            "preferred_topics": self.pattern_analyzer.get_preferred_topics(),
            "peak_hours": self.pattern_analyzer.get_peak_activity_hours(),
            "recommended_strategy": self.pattern_analyzer.suggest_response_strategy(),
            "average_input_length": self.pattern_analyzer.get_average_input_length()
        }
        
        # Create optimization report
        report = {
            "optimized": True,
            "timestamp": datetime.now().isoformat(),
            "metrics_summary": {
                "average_response_time": self.metrics.get_average_response_time(),
                "success_rate": self.metrics.get_success_rate(),
                "total_interactions": self.metrics.total_requests
            },
            "code_issues": code_issues,
            "suggestions": suggestions,
            "user_insights": insights,
            "optimizations_applied": []
        }
        
        # Apply automatic optimizations if safe
        optimizations_applied = self._apply_safe_optimizations()
        report["optimizations_applied"] = optimizations_applied
        
        self.optimization_history.append(report)
        self._save_data()
        
        return report
    
    def _apply_safe_optimizations(self) -> List[str]:
        """Apply safe, automatic optimizations"""
        applied = []
        
        # 1. Update optimal response times based on recent performance
        for skill in self.metrics.skill_usage.keys():
            success_rate = self.metrics.get_skill_success_rate(skill)
            if success_rate > 0.9:
                self.metrics.optimal_response_times[skill] = 0.8  # Target time
                applied.append(f"Updated optimal response time for {skill}")
        
        # 2. Create response strategy preference
        strategy = self.pattern_analyzer.suggest_response_strategy()
        strategy_file = os.path.join(
            self.allowed_dirs[1], "response_strategy.json"  # customizations
        )
        try:
            with open(strategy_file, 'w') as f:
                json.dump({
                    "strategy": strategy,
                    "updated": datetime.now().isoformat()
                }, f, indent=2)
            applied.append(f"Updated response strategy to '{strategy}'")
        except:
            pass
        
        return applied
    
    def generate_optimization_prompt(self) -> str:
        """Generate a prompt for AI to create new optimizations"""
        insights = {
            "preferred_topics": self.pattern_analyzer.get_preferred_topics(),
            "recommended_strategy": self.pattern_analyzer.suggest_response_strategy(),
            "performance_issues": self.code_analyzer.suggest_optimizations(self.metrics)
        }
        
        prompt = f"""
Based on my analysis, here are opportunities for self-improvement:

User Patterns:
- Preferred topics: {', '.join(insights['preferred_topics'])}
- Recommended response strategy: {insights['recommended_strategy']}

Performance Issues:
{chr(10).join(f'- {issue}' for issue in insights['performance_issues'])}

I can create new skills or modify existing ones in ai_selfdevelop/skills to better serve the user's needs.
Consider creating specialized skills for the user's frequent topics.
"""
        return prompt
    
    def get_status_summary(self) -> str:
        """Get a human-readable status summary"""
        summary = []
        summary.append(f"Total interactions: {self.metrics.total_requests}")
        summary.append(f"Average response time: {self.metrics.get_average_response_time():.2f}s")
        summary.append(f"Success rate: {self.metrics.get_success_rate():.1%}")
        summary.append(f"Preferred topics: {', '.join(self.pattern_analyzer.get_preferred_topics(3))}")
        summary.append(f"Response strategy: {self.pattern_analyzer.suggest_response_strategy()}")
        
        if self.last_optimization:
            elapsed = datetime.now() - self.last_optimization
            summary.append(f"Last optimization: {elapsed.total_seconds()/60:.1f} minutes ago")
        
        return "\n".join(summary)


# Singleton instance
_optimizer_instance = None

def get_optimizer() -> SelfOptimizer:
    """Get the singleton optimizer instance"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = SelfOptimizer()
    return _optimizer_instance
