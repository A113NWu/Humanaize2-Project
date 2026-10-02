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
        """转发GAN的进度回调。注意：思考內容不做敏感詞過濾（Aize 內部思考保留），
        過濾僅作用於對外發送的社交內容。"""
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
                # Aize wants to talk to user：真正把開場白生成出來（break_silence 任務），
                # 完成後經事件匯流排 PO 到網頁聊天界面，而不是只留一條思考日誌
                if self.callback:
                    self.callback({
                        "type": "internal_thought",
                        "thought": f"[Idle Activity] Aize wants to talk to user: {thinking_topic}"
                    })
                try:
                    from thinking_engine_api import ThinkingEngineState
                    engine = ThinkingEngineState().get_thinking_engine()
                    if engine is not None:
                        engine.queue_break_silence_task(prompt=thinking_topic or "", memory=self.memory)
                except Exception as e:
                    if self.callback:
                        self.callback({"type": "error", "error": f"break_silence queue failed: {e}"})
            elif "社交" in activity or "social" in activity.lower():
                # Aize 選擇去社交平台逛逛/發動態
                self._do_social_activity(thinking_topic)
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

    def _do_social_activity(self, plan: str = ""):
        """閒時社交活動：把站点内容（提及/时间线/表情说明）原样喂给 Aize，
        由她自己决定回复、点表情、发新动态、上网搜索或直接问主人；
        我们只负责执行她的决定，所有对外文本仍经过滤器。

        平台選擇策略：從「已配置且可用」的平台中挑選（目前支持 Misskey；
        日後新增平台只需在 _available_social_platforms 註冊即可）。
        """
        from llm import chat
        from core.data.prompts_manager import load_prompt
        try:
            from core.tools import content_filter
        except ImportError:
            from tools import content_filter

        def _thought(msg):
            if self.callback:
                self.callback({"type": "internal_thought", "thought": msg})

        platforms = self._available_social_platforms()
        if not platforms:
            _thought("[Social] 想去社交网站逛逛，但还没有配置任何平台（可先用 misskey-bot 技能 configure）")
            return

        platform = platforms[0]
        bot = platform["bot"]
        _thought(f"[Social] Aize 选择去 {platform['label']} 逛逛" + (f"：{plan}" if plan else ""))

        # 1. 收集她能看到的内容：提及 + 时间线（只呈现，不替她决定）
        notes, mentions = [], []
        try:
            tl = bot.timeline("local", limit=5)
            if tl.get("success"):
                notes = tl.get("notes") or []
        except Exception as e:
            _thought(f"[Social] 浏览时间线出错：{e}")
        try:
            mt = bot.mentions(limit=3)
            if mt.get("success"):
                mentions = mt.get("mentions") or []
        except Exception as e:
            _thought(f"[Social] 读取提及出错：{e}")
        _thought(f"[Social] 看到 {len(mentions)} 条提及、{len(notes)} 条新动态，Aize 正在想怎么做…")

        # 2. 上下文 + 站点表情说明
        context = ""
        if self.memory is not None:
            try:
                recent = [m for m in self.memory[-6:] if isinstance(m, dict)]
                if recent:
                    context = "最近的对话上下文：\n" + "\n".join(
                        f"- {m.get('role','?')}: {str(m.get('content',''))[:80]}" for m in recent)
            except Exception:
                pass
        emoji_guide = self._build_emoji_guide(bot)

        def _fmt(items, empty):
            if not items:
                return empty
            return "\n".join(f"[{n.get('id')}] @{n.get('user','?')}: {n.get('text','')}" for n in items)

        base_prompt = load_prompt("social_decide")
        if not base_prompt:
            _thought("[Social] social_decide 提示词缺失，本次跳过")
            return

        # 3. 决策-执行闭环：每轮她输出 JSON 动作列表 → 我们执行并把结果反馈给她 →
        #    她看着结果决定下一步，直到她主动输出 done/none、连续没有新动作、
        #    或达到安全上限（轮数/总动作数）才结束——和普通任务的多轮 followup 同构。
        search_results = ""
        action_feedback = []  # 每轮动作执行结果的文字记录，反馈进下一轮提示词
        acted = set()    # (动作, 目标) 去重
        done_count = 0
        max_actions = 10
        max_rounds = 10

        for round_no in range(max_rounds):
            if action_feedback:
                results_block = "【你上一轮的动作执行结果】\n" + "\n".join(action_feedback)
            else:
                results_block = ""
            prompt = (base_prompt
                      .replace("{platforms}", platform["label"])
                      .replace("{context}", context)
                      .replace("{emojis}", emoji_guide)
                      .replace("{mentions}", _fmt(mentions, "（没有人@你）"))
                      .replace("{timeline}", _fmt(notes, "（时间线空空如也）"))
                      .replace("{search_results}", search_results)
                      .replace("{action_results}", results_block))
            # 舊版提示詞（升級前已種植到 Prompt 目錄）沒有 {action_results} 佔位符，
            # 此時把反饋塊直接追加到末尾，保證閉環依然成立
            if results_block and "{action_results}" not in base_prompt:
                prompt += "\n" + results_block
            try:
                raw = chat(prompt, max_tokens=400, timeout=60).strip()
            except Exception as e:
                _thought(f"[Social] Aize 决策失败: {e}")
                return
            actions = self._parse_social_actions(raw)
            if actions is None:
                _thought("[Social] 没看懂 Aize 的决定（输出不是有效 JSON），本次不采取行动")
                return

            action_feedback = []
            pending_search = None
            asked_user = False
            new_actions_this_round = 0

            # 她明确表示结束（done 或空动作列表）→ 闭环正常收尾
            effective = [a for a in actions if isinstance(a, dict)
                         and str(a.get("type", "")).strip().lower() not in ("", "none")]
            if not effective:
                if round_no == 0:
                    _thought("[Social] Aize 看了一圈，这次决定什么都不做")
                else:
                    _thought(f"[Social] Aize 觉得事情办完了，本次社交结束（共 {done_count} 个动作）")
                return
            if any(str(a.get("type", "")).strip().lower() == "done" for a in effective):
                _thought(f"[Social] Aize 主动结束了这次社交（共 {done_count} 个动作）")
                return

            for act in effective:
                atype = str(act.get("type", "")).strip().lower()
                if done_count >= max_actions and atype != "search":
                    action_feedback.append(f"- 动作 {atype} 未执行：已达到本次社交的动作上限")
                    continue

                if atype == "react":
                    nid = str(act.get("note_id", "")).strip()
                    reaction = str(act.get("reaction", "👍")).strip() or "👍"
                    if not nid or ("react", nid) in acted:
                        continue
                    acted.add(("react", nid))
                    r = bot.react(nid, reaction)
                    if r.get("success"):
                        done_count += 1
                        new_actions_this_round += 1
                        action_feedback.append(f"- 已给帖子 {nid} 点了 {reaction}（成功）")
                        _thought(f"[Social] Aize 给帖子 {nid} 点了 {reaction}")
                    else:
                        action_feedback.append(f"- 给帖子 {nid} 点 {reaction} 失败：{r.get('error')}")
                        _thought(f"[Social] 点表情失败（{reaction}）：{r.get('error')}")

                elif atype == "reply":
                    nid = str(act.get("note_id", "")).strip()
                    text = str(act.get("text", "")).strip()
                    if not nid or not text or ("reply", nid) in acted:
                        continue
                    acted.add(("reply", nid))
                    ok, hits = content_filter.check(text)
                    if not ok:
                        action_feedback.append(f"- 回复 {nid} 未发送：内容被过滤器拦截（{len(hits)} 个敏感词），请换一种表达")
                        _thought(f"[Social] Aize 的回复被过滤器拦截（{len(hits)} 个敏感词），未发送")
                        continue
                    r = bot.post(text, reply_id=nid)
                    if r.get("success"):
                        done_count += 1
                        new_actions_this_round += 1
                        action_feedback.append(f"- 已回复 {nid}：「{text[:60]}」（成功）")
                        _thought(f"[Social] Aize 回复了 {nid}：{text[:40]}")
                    else:
                        action_feedback.append(f"- 回复 {nid} 失败：{r.get('error')}")
                        _thought(f"[Social] 回复失败：{r.get('error')}")

                elif atype == "post":
                    text = str(act.get("text", "")).strip()
                    if not text or ("post", text) in acted:
                        continue
                    acted.add(("post", text))
                    ok, hits = content_filter.check(text)
                    if not ok:
                        action_feedback.append(f"- 新动态未发布：内容被过滤器拦截（{len(hits)} 个敏感词），请换一种表达")
                        _thought(f"[Social] Aize 的动态被过滤器拦截（{len(hits)} 个敏感词），未发布")
                        continue
                    try:
                        r = platform["post"](text)
                    except Exception as e:
                        r = {"success": False, "error": str(e)}
                    if r.get("success"):
                        done_count += 1
                        new_actions_this_round += 1
                        action_feedback.append(f"- 已发布新动态：「{text[:60]}」({r.get('url', '')})")
                        _thought(f"[Social] Aize 发布了新动态：{text[:50]} ({r.get('url', '')})")
                    else:
                        action_feedback.append(f"- 发布新动态失败：{r.get('error')}")
                        _thought(f"[Social] 发布被平台拒绝：{r.get('error')}")

                elif atype == "ask_user":
                    question = str(act.get("question", "")).strip()
                    if question and self.callback:
                        done_count += 1
                        new_actions_this_round += 1
                        asked_user = True
                        action_feedback.append(f"- 已向主人提问：{question}")
                        _thought(f"[Social] Aize 有事情想请教你：{question}")
                        self.callback({"type": "autonomous_message",
                                       "message": f"我在 {platform['label']} 闲逛时遇到了想请教你的问题：{question}"})

                elif atype == "search":
                    query = str(act.get("query", "")).strip()
                    if query and pending_search is None:
                        pending_search = query

            # 向主人提问后本轮社交收尾：等待主人回复，不继续自顾自行动
            if asked_user:
                _thought(f"[Social] 已向主人提问，等待回复中结束本次社交（共 {done_count} 个动作）")
                return

            if pending_search:
                _thought(f"[Social] Aize 想先搞清楚「{pending_search}」，正在上网搜索…")
                search_results = self._social_web_search(pending_search)
                if not action_feedback:
                    # 纯搜索轮：搜索结果本身即反馈，继续下一轮决策
                    continue
                # 既有动作又有搜索：带着动作结果和搜索结果进入下一轮
                continue

            # 停滞检测：本轮没有任何新动作被执行（全是重复/无效），闭环不再推进
            if new_actions_this_round == 0:
                if round_no == 0:
                    _thought("[Social] Aize 看了一圈，这次决定什么都不做")
                else:
                    _thought(f"[Social] 没有新的动作可执行，本次社交结束（共 {done_count} 个动作）")
                return
            # 有动作执行 → 把结果反馈给她，进入下一轮决策
        else:
            _thought(f"[Social] 达到最大轮数（{max_rounds}），本次社交结束（共 {done_count} 个动作）")

    @staticmethod
    def _parse_social_actions(raw: str):
        """從 Aize 的輸出中提取 {"actions": [...]}；解析失敗返回 None。"""
        import json as _json
        import re as _re
        m = _re.search(r"\{.*\}", (raw or "").strip(), _re.DOTALL)
        if not m:
            return None
        try:
            data = _json.loads(m.group(0))
        except Exception:
            return None
        acts = data.get("actions")
        return acts if isinstance(acts, list) else None

    @staticmethod
    def _build_emoji_guide(bot) -> str:
        """把站点自定义表情整理成 :名字:（分类/别名） 清单，帮 Aize 理解每个表情的意思。"""
        try:
            res = bot.emojis(limit=100)
        except Exception:
            res = {}
        if not res.get("success"):
            return "（站点表情列表暂时获取失败，这次只用通用 emoji 就好）"
        parts = []
        for e in res.get("emojis", []):
            name = e.get("name")
            if not name:
                continue
            hints = [h for h in ([e.get("category") or ""] + list(e.get("aliases") or [])) if h]
            parts.append(f":{name}:（{'，'.join(hints)}）" if hints else f":{name}:")
        if not parts:
            return "（站点没有自定义表情，用通用 emoji 就好）"
        joined = "、".join(parts)
        if len(joined) > 1800:
            joined = joined[:1800] + "…"
        return joined

    def _social_web_search(self, query: str) -> str:
        """調用 web-search 技能並把結果整理成提示詞段落（失敗時如實告知）。"""
        mod = self._load_skill_module("web-search")
        if mod is None:
            return "【搜索结果】\n（搜索技能当前不可用）\n请根据现有信息重新决定后续动作。"
        try:
            res = mod.execute({"query": query, "num_results": 3})
        except Exception as e:
            res = {"success": False, "error": str(e)}
        if not res.get("success"):
            return f"【搜索结果】\n搜索失败：{res.get('error')}\n请根据现有信息重新决定后续动作。"
        lines = [f"- {r.get('title','')}: {r.get('snippet','')}" for r in (res.get("results") or [])[:3]]
        body = "\n".join(lines) if lines else "（没有搜到相关结果）"
        return (f"【搜索结果】（你刚才搜索了「{query}」）\n{body}\n"
                f"请根据搜索结果重新决定后续动作（这次尽量直接行动，不要再搜索）。")

    @staticmethod
    def _load_skill_module(skill_name: str):
        """以文件路徑隔離載入技能模塊（兼容 dev 與打包態）。"""
        import importlib.util
        import sys as _sys
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidates = [os.path.join(root, "skills", skill_name, "__init__.py")]
        if getattr(_sys, "frozen", False):
            candidates.insert(0, os.path.join(os.path.dirname(_sys.executable),
                                              "skills", skill_name, "__init__.py"))
        for init in candidates:
            if not os.path.exists(init):
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"skills_{skill_name.replace('-', '_')}", init)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
            except Exception:
                continue
        return None

    @staticmethod
    def _available_social_platforms():
        """已配置可用的社交平台列表（可寫入的才會列入）。"""
        platforms = []
        mod = IdleEngine._load_skill_module("misskey-bot")
        if mod is not None:
            try:
                bot = mod._get_bot()
                if bot.config.get("token"):
                    platforms.append({
                        "label": f"Misskey（{bot.config.get('host')}）",
                        "post": bot.post,
                        "bot": bot,
                    })
            except Exception:
                pass
        return platforms

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
        """收到用户活动信号，暂停当前的GAN思考，并安排 60 秒后自动恢复"""
        if self.is_running_gan:
            try:
                self.gan.stop_immediately()
            except Exception:
                pass
        self.paused = True
        self._resume_timer = time.time()
        self._start_resume_timer(60)

    def schedule_resume(self, delay: int = 60):
        """请求在 delay 秒后自动恢复（对话结束时调用）。

        期间若用户又有新活动，signal_user_activity 会刷新计时，
        旧计时器到期时发现自己已过期，不会提前恢复。
        """
        self.paused = True
        self._resume_timer = time.time()
        self._start_resume_timer(delay)

    def _start_resume_timer(self, delay: int):
        token = getattr(self, "_resume_timer", None)

        def _wait():
            time.sleep(max(5, int(delay)))
            if not self.running:
                return
            # 只有自己仍是最新一次计时时才恢复，避免旧计时器提前解锁
            if self._resume_timer == token:
                self.paused = False

        threading.Thread(target=_wait, daemon=True).start()

    def check_resume(self):
        """检查是否应该恢复空闲思考（用户活动结束1分钟后）"""
        if self.paused and hasattr(self, '_resume_timer'):
            if time.time() - self._resume_timer >= 60:
                self.paused = False

    def stop(self):
        """停止空闲引擎"""
        self.running = False
