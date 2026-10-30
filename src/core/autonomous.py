from datetime import datetime, timedelta
import threading
import time
import re
import random
import collections
from typing import Optional

try:
    from core.persona import habit_status, suppression_until
except ImportError:
    try:
        from persona import habit_status, suppression_until
    except ImportError:
        habit_status = None
        suppression_until = None

# 同一进程内最近 8 条主动开场白，避免反复说同一句
_RECENT_OUTPUTS = collections.deque(maxlen=8)

# 自主行动类型
ACTION_TYPES = {
    "INITIATE_TOPIC": "主动发起新话题",
    "ASK_QUESTION": "提出问题",
    "SHARE_INSIGHT": "分享见解",
    "FOLLOW_UP": "追问跟进",
    "EXPLORE_INTEREST": "探索用户兴趣",
    "REFLECT_ON_CHAT": "反思对话",
    "AUTO_THINK": "内部思考"
}


def check_silence_and_decide(memory, threshold_seconds=60):
    """
    如果使用者长时间未回复，则返回一个自主思考建议。
    基于记忆做出决策，不依赖固定性格特征。
    """
    # 主人说过「我要上课了」之类：在预计回来时间（+10 分钟宽限）之前不打扰
    try:
        if suppression_until is not None and suppression_until():
            return None
    except Exception:
        pass

    if not memory.get("messages"):
        return None

    last_user = None
    for msg in reversed(memory["messages"]):
        if msg.get("role") == "user":
            last_user = msg
            break

    if last_user is None:
        return None

    try:
        last_time = datetime.fromisoformat(last_user.get("time"))
    except Exception:
        return None

    now = datetime.now()
    elapsed = (now - last_time).total_seconds()

    if elapsed < threshold_seconds:
        return None

    # 基于对话历史决定行动类型
    action_type = _decide_action_type(memory)

    return {
        "action": action_type,
        "message": ACTION_TYPES.get(action_type, "AI正在思考下一步行动"),
        "confidence": _calculate_confidence(memory, elapsed),
        "elapsed_seconds": elapsed,
        "habit": _habit_snapshot(),
        "now": datetime.now().isoformat(),
    }


def _habit_snapshot():
    """习惯快照（awaiting / patterns），失败返回 None。"""
    try:
        return habit_status() if habit_status is not None else None
    except Exception:
        return None


def _decide_action_type(memory):
    """根据记忆决定自主行动类型 - AI自主决定"""
    messages = memory.get("messages", [])
    is_ongoing_conversation = len(messages) > 5

    # 根据对话状态决定行动
    if is_ongoing_conversation:
        # 对话进行中，随机选择跟进方式
        weights = {
            "FOLLOW_UP": 0.3,
            "ASK_QUESTION": 0.25,
            "SHARE_INSIGHT": 0.2,
            "EXPLORE_INTEREST": 0.15,
            "REFLECT_ON_CHAT": 0.1
        }
    else:
        # 对话刚开始，随机选择开场方式
        weights = {
            "INITIATE_TOPIC": 0.35,
            "EXPLORE_INTEREST": 0.3,
            "ASK_QUESTION": 0.2,
            "SHARE_INSIGHT": 0.15
        }

    # 随机选择行动类型
    rand = random.random()
    cumulative = 0
    for action, weight in weights.items():
        cumulative += weight
        if rand <= cumulative:
            return action

    return "AUTO_THINK"


def _calculate_confidence(memory, elapsed_seconds=60):
    """计算决策置信度"""
    confidence = 0.5

    # 基于沉默时间
    if elapsed_seconds >= 300:  # 5分钟
        confidence += 0.3
    elif elapsed_seconds >= 120:  # 2分钟
        confidence += 0.15

    # 基于对话历史长度
    messages = memory.get("messages", [])
    if len(messages) > 10:
        confidence += 0.1

    return min(1.0, confidence)


