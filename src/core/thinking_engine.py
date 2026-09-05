import os
import sys
import threading, queue, re, json
from datetime import datetime

# Add core directory to path
core_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, core_dir)

# 导入日志模块
try:
    from tools.logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from memory import add, add_thought, save_memory
from llm.llm_enhanced import generate_with_emotion_feedback, generate_with_emotion_feedback_stream
from Agent import Agent
from tools.notify import notify_ai_decision, notify_ai_response
from tools.web_search import WebSearch
from tools.self_optimizer import get_optimizer
from Prompt.chat_prompt import get_break_silence_prompt
from data.prompts_manager import (
    load_should_answer_user_prompt,
    load_should_use_gan_prompt,
    load_should_use_solve_prompt,
    load_should_reconsider_prompt,
    load_should_proactively_speak_prompt,
    load_choose_response_topic_prompt,
    load_followup_prompt,
    load_web_search_prefix_prompt
)

class ThinkingEngine:
    _game_mode = False
    
    def __init__(self, on_response_callback=None):
        logger.info("Initializing ThinkingEngine")
        self.on_response = on_response_callback
        self.queue = queue.Queue()
        self.running = True
        self.latest_gan_result = None
        self.thread = threading.Thread(target=self._process, daemon=True)
        self.thread.start()
        self.language = "en"
        self._decision_queue = queue.Queue()
        self._decision_thread = threading.Thread(target=self._process_decisions, daemon=True)
        # 初始化自我优化器
        self.optimizer = get_optimizer()
        self._last_interaction_time = None
        self._interaction_count = 0
        self._decision_thread.start()
        
        # Initialize web search capability
        self.web_search = WebSearch()
        logger.info("ThinkingEngine initialized successfully")
        self.search_enabled = True  # Enable web search by default
        
        self._stream_callbacks = []
    
    def register_stream_callback(self, callback):
        """注册流式输出回调函数，用于实时发送消息（如QQ）"""
        if callback not in self._stream_callbacks:
            self._stream_callbacks.append(callback)
    
    def unregister_stream_callback(self, callback):
        """注销流式输出回调函数"""
        if callback in self._stream_callbacks:
            self._stream_callbacks.remove(callback)
    
    def _notify_stream_callbacks(self, sentence, target_info=None):
        """通知所有注册的流式回调函数"""
        for callback in self._stream_callbacks:
            try:
                callback(sentence, target_info)
            except Exception as e:
                logger.error(f"Stream callback error: {e}")
    
    @classmethod
    def set_game_mode(cls, enabled: bool):
        cls._game_mode = enabled
        logger.info(f"Game mode {'enabled' if enabled else 'disabled'}")
    
    def set_language(self, language: str):
        """Set the current language for the engine"""
        self.language = language
    
    def _process_decisions(self):
        """Process asynchronous decision requests in a dedicated thread"""
        while self.running:
            try:
                task = self._decision_queue.get(timeout=0.5)
                if task is None:
                    break

                task_type = task.get("type")
                callback = task.get("callback")

                if task_type == "should_answer":
                    logger.info("Processing should_answer decision...")
                    result = self._should_answer_user_sync(task.get("user_text"))
                    logger.info(f"should_answer result: {result[0]}")
                    if callback:
                        callback(result)
                elif task_type == "should_use_gan":
                    logger.info("Processing should_use_gan decision...")
                    result = self._should_use_gan_sync(task.get("user_text"), task.get("context"))
                    logger.info(f"should_use_gan result: {result[0]}")
                    if callback:
                        callback(result)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Decision processing error: {e}")
    
    def _should_answer_user_sync(self, user_text):
        """Synchronous version of should_answer_user for internal use"""
        from llm import chat

        decision_prompt = load_should_answer_user_prompt(user_text)

        try:
            logger.info(f"Calling LLM for should_answer decision (text: {user_text[:50] if user_text else 'None'})")
            response = chat(decision_prompt, max_tokens=100, temperature=0.3, timeout=30, max_retries=0).strip()
            logger.info(f"should_answer LLM response: {response[:100] if response else 'Empty'}")
            decision = self._parse_json_decision(response)
            should_answer = decision.get("decision") == "answer"
            if not decision:
                should_answer = "是" in response or "YES" in response.upper() or "会" in response
            # 发送AI决策通知
            decision = "YES" if should_answer else "NO"
            notify_ai_decision(decision, response)
            return (should_answer, response)
        except Exception as e:
            # 默认回答用户，避免流程中断
            logger.error(f"should_answer LLM error: {e}")
            return (True, f"Error: {e} (defaulting to answer)")
    
    def _should_use_gan_sync(self, user_text, context=""):
        """Synchronous version of should_use_gan_for_answer for internal use"""
        from llm import chat

        decision_prompt = load_should_use_gan_prompt(user_text, context)

        try:
            logger.info(f"Calling LLM for GAN decision (text: {user_text[:50] if user_text else 'None'})")
            response = chat(decision_prompt, max_tokens=100, temperature=0.3, timeout=30, max_retries=0).strip()
            logger.info(f"GAN decision LLM response: {response[:100] if response else 'Empty'}")
            decision = self._parse_json_decision(response)
            should_use_gan = bool(decision.get("use_gan")) if decision else ("是" in response or "YES" in response.upper())
            return (should_use_gan, response)
        except Exception as e:
            logger.error(f"GAN decision LLM error: {e}")
            return (False, f"Error: {e} (defaulting to no GAN)")

    def _should_use_solve_sync(self, user_text):
        """请求 AI 判断是否允许使用经验库中的 Solve 快速方案。"""
        from llm import chat

        decision_prompt = load_should_use_solve_prompt(user_text)
        try:
            logger.info(f"Calling LLM for Solve decision (text: {user_text[:50] if user_text else 'None'})")
            response = chat(decision_prompt, max_tokens=100, temperature=0.3, timeout=30, max_retries=0).strip()
            decision = self._parse_json_decision(response)
            should_use_solve = bool(decision.get("use_solve")) if decision else False
            logger.info(
                f"Solve decision: use_solve={should_use_solve}, "
                f"reason={decision.get('reason', response[:100] if response else 'Empty')}"
            )
            return should_use_solve
        except Exception as e:
            logger.error(f"Solve decision LLM error: {e}")
            return False

    @staticmethod
    def _parse_json_decision(response):
        """从模型输出中提取严格 JSON 决策对象。"""
        try:
            payload = json.loads(response)
            return payload if isinstance(payload, dict) else {}
        except (TypeError, json.JSONDecodeError):
            match = re.search(r"\{.*\}", response or "", flags=re.DOTALL)
            if not match:
                return {}
            try:
                payload = json.loads(match.group(0))
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                return {}
    
    def should_answer_user_async(self, user_text, callback):
        """Asynchronously decide if AI should answer the user"""
        self._decision_queue.put({
            "type": "should_answer",
            "user_text": user_text,
            "callback": callback
        })
    
    def should_use_gan_async(self, user_text, context, callback):
        """Asynchronously decide if AI should use GAN thinking"""
        self._decision_queue.put({
            "type": "should_use_gan",
            "user_text": user_text,
            "context": context,
            "callback": callback
        })

    def _load_ui_settings(self) -> dict:
        settings_path = os.path.join(os.path.dirname(__file__), "data", "ui_settings.json")
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_agent_prompt(self, personality=None) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "data", "agent_prompt.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
        except Exception:
            prompt = (
                "You are an assistant that can execute shell commands and Openclaw-style skills through the Agent interface. "
                "Always begin by writing an internal thought section labeled THOUGHT:, then write a final answer section labeled RESPONSE:. "
                "If you need to invoke a skill, output exactly one JSON object with keys such as {\"skill\": \"shell\", \"input\": \"...\"} or {\"skill\": \"shell\", \"input\": {\"command\": \"...\"}}. "
                "Do not output any other text outside the exact command or JSON object. "
                "Do not use markdown formatting, code fences, or extra commentary. "
                "If you do not need to execute anything, still provide a THOUGHT: section describing your reasoning, followed by RESPONSE: with the answer. "
                "After the Agent runs the command or skill, wait for the result and continue with the next step in plain text. "
                "If a command fails, fix it in the next response. "
            )
        
        # 添加人格信息到提示词
        if personality:
            try:
                try:
                    from core.personality import get_personality_context
                except ImportError:
                    from personality import get_personality_context
                personality_context = get_personality_context(personality)
                prompt = personality_context + "\n\n" + prompt
            except Exception as e:
                logger.warning(f"Failed to load personality context: {e}")
        
        try:
            from Agent import Agent
            agent = Agent('!')
            skills_prompt = agent.get_skills_prompt()
            if skills_prompt:
                prompt += "\n\n" + skills_prompt
        except Exception:
            pass
        
        ui_settings = self._load_ui_settings()
        skills_prompt = ui_settings.get("skills_prompt", "")
        if skills_prompt:
            prompt += "\n\n# Skills configuration\n" + skills_prompt.strip()
        return prompt

    def _build_model_prompt(self, main_prompt, memory, user_question, gan_prompt="", other_prompts=None):
        """Build the English-labeled prompt contract used for user responses."""
        memory_messages = (memory or {}).get("messages", []) if isinstance(memory, dict) else []
        memory_lines = []
        for message in memory_messages[-20:]:
            if not isinstance(message, dict):
                continue
            role = message.get("role", "unknown")
            content = message.get("content", "")
            if content:
                memory_lines.append(f"{role}: {content}")

        memory_text = "\n".join(memory_lines) or "No previous memory."
        other_text = "\n\n".join(str(item).strip() for item in (other_prompts or []) if str(item).strip())
        other_text = other_text or "None."
        gan_text = str(gan_prompt or "").strip() or "None."

        return (
            "MAIN PROMPT:\n"
            f"{str(main_prompt or '').strip()}\n\n"
            "MEMORY DATABASE:\n"
            f"{memory_text}\n\n"
            "CURRENT USER QUESTION:\n"
            f"{str(user_question or '').strip()}\n\n"
            "GAN PROMPT:\n"
            f"{gan_text}\n\n"
            "OTHER PROMPTS:\n"
            f"{other_text}\n\n"
            "Respond concisely. Respond in the same language as the user's input."
        )

    def _build_response_prompt(self, exec_instr, prompt, memory, user_text):
        """Place task-specific context into the standard response prompt."""
        prompt_text = str(prompt or "")
        gan_prompt = ""
        other_prompts = [prompt_text]
        if "[GAN synthesis:" in prompt_text or "[GAN topic:" in prompt_text:
            gan_prompt = prompt_text
            other_prompts = []
        return self._build_model_prompt(exec_instr, memory, user_text, gan_prompt, other_prompts)

    def _extract_thought_and_response(self, text: str):
        if not text:
            return None, ""

        try:
            payload = json.loads(text)
            if isinstance(payload, dict) and "skill" not in payload:
                thought = payload.get("thought")
                response = payload.get("response", payload.get("message", payload.get("content", "")))
                if isinstance(response, dict):
                    response = response.get("content", response.get("message", ""))
                if isinstance(response, str):
                    return thought if isinstance(thought, str) else None, response
        except (TypeError, json.JSONDecodeError):
            pass

        pattern = re.compile(r"(?si)(THOUGHT|RESPONSE)\s*:\s*")
        segments = []
        last_label = None
        last_end = 0

        for match in pattern.finditer(text):
            if last_label is not None:
                segments.append((last_label, text[last_end:match.start()].strip()))
            last_label = match.group(1).upper()
            last_end = match.end()

        if last_label is not None:
            segments.append((last_label, text[last_end:].strip()))

        thought = None
        response = None
        for label, content in segments:
            if not content:
                continue
            if label == "THOUGHT":
                thought = content
            elif label == "RESPONSE":
                response = content

        if response is not None:
            return thought, response
        return None, text.strip()

    def _process(self):
        logger.info("Process thread started")
        while self.running:
            task = self.queue.get()
            if task is None:
                logger.info("Process thread received None, stopping")
                break
            
            task_type = task.get("type", "chat")
            prompt = task.get("prompt", "")
            memory = task.get("memory")
            emotion_monitor = task.get("emotion_monitor")
            user_text = task.get("user_text")
            personality = task.get("personality")
            
            logger.info(f"Processing task: type={task_type}, prompt_length={len(prompt) if prompt else 0}")
            
            # 从 data/agent_prompt.txt 加载提示词（包含人格信息）
            exec_instr = self._load_agent_prompt(personality)
            
            # 区分不同的任务类型
            if task_type == "gan":
                # GAN debate task - only internal thought, no direct response
                self._handle_gan_task(task, memory)
            elif task_type == "break_silence":
                # break_silence task - generate an actual assistant reply
                self._handle_break_silence_task(prompt, memory, emotion_monitor, exec_instr)
            elif task_type == "reflection":
                # reflection task - internal thought only
                self._handle_reflection_task(prompt, memory, emotion_monitor, exec_instr)
            elif task_type == "chat_with_gan_decision":
                self._handle_chat_with_gan_decision_task(task, prompt, memory, emotion_monitor, exec_instr, user_text)
            elif task_type == "chat_stream":
                # 流式聊天任务 - 实时发送句子（包含GAN决策）
                target_info = task.get("target_info")
                self._handle_chat_with_gan_decision_stream_task(prompt, memory, emotion_monitor, exec_instr, user_text, target_info)
            else:  # chat
                # 普通聊天任务
                self._handle_chat_task(prompt, memory, emotion_monitor, exec_instr)
        
        logger.info("Process thread stopped")

    def _handle_chat_task(self, prompt, memory, emotion_monitor, exec_instr):
        """Handle a normal chat task."""
        final_reply = ""
        logger.info(f"Handling chat task, prompt length: {len(prompt) if prompt else 0}")
        # First check if web search is needed
        user_text = self._extract_user_text_from_prompt(prompt)
        
        # Solve模式：先尝试从经验数据库快速查找解决方案
        quick_solution = None
        if self._should_use_solve_sync(user_text):
            quick_solution = self.optimizer.solve_problem(user_text)
        if quick_solution:
            logger.info(f"Solve mode: Found quick solution for '{user_text[:30]}'")
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": "[Solve Mode] 使用经验数据库快速解决问题", "thought_type": "solve_mode"})
            
            # 只保存到经验数据库（Solve模式）
            self.optimizer.record_solve_interaction(user_text, quick_solution, success=True)
            
            if memory is not None:
                add(memory, "assistant", quick_solution, source="ai_response")
                save_memory(memory)
            if self.on_response:
                self.on_response({"type": "chat_response", "reply": quick_solution})
            notify_ai_response(quick_solution)
            
            # 记录学习（只记录到经验）
            self._record_and_learn(user_text, quick_solution)
            return
        
        # 检查是否有蒸馏知识可用
        distilled_prompt = self.optimizer.conversation_learner.prompt_distiller.generate_training_prompt(user_text)
        if distilled_prompt:
            logger.info(f"Using distilled prompt for topic: {user_text[:30]}")
            # 将蒸馏知识添加到提示词中
            prompt = distilled_prompt + "\n\n" + prompt
        
        # Check if we should perform a web search
        if self.search_enabled and user_text and self.web_search.needs_search(user_text):
            search_results = self.web_search.search(user_text)
            if search_results:
                # Add search results to prompt
                search_summary = self.web_search.summarize_results(user_text, search_results)
                if self.on_response:
                    self.on_response({"type": "internal_thought", "thought": f"[Web Search] Found information about: {user_text}", "thought_type": "web_search"})
                search_prefix = load_web_search_prefix_prompt(search_summary)
                prompt = search_prefix + "\n\n" + prompt
                logger.info(f"Web search performed for: {user_text}")
        
        logger.info("Calling generate_with_emotion_feedback")
        model_prompt = self._build_response_prompt(exec_instr, prompt, memory, user_text)
        reply, adaptation = generate_with_emotion_feedback(model_prompt, emotion_monitor)
        logger.info(f"LLM reply received: {reply[:200] if reply else 'Empty'}...")
        
        thought, target_reply = self._extract_thought_and_response(reply)
        logger.info(f"Extracted thought: {thought[:100] if thought else 'None'}, target_reply: {target_reply[:100] if target_reply else 'None'}")
        
        if thought:
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": thought, "thought_type": "internal"})
            if memory is not None:
                add_thought(memory, thought, thought_type="internal")
                save_memory(memory)

        if memory is not None:
            add(memory, "assistant", reply, source="ai_response")
            save_memory(memory)

        actual_reply = target_reply or reply
        
        # 提取RESPONSE内容（如果存在）
        response_content = self._extract_response_content(actual_reply)
        logger.info(f"Response content extracted: {response_content[:100] if response_content else 'None'}")
        
        try:
            agent = Agent('!')
            agent.set_language(self.language)
            if agent.has_actions(actual_reply):
                logger.info("Agent has actions to execute")
                if self.on_response:
                    self.on_response({"type": "command_start", "message": "AI is executing a command...\n"})
                out = agent.agent('!', actual_reply)
                logger.info(f"Agent output: {out[:200] if out else 'Empty'}")
                if self.on_response:
                    self.on_response({"type": "command_result", "output": out})
                
                # 从命令执行中学习
                self._learn_from_command_result(actual_reply, out, success=True)
                
                # 如果有RESPONSE内容，使用它；否则清理命令后作为回复
                if response_content:
                    final_reply = response_content
                else:
                    cleaned = re.sub(r'!.*?!', '', actual_reply, flags=re.S).strip()
                    if not cleaned or (cleaned.startswith('{') and cleaned.endswith('}')):
                        final_reply = "[Command executed; see command output]"
                    else:
                        final_reply = cleaned
                
                # 幻觉检测
                final_reply = self._hallucination_check(final_reply, user_text)
                        
                logger.info(f"AI final reply (with command): {final_reply}")
                
                if memory is not None:
                    add(memory, "assistant", final_reply, source="ai_response")
                    add(memory, "system", f"Command output:\n{out}", source="system")
                    save_memory(memory)
                if self.on_response:
                    self.on_response({"type": "chat_response", "reply": final_reply})
                # 发送AI回复通知
                notify_ai_response(final_reply)
                
                # 将命令结果发给AI，引导她解决问题
                try:
                    followup_prompt = load_followup_prompt(out, user_text)
                    logger.info("Generating followup response after command execution")
                    followup_model_prompt = self._build_response_prompt(exec_instr, followup_prompt, memory, user_text)
                    freply, fadapt = generate_with_emotion_feedback(followup_model_prompt, emotion_monitor)
                    logger.info(f"Followup reply: {freply[:200] if freply else 'Empty'}")
                    if memory is not None:
                        add(memory, "assistant", freply, source="ai_response")
                        save_memory(memory)
                    if self.on_response:
                        self.on_response({"type": "chat_response", "reply": freply})
                except Exception as e:
                    logger.error(f"Followup generation error: {e}")
            else:
                # 没有命令时，使用RESPONSE内容（如果存在）或完整回复
                if response_content:
                    final_reply = response_content
                else:
                    final_reply = actual_reply
                
                # 清理并人性化回复
                final_reply = self._clean_and_humanize_reply(final_reply)
                
                # 幻觉检测
                final_reply = self._hallucination_check(final_reply, user_text)
                
                # 如果清理后返回None，不发送回复（让AI重新生成）
                if final_reply:
                    logger.info(f"AI final reply (no command): {final_reply}")
                    if self.on_response:
                        self.on_response({"type": "chat_response", "reply": final_reply})
                    # 发送AI回复通知
                    notify_ai_response(final_reply)
                else:
                    logger.warning("AI reply was filtered out; sending fallback response")
                    if self.on_response:
                        self.on_response({
                            "type": "chat_response",
                            "reply": "抱歉，我暂时无法生成有效回复，请稍后再试。"
                        })
        except Exception as e:
            logger.error(f"Error in _handle_chat_task: {e}")
            if self.on_response:
                self.on_response({"type": "error", "error": str(e)})
        
        finally:
            # 记录交互并进行学习
            self._record_and_learn(user_text, final_reply)
    
    def _handle_chat_with_gan_decision_stream_task(self, prompt, memory, emotion_monitor, exec_instr, user_text, target_info=None):
        """Handle a streaming chat task with GAN decision - send sentences as they are generated."""
        logger.info(f"Handling chat_with_gan_decision_stream task, user_text: {user_text[:50] if user_text else 'None'}")
        
        try:
            from tools.gan_iteration import GANIteration
            gan = GANIteration()
            should_use_gan, decision_text = gan.decide_use_gan(user_text, exec_instr)
            logger.info(f"GAN decision: should_use_gan={should_use_gan}, decision_text={decision_text[:100] if decision_text else 'None'}")
        except Exception as e:
            logger.error(f"GAN decision error: {e}")
            should_use_gan, decision_text = False, f"GAN decision failed: {e}"

        if self.on_response and decision_text:
            self.on_response({"type": "internal_thought", "thought": f"[GAN Decision] {decision_text}"})

        ui_settings = self._load_ui_settings()
        gan_enabled = ui_settings.get("gan_enabled", True)

        if ThinkingEngine._game_mode:
            logger.info("Game mode active, skipping GAN to save computational resources")
            should_use_gan = False

        if should_use_gan and gan_enabled:
            logger.info("GAN enabled, performing GAN debate")
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": "[GAN Decision] AI chose to perform GAN thinking before answering.", "thought_type": "gan_decision"})
            debate_result = gan.self_debate(True, user_text)
            synthesis = debate_result.get("synthesis", "")
            logger.info(f"GAN synthesis: {synthesis[:100] if synthesis else 'None'}")
            if memory is not None:
                add_thought(memory, synthesis, thought_type="gan")
                save_memory(memory)
            self._save_gan_result(gan, debate_result, True, user_text)
            gan_topic = getattr(gan, "topic", None)
            augmentation = ""
            if gan_topic:
                augmentation += f"\n[GAN topic: {gan_topic}]"
            if synthesis:
                augmentation += f"\n[GAN synthesis: {synthesis}]"
            enhanced_prompt = prompt + "\n\n" + augmentation + "\n\nAssistant: Please answer the user's question using the GAN debate synthesis above."
            logger.info(f"Enhanced prompt with GAN augmentation")
            self._handle_chat_stream_task(enhanced_prompt, memory, emotion_monitor, exec_instr, user_text, target_info)
        else:
            logger.info("GAN skipped, answering directly")
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": "[GAN Decision] AI chose to answer directly without GAN thinking.", "thought_type": "gan_decision"})
            self._handle_chat_stream_task(prompt, memory, emotion_monitor, exec_instr, user_text, target_info)

    def _handle_chat_stream_task(self, prompt, memory, emotion_monitor, exec_instr, user_text, target_info=None):
        """Handle a streaming chat task - send sentences as they are generated."""
        logger.info(f"Handling streaming chat task, prompt length: {len(prompt) if prompt else 0}")
        
        user_text = user_text or self._extract_user_text_from_prompt(prompt)
        
        quick_solution = None
        if self._should_use_solve_sync(user_text):
            quick_solution = self.optimizer.solve_problem(user_text)
        if quick_solution:
            logger.info(f"Solve mode: Found quick solution for '{user_text[:30]}'")
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": "[Solve Mode] 使用经验数据库快速解决问题", "thought_type": "solve_mode"})
            self.optimizer.record_solve_interaction(user_text, quick_solution, success=True)
            if memory is not None:
                add(memory, "assistant", quick_solution, source="ai_response")
                save_memory(memory)
            
            sentences = self._split_sentences(quick_solution)
            for sentence in sentences:
                if self.on_response:
                    self.on_response({"type": "chat_response", "reply": sentence})
                self._notify_stream_callbacks(sentence, target_info)
            
            notify_ai_response(quick_solution)
            self._record_and_learn(user_text, quick_solution)
            return
        
        distilled_prompt = self.optimizer.conversation_learner.prompt_distiller.generate_training_prompt(user_text)
        if distilled_prompt:
            prompt = distilled_prompt + "\n\n" + prompt
        
        if self.search_enabled and user_text and self.web_search.needs_search(user_text):
            search_results = self.web_search.search(user_text)
            if search_results:
                search_summary = self.web_search.summarize_results(user_text, search_results)
                if self.on_response:
                    self.on_response({"type": "internal_thought", "thought": f"[Web Search] Found information about: {user_text}", "thought_type": "web_search"})
                search_prefix = load_web_search_prefix_prompt(search_summary)
                prompt = search_prefix + "\n\n" + prompt
        
        logger.info("Calling generate_with_emotion_feedback_stream")
        
        full_reply = ""
        current_buffer = ""
        sent_sentences = []
        
        try:
            model_prompt = self._build_response_prompt(exec_instr, prompt, memory, user_text)
            for token in generate_with_emotion_feedback_stream(model_prompt, emotion_monitor):
                if token:
                    full_reply += token
                    current_buffer += token
                    
                    completed_sentences = self._extract_completed_sentences(current_buffer)
                    for sentence in completed_sentences:
                        sentence = sentence.strip()
                        if sentence and sentence not in sent_sentences:
                            sent_sentences.append(sentence)
                            cleaned = self._clean_and_humanize_reply(sentence)
                            if cleaned:
                                cleaned = self._hallucination_check(cleaned, user_text)
                                logger.info(f"Streaming sentence: {cleaned[:50]}...")
                                if self.on_response:
                                    self.on_response({"type": "chat_response", "reply": cleaned})
                                self._notify_stream_callbacks(cleaned, target_info)
                            
                    current_buffer = self._get_remaining_buffer(current_buffer)
            
            if current_buffer.strip():
                cleaned = self._clean_and_humanize_reply(current_buffer.strip())
                if cleaned and cleaned not in sent_sentences:
                    cleaned = self._hallucination_check(cleaned, user_text)
                    sent_sentences.append(cleaned)
                    logger.info(f"Final streaming sentence: {cleaned[:50]}...")
                    if self.on_response:
                        self.on_response({"type": "chat_response", "reply": cleaned})
                    self._notify_stream_callbacks(cleaned, target_info)
            
            thought, target_reply = self._extract_thought_and_response(full_reply)
            if thought:
                if self.on_response:
                    self.on_response({"type": "internal_thought", "thought": thought, "thought_type": "internal"})
                if memory is not None:
                    add_thought(memory, thought, thought_type="internal")
                    save_memory(memory)
            
            if memory is not None:
                add(memory, "assistant", full_reply, source="ai_response")
                save_memory(memory)
            
            try:
                agent = Agent('!')
                agent.set_language(self.language)
                if agent.has_actions(full_reply):
                    logger.info("Agent has actions to execute")
                    if self.on_response:
                        self.on_response({"type": "command_start", "message": "AI is executing a command...\n"})
                    
                    out = agent.agent('!', full_reply)
                    logger.info(f"Agent output: {out[:200] if out else 'Empty'}")
                    
                    if self.on_response:
                        self.on_response({"type": "command_result", "output": out})
                    
                    self._learn_from_command_result(full_reply, out, success=True)
                    
                    response_content = self._extract_response_content(full_reply)
                    if response_content:
                        final_reply = response_content
                    else:
                        cleaned = re.sub(r'!.*?!', '', full_reply, flags=re.S).strip()
                        if not cleaned or (cleaned.startswith('{') and cleaned.endswith('}')):
                            final_reply = "[Command executed; see command output]"
                        else:
                            final_reply = cleaned
                    
                    sentences = self._split_sentences(final_reply)
                    for sentence in sentences:
                        if sentence and sentence not in sent_sentences:
                            sent_sentences.append(sentence)
                            cleaned_sentence = self._clean_and_humanize_reply(sentence)
                            if cleaned_sentence:
                                logger.info(f"Command result sentence: {cleaned_sentence[:50]}...")
                                if self.on_response:
                                    self.on_response({"type": "chat_response", "reply": cleaned_sentence})
                                self._notify_stream_callbacks(cleaned_sentence, target_info)
                    
                    try:
                        followup_prompt = load_followup_prompt(out, user_text)
                        logger.info("Generating followup response after command execution")
                        followup_model_prompt = self._build_response_prompt(exec_instr, followup_prompt, memory, user_text)
                        freply, fadapt = generate_with_emotion_feedback(followup_model_prompt, emotion_monitor)
                        logger.info(f"Followup reply: {freply[:200] if freply else 'Empty'}")
                        
                        if memory is not None:
                            add(memory, "assistant", freply, source="ai_response")
                            save_memory(memory)
                        
                        fthought, ftarget_reply = self._extract_thought_and_response(freply)
                        fresponse_content = self._extract_response_content(ftarget_reply or freply)
                        ffinal_reply = fresponse_content or (ftarget_reply or freply)
                        
                        fsentences = self._split_sentences(ffinal_reply)
                        for sentence in fsentences:
                            if sentence and sentence not in sent_sentences:
                                sent_sentences.append(sentence)
                                cleaned_sentence = self._clean_and_humanize_reply(sentence)
                                if cleaned_sentence:
                                    if self.on_response:
                                        self.on_response({"type": "chat_response", "reply": cleaned_sentence})
                                    self._notify_stream_callbacks(cleaned_sentence, target_info)
                    except Exception as e:
                        logger.error(f"Followup generation error: {e}")
            except Exception as e:
                logger.error(f"Error checking for agent actions: {e}")
            
            notify_ai_response(full_reply)
            
        except Exception as e:
            logger.error(f"Error in _handle_chat_stream_task: {e}")
            if self.on_response:
                self.on_response({"type": "error", "error": str(e)})
        
        finally:
            self._record_and_learn(user_text, full_reply)
    
    def _split_sentences(self, text):
        """按标点符号分割句子"""
        if not text:
            return []
        
        main_separators = r'([。！？…….!?])'
        parts = re.split(main_separators, text)
        
        sentences = []
        for i in range(0, len(parts), 2):
            sentence = parts[i].strip()
            if i + 1 < len(parts):
                sentence += parts[i + 1]
            if sentence:
                sentences.append(sentence)
        
        for i in range(len(sentences)):
            if len(sentences[i]) > 80:
                comma_parts = sentences[i].split('，')
                sub_segments = []
                current = ""
                for j, cp in enumerate(comma_parts):
                    if j > 0:
                        cp = '，' + cp
                    if len(current) + len(cp) <= 80:
                        current += cp
                    else:
                        if current:
                            sub_segments.append(current)
                        current = cp
                if current:
                    sub_segments.append(current)
                sentences[i:i+1] = sub_segments
        
        return sentences
    
    def _extract_completed_sentences(self, text):
        """从文本中提取已完成的句子（以标点结尾）"""
        if not text:
            return []
        
        sentence_end_pattern = r'[^。！？…….!?]*[。！？…….!?]'
        matches = re.findall(sentence_end_pattern, text)
        return [m.strip() for m in matches if m.strip()]
    
    def _get_remaining_buffer(self, text):
        """获取剩余未完成的句子缓冲"""
        if not text:
            return ""
        
        main_separators = r'[。！？…….!?]'
        parts = re.split(main_separators, text)
        if parts:
            return parts[-1].strip()
        return text.strip()
                
    def _record_and_learn(self, user_input, ai_response, command_result=None, command_success=True):
        """Record interaction and run continuous learning"""
        try:
            # 记录交互到自我优化器
            self.optimizer.record_interaction(
                user_input=user_input,
                ai_response=ai_response,
                response_time=0.0,
                success=True,
                sentiment=0.5
            )
            
            # 如果有命令执行结果，也记录下来
            if command_result:
                self.optimizer.record_command_result(command_result, ai_response, command_success)
            
            # 运行学习更新
            learning_result = self.optimizer.run_learning_update()
            if learning_result.get("learned", False):
                logger.info(f"Continuous learning completed: {learning_result}")
                
                # 如果学习到了新模式，检查是否需要创建新技能
                skill_suggestion = self.optimizer.conversation_learner.suggest_new_skill()
                if skill_suggestion:
                    logger.info(f"Skill suggestion: {skill_suggestion}")
                    # 自动生成技能创建提示
                    self._suggest_skill_creation(skill_suggestion)
            
            # 运行优化（如果条件满足）
            optimization_result = self.optimizer.run_optimization()
            if optimization_result.get("optimized", False):
                logger.info(f"Self-optimization completed: {optimization_result}")
                
        except Exception as e:
            logger.error(f"Error in _record_and_learn: {e}")
    
    def _suggest_skill_creation(self, suggestion):
        """Suggest creating a new skill based on learning"""
        if self.on_response:
            self.on_response({
                "type": "learning_insight",
                "message": f"根据学习分析，{suggestion} 需要我帮你创建这个技能吗？"
            })
    
    def _learn_from_command_result(self, command, result, success):
        """Learn from command execution result"""
        try:
            self.optimizer.record_command_result(command, result, success)
            
            # 分析命令执行结果，看看是否可以创建新技能
            if success:
                skill_suggestion = self.optimizer.conversation_learner.suggest_new_skill()
                if skill_suggestion:
                    if self.on_response:
                        self.on_response({
                            "type": "skill_suggestion",
                            "suggestion": skill_suggestion,
                            "command": command,
                            "result": result
                        })
        except Exception as e:
            logger.error(f"Error learning from command result: {e}")
                
    def _extract_user_text_from_prompt(self, prompt):
        """Extract user text from the prompt"""
        # Try to find user message in the prompt
        patterns = [
            r'USER:\s*(.+?)\s*(?:ASSISTANT:|$)',
            r'User:\s*(.+?)\s*(?:AI:|$)',
            r'user:\s*(.+?)\s*(?:assistant:|$)',
            r'你:\s*(.+?)\s*(?:我:|$)',
            r'用户:\s*(.+?)\s*(?:助手:|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt, re.DOTALL)
            if match:
                return match.group(1).strip()
                
        # If no pattern matches, return the whole prompt (truncated)
        return prompt[:500].strip()
    
    def _extract_response_content(self, text):
        """
        提取RESPONSE标签后的内容
        如果存在RESPONSE:标签，返回其后面的内容；否则返回None
        """
        if not text:
            return None

        matches = list(re.finditer(r'RESPONSE:\s*', text, flags=re.IGNORECASE))
        if not matches:
            return None

        start_pos = matches[-1].end()
        tail = text[start_pos:]

        next_label = re.search(r'(?i)\b(?:THOUGHT|RESPONSE)\s*:', tail)
        if next_label:
            content = tail[:next_label.start()].strip()
        else:
            content = tail.strip()

        content = re.sub(r'^```(?:json)?\s*\n?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\s*```$', '', content, flags=re.IGNORECASE).strip()

        return content if content else None

    def _run_gan_debate(self, user_topic, memory):
        try:
            from tools.gan_iteration import GANIteration
            gan = GANIteration()
            debate_result = gan.self_debate(True, user_topic)
            synthesis = debate_result.get("synthesis", "")
            if memory is not None:
                add_thought(memory, synthesis, thought_type="gan")
                save_memory(memory)
            self._save_gan_result(gan, debate_result, True, user_topic)
            return gan, synthesis
        except Exception:
            return None, ""

    def _handle_chat_with_gan_decision_task(self, task, prompt, memory, emotion_monitor, exec_instr, user_text):
        logger.info(f"Handling chat_with_gan_decision task, user_text: {user_text[:50] if user_text else 'None'}")
        decision_override = task.get("gan_decision")
        try:
            from tools.gan_iteration import GANIteration
            gan = GANIteration()
            if decision_override is None:
                should_use_gan, decision_text = gan.decide_use_gan(user_text, exec_instr)
            else:
                should_use_gan = bool(decision_override)
                decision_text = task.get("gan_decision_reason", "")
            logger.info(f"GAN decision: should_use_gan={should_use_gan}, decision_text={decision_text[:100] if decision_text else 'None'}")
        except Exception as e:
            logger.error(f"GAN decision error: {e}")
            should_use_gan, decision_text = False, f"GAN decision failed: {e}"

        if self.on_response and decision_text:
            self.on_response({"type": "internal_thought", "thought": f"[GAN Decision] {decision_text}"})

        ui_settings = self._load_ui_settings()
        gan_enabled = ui_settings.get("gan_enabled", True)

        if ThinkingEngine._game_mode:
            logger.info("Game mode active, skipping GAN to save computational resources")
            should_use_gan = False

        if should_use_gan and gan_enabled:
            logger.info("GAN enabled, performing GAN debate")
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": "[GAN Decision] AI chose to perform GAN thinking before answering.", "thought_type": "gan_decision"})
            debate_result = gan.self_debate(True, user_text)
            synthesis = debate_result.get("synthesis", "")
            logger.info(f"GAN synthesis: {synthesis[:100] if synthesis else 'None'}")
            if memory is not None:
                add_thought(memory, synthesis, thought_type="gan")
                save_memory(memory)
            self._save_gan_result(gan, debate_result, True, user_text)
            gan_topic = getattr(gan, "topic", None)
            augmentation = ""
            if gan_topic:
                augmentation += f"\n[GAN topic: {gan_topic}]"
            if synthesis:
                augmentation += f"\n[GAN synthesis: {synthesis}]"
            enhanced_prompt = prompt + "\n\n" + augmentation + "\n\nAssistant: Please answer the user's question using the GAN debate synthesis above."
            logger.info(f"Enhanced prompt with GAN augmentation")
            self._handle_chat_task(enhanced_prompt, memory, emotion_monitor, exec_instr)
        else:
            logger.info("GAN skipped, answering directly")
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": "[GAN Decision] AI chose to answer directly without GAN thinking.", "thought_type": "gan_decision"})
            self._handle_chat_task(prompt, memory, emotion_monitor, exec_instr)

    def _handle_break_silence_task(self, prompt, memory, emotion_monitor, exec_instr):
        """Handle break silence task - generate an actual assistant reply."""
        logger.info("Handling break_silence task")
        
        # 使用更友好的break silence提示词
        friendly_prompt = self._build_friendly_break_silence_prompt(prompt)
        
        reply, adaptation = generate_with_emotion_feedback(friendly_prompt, emotion_monitor)
        logger.info(f"Break silence reply: {reply[:200] if reply else 'Empty'}")
        thought, target_reply = self._extract_thought_and_response(reply)
        if thought:
            logger.info(f"Break silence thought: {thought[:100] if thought else 'None'}")
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": thought, "thought_type": "break_silence"})
            if memory is not None:
                add_thought(memory, thought, thought_type="break_silence")
                save_memory(memory)

        if memory is not None:
            add(memory, "assistant", reply, source="ai_autonomous")
            save_memory(memory)

        actual_reply = target_reply or reply
        # 清理回复，使其更自然
        actual_reply = self._clean_and_humanize_reply(actual_reply)
        
        # 如果清理后返回None，不发送回复（让AI重新生成）
        if actual_reply:
            logger.info(f"Break silence final reply: {actual_reply}")
            if self.on_response:
                self.on_response({"type": "chat_response", "reply": actual_reply})
        else:
            logger.info("Break silence reply was filtered out, not sending")
    
    def _build_friendly_break_silence_prompt(self, base_prompt):
        """构建更友好的打破沉默提示词（从统一的提示词文件获取）"""
        return get_break_silence_prompt(base_prompt)
    
    def _clean_and_humanize_reply(self, reply):
        """清理并人性化回复内容"""
        from utils.reply_cleaner import clean_reply
        
        if not reply:
            return None

        cleaned = clean_reply(reply)

        if not cleaned or cleaned.lower() in ['none', 'null', 'undefined', 'empty']:
            return None

        if re.match(r'(?i)^(command|instruction|next|execute|task|waiting|skill|json)\b', cleaned):
            return None

        cleaned = re.sub(r'(?i)\bTHOUGHT\s*:\s*', '', cleaned)
        cleaned = re.sub(r'(?i)\bRESPONSE\s*:\s*', '', cleaned)

        return cleaned.strip()

    def _handle_gan_task(self, task, memory):
        """Handle GAN task - show internal debate process."""
        logger.info("Handling GAN task")
        try:
            from tools.gan_iteration import GANIteration
            gan = GANIteration()
            
            # Set callback for real-time updates
            gan.callback = self.on_response
            
            is_user_topic = task.get("is_user_topic", False)
            user_topic = task.get("user_topic")
            user_context = task.get("user_context", "")
            
            logger.info(f"GAN task params: is_user_topic={is_user_topic}, user_topic={user_topic[:50] if user_topic else 'None'}")
            
            # Set user context for topic anchoring
            gan.user_context = user_context
            
            debate_result = gan.self_debate(is_user_topic, user_topic)
            synthesis = debate_result.get("synthesis", "")
            iterations = debate_result.get("iterations", 0)
            coherent = debate_result.get("coherent", True)
            
            logger.info(f"GAN result: iterations={iterations}, coherent={coherent}, synthesis={synthesis[:100] if synthesis else 'None'}")

            if memory is not None:
                add_thought(memory, synthesis, thought_type="gan")
                save_memory(memory)

            self._save_gan_result(gan, debate_result, is_user_topic, user_topic)

            if self.on_response:
                # Send final GAN complete event
                self.on_response({
                    "type": "gan_complete",
                    "gan_result": {
                        "topic": gan.topic,
                        "synthesis": synthesis,
                        "reply_a": gan.reply_a,
                        "reply_b": gan.reply_b,
                        "iterations": iterations,
                        "coherent": coherent
                    }
                })
        except Exception as e:
            if self.on_response:
                self.on_response({"type": "error", "error": f"GAN task failed: {e}"})

    def _save_gan_result(self, gan, debate_result, is_user_topic, user_topic):
        try:
            result = {
                "timestamp": datetime.now().isoformat(),
                "is_user_topic": bool(is_user_topic),
                "user_topic": user_topic,
                "gan_topic": gan.topic,
                "reply_a": gan.reply_a,
                "reply_b": gan.reply_b,
                "synthesis": gan.synthesis,
                "iterations": debate_result.get("iterations", 0),
                "coherent": debate_result.get("coherent", True)
            }
            self.latest_gan_result = result

            data_dir = os.path.join(os.path.dirname(__file__), "data")
            os.makedirs(data_dir, exist_ok=True)
            file_path = os.path.join(data_dir, "gan_results.json")
            existing = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []
            existing.append(result)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _normalize_text(self, text):
        if not text:
            return ""
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower()).strip()
        return normalized

    def _extract_topic(self, text):
        if not text:
            return ""
        normalized = self._normalize_text(text)
        if not normalized:
            return ""
        parts = re.split(r"[\?\!\.。！？]", text, maxsplit=1)
        return parts[0].strip() if parts else normalized

    def _topic_similarity(self, a, b):
        if not a or not b:
            return 0.0
        tokens_a = set(self._normalize_text(a).split())
        tokens_b = set(self._normalize_text(b).split())
        if not tokens_a or not tokens_b:
            return 0.0
        shared = tokens_a & tokens_b
        return len(shared) / max(len(tokens_a), len(tokens_b))

    def pause_idle(self):
        """暂停空闲引擎（用于外部API调用时优先处理用户消息）"""
        try:
            from ui.idle import IdleEngine
            global _idle_engine_instance
            if _idle_engine_instance:
                _idle_engine_instance.signal_user_activity()
        except Exception:
            pass

    def should_answer_user(self, user_text):
        """
        Let AI decide whether to answer the user's question at all.
        Returns: (should_answer: bool, reason: str)
        """
        from llm import chat
        
        decision_prompt = load_should_answer_user_prompt(user_text)
        
        try:
            response = chat(decision_prompt).strip()
            should_answer = "是" in response or "YES" in response.upper() or "会" in response
            return should_answer, response
        except Exception as e:
            return True, f"Error: {e}"
    
    def should_use_gan_for_answer(self, user_text, context=""):
        """
        Let AI decide whether to use GAN thinking before answering.
        Returns: (should_use_gan: bool, reason: str)
        """
        from llm import chat
        
        decision_prompt = load_should_use_gan_prompt(user_text, context)
        
        try:
            response = chat(decision_prompt).strip()
            should_use_gan = "是" in response or "YES" in response.upper()
            return should_use_gan, response
        except Exception as e:
            return False, f"Error: {e}"
    
    def review_memory_for_reconsideration(self, memory):
        """
        Let AI review memory and decide if there's something worth reconsidering.
        Returns: (should_reconsider: bool, reason: str, topic: str or None)
        """
        from llm import chat
        
        if memory is None:
            return False, "No memory available", None
        
        messages = memory.get("messages", [])[-10:]
        thoughts = memory.get("thoughts", [])[-5:]
        
        if not messages and not thoughts:
            return False, "Memory is empty", None
        
        context = "最近对话：\n"
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")[:200]
            context += f"- {role}: {content}\n"
        
        if thoughts:
            context += "\n最近思考：\n"
            for t in thoughts:
                content = t.get("content", "")[:200]
                context += f"- [{t.get('type', 'unknown')}]: {content}\n"
        
        decision_prompt = load_should_reconsider_prompt(context)
        
        try:
            response = chat(decision_prompt).strip()
            if "重新考虑" in response:
                topic = response.replace("重新考虑:", "").strip()
                return True, f"Found topic worth reconsidering: {topic}", topic
            else:
                return False, response, None
        except Exception as e:
            return False, f"Error: {e}", None
    
    def should_proactively_speak(self, memory, gan_result):
        """
        After GAN completes, decide whether AI should proactively speak to user.
        Returns: (should_speak: bool, message: str)
        """
        from llm import chat
        
        if memory is None or gan_result is None:
            return False, ""
        
        gan_topic = gan_result.get("gan_topic", "")
        gan_synthesis = gan_result.get("synthesis", "")[:300]
        
        messages = memory.get("messages", [])[-6:]
        context = "最近对话：\n"
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")[:150]
            context += f"- {role}: {content}\n"
        
        decision_prompt = load_should_proactively_speak_prompt(gan_topic, gan_synthesis, context)
        
        try:
            response = chat(decision_prompt).strip()
            if "说话" in response:
                message = response.replace("说话:", "").replace("说话：", "").strip()
                if not message.endswith("让我们开始工作吧"):
                    message = message + " 让我们开始工作吧"
                return True, message
            else:
                return False, ""
        except Exception as e:
            return False, ""
    
    def choose_response_topic(self, user_text):
        """
        Let AI decide whether to answer the user's topic or continue the GAN topic.
        Returns: (decision, user_topic, gan_topic, similarity)
        """
        from llm import chat
        
        user_topic = self._extract_topic(user_text)
        gan_topic = None
        gan_synthesis = None
        
        if self.latest_gan_result:
            gan_topic = self.latest_gan_result.get("gan_topic")
            gan_synthesis = self.latest_gan_result.get("synthesis")
        
        if not gan_topic:
            return "user", user_topic, gan_topic, 0.0

        similarity = self._topic_similarity(user_topic, gan_topic)
        
        # Let AI decide through LLM
        decision_prompt = load_choose_response_topic_prompt(user_text, user_topic, gan_topic, gan_synthesis, similarity)
        
        try:
            response = chat(decision_prompt).strip().upper()
            if "用户" in response:
                decision = "user"
            elif "思考" in response:
                decision = "gan"
            else:
                # Fallback to rule-based if LLM response is invalid
                explicit_question = bool(re.search(r"\b(why|what|how|when|where|who|should|could|would|can|please|问|什么|为什么|怎么|如何|是否|能否)\b", user_text, re.I))
                decision = "user" if (explicit_question or similarity >= 0.35) else "gan"
        except Exception:
            # Fallback to rule-based if LLM fails
            explicit_question = bool(re.search(r"\b(why|what|how|when|where|who|should|could|would|can|please|问|什么|为什么|怎么|如何|是否|能否)\b", user_text, re.I))
            decision = "user" if (explicit_question or similarity >= 0.35) else "gan"
        
        return decision.lower(), user_topic, gan_topic, similarity

    def _handle_reflection_task(self, prompt, memory, emotion_monitor, exec_instr):
        """Handle reflection task - show AI reflection content."""
        logger.info("Handling reflection task")
        reply, adaptation = generate_with_emotion_feedback(exec_instr + "\n\n" + prompt, emotion_monitor)
        logger.info(f"Reflection reply: {reply[:200] if reply else 'Empty'}")
        thought, _ = self._extract_thought_and_response(reply)
        content = thought or reply
        logger.info(f"Reflection content: {content[:100] if content else 'None'}")
        if memory is not None:
            add_thought(memory, content, thought_type="reflection")
            save_memory(memory)
        
        if self.on_response:
            self.on_response({
                "type": "internal_thought",
                "thought": f"[Reflection] {content}"
            })

    def queue_chat_task(self, prompt, memory=None, emotion_monitor=None, use_gan_decision=False, user_text=None, personality=None, gan_decision=None, gan_decision_reason=""):
        task_type = "chat_with_gan_decision" if use_gan_decision else "chat"
        task = {
            "type": task_type,
            "prompt": prompt,
            "memory": memory,
            "emotion_monitor": emotion_monitor,
            "user_text": user_text,
            "personality": personality,
            "gan_decision": gan_decision,
            "gan_decision_reason": gan_decision_reason,
        }
        self.queue.put(task)

    def queue_user_chat_task(self, prompt, memory=None, emotion_monitor=None, user_text=None, personality=None):
        """立即处理用户消息，避免被后台 GAN 或反思任务阻塞。"""
        def process_user_message():
            exec_instr = self._load_agent_prompt(personality)
            logger.info(f"Processing user chat directly, prompt_length={len(prompt) if prompt else 0}")
            self._handle_chat_task(prompt, memory, emotion_monitor, exec_instr)

        threading.Thread(target=process_user_message, daemon=True).start()

    def queue_chat_stream_task(self, prompt, memory=None, emotion_monitor=None, user_text=None, personality=None, target_info=None):
        """队列流式聊天任务 - 实时发送句子"""
        task = {
            "type": "chat_stream",
            "prompt": prompt,
            "memory": memory,
            "emotion_monitor": emotion_monitor,
            "user_text": user_text,
            "personality": personality,
            "target_info": target_info,
        }
        self.queue.put(task)

    def queue_break_silence_task(self, prompt, memory=None, emotion_monitor=None, personality=None):
        """队列打破沉默任务 - AI主动对用户说话"""
        self.queue.put({"type": "break_silence", "prompt": prompt, "memory": memory, "emotion_monitor": emotion_monitor, "personality": personality})

    def queue_gan_task(self, is_user_topic=False, user_topic=None, memory=None):
        """Queue a GAN debate task - internal thinking only."""
        self.queue.put({"type": "gan", "is_user_topic": is_user_topic, "user_topic": user_topic, "memory": memory})

    def queue_reflection_task(self, prompt, memory=None, emotion_monitor=None, personality=None):
        """Queue a reflection task - AI internal reflection."""
        self.queue.put({"type": "reflection", "prompt": prompt, "memory": memory, "emotion_monitor": emotion_monitor, "personality": personality})

    def _hallucination_check(self, reply: str, user_text: str = "") -> str:
        """
        检测回复中可能的幻觉内容，并添加适当的限定语
        识别高风险内容：具体数字、URL、日期、人名、专业术语等
        如果检测到高风险内容且没有明确的信息来源标注，添加"我不太确定"等限定语
        """
        if not reply:
            return reply

        risk_patterns = [
            r'https?://[^\s]+',
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'\d{4}-\d{2}-\d{2}',
            r'\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:亿|万|千|元|美元|欧元|%|人|个|次)',
            r'根据(?:《[^》]+》|[\u4e00-\u9fff]+的报道|[\u4e00-\u9fff]+的研究)',
            r'(?:博士|教授|专家|研究员)\s+[\u4e00-\u9fff]{2,4}',
            r'(?:发现|证明|表明|显示)\s+[\u4e00-\u9fff]+',
            r'(?:获得|赢得|荣获)\s+[\u4e00-\u9fff]+奖',
        ]

        source_indicators = [
            '根据搜索结果', '搜索到的信息', '我查了一下', '据报道',
            '根据资料', '我记得', '我了解到', '据说', '听说'
        ]

        has_risk_content = False
        for pattern in risk_patterns:
            if re.search(pattern, reply):
                has_risk_content = True
                break

        has_source = any(indicator in reply for indicator in source_indicators)

        if has_risk_content and not has_source:
            logger.info(f"Hallucination check: detected risk content without source in reply: {reply[:100]}")
            reply = reply.replace('。', '。(我不太确定这个信息是否准确，建议你自己核实一下～)', 1)

        return reply

    def stop(self):
        self.running = False
        self.queue.put(None)
        self._decision_queue.put(None)