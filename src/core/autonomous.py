from datetime import datetime, timedelta
import threading
import time
import re
import random
from typing import Optional

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
        "elapsed_seconds": elapsed
    }


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
    """生成自主消息内容"""
    messages = memory.get("messages", [])

    # 获取最近的对话主题
    recent_topics = _extract_topics(messages)

    # 根据对话状态生成消息
    if not messages:
        # 初次对话
        greetings = [
            f"嗨~ 我是{name}！有什么我可以帮你的吗？",
            f"你好呀！我是{name}，很高兴认识你~ 今天想聊点什么呢？",
            f"哈喽！我是{name}，随时为你效劳！有什么想聊的吗？"
        ]
        return random.choice(greetings)

    elif len(messages) <= 3:
        # 对话刚开始
        questions = [
            "我们刚刚聊到哪儿了？或者你有什么特别想聊的话题吗？",
            "对了，你平时有什么兴趣爱好吗？",
            "最近有什么有趣的事情发生吗？"
        ]
        return random.choice(questions)

    else:
        # 对话进行中
        if recent_topics:
            topic = random.choice(recent_topics)
            follow_up_options = [
                f"说到{topic}，我突然想到一个问题...",
                f"关于{topic}，你有什么特别的见解吗？",
                f"如果我们深入聊聊{topic}，你觉得怎么样？"
            ]
            return random.choice(follow_up_options)
        else:
            return f"{name}在思考呢... 你有什么想法吗？"


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
