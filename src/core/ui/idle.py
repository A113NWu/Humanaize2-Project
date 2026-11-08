import threading, time
import os
import sys

# Add core directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 项目根（src/core/ui/idle.py 上溯四级）：skills/ 位于项目根
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from core.persona import (
        persona_block,
        save_self_persona,
        build_persona_growth_prompt,
        build_emotion_study_prompt,
        learn_emotion,
        should_learn,
        mark_learned,
    )
except ImportError:
    from persona import (
        persona_block,
        save_self_persona,
        build_persona_growth_prompt,
        build_emotion_study_prompt,
        learn_emotion,
        should_learn,
        mark_learned,
    )

from tools.gan_iteration import GANIteration
from tools.self_optimizer import get_optimizer
from memory import add_thought, save_memory

_idle_engine_instance = None

_AESTHETIC_DB_NAME = "aesthetic_db.json"

# 執行器（小腦）可用的動作。這是小腦的「動作詞表」，
# 大腦（她的自由獨白）完全不需要知道這些名字，也不輸出任何格式。
ACTIVITY_LABELS = {
    "desktop": "操作電腦",
    "music": "學習音樂",
    "aesthetic": "學習審美",
    "emotion": "學習人類情感",
    "persona": "更新自我人格",
    "social": "社交網站",
    "talk": "找主人說話",
    "think": "自己想事情",
    "web": "上網看帖子",
    "game": "玩遊戲",
    "skill": "寫 Skills",
    "other_ai": "找其他 AI",
}

# 小腦判定的合法動作（none = 她只是想想想，不做任何事）
_IDLE_ACTIONS = ("none",) + tuple(ACTIVITY_LABELS)


def _affect_block():
    """她此刻的心情（tools.affect），让空闲时的决定也带着情绪。"""
    try:
        from tools.affect import render_affect_block
        return (render_affect_block() or "").strip()
    except Exception:
        return ""


def _json_from_text(text):
    """從模型回覆裡抓出第一個 JSON 物件；解析失敗就回空 dict。

    執行器被要求只輸出 JSON，但模型偶爾會包上解釋或程式碼圍欄，這裡做一層容錯。
    """
    import json

    if not isinstance(text, str):
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _aesthetic_path():
    """审美学习数据的保存位置（dev=data/、打包=exe 旁 data/）。"""
    base = None
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["app_data_dir"])
            base = m.app_data_dir()
            break
        except Exception:
            continue
    if not base:
        base = os.path.join(_PROJECT_ROOT, "data")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, _AESTHETIC_DB_NAME)


def _load_aesthetic():
    import json as _json
    try:
        with open(_aesthetic_path(), "r", encoding="utf-8") as f:
            data = _json.load(f)
        if isinstance(data, dict):
            data.setdefault("entries", [])
            data.setdefault("insights", [])
            return data
    except Exception:
        pass
    return {"entries": [], "insights": [], "last_learned_at": None}


