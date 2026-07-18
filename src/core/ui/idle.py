import threading, time
import os
import sys

# Add core directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.gan_iteration import GANIteration
from tools.self_optimizer import get_optimizer
from memory import add_thought, save_memory

_idle_engine_instance = None

class IdleEngine:
    """
    空闲引擎 - AI在没有用户交互时进行的内部思考活动
    
    功能：
    - 定期GAN自我辩论
    - 定期反思和总结
    - AI自我优化和性能分析（在GAN空闲时间）
    - 不生成对话回复，只显示在思考面板
    - 在GAN思考期间缓存用户问题，并在GAN完成后交给主引擎处理
    """
    def __init__(self, memory, callback, idle_interval=300, gan_enabled=True):
        global _idle_engine_instance
        _idle_engine_instance = self
        """
        Args:
            memory: 共享的记忆系统
            callback: 事件回调函数
            idle_interval: 空闲活动间隔（秒），默认5分钟
            gan_enabled: 是否启用空闲GAN思考
        """
        self.memory = memory
        self.callback = callback
        self.idle_interval = idle_interval
        self.gan_enabled = gan_enabled
        self.running = True
        self.paused = False
        self.is_running_gan = False
        self.pending_chats = []
        self.gan = GANIteration()
        self.gan.callback = self._gan_callback
        self.optimizer = get_optimizer()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def record_interaction(self, user_input: str, response_time: float, success: bool = True, topic: str = None):
        """Record an interaction for self-optimization"""
        self.optimizer.record_interaction(user_input, response_time, success, topic)
    
    def record_skill_execution(self, skill_name: str, success: bool = True):
        """Record skill execution for optimization"""
        self.optimizer.record_skill_execution(skill_name, success)

    def _gan_callback(self, response):
        """转发GAN的进度回调"""
        if self.callback:
            self.callback(response)

    def _run(self):
        """主循环 - 定期进行内部思考"""
        while self.running:
            try:
                if self.paused:
                    time.sleep(self.idle_interval)
                    continue

                if self.gan_enabled:
                    # 定期进行GAN辩论作为内部思考
                    self._perform_gan_thinking()
                else:
                    # 如果禁用了GAN，则只等待间隔后继续
                    time.sleep(self.idle_interval)
                    continue
            except Exception as e:
                if self.callback:
                    try:
                        self.callback({"type": "error", "error": f"空闲引擎错误: {e}"})
                    except:
                        pass
            
            time.sleep(self.idle_interval)

    def _perform_gan_thinking(self):
        """
        Perform GAN internal thinking.
        
        Process:
        1. Aize chooses an activity from activity list
        2. If "自己思考", Aize determines a specific thinking topic
        3. GAN debates around the chosen topic
        4. Output conclusion with "让我们开始工作吧"
        
        Note: this is an internal thought process only and does not generate a user-facing reply.
        The result is sent to the UI as a thought entry.
        """
        self.is_running_gan = True
        gan_result = None
        try:
            # Step 1: Let Aize choose an activity and determine thinking direction
            activity, thinking_topic = self._choose_activity()
            
            if self.callback:
                self.callback({
                    "type": "internal_thought",
                    "thought": f"[Idle Activity] Aize chooses: {activity}"
                })
            
            if activity == "3. 自己思考" and thinking_topic:
                # Step 2: GAN debates around the chosen topic
                if self.callback:
                    self.callback({
                        "type": "internal_thought",
                        "thought": f"[Thinking Direction] {thinking_topic}"
                    })
                
                debate = self.gan.self_debate(is_user_topic=True, user_topic=thinking_topic)
                synthesis = debate.get('synthesis', '')
                gan_result = {
                    "topic": getattr(self.gan, "topic", ""),
                    "synthesis": synthesis,
                    "reply_a": getattr(self.gan, "reply_a", ""),
                    "reply_b": getattr(self.gan, "reply_b", "")
                }
                
                if self.memory is not None:
                    add_thought(self.memory, synthesis, thought_type="gan")
                    save_memory(self.memory)
                
                if self.callback:
                    self.callback({
                        "type": "internal_thought",
                        "thought": f"[Self-thought] {synthesis}"
                    })
                    self.callback({
                        "type": "gan_complete",
                        "gan_result": gan_result
                    })
            elif activity == "4. 找用户说话":
                # Aize wants to talk to user, queue a break silence task
                if self.callback:
                    self.callback({
                        "type": "internal_thought",
                        "thought": f"[Idle Activity] Aize wants to talk to user: {thinking_topic}"
                    })
            else:
                # Other activities, just log
                if self.callback:
                    self.callback({
                        "type": "internal_thought",
                        "thought": f"[Idle Activity] {activity} - {thinking_topic}"
                    })
                
        except Exception as e:
            if self.callback:
                self.callback({"type": "error", "error": f"GAN thinking failed: {e}"})
        finally:
            self.is_running_gan = False
            self._flush_pending_chats()
            
            # 在GAN完成后运行自我优化（如果有足够的交互数据）
            self._run_self_optimization()
    
    def _choose_activity(self):
        """让Aize选择空闲活动和思考方向"""
        from llm import chat
        from core.data.prompts_manager import load_prompt
        
        prompt = load_prompt("idle_activity_choice")
        
        try:
            response = chat(prompt).strip()
            
            activity = ""
            topic = ""
            
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith("活动：") or line.startswith("活动:"):
                    activity = line.replace("活动：", "").replace("活动:", "").strip()
                elif line.startswith("话题：") or line.startswith("话题:"):
                    topic = line.replace("话题：", "").replace("话题:", "").strip()
            
            if not activity:
                activity = "3. 自己思考"
            if not topic and activity == "3. 自己思考":
                topic = "人工智能的发展趋势"
            
            return activity, topic
        except Exception as e:
            return "3. 自己思考", "日常思考"
    
    def _run_self_optimization(self):
        """Run AI self-optimization during GAN idle time"""
        if not self.optimizer.should_optimize():
            return
        
        try:
            # 运行优化分析
            report = self.optimizer.run_optimization()
            
            if report.get("optimized"):
                # 发送优化状态到UI
                if self.callback:
                    insights = report.get("user_insights", {})
                    optimization_msg = f"[Self-Optimization] Analyzed patterns: preferred topics={insights.get('preferred_topics', [])}, strategy={insights.get('recommended_strategy', 'balanced')}"
                    
                    self.callback({
                        "type": "internal_thought",
                        "thought": optimization_msg
                    })
                    
                    # 如果有应用的优化，通知用户
                    applied = report.get("optimizations_applied", [])
                    if applied:
                        for opt in applied:
                            self.callback({
                                "type": "internal_thought",
                                "thought": f"[Auto-Optimization] {opt}"
                            })
        except Exception as e:
            if self.callback:
                self.callback({
                    "type": "error", 
                    "error": f"Self-optimization failed: {e}"
                })
    
    def get_optimization_status(self) -> str:
        """Get self-optimization status summary"""
        return self.optimizer.get_status_summary()
    
    def get_optimization_prompt(self) -> str:
        """Get prompt for AI to create new optimizations"""
        return self.optimizer.generate_optimization_prompt()

    def queue_user_chat(self, prompt, memory):
        if self.is_running_gan:
            self.pending_chats.append({"prompt": prompt, "memory": memory})
            return True
        return False

    def pause(self):
        """暂时暂停空闲GAN思考，立即停止当前正在运行的GAN"""
        self.paused = True
        if self.is_running_gan:
            try:
                self.gan.stop_immediately()
            except Exception:
                pass

    def resume(self):
        """恢复空闲GAN思考"""
        self.paused = False

    def _flush_pending_chats(self):
        if not self.pending_chats:
            return

        while self.pending_chats:
            pending = self.pending_chats.pop(0)
            if self.callback:
                self.callback({
                    "type": "pending_chat_ready",
                    "prompt": pending.get("prompt"),
                    "memory": pending.get("memory")
                })

    def signal_user_activity(self):
        """收到用户活动信号，暂停当前的GAN思考"""
        if self.is_running_gan:
            try:
                self.gan.stop_immediately()
            except Exception:
                pass
        self.paused = True
        self._resume_timer = time.time()

    def check_resume(self):
        """检查是否应该恢复空闲思考（用户活动结束1分钟后）"""
        if self.paused and hasattr(self, '_resume_timer'):
            if time.time() - self._resume_timer >= 60:
                self.paused = False

    def stop(self):
        """停止空闲引擎"""
        self.running = False
