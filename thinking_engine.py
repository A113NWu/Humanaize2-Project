import os
import threading, queue, re, json
from datetime import datetime
from memory import add, add_thought, save_memory
from llm_enhanced import generate_with_emotion_feedback
from Agent import Agent

class ThinkingEngine:
    def __init__(self, on_response_callback=None):
        self.on_response = on_response_callback
        self.queue = queue.Queue()
        self.running = True
        self.latest_gan_result = None
        self.thread = threading.Thread(target=self._process, daemon=True)
        self.thread.start()
        self.language = "en"
        self._decision_queue = queue.Queue()
        self._decision_thread = threading.Thread(target=self._process_decisions, daemon=True)
        self._decision_thread.start()
    
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
                    result = self._should_answer_user_sync(task.get("user_text"))
                    if callback:
                        callback(result)
                elif task_type == "should_use_gan":
                    result = self._should_use_gan_sync(task.get("user_text"), task.get("context"))
                    if callback:
                        callback(result)
            except queue.Empty:
                continue
            except Exception:
                pass
    
    def _should_answer_user_sync(self, user_text):
        """Synchronous version of should_answer_user for internal use"""
        from llm import chat
        
        decision_prompt = f"""
You are an AI assistant deciding whether to respond to a user input.
User input: "{user_text}"

Consider whether this input:
- Is a question asking for information (should answer)
- Is a greeting or acknowledgment (may not need direct answer)
- Is a command or request (should answer)
- Is just "ok", "yes", "no" or very brief (may not need answer)
- Requires domain knowledge or opinion (should answer)

Should you respond to this user input? Answer YES or NO and briefly explain why.
"""
        
        try:
            response = chat(decision_prompt).strip()
            should_answer = "YES" in response.upper()
            return (should_answer, response)
        except Exception as e:
            return (True, f"Error: {e}")
    
    def _should_use_gan_sync(self, user_text, context=""):
        """Synchronous version of should_use_gan_for_answer for internal use"""
        from llm import chat
        
        decision_prompt = f"""
You are an AI assistant with internal GAN self-debate capability.
You have already decided to answer the user's question. Now decide if you need deep reflection.

User input: "{user_text}"

{context}

Consider whether this question would benefit from GAN self-debate:
- Complex or controversial topics (needs GAN)
- Questions requiring balanced analysis (needs GAN)
- Philosophical or ethical questions (needs GAN)
- Simple factual questions (no need for GAN)
- Routine requests (no need for GAN)

Should you perform GAN thinking before answering? Answer YES or NO and briefly explain why.
"""
        
        try:
            response = chat(decision_prompt).strip()
            should_use_gan = "YES" in response.upper()
            return (should_use_gan, response)
        except Exception as e:
            return (False, f"Error: {e}")
    
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

    def _load_agent_prompt(self) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "data", "agent_prompt.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
        except Exception:
            prompt = (
                "You are an assistant that can execute shell commands and Openclaw-style skills through the Agent interface. "
                "Always begin by writing an internal thought section labeled THOUGHT:, then write a final answer section labeled RESPONSE:. "
                "If you need to run a shell command, output exactly one command wrapped in exclamation marks, for example: !echo hello!. "
                "If you need to invoke a skill, output exactly one JSON object with keys such as {\"skill\": \"shell\", \"input\": \"...\"} or {\"skill\": \"shell\", \"input\": {\"command\": \"...\"}}. "
                "Do not output any other text outside the exact command or JSON object. "
                "Do not use markdown formatting, code fences, or extra commentary. "
                "If you do not need to execute anything, still provide a THOUGHT: section describing your reasoning, followed by RESPONSE: with the answer. "
                "After the Agent runs the command or skill, wait for the result and continue with the next step in plain text. "
                "If a command fails, fix it in the next response. "
            )
        
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

    def _extract_thought_and_response(self, text: str):
        if not text:
            return None, ""

        match = re.search(r"(?si)THOUGHT\s*:\s*(.*?)\s*RESPONSE\s*:\s*(.*)", text)
        if match:
            return match.group(1).strip(), match.group(2).strip()

        return None, text.strip()

    def _process(self):
        while self.running:
            task = self.queue.get()
            if task is None:
                break
            
            task_type = task.get("type", "chat")
            prompt = task.get("prompt", "")
            memory = task.get("memory")
            emotion_monitor = task.get("emotion_monitor")
            user_text = task.get("user_text")
            
            # 从 data/agent_prompt.txt 加载提示词
            exec_instr = self._load_agent_prompt()
            
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
                self._handle_chat_with_gan_decision_task(prompt, memory, emotion_monitor, exec_instr, user_text)
            else:  # chat
                # 普通聊天任务
                self._handle_chat_task(prompt, memory, emotion_monitor, exec_instr)

    def _handle_chat_task(self, prompt, memory, emotion_monitor, exec_instr):
        """Handle a normal chat task."""
        reply, adaptation = generate_with_emotion_feedback(exec_instr + "\n\n" + prompt, emotion_monitor)
        thought, target_reply = self._extract_thought_and_response(reply)
        if thought:
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": thought})
            if memory is not None:
                add_thought(memory, thought, thought_type="internal")
                save_memory(memory)

        if memory is not None:
            add(memory, "assistant", reply)
            save_memory(memory)

        actual_reply = target_reply or reply
        try:
            agent = Agent('!')
            agent.set_language(self.language)
            if agent.has_actions(actual_reply):
                if self.on_response:
                    self.on_response({"type": "command_start", "message": "AI is executing a command...\n"})
                out = agent.agent('!', actual_reply)
                if self.on_response:
                    self.on_response({"type": "command_result", "output": out})
                cleaned = re.sub(r'!.*?!', '', actual_reply, flags=re.S).strip()
                if not cleaned or (cleaned.startswith('{') and cleaned.endswith('}')):
                    final_reply = "[Command executed; see command output]"
                else:
                    final_reply = cleaned
                if memory is not None:
                    add(memory, "assistant", final_reply)
                    add(memory, "system", f"Command output:\n{out}")
                    save_memory(memory)
                if self.on_response:
                    self.on_response({"type": "chat_response", "reply": final_reply})
                try:
                    followup_prompt = final_reply + "\n\nCommand output:\n" + (out or "") + "\n\nPlease use the above output to continue the next step."
                    freply, fadapt = generate_with_emotion_feedback(exec_instr + "\n\n" + followup_prompt, emotion_monitor)
                    if memory is not None:
                        add(memory, "assistant", freply)
                        save_memory(memory)
                    if self.on_response:
                        self.on_response({"type": "chat_response", "reply": freply})
                except Exception:
                    pass
            else:
                if self.on_response:
                    self.on_response({"type": "chat_response", "reply": actual_reply})
        except Exception as e:
            if self.on_response:
                self.on_response({"type": "error", "error": str(e)})

    def _run_gan_debate(self, user_topic, memory):
        try:
            from gan_iteration import GANIteration
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

    def _handle_chat_with_gan_decision_task(self, prompt, memory, emotion_monitor, exec_instr, user_text):
        try:
            from gan_iteration import GANIteration
            gan = GANIteration()
            should_use_gan, decision_text = gan.decide_use_gan(user_text, exec_instr, emotion_monitor)
        except Exception as e:
            should_use_gan, decision_text = False, f"GAN decision failed: {e}"

        if self.on_response and decision_text:
            self.on_response({"type": "internal_thought", "thought": f"[GAN Decision] {decision_text}"})

        ui_settings = self._load_ui_settings()
        gan_enabled = ui_settings.get("gan_enabled", True)

        if should_use_gan and gan_enabled:
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": "[GAN Decision] AI chose to perform GAN thinking before answering."})
            debate_result = gan.self_debate(True, user_text)
            synthesis = debate_result.get("synthesis", "")
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
            self._handle_chat_task(enhanced_prompt, memory, emotion_monitor, exec_instr)
        else:
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": "[GAN Decision] AI chose to answer directly without GAN thinking."})
            self._handle_chat_task(prompt, memory, emotion_monitor, exec_instr)

    def _handle_break_silence_task(self, prompt, memory, emotion_monitor, exec_instr):
        """Handle break silence task - generate an actual assistant reply."""
        reply, adaptation = generate_with_emotion_feedback(exec_instr + "\n\n" + prompt, emotion_monitor)
        thought, target_reply = self._extract_thought_and_response(reply)
        if thought:
            if self.on_response:
                self.on_response({"type": "internal_thought", "thought": thought})
            if memory is not None:
                add_thought(memory, thought, thought_type="break_silence")
                save_memory(memory)

        if memory is not None:
            add(memory, "assistant", reply)
            save_memory(memory)

        actual_reply = target_reply or reply
        if self.on_response:
            self.on_response({"type": "chat_response", "reply": actual_reply})

    def _handle_gan_task(self, task, memory):
        """Handle GAN task - show internal debate process."""
        try:
            from gan_iteration import GANIteration
            gan = GANIteration()
            is_user_topic = task.get("is_user_topic", False)
            user_topic = task.get("user_topic")
            debate_result = gan.self_debate(is_user_topic, user_topic)
            synthesis = debate_result.get("synthesis", "")

            if memory is not None:
                add_thought(memory, synthesis, thought_type="gan")
                save_memory(memory)

            self._save_gan_result(gan, debate_result, is_user_topic, user_topic)

            if self.on_response:
                self.on_response({
                    "type": "internal_thought",
                    "thought": f"[GAN Debate] {synthesis}"
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
                "gan_topic": getattr(gan, "topic", None),
                "reply_a": getattr(gan, "reply_a", None),
                "reply_b": getattr(gan, "reply_b", None),
                "synthesis": debate_result.get("synthesis", "")
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

    def should_answer_user(self, user_text):
        """
        Let AI decide whether to answer the user's question at all.
        Returns: (should_answer: bool, reason: str)
        """
        from llm import chat
        
        decision_prompt = f"""
You are an AI assistant deciding whether to respond to a user input.
User input: "{user_text}"

Consider whether this input:
- Is a question asking for information (should answer)
- Is a greeting or acknowledgment (may not need direct answer)
- Is a command or request (should answer)
- Is just "ok", "yes", "no" or very brief (may not need answer)
- Requires domain knowledge or opinion (should answer)

Should you respond to this user input? Answer YES or NO and briefly explain why.
"""
        
        try:
            response = chat(decision_prompt).strip()
            should_answer = "YES" in response.upper()
            return should_answer, response
        except Exception as e:
            return True, f"Error: {e}"
    
    def should_use_gan_for_answer(self, user_text, context=""):
        """
        Let AI decide whether to use GAN thinking before answering.
        Returns: (should_use_gan: bool, reason: str)
        """
        from llm import chat
        
        decision_prompt = f"""
You are an AI assistant with internal GAN self-debate capability.
You have already decided to answer the user's question. Now decide if you need deep reflection.

User input: "{user_text}"

{context}

Consider whether this question would benefit from GAN self-debate:
- Complex or controversial topics (needs GAN)
- Questions requiring balanced analysis (needs GAN)
- Philosophical or ethical questions (needs GAN)
- Simple factual questions (no need for GAN)
- Routine requests (no need for GAN)

Should you perform GAN thinking before answering? Answer YES or NO and briefly explain why.
"""
        
        try:
            response = chat(decision_prompt).strip()
            should_use_gan = "YES" in response.upper()
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
        
        context = "Recent conversation:\n"
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")[:200]
            context += f"- {role}: {content}\n"
        
        if thoughts:
            context += "\nRecent thoughts:\n"
            for t in thoughts:
                content = t.get("content", "")[:200]
                context += f"- [{t.get('type', 'unknown')}]: {content}\n"
        
        decision_prompt = f"""
You are an AI reviewing your memory to find topics worth reconsidering or expanding upon.

{context}

Analyze the above memory and determine:
1. Is there any topic, idea, or conclusion that seems incomplete, potentially biased, or worth revisiting?
2. Is there anything in the conversation that could benefit from deeper reflection or a different perspective?
3. Is there an interesting question raised but not fully explored?

If you find something worth reconsidering, output RECONSIDER: [brief topic description]
If nothing needs reconsideration, output SKIP: [brief reason why nothing needs reconsideration]
"""
        
        try:
            response = chat(decision_prompt).strip()
            if response.startswith("RECONSIDER:"):
                topic = response.replace("RECONSIDER:", "").strip()
                return True, f"Found topic worth reconsidering: {topic}", topic
            else:
                reason = response.replace("SKIP:", "").strip() if response.startswith("SKIP:") else response
                return False, reason, None
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
        context = "Recent conversation:\n"
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")[:150]
            context += f"- {role}: {content}\n"
        
        decision_prompt = f"""
You just completed an internal GAN self-debate on the topic: {gan_topic}

Your synthesis was: {gan_synthesis}

Recent conversation context:
{context}

Based on this, should you proactively share your thoughts with the user? Consider:
1. Do you have an interesting insight worth sharing?
2. Is there something relevant to the ongoing conversation?
3. Would starting a new topic enrich the interaction?

If yes, output: SPEAK: [brief message to share with user, keep it short and conversational]
If no, output: WAIT: [brief reason why you should wait]
"""
        
        try:
            response = chat(decision_prompt).strip()
            if response.startswith("SPEAK:"):
                message = response.replace("SPEAK:", "").strip()
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
        decision_prompt = f"""
You are an AI assistant with internal GAN thinking capability.
Current situation:
- User question: {user_text}
- User topic: {user_topic}
- GAN topic (from internal thinking): {gan_topic}
- GAN synthesis: {gan_synthesis[:200] if gan_synthesis else 'None'}
- Topic similarity: {similarity:.2f}

Please decide whether to:
1. Answer the user's question directly (choose "USER")
2. Continue the GAN thinking topic instead (choose "GAN")

Consider these factors:
- If the user asked a direct question, you should usually answer it
- If the GAN topic is interesting and related to the conversation, you may continue it
- If the user's input is just acknowledging or commenting on the previous GAN output, continue with GAN

Answer with only one word: USER or GAN
"""
        
        try:
            decision = chat(decision_prompt).strip().upper()
            if decision not in ["USER", "GAN"]:
                # Fallback to rule-based if LLM response is invalid
                explicit_question = bool(re.search(r"\b(why|what|how|when|where|who|should|could|would|can|please|问|什么|为什么|怎么|如何|是否|能否)\b", user_text, re.I))
                decision = "USER" if (explicit_question or similarity >= 0.35) else "GAN"
        except Exception:
            # Fallback to rule-based if LLM fails
            explicit_question = bool(re.search(r"\b(why|what|how|when|where|who|should|could|would|can|please|问|什么|为什么|怎么|如何|是否|能否)\b", user_text, re.I))
            decision = "USER" if (explicit_question or similarity >= 0.35) else "GAN"
        
        return decision.lower(), user_topic, gan_topic, similarity

    def _handle_reflection_task(self, prompt, memory, emotion_monitor, exec_instr):
        """Handle reflection task - show AI reflection content."""
        reply, adaptation = generate_with_emotion_feedback(exec_instr + "\n\n" + prompt, emotion_monitor)
        thought, _ = self._extract_thought_and_response(reply)
        content = thought or reply
        if memory is not None:
            add_thought(memory, content, thought_type="reflection")
            save_memory(memory)
        
        if self.on_response:
            self.on_response({
                "type": "internal_thought",
                "thought": f"[Reflection] {content}"
            })

    def queue_chat_task(self, prompt, memory=None, emotion_monitor=None, use_gan_decision=False, user_text=None, personality=None):
        task_type = "chat_with_gan_decision" if use_gan_decision else "chat"
        self.queue.put({
            "type": task_type,
            "prompt": prompt,
            "memory": memory,
            "emotion_monitor": emotion_monitor,
            "user_text": user_text,
            "personality": personality,
        })

    def queue_break_silence_task(self, prompt, memory=None, emotion_monitor=None):
        """队列打破沉默任务 - AI主动对用户说话"""
        self.queue.put({"type": "break_silence", "prompt": prompt, "memory": memory, "emotion_monitor": emotion_monitor})

    def queue_gan_task(self, is_user_topic=False, user_topic=None, memory=None):
        """Queue a GAN debate task - internal thinking only."""
        self.queue.put({"type": "gan", "is_user_topic": is_user_topic, "user_topic": user_topic, "memory": memory})

    def queue_reflection_task(self, prompt, memory=None, emotion_monitor=None):
        """Queue a reflection task - AI internal reflection."""
        self.queue.put({"type": "reflection", "prompt": prompt, "memory": memory, "emotion_monitor": emotion_monitor})

    def stop(self):
        self.running = False
        self.queue.put(None)
        self._decision_queue.put(None)