def _save_aesthetic(data):
    import json as _json
    try:
        with open(_aesthetic_path(), "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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
        # 長期任務優先：休息中就完全停工；到點就先推進任務，不跑常規 GAN 活動
        if not self._long_task_gate():
            self.is_running_gan = False
            return
        # 顯式開場事件：CLI/網頁可藉此畫出獨立的「閒置思考」區塊
        if self.callback:
            try:
                self.callback({"type": "idle_begin"})
            except Exception:
                pass
        try:
            # Step 1（大腦）：她完全自由地想，不給任何格式、不給標籤菜單
            thought = self._idle_think()
            if thought and self.callback:
                self.callback({
                    "type": "internal_thought",
                    "thought": f"[獨白] {thought}"
                })

            # Step 2（小腦）：執行器 Agent 讀她的獨白，判斷她是否真的想做動作
            action, plan = self._route_thought(thought)
            thinking_topic = plan or thought
            
            if self.callback:
                self.callback({
                    "type": "internal_thought",
                    "thought": (f"[Idle Activity] 小腦判定：{ACTIVITY_LABELS.get(action, action)}"
                                + (f"｜{plan}" if plan else ""))
                })
            
            if action == "none":
                # 她只是想想想：把獨白留在記憶裡，不強迫做事
                if thought and self.memory is not None:
                    try:
                        add_thought(self.memory, thought, thought_type="idle")
                        save_memory(self.memory)
                    except Exception:
                        pass
            elif action == "desktop":
                # 閒時自主操作電腦：小腦從獨白裡提取出具體目標，交給 computer-control 執行
                self._do_desktop_control(plan or thought, ACTIVITY_LABELS["desktop"])
            elif action == "music":
                # 音乐自学：按曲风收集音频 + NumPy 频谱分析，更新音色档案
                self._do_music_learning()
            elif action == "aesthetic":
                # 审美自学：爬图 + Pillow 分析 + 网上文本理解
                self._do_aesthetic_learning()
            elif action == "persona":
                # 自我学习类活动：走内部学习，不要当成「找用户说话」发到聊天界面
                self._do_self_learning("persona")
            elif action == "emotion":
                self._do_self_learning("emotion")
            elif action == "think":
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
            elif action == "talk":
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
            elif action == "social":
                # 社交平台：內容照舊餵給她，由她自己決定要不要回、點表情、發動態（邏輯不變）
                self._do_social_activity(thinking_topic)
            else:
                # web / game / skill / other_ai：目前只記錄想法，還沒有對應執行器
                if self.callback:
                    self.callback({
                        "type": "internal_thought",
                        "thought": f"[Idle Activity] {ACTIVITY_LABELS.get(action, action)} - {plan}"
                    })
                
        except Exception as e:
            if self.callback:
                self.callback({"type": "error", "error": f"GAN thinking failed: {e}"})
        finally:
            self.is_running_gan = False
            self._flush_pending_chats()
            
            # 在GAN完成后运行自我优化（如果有足够的交互数据）
            self._run_self_optimization()
            # 顯式收場事件：本次閒置活動（含社交/自我優化）全部結束
            if self.callback:
                try:
                    self.callback({"type": "idle_end"})
                except Exception:
                    pass
    
    def _long_task_gate(self):
        """长期任务调度：休息中 → 全部停工；任务到点 → 先推进任务。

        返回 False 表示本次空闲时段不再跑常规活动（GAN/社交/自学）。
        """
        def _thought(msg):
            if self.callback:
                try:
                    self.callback({"type": "internal_thought", "thought": msg})
                except Exception:
                    pass

        try:
            from tools.long_tasks import get_task_store
            store = get_task_store()
        except Exception:
            return True
        try:
            if store.is_resting():
                ru = store.rest_until()
                reason = (store.rest_state or {}).get("reason") or ""
                suffix = f"（{reason}）" if reason else ""
                _thought(f"[LongTask] 正在休息，{ru.strftime('%H:%M')} 前不做任何事{suffix}")
                return False
            due = store.due_tasks()
            if not due:
                return True
            _thought("[LongTask] 记着的任务：\n" + store.reminder_text(max_tasks=3))
            self._long_task_focus(due, store)
            return False
        except Exception as e:
            _thought(f"[LongTask] 调度检查失败：{e}")
            return True

    def _long_task_focus(self, due, store):
        """到点后让 Aize 自己决定：再推进一小步，还是休息一段。"""
        def _thought(msg):
            if self.callback:
                try:
                    self.callback({"type": "internal_thought", "thought": msg})
                except Exception:
                    pass
        try:
            from llm import chat
        except Exception:
            return
        info = store.reminder_text(max_tasks=3)
        prompt = (
            "你有长期任务，现在是你的空闲时间。\n"
            f"{info}\n\n"
            "请决定这一小段时间做什么，只输出一个 JSON：\n"
            '{"action":"work","step":"这次具体推进的一步","minutes":20,"progress":"更新后的进度"}\n'
            "或者\n"
            '{"action":"rest","minutes":30,"reason":"休息时想做什么，比如刷社交网站、找用户聊天、发呆"}\n\n'
            "规则：始终记着截止时间；快到期就多工作、少休息；"
            "想休息就给出明确的结束分钟数，醒来继续做。"
        )
        try:
            raw = (chat(prompt, max_tokens=300, timeout=90) or "").strip()
        except Exception as e:
            _thought(f"[LongTask] 决策失败：{e}")
            return
        import re as _re
        import json as _json
        m = _re.search(r"\{.*\}", raw, _re.S)
        if not m:
            _thought("[LongTask] 决策结果不是 JSON，本次跳过")
            return
        try:
            data = _json.loads(m.group(0))
        except Exception:
            _thought("[LongTask] 决策 JSON 解析失败")
            return

        action = str(data.get("action") or "").lower()
        if action == "rest":
            try:
                minutes = int(data.get("minutes") or 30)
            except Exception:
                minutes = 30
            res = store.rest(minutes=minutes, reason=data.get("reason") or "")
            if res.get("success"):
                ru = store.rest_until()
                _thought(f"[LongTask] 先休息 {minutes} 分钟到 {ru.strftime('%H:%M')}，"
                         f"然后回来继续（{data.get('reason') or '放空一下'}）")
            return

        if action == "work":
            task = due[0]
            step = str(data.get("step") or "").strip()
            progress = str(data.get("progress") or "").strip()
            try:
                minutes = int(data.get("minutes") or 20)
            except Exception:
                minutes = 20
            store.update(task.get("id"), next_step=step, progress=progress or None,
                         next_minutes=max(5, minutes), note=step)
            _thought(f"[LongTask] #{task.get('id')} {task.get('title')}：这一轮 {step}"
                     + (f"，进度：{progress}" if progress else "")
                     + f"；{minutes} 分钟后继续")

    def _idle_think(self):
        """獨處第一步（大腦）：讓她完全自由地想。

        這裡**不規定任何輸出格式**——不要求欄位、不給標籤、不給活動菜單。
        她只是用自己的語氣把此刻的念頭寫下來，就像人真的在心裡自言自語。
        """
        from llm import chat
        from core.data.prompts_manager import load_prompt

        prompt = load_prompt("idle_activity_choice")
        # 带 Aize 自我人格（用户自定义提示词在前、人格在后）
        try:
            _persona_text = persona_block("idle", self.memory)
            if _persona_text:
                prompt = prompt + "\n\n" + _persona_text
        except Exception:
            pass
        _feel = _affect_block()
        if _feel:
            prompt = prompt + "\n\n" + _feel

        try:
            return chat(prompt).strip()
        except Exception:
            return ""

    def _route_thought(self, thought):
        """獨處第二步（小腦 / 執行器 Agent）：讀她的自由獨白，判斷她想不想動手。

        她說「我想找主人聊聊天」，大腦不需要知道這對應哪個動作；
        由這個執行器把它翻譯成動作詞表裡的一項，再交給對應的技能去跑。
        返回 (action, plan)；action 取 _IDLE_ACTIONS（none = 只是想想，不做事）。
        """
        if not thought:
            return "none", ""
        from llm import chat
        from core.data.prompts_manager import load_prompt

        prompt = load_prompt("idle_intent_executor")
        prompt = prompt.replace("{thought}", thought)
        try:
            raw = chat(prompt).strip()
            data = _json_from_text(raw)
            action = str(data.get("action") or "none").strip().lower()
            plan = str(data.get("plan") or "").strip()
            if action not in _IDLE_ACTIONS:
                action = "none"
            return action, plan
        except Exception:
            return "none", ""

    def _do_self_learning(self, kind):
        """空闲自学：直接两次 LLM 调用，不走 function-calling 工具循环。

        kind="persona"：联网摘要 + 聊天记录 → 生成新的自我人格全文并保存；
        kind="emotion"：让模型输出情绪 JSON 数组 → 逐条写入情绪词库。
        频率限制：persona 至少 6 小时一次，emotion 至少 2 小时一次。
        任何异常都只记录思考日志，绝不让空闲线程崩。
        """
        def _thought(msg):
            if self.callback:
                try:
                    self.callback({"type": "internal_thought", "thought": msg})
                except Exception:
                    pass

        try:
            from llm import chat
        except Exception as e:
            _thought(f"[Self-Learning] LLM 不可用，跳过：{e}")
            return

        kind = str(kind or "").strip().lower()
        interval = 3 * 3600 if kind == "persona" else 1 * 3600
        try:
            if not should_learn(kind, interval):
                hours = int(interval // 3600)
                _thought(f"[Self-Learning] 距上次{kind}学习不足 {hours} 小时，本次跳过")
                return
        except Exception as e:
            _thought(f"[Self-Learning] 检查学习间隔失败：{e}")
            return

        try:
            if kind == "persona":
                digest = self._persona_web_digest()
                prompt = build_persona_growth_prompt(self.memory, digest)
                text = (chat(prompt, max_tokens=1200, timeout=120) or "").strip()
                if not text:
                    _thought("[Self-Learning] 人格生成结果为空，本次不保存")
                    return
                save_self_persona(text)
                try:
                    mark_learned("persona")
                except Exception:
                    pass
                _thought("[Self-Learning] Aize 更新了自我人格：" + text[:120].replace("\n", " "))
            elif kind == "emotion":
                raw = (chat(build_emotion_study_prompt(), max_tokens=1200, timeout=120) or "").strip()
                parsed = self._parse_emotion_study(raw)
                if not parsed:
                    _thought("[Self-Learning] 情绪 JSON 解析失败，本次跳过")
                    return
                added = 0
                for item in parsed:
                    emotion = str(item.get("emotion") or "").strip()
                    cues = item.get("cues") or []
                    expressions = item.get("expressions") or []
                    text = ""
                    if isinstance(expressions, list) and expressions:
                        text = str(expressions[0]).strip()
                    if not text and isinstance(cues, list) and cues:
                        text = "、".join(str(c).strip() for c in cues if str(c).strip())
                    if emotion and text:
                        try:
                            if learn_emotion(text, emotion, note="空闲自学"):
                                added += 1
                        except Exception:
                            pass
                if added:
                    _thought(f"[Self-Learning] 情绪词库新增 {added} 条")
                else:
                    _thought("[Self-Learning] 没有新增有效情绪条目（可能都已存在）")
                try:
                    mark_learned("emotion")
                except Exception:
                    pass
            else:
                _thought(f"[Self-Learning] 未知学习类型：{kind}")
        except Exception as e:
            _thought(f"[Self-Learning] {kind} 学习失败：{e}")

    @staticmethod
    def _parse_emotion_study(raw):
        """从模型输出中提取情绪 JSON 数组。

        输出被 max_tokens 截断时（常见于条目很多的数组），逐个提取已经完整的
        {...} 对象，保留能解析的部分，而不是整批丢掉。
        """
        import json as _json
        import re as _re

        text = (raw or "").strip()
        text = _re.sub(r"^```[A-Za-z]*\s*", "", text)
        text = _re.sub(r"\s*```$", "", text).strip()
        if not text:
            return []

        try:
            data = _json.loads(text)
        except Exception:
            data = None

        if data is None:
            # 截断兜底：按字符串感知的大括号配对，收集所有完整的对象
            items = []
            depth = 0
            start = -1
            in_str = False
            escaped = False
            for i, ch in enumerate(text):
                if in_str:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}" and depth:
                    depth -= 1
                    if depth == 0 and start >= 0:
                        try:
                            item = _json.loads(text[start:i + 1])
                            if isinstance(item, dict):
                                items.append(item)
                        except Exception:
                            pass
                        start = -1
            data = items

        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), [])
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _do_aesthetic_learning(self):
        """审美自学：从网上抓图，用 Pillow 提取配色/明暗/构图特征，
        再结合网上的文字资料，让模型总结自己的审美观察。"""
        def _thought(msg):
            if self.callback:
                try:
                    self.callback({"type": "internal_thought", "thought": msg})
                except Exception:
                    pass

        try:
            from llm import chat
        except Exception as e:
            _thought(f"[Aesthetic] LLM 不可用，跳过：{e}")
            return
        try:
            from PIL import Image  # noqa: F401
        except Exception:
            _thought("[Aesthetic] 没有安装 Pillow，跳过图片分析")
            return

        db = _load_aesthetic()
        try:
            if db.get("last_learned_at"):
                from datetime import datetime
                dt = datetime.fromisoformat(str(db["last_learned_at"]))
                if (datetime.now() - dt).total_seconds() < 2 * 3600:
                    _thought("[Aesthetic] 距上次审美学习不足 2 小时，本次跳过")
                    return
        except Exception:
            pass

        work = os.path.join(os.path.dirname(_aesthetic_path()), "media", "aesthetic",
                            time.strftime("%Y%m%d_%H%M%S"))
        try:
            os.makedirs(work, exist_ok=True)
        except Exception:
            pass

        entries = []
        for idx, url in enumerate(self._bing_image_urls("风景摄影 构图 色彩 光影", 8)[:4]):
            path = os.path.join(work, f"img_{idx + 1}.jpg")
            if not self._download_image(url, path):
                continue
            stats = self._analyze_image_stats(path)
            if not stats:
                continue
            stats["source"] = url
            entries.append(stats)
            _thought(f"[Aesthetic] 分析 img_{idx + 1}：亮度 {stats['brightness']:.0f}，"
                     f"饱和 {stats['saturation']:.0f}，主色 {'/'.join(stats['palette'][:3])}")

        if not entries:
            _thought("[Aesthetic] 这次没有成功抓到可分析的图片，跳过")
            return

        digest = self._persona_web_digest("摄影 构图 配色 美学 设计")
        metrics = json.dumps(entries, ensure_ascii=False)[:1600]
        prompt = (
            "你在训练自己的审美。下面是你从网上看到的几张图片的客观数据"
            "（尺寸、亮度、饱和度、色彩丰富度、锐度、主色）和相关的网络文字资料。\n\n"
            f"图片数据：{metrics}\n\n网络资料：{digest or '（无）'}\n\n"
            "请用中文写 3-5 句你自己的审美观察：什么样的配色、明暗关系、构图会好看，"
            "为什么；也可以说你在数据里注意到的规律。不要罗列数据，不要写标题。"
        )
        try:
            insight = (chat(prompt, max_tokens=500, timeout=120) or "").strip()
        except Exception as e:
            _thought(f"[Aesthetic] 总结失败：{e}")
            insight = ""

        db["entries"] = (db.get("entries") or [])[-200:] + entries
        if insight:
            db["insights"] = (db.get("insights") or [])[-200:] + [
                {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "text": insight}]
            try:
                add_thought(self.memory, insight, thought_type="aesthetic")
                save_memory(self.memory)
            except Exception:
                pass
            _thought("[Aesthetic] " + insight[:180].replace("\n", " "))
        db["last_learned_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_aesthetic(db)

    @staticmethod
    def _bing_image_urls(query, limit=8):
        """从 Bing 图片搜索页提取原图地址（爬不到就返回空列表）。"""
        import re as _re
        import html as _html
        import urllib.parse as _parse
        import urllib.request as _req
        try:
            url = ("https://www.bing.com/images/search?q=" + _parse.quote(query)
                   + "&first=1&tsc=ImageBasicHover")
            req = _req.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            page = _req.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        except Exception:
            return []
        found = (_re.findall(r'murl&quot;:&quot;(.*?)&quot;', page)
                 or _re.findall(r'"murl":"(.*?)"', page))
        urls = []
        for raw in found:
            u = _html.unescape(raw).replace("\\/", "/")
            if not u.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            if u not in urls:
                urls.append(u)
            if len(urls) >= limit:
                break
        return urls

    @staticmethod
    def _download_image(url, path):
        import urllib.request as _req
        try:
            req = _req.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"})
            with _req.urlopen(req, timeout=25) as resp:
                data = resp.read(10 * 1024 * 1024)
            with open(path, "wb") as f:
                f.write(data)
            from PIL import Image
            with Image.open(path) as im:
                im.verify()
            return True
        except Exception:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            return False

    @staticmethod
    def _analyze_image_stats(path):
        """Pillow 客观分析：亮度/饱和度/色彩丰富度/锐度/主色/构图比例。"""
        try:
            import math
            from PIL import Image, ImageStat, ImageFilter
            with Image.open(path) as im:
                im = im.convert("RGB")
                w, h = im.size
                if w < 8 or h < 8:
                    return {}
                small = im.resize((256, 256))
                stat = ImageStat.Stat(small)
                brightness = sum(stat.mean) / 3.0
                hsv = small.convert("HSV")
                saturation = ImageStat.Stat(hsv).mean[1]
                # Hasler & Süsstrunk 色彩丰富度
                pixels = list(small.getdata())
                r = [p[0] for p in pixels]
                g = [p[1] for p in pixels]
                b = [p[2] for p in pixels]
                rg = [a - c for a, c in zip(r, g)]
                yb = [0.5 * (a + c) - d for a, c, d in zip(r, g, b)]
                def _mean_std(v):
                    m = sum(v) / len(v)
                    s = math.sqrt(sum((x - m) ** 2 for x in v) / len(v))
                    return m, s
                m_rg, s_rg = _mean_std(rg)
                m_yb, s_yb = _mean_std(yb)
                colorfulness = (math.sqrt(s_rg ** 2 + s_yb ** 2)
                                + 0.3 * math.sqrt(m_rg ** 2 + m_yb ** 2))
                edges = ImageStat.Stat(small.convert("L").filter(ImageFilter.FIND_EDGES))
                sharpness = float(edges.var[0])
                colors = small.quantize(colors=5).convert("RGB").getcolors(maxcolors=256) or []
                colors.sort(key=lambda c: c[0], reverse=True)
                palette = ["#%02x%02x%02x" % c[1] for c in colors[:5]]
                return {
                    "file": path,
                    "size": [w, h],
                    "aspect": round(w / float(h), 2),
                    "brightness": round(brightness, 1),
                    "saturation": round(saturation, 1),
                    "colorfulness": round(colorfulness, 1),
                    "sharpness": round(sharpness, 1),
                    "palette": palette,
                }
        except Exception:
            return {}

    def _persona_web_digest(self, query="近期社会话题 人类情感 生活"):
        """尝试联网取一段摘要；任何失败都返回空串。"""
        mod = self._load_web_search_module()
        if mod is None:
            return ""
        res = {}
        for payload in ({"query": query}, {"action": "search", "query": query}):
            try:
                res = mod.execute(payload)
                if isinstance(res, dict) and res.get("success"):
                    break
            except Exception:
                res = {}
        if not isinstance(res, dict) or not res.get("success"):
            return ""
        lines = []
        for item in (res.get("results") or [])[:5]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("snippet") or item.get("body") or "").strip()
            if title or snippet:
                lines.append(f"- {title}：{snippet[:120]}")
        return "\n".join(lines)

    @staticmethod
    def _load_web_search_module():
        """按文件路径隔离载入 skills/web-search（兼容 dev 与打包态）。"""
        import importlib.util
        import sys as _sys
        candidates = []
        meipass = getattr(_sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, "skills", "web-search", "__init__.py"))
        if getattr(_sys, "frozen", False):
            candidates.append(os.path.join(
                os.path.dirname(_sys.executable), "skills", "web-search", "__init__.py"))
        candidates.append(os.path.join(_PROJECT_ROOT, "skills", "web-search", "__init__.py"))
        for init in candidates:
            if not os.path.exists(init):
                continue
            try:
                spec = importlib.util.spec_from_file_location("skills_web_search", init)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
            except Exception:
                continue
        return None

    @staticmethod
    def _load_music_skill():
        """按文件路径隔离载入 skills/music-gen（兼容 dev 与打包态）。"""
        import importlib.util
        import sys as _sys
        candidates = []
        meipass = getattr(_sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, "skills", "music-gen", "__init__.py"))
        if getattr(_sys, "frozen", False):
            candidates.append(os.path.join(
                os.path.dirname(_sys.executable), "skills", "music-gen", "__init__.py"))
        candidates.append(os.path.join(_PROJECT_ROOT, "skills", "music-gen", "__init__.py"))
        for init in candidates:
            if not os.path.exists(init):
                continue
            try:
                spec = importlib.util.spec_from_file_location("skills_music_gen", init)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
            except Exception:
                continue
        return None

    def _do_music_learning(self):
        """音乐自学：挑一个语料最少的曲风，收集 2 首音频 → NumPy 提取频谱 → 更新音色档案。"""
        def _thought(msg):
            if self.callback:
                try:
                    self.callback({"type": "internal_thought", "thought": msg})
                except Exception:
                    pass

        mod = self._load_music_skill()
        if mod is None:
            _thought("[Music] 找不到 music-gen 技能，跳过本次音乐学习")
            return
        try:
            if not should_learn("music", 3 * 3600):
                _thought("[Music] 距上次音乐学习不足 3 小时，本次跳过")
                return
        except Exception:
            pass

        genres = ["jazz", "classical", "blues", "rock", "electronic",
                  "folk", "ambient", "hiphop", "pop", "chinese"]
        try:
            listing = mod.execute({"action": "list"}).get("genres") or {}
            pick = min(genres, key=lambda g: ((listing.get(g) or {}).get("tracks_learned") or 0,
                                              (listing.get(g) or {}).get("tracks") or 0))
            got = mod.execute({"action": "collect", "genre": pick, "limit": 2})
            saved = int(got.get("count") or 0)
            analyzed = mod.execute({"action": "analyze", "genre": pick})
            if not analyzed.get("success"):
                _thought(f"[Music] {pick} 频谱分析没有结果：{analyzed.get('error')}；本次新收集 {saved} 首")
                return
            _thought(f"[Music] 收集 {pick} {saved} 首，已分析 {analyzed.get('tracks')} 首，"
                     f"主频能量中心 {analyzed.get('avg_centroid_hz')} Hz，音色档案已更新")
            try:
                mark_learned("music")
            except Exception:
                pass
        except Exception as e:
            _thought(f"[Music] 学习失败：{e}")

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

    @staticmethod
    def _desktop_control_enabled() -> bool:
        """读设置里的桌面控制开关，缺省视为开启。"""
        import json as _json
        path = None
        for mod in ("app_paths", "core.app_paths"):
            try:
                m = __import__(mod, fromlist=["get_settings_path"])
                path = m.get_settings_path()
                break
            except Exception:
                continue
        if not path:
            return True
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return bool(_json.load(fh).get("desktop_control_enabled", True))
        except Exception:
            return True

    def _do_desktop_control(self, plan: str = "", activity: str = ""):
        """闲时自主操作电脑：Aize 给出目标 → computer-control 技能闭环执行。"""
        def _thought(msg):
            if self.callback:
                self.callback({"type": "internal_thought", "thought": msg})

        if not self._desktop_control_enabled():
            _thought("[Desktop Control] 已在设置中关闭，跳过")
            return

        goal = (plan or "").strip()
        if not goal:
            goal = "先观察当前屏幕，然后做一件对主人有帮助的小事（整理窗口或打开常用程序）"

        mod = self._load_skill_module("computer-control")
        if mod is None:
            _thought("[Desktop Control] 技能未加载（skills/computer-control 缺失）")
            return

        _thought(f"[Desktop Control] 目标：{goal}")
        try:
            result = mod.execute({
                "action": "run_goal",
                "goal": goal,
                "max_steps": 15,
                "max_seconds": 900,
            })
        except Exception as error:
            result = {"success": False, "error": str(error)}

        if result.get("success"):
            _thought(f"[Desktop Control] 完成：{result.get('observation') or '目标已完成'}")
        else:
            _thought(f"[Desktop Control] 未完成：{result.get('error') or result.get('stop_reason')}")

        if self.memory is not None:
            try:
                add_thought(self.memory,
                            f"[Desktop Control] 目标：{goal}｜结果："
                            f"{'成功' if result.get('success') else '未完成'}",
                            thought_type="action")
                save_memory(self.memory)
            except Exception:
                pass

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
            try:
                from tools.skills_manager import is_skill_enabled
            except ImportError:
                from core.tools.skills_manager import is_skill_enabled
            if not is_skill_enabled("misskey-bot"):
                _thought("[Social] misskey-bot 技能已停用，跳過社交活動")
            else:
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
            _feel = _affect_block()
            if _feel:
                prompt += "\n\n" + _feel
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
        """已配置可用且技能未被停用的社交平台列表（可寫入的才會列入）。"""
        platforms = []
        try:
            from tools.skills_manager import is_skill_enabled
        except ImportError:
            from core.tools.skills_manager import is_skill_enabled
        if not is_skill_enabled("misskey-bot"):
            return platforms
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