def _recent_dialogue(memory, n=10):
    """取最近 n 句對話作為主動搭話的上下文，避免開口就是空話套話。"""
    rows = []
    for msg in (memory or {}).get("messages", [])[-n:]:
        text = str(msg.get("content") or "").strip()
        if not text:
            continue
        if "RESPONSE:" in text:
            text = text.split("RESPONSE:", 1)[1].strip()
        text = re.sub(r"\[\s*motion\s*:[^\]]*\]", "", text, flags=re.I).strip()
        if not text:
            continue
        if msg.get("role") == "assistant":
            text = text[:120]
        rows.append(("主人" if msg.get("role") == "user" else "Aize") + "：" + text)
    return "\n".join(rows)


def generate_autonomous_message(memory, name="Aize"):
    """生成自主消息内容：以开启新话题为目的，避免重复最近说过的话。"""
    messages = (memory or {}).get("messages", [])

    # 获取最近的对话主题
    recent_topics = _extract_topics(messages)
    # 最近 10 条自己说过的话：作为「请换新话题」的提醒
    recent_self = _recent_assistant_lines(memory, 10)

    new_topic_prompts = [
        "最近让你觉得有意思的一件小事",
        "如果你现在能立刻去一个地方，会去哪里",
        "小时候最想成为什么样的人",
        "最近有什么让你好奇但还没弄明白的事",
        "如果明天突然放假，你会怎么过",
        "你最近吃到的最好吃的东西",
    ]

    # 根据对话状态生成消息
    if not messages:
        # 初次对话
        candidates = [
            f"嗨，我是{name}。想聊点新鲜的：{random.choice(new_topic_prompts)}？",
            f"你好呀，我是{name}。我们从没聊过——{random.choice(new_topic_prompts)}，你怎么看？",
            f"我是{name}。不聊客套话，想听听你对「{random.choice(new_topic_prompts)}」的想法。",
        ]
    elif len(messages) <= 3:
        # 对话刚开始
        candidates = [
            f"我们刚认识不久，换个新话题吧：{random.choice(new_topic_prompts)}。",
            f"我想多了解你一点：{random.choice(new_topic_prompts)}，愿意说说吗？",
            f"突然想到一个问题：{random.choice(new_topic_prompts)}，你的答案是什么？",
        ]
    else:
        # 对话进行中：从旧话题之外找个新角度
        topic = random.choice(recent_topics) if recent_topics else random.choice(new_topic_prompts)
        candidates = [
            f"刚才聊的都过去了，我想开启一个新话题：{topic}。",
            f"关于{topic}，我脑子里冒出一个新角度，想和你聊聊。",
            f"我们还没认真聊过{topic}，要不要现在说说？",
            f"换个方向：{random.choice(new_topic_prompts)}，我挺好奇你的看法。",
            f"我突然想问你一个和之前不一样的问题：{random.choice(new_topic_prompts)}。",
        ]

    message = _pick_new_message(candidates)
    if recent_self:
        message += ("\n\n【最近你说过（请换个新话题，不要重复）】\n" +
                    "\n".join("- " + t for t in recent_self))
    return message


def _clean_short(text, limit=120):
    """清理回复文本（去掉 RESPONSE 前缀与动作标签），用于去重参考。"""
    text = str(text or "").strip()
    if "RESPONSE:" in text:
        text = text.split("RESPONSE:", 1)[1].strip()
    text = re.sub(r"\[\s*motion\s*:[^\]]*\]", "", text, flags=re.I).strip()
    return text[:limit]


def _recent_assistant_lines(memory, n=10):
    """取最近 n 条 assistant 文案（时间正序），供自主开场白避免重复。"""
    texts = []
    for msg in reversed((memory or {}).get("messages", [])):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        text = _clean_short(msg.get("content"), 80)
        if text:
            texts.append(text)
        if len(texts) >= n:
            break
    return list(reversed(texts))


def _pick_new_message(candidates):
    """从候选开场白中挑一条最近 8 条里没说过的，避免重复。"""
    pool = list(candidates or [])
    if not pool:
        return "我在想点自己的事情，你有空的话我们可以聊聊。"
    random.shuffle(pool)
    for item in pool:
        if item not in _RECENT_OUTPUTS:
            _RECENT_OUTPUTS.append(item)
            return item
    chosen = pool[0]
    _RECENT_OUTPUTS.append(chosen)
    return chosen


def _extract_topics(messages, num_topics=3):
    """从对话中提取主题"""
    topics = []
    
    for msg in reversed(messages[-10:]):
        content = msg.get("content", "")
        # 简单提取名词作为主题
        topic_keywords = ["关于", "讨论", "聊聊", "说说", "想知道", "觉得"]
        for keyword in topic_keywords:
            idx = content.find(keyword)
            if idx != -1:
                topic = content[idx+len(keyword):].strip()
                if topic and topic not in topics:
                    topics.append(topic[:30])
                    if len(topics) >= num_topics:
                        return topics
    
    return topics


class AutonomousEngine:
    def __init__(self, memory, callback=None, interval_seconds=30, auto_break_silence=True):
        self.memory = memory
        self.callback = callback
        self.interval_seconds = interval_seconds
        self.auto_break_silence = auto_break_silence
        self.running = False
        self._thread = None
        self._last_user_time = None
        self._last_action_time = None
        self.name = "Aize"  # AI名字
        self.thinking_engine = None
        # 空闲小动作：不对话时也隔一段时间让 Live2D 身体动一动
        self._last_motion_time = 0.0
        self._next_motion_gap = random.uniform(8, 20)

    def set_name(self, name):
        """设置AI名字"""
        self.name = name

    def set_thinking_engine(self, engine):
        """设置思考引擎引用"""
        self.thinking_engine = engine

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def on_user_message(self):
        self._last_user_time = datetime.now()
        self._last_action_time = datetime.now()

    def _run(self):
        while self.running:
            try:
                self._maybe_idle_motion()
                if not self.auto_break_silence:
                    time.sleep(self.interval_seconds)
                    continue

                decision = check_silence_and_decide(self.memory)
                if decision and self.callback:
                    self.callback({"type": "autonomous_decision", "decision": decision})

                    # 如果置信度足够高，主动发起对话
                    if decision.get("confidence", 0) >= 0.7:
                        self._initiate_conversation()
            except Exception as e:
                # 静默处理异常
                pass
            time.sleep(self.interval_seconds)

    def _maybe_idle_motion(self):
        """不对话时让 Aize 自己动一下，但只用轻微 Idle，且动作由当下情绪决定。

        旧版是按 15~30 秒随机抽 Idle 0~8、还夹 25% TapBody，
        既太频繁又毫无依据（难过时也可能点头傻笑）。
        """
        if not self.running:
            return
        # 正在回覆時由對話裡的動作控制身體，閒置動作不插隊
        engine = self.thinking_engine
        if engine is not None and getattr(engine, "_chat_cancel_event", None) is not None:
            return
        now = time.time()
        if now - self._last_motion_time < self._next_motion_gap:
            return
        try:
            from tools.live2d_hub import get_live2d_hub
            from tools.motion_policy import pick_idle_motion

            hub = get_live2d_hub()
            # 刚在说话/回覆（12 秒内推过命令）时不插闲置动作，避免两套动作打架
            if now - getattr(hub, "last_command_ts", 0.0) < 12:
                return
            command = pick_idle_motion()
            self._last_motion_time = now
            # 闲置动作稀疏一点，别一直动个不停
            self._next_motion_gap = random.uniform(30, 75)
            if command:
                hub.push_command(command)
        except Exception:
            pass


    def _initiate_conversation(self):
        """主动发起对话"""
        if self._last_action_time and (datetime.now() - self._last_action_time).total_seconds() < 300:
            # 5分钟内已经有行动，避免过于频繁
            return

        try:
            message = generate_autonomous_message(self.memory, self.name)
            recent = _recent_dialogue(self.memory, 10)
            if recent:
                message = (f"{message}\n\n【最近10句對話（接話要具體，別說空話套話）】\n{recent}")

            if self.thinking_engine and message:
                # 通过思考引擎发送消息
                self.thinking_engine.queue_break_silence_task(
                    prompt=message,
                    memory=self.memory
                )

            self._last_action_time = datetime.now()

        except Exception as e:
            # 静默处理异常
            pass

    def should_initiate_topic(self) -> bool:
        """判断是否应该主动发起话题"""
        decision = check_silence_and_decide(self.memory)
        return decision and decision.get("confidence", 0) >= 0.6
