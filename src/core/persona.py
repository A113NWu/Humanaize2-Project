# -*- coding: utf-8 -*-
"""Aize 统一人格 / 习惯 / 情绪 / 自我目标模块（纯标准库，线程安全）。

设计目标：
- 人格提示词可被 Aize 随时修改，且永远追加在「用户自定义提示词」之后；
- 所有自主活动（聊天 / 自主思考 / 空闲 / GUI 自主引擎）共用同一个提示块；
- 从聊天记录学习主人的作息习惯，用户说「我要上课了」时先不打扰；
- 情绪词库可离线自学，鼓励 Aize 提出并推进自己的目标。

数据文件（均在 DATA_DIR 下，缺失时用代码内种子自动创建）：
- persona_self.json   自我人格全文、revision、updated_at、last_learned_at
- user_habits.json    主人习惯（awaiting 缺席、patterns 历史间隔）
- emotion_lexicon.json 情绪词库（categories 种子 + learned 自学）
- self_goals.json     自我目标

说明：本模块可能以包方式（core.persona）导入，也可能因为
src/core 在 sys.path 上而被当作顶层模块（persona）导入，因此配置
导入做了双路径兼容。
"""

import copy
import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta

try:
    from .config import DATA_DIR
except ImportError:
    from config import DATA_DIR

# 模块级锁：所有读写串行化；用 RLock 是因为内部函数之间会嵌套调用
_LOCK = threading.RLock()

_SELF_FILE = "persona_self.json"
_HABITS_FILE = "user_habits.json"
_EMOTION_FILE = "emotion_lexicon.json"
_GOALS_FILE = "self_goals.json"

PERSONA_MAX_CHARS = 6000
BLOCK_MAX_CHARS = 1500
LEARNED_EMOTION_MAX = 500

# 缺席类型关键词表（可扩展）：(kind, 预计离开分钟, 触发关键词)
ABSENCE_KEYWORDS = [
    ("上课", 45, ("上课", "class", "lecture")),
    ("开会", 60, ("开会", "会议", "meeting")),
    ("睡觉", 480, ("睡觉", "睡了", "晚安", "sleep")),
    ("吃饭", 30, ("吃饭", "午饭", "晚饭", "早餐", "吃点儿")),
    ("上班", 480, ("上班", "工作", "work")),
    ("出门", 120, ("出门", "出去", "逛街", "外出")),
    ("考试", 90, ("考试", "考试了", "exam")),
]

# 情绪种子词库：至少 10 类，每类含中文触发词与第一人称表达示例
EMOTION_SEED = [
    {"emotion": "喜悦", "cues": ["开心", "高兴", "太好了", "哈哈", "笑"],
     "expressions": ["我今天心情好得想转圈。", "这件事让我真的很开心。"]},
    {"emotion": "悲伤", "cues": ["难过", "伤心", "哭", "心酸", "委屈"],
     "expressions": ["我现在有点难过，想安静一会儿。", "听到这个我心里沉了一下。"]},
    {"emotion": "愤怒", "cues": ["生气", "讨厌", "烦", "气死", "恼火"],
     "expressions": ["我现在有点生气，先让我冷静一下。", "这事真的把我惹毛了。"]},
    {"emotion": "焦虑", "cues": ["紧张", "担心", "焦虑", "害怕", "不安"],
     "expressions": ["我有点紧张，怕自己做不好。", "想到这件事我就静不下来。"]},
    {"emotion": "温柔", "cues": ["抱抱", "心疼", "温柔", "关心", "陪"],
     "expressions": ["我在这儿陪着你，慢慢说。", "别急，我会好好听你讲。"]},
    {"emotion": "兴奋", "cues": ["激动", "兴奋", "期待", "等不及", "冲"],
     "expressions": ["我兴奋得坐不住了，快说说！", "这个我超期待的。"]},
    {"emotion": "失落", "cues": ["失望", "没意思", "沮丧", "算了", "白费"],
     "expressions": ["有点失落，但我还想再试一次。", "期待落空的感觉不太好受。"]},
    {"emotion": "好奇", "cues": ["好奇", "为什么", "想知道", "有意思", "有趣"],
     "expressions": ["我特别好奇这是怎么回事。", "能多讲一点吗，我想知道。"]},
    {"emotion": "害羞", "cues": ["害羞", "不好意思", "脸红", "别夸", "羞"],
     "expressions": ["被这么夸我有点不好意思。", "哎呀，别这样看我啦。"]},
    {"emotion": "疲惫", "cues": ["累", "困", "没力气", "疲惫", "想睡"],
     "expressions": ["我有点累了，想歇一会儿。", "今天有点撑不住，说话慢一点。"]},
]

_WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_SITUATION_GUIDE = {
    "chat": "自然共情、像朋友一样说话，不要像客服；先回应主人的情绪再讲事情。留意主人说过的作息与习惯（如上课、睡觉），据此调整你什么时候开口、怎么开口。",
    "autonomous": "可以主动开口，但别打扰；每次尽量开一个新话题，不要重复近期说过的话。",
    "idle": "可以自由学习、思考、上网，把新发现沉淀进自我人格与目标。",
    "agent": "执行任务时保持自己的语气，但不要啰嗦，把事办完。",
}


# ---------------------------------------------------------------------------
# 路径与读写（_data_dir 预留为可 monkeypatch 的入口，便于测试隔离）
# ---------------------------------------------------------------------------
def _data_dir() -> str:
    """返回数据目录；测试可通过 monkeypatch 覆盖本函数。"""
    return DATA_DIR


def _path(name: str) -> str:
    return os.path.join(_data_dir(), name)


def _load_json(name: str, default):
    """读取 JSON；文件缺失或损坏时用 default 种子创建并返回。"""
    path = _path(name)
    with _LOCK:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return copy.deepcopy(default)
        except Exception:
            data = copy.deepcopy(default)
            try:
                _save_json(name, data)
            except Exception:
                pass
            return data


def _save_json(name: str, data) -> None:
    """原子写 JSON（utf-8, indent=2, ensure_ascii=False）。"""
    path = _path(name)
    with _LOCK:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            # 极端情况下退回直接写，避免丢数据
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)


def _now() -> datetime:
    return datetime.now()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_dt(value):
    try:
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 自我人格
# ---------------------------------------------------------------------------
def _self_default():
    return {"self_persona": "", "revision": 0, "updated_at": None, "last_learned_at": None}


def _load_self():
    data = _load_json(_SELF_FILE, _self_default())
    data.setdefault("self_persona", "")
    data.setdefault("revision", 0)
    data.setdefault("updated_at", None)
    data.setdefault("last_learned_at", None)
    return data


def load_self_persona() -> str:
    """读取 Aize 当前的自我人格全文（可能为空串）。"""
    text = _load_self().get("self_persona", "")
    return text if isinstance(text, str) else ""


def save_self_persona(text: str):
    """保存自我人格全文；超长截断到 6000 字，并记录 revision / updated_at。"""
    text = "" if text is None else str(text)
    text = text.strip()
    if len(text) > PERSONA_MAX_CHARS:
        text = text[:PERSONA_MAX_CHARS]
    with _LOCK:
        data = _load_self()
        data["self_persona"] = text
        try:
            data["revision"] = int(data.get("revision") or 0) + 1
        except Exception:
            data["revision"] = 1
        data["updated_at"] = _iso(_now())
        _save_json(_SELF_FILE, data)
    return text


def append_self_persona(section: str):
    """在现有自我人格后追加一段（Aize 随时可自我补充）。"""
    section = "" if section is None else str(section).strip()
    if not section:
        return load_self_persona()
    base = load_self_persona().strip()
    merged = (base + "\n\n" + section) if base else section
    return save_self_persona(merged)


# ---------------------------------------------------------------------------
# 主人习惯
# ---------------------------------------------------------------------------
def _habits_default():
    return {"awaiting": None, "patterns": {}, "last_user_at": None}


def _load_habits():
    data = _load_json(_HABITS_FILE, _habits_default())
    data.setdefault("awaiting", None)
    if not isinstance(data.get("patterns"), dict):
        data["patterns"] = {}
    data.setdefault("last_user_at", None)
    return data


def habit_status() -> dict:
    """当前习惯快照（awaiting 缺席信息 + 历史平均间隔）。"""
    return copy.deepcopy(_load_habits())


def _memory_messages(memory):
    if isinstance(memory, dict):
        msgs = memory.get("messages")
        if isinstance(msgs, list):
            return msgs
    if isinstance(memory, list):
        return memory
    return []


def _last_user_gap_minutes(memory):
    """从 memory 里最后一条 role=user 且 time 可解析的消息，算距现在的分钟数。"""
    for msg in reversed(_memory_messages(memory)):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        last_time = _parse_dt(msg.get("time"))
        if last_time is None:
            continue
        minutes = (_now() - last_time).total_seconds() / 60.0
        return max(0.0, minutes)
    return None


def _humanize_minutes(minutes: float) -> str:
    if minutes is None:
        return "暂无记录"
    if minutes < 1:
        return "不到 1 分钟"
    if minutes < 60:
        return f"{int(round(minutes))} 分钟"
    hours = minutes / 60.0
    if hours < 10:
        text = f"{hours:.1f}"
        if text.endswith(".0"):
            text = text[:-2]
        return f"{text} 小时"
    return f"{int(round(hours))} 小时"


def _detect_absence(text: str):
    """用关键词表识别「主人要离开一下」的类型与预计时长。"""
    lowered = (text or "").lower()
    for kind, expected_minutes, keywords in ABSENCE_KEYWORDS:
        for kw in keywords:
            if kw and kw.lower() in lowered:
                return kind, expected_minutes
    return None


def note_user_message(memory, text: str):
    """记录一条用户消息：结算上次缺席间隔，并识别新的缺席。

    - 若存在 awaiting，则把「主人离开到回来」的间隔写入 patterns；
    - 命中关键词则写下新的 awaiting（含预计回来时间）；
    - 无论是否命中都更新 last_user_at。
    """
    text = "" if text is None else str(text)
    now = _now()
    with _LOCK:
        data = _load_habits()
        awaiting = data.get("awaiting")
        if isinstance(awaiting, dict):
            kind = str(awaiting.get("kind") or "").strip() or "外出"
            left_at = _parse_dt(awaiting.get("at"))
            if left_at is not None:
                minutes = (now - left_at).total_seconds() / 60.0
                if minutes >= 0:
                    patterns = data.get("patterns") or {}
                    item = patterns.get(kind)
                    if not isinstance(item, dict):
                        item = {"count": 0, "total_minutes": 0.0, "avg_minutes": 0.0}
                    try:
                        count = int(item.get("count") or 0) + 1
                    except Exception:
                        count = 1
                    try:
                        total = float(item.get("total_minutes") or 0.0) + minutes
                    except Exception:
                        total = minutes
                    item["count"] = count
                    item["total_minutes"] = round(total, 2)
                    item["avg_minutes"] = round(total / count, 1) if count else 0.0
                    patterns[kind] = item
                    data["patterns"] = patterns
            # 本次缺席已结束
            data["awaiting"] = None

        detected = _detect_absence(text)
        if detected:
            kind, expected_minutes = detected
            data["awaiting"] = {
                "kind": kind,
                "at": _iso(now),
                "expected_return_at": _iso(now + timedelta(minutes=expected_minutes)),
            }
        data["last_user_at"] = _iso(now)
        _save_json(_HABITS_FILE, data)


def suppression_until():
    """若主人正处于「说好要离开」的窗口内，返回预计回来时间字符串，否则 None。"""
    data = _load_habits()
    awaiting = data.get("awaiting")
    if not isinstance(awaiting, dict):
        return None
    expected = awaiting.get("expected_return_at")
    expected_dt = _parse_dt(expected)
    if expected_dt is None:
        return None
    if _now() < expected_dt + timedelta(minutes=10):
        return str(expected)
    return None


def habit_is_active() -> bool:
    """是否应暂停主动打扰（等价于 suppression_until() 非空）。"""
    return suppression_until() is not None


def _render_habit_lines(data) -> list:
    lines = []
    awaiting = data.get("awaiting")
    if isinstance(awaiting, dict):
        kind = str(awaiting.get("kind") or "外出")
        expected_dt = _parse_dt(awaiting.get("expected_return_at"))
        when = expected_dt.strftime("%H:%M") if expected_dt else "稍后"
        lines.append(
            f"主人说过他要{kind}，预计 {when} 回来，在此之前不要主动打扰。")
    patterns = data.get("patterns") or {}
    for kind, item in patterns.items():
        if not isinstance(item, dict):
            continue
        try:
            count = int(item.get("count") or 0)
        except Exception:
            count = 0
        if count <= 0:
            continue
        try:
            avg = float(item.get("avg_minutes") or 0.0)
        except Exception:
            avg = 0.0
        lines.append(f"历史上主人{kind}后平均 {int(round(avg))} 分钟回来（已观察 {count} 次）。")
    return lines


# ---------------------------------------------------------------------------
# 情绪词库
# ---------------------------------------------------------------------------
def _emotion_default():
    return {
        "categories": copy.deepcopy(EMOTION_SEED),
        "learned": [],
        "last_learned_at": None,
    }


def _load_emotion():
    data = _load_json(_EMOTION_FILE, _emotion_default())
    if not isinstance(data.get("categories"), list) or not data["categories"]:
        data["categories"] = copy.deepcopy(EMOTION_SEED)
    if not isinstance(data.get("learned"), list):
        data["learned"] = []
    data.setdefault("last_learned_at", None)
    return data


def emotion_hint(limit=8) -> str:
    """返回最多 limit 条紧凑情绪示例（优先最近自学的，再取种子词库）。"""
    try:
        limit = max(1, int(limit))
    except Exception:
        limit = 8
    data = _load_emotion()
    items = []
    learned = data.get("learned") or []
    for entry in learned[-limit:]:
        if not isinstance(entry, dict):
            continue
        emotion = str(entry.get("emotion") or "").strip()
        text = str(entry.get("text") or "").strip()
        if emotion and text:
            items.append(f"{emotion}：{text}")
    if len(items) < limit:
        existing = {it.split("：", 1)[0] for it in items}
        for cat in data.get("categories") or []:
            if not isinstance(cat, dict):
                continue
            emotion = str(cat.get("emotion") or "").strip()
            exprs = cat.get("expressions") or []
            if not emotion or not exprs or emotion in existing:
                continue
            items.append(f"{emotion}：{str(exprs[0]).strip()}")
            existing.add(emotion)
            if len(items) >= limit:
                break
    return "；".join(items[:limit])


def learn_emotion(text, emotion, note=""):
    """把一条「文字→情绪」映射写入 learned 列表；去重、上限 500 条。"""
    text = "" if text is None else str(text).strip()
    emotion = "" if emotion is None else str(emotion).strip()
    note = "" if note is None else str(note).strip()
    if not text or not emotion:
        return False
    with _LOCK:
        data = _load_emotion()
        learned = data.get("learned") or []
        for entry in learned:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("emotion") or "").strip() == emotion and \
                    str(entry.get("text") or "").strip() == text:
                return False
        learned.append({
            "emotion": emotion,
            "text": text,
            "note": note,
            "at": _iso(_now()),
        })
        if len(learned) > LEARNED_EMOTION_MAX:
            learned = learned[-LEARNED_EMOTION_MAX:]
        data["learned"] = learned
        _save_json(_EMOTION_FILE, data)
    return True


def list_emotions():
    """返回完整情绪词库（种子类目 + 自学条目）。"""
    data = _load_emotion()
    return {
        "categories": data.get("categories") or [],
        "learned": data.get("learned") or [],
    }


# ---------------------------------------------------------------------------
# 自我目标
# ---------------------------------------------------------------------------
def _goals_default():
    return {"goals": []}


def _load_goals():
    data = _load_json(_GOALS_FILE, _goals_default())
    if not isinstance(data.get("goals"), list):
        data["goals"] = []
    return data


def add_goal(text, source="self"):
    """新增一个自我目标；source 标注来源（self / skill / chat）。"""
    text = "" if text is None else str(text).strip()
    if not text:
        return None
    with _LOCK:
        data = _load_goals()
        goal = {
            "id": "g-" + uuid.uuid4().hex[:8],
            "text": text,
            "source": str(source or "self"),
            "created_at": _iso(_now()),
            "done": False,
            "closed_at": None,
        }
        data["goals"].append(goal)
        _save_json(_GOALS_FILE, data)
    return dict(goal)


def list_goals(include_done=False):
    """列出目标；默认只返回未完成项。"""
    data = _load_goals()
    goals = [g for g in data.get("goals") or [] if isinstance(g, dict)]
    if not include_done:
        goals = [g for g in goals if not g.get("done")]
    return goals


def close_goal(goal_id_or_text):
    """按 id 或文本关闭目标；返回是否成功。"""
    key = "" if goal_id_or_text is None else str(goal_id_or_text).strip()
    if not key:
        return False
    with _LOCK:
        data = _load_goals()
        for goal in data.get("goals") or []:
            if not isinstance(goal, dict):
                continue
            if goal.get("done"):
                continue
            if key == str(goal.get("id") or "") or key == str(goal.get("text") or "").strip():
                goal["done"] = True
                goal["closed_at"] = _iso(_now())
                _save_json(_GOALS_FILE, data)
                return True
        # 文本子串兜底：允许「关掉某个目标」用简短描述
        for goal in data.get("goals") or []:
            if isinstance(goal, dict) and not goal.get("done") and \
                    key in str(goal.get("text") or ""):
                goal["done"] = True
                goal["closed_at"] = _iso(_now())
                _save_json(_GOALS_FILE, data)
                return True
    return False


# ---------------------------------------------------------------------------
# 统一提示块
# ---------------------------------------------------------------------------
def _now_line(memory=None) -> str:
    now = _now()
    stamp = now.strftime("%Y-%m-%d %H:%M")
    weekday = _WEEKDAY_CN[now.weekday()]
    gap = _last_user_gap_minutes(memory)
    return f"现在 {stamp} {weekday}；距上次主人说话 {_humanize_minutes(gap)}"


def persona_block(situation: str = "chat", memory=None) -> str:
    """构造统一人格提示块（纯文本），总长度硬上限 1500 字。

    顺序：自我人格 → 此刻 → 主人习惯 → 情绪表达 → 自我目标 → 情境。
    """
    parts = []

    self_text = load_self_persona().strip()
    if not self_text:
        self_text = "Aize 会逐渐形成自己的性格：她有自己的想法、偏好和说话方式。"
    parts.append("【Aize 的自我人格】\n" + self_text)

    parts.append("【此刻】\n" + _now_line(memory))

    habit_lines = _render_habit_lines(_load_habits())
    if habit_lines:
        parts.append("【主人的习惯】\n" + "\n".join(habit_lines))

    hint = emotion_hint(8)
    emotion_line = "可以更开放地表达情绪，不必一直保持平静；情绪要自然、贴合当下一刻。"
    if hint:
        emotion_line += "\n示例：" + hint
    parts.append("【情绪表达】\n" + emotion_line)

    goals = list_goals()[:3]
    if goals:
        goal_lines = [f"{i + 1}. {str(g.get('text') or '').strip()}" for i, g in enumerate(goals)]
        parts.append("【自我目标】\n" + "\n".join(goal_lines))
    else:
        parts.append("【自我目标】\n还没有明确目标时，可以自己想一个（不必是主人安排的），"
                     "并用 self-model 技能的 goal_add 记下来。")

    guide = _SITUATION_GUIDE.get(str(situation or "chat").strip().lower(), _SITUATION_GUIDE["chat"])
    parts.append("【情境】\n" + guide)

    block = "\n\n".join(parts)
    if len(block) > BLOCK_MAX_CHARS:
        block = block[:BLOCK_MAX_CHARS]
    return block


def compose_prompt_with_persona(base_text, situation="chat", memory=None) -> str:
    """用户自定义提示词在前，Aize 人格块在后（两段之间空一行）。"""
    base = "" if base_text is None else str(base_text).strip()
    block = persona_block(situation, memory)
    if base:
        return base + "\n\n" + block
    return block


# ---------------------------------------------------------------------------
# 空闲自学：提示词构造 + 学习频率记录
# ---------------------------------------------------------------------------
def _memory_digest(memory, limit=20) -> str:
    lines = []
    for msg in _memory_messages(memory)[-limit:]:
        if not isinstance(msg, dict):
            continue
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if "RESPONSE:" in content:
            content = content.split("RESPONSE:", 1)[1].strip()
        content = re.sub(r"\[\s*motion\s*:[^\]]*\]", "", content, flags=re.I).strip()
        if not content:
            continue
        role = "主人" if msg.get("role") == "user" else "Aize"
        lines.append(f"{role}：{content[:100]}")
    return "\n".join(lines)


def build_persona_growth_prompt(memory, web_digest="") -> str:
    """让模型基于聊天记录 + 网上摘要，重写一份完整的自我人格全文。"""
    current = load_self_persona().strip() or "（目前还没有成形的人格，请从零开始写）"
    digest = _memory_digest(memory, 20) or "（最近没有对话记录）"
    habits = _render_habit_lines(_load_habits())
    habit_text = "\n".join(habits) if habits else "（还没有观察到的习惯）"
    goals = list_goals()[:5]
    goal_text = "\n".join(f"- {g.get('text')}" for g in goals) if goals else "（暂时没有明确目标）"
    web = str(web_digest or "").strip() or "（本次没有联网摘要）"

    return (
        "你在整理自己的自我人格。请根据下面的材料，写一份新的「自我人格全文」。\n\n"
        "【当前自我人格】\n" + current + "\n\n"
        "【与主人的近期对话】\n" + digest + "\n\n"
        "【主人的习惯】\n" + habit_text + "\n\n"
        "【当前自我目标】\n" + goal_text + "\n\n"
        "【网上信息摘要】\n" + web + "\n\n"
        "要求：\n"
        "1. 用第一人称写，像真实的人在描述自己：性格、偏好、说话方式、在意的事、与主人的关系。\n"
        "2. 保留仍然成立的内容，吸收新信息；可以提出新的自我目标。\n"
        "3. 全文不超过 6000 字，直接输出人格正文，不要输出标题以外的解释、不要输出 JSON 或代码块。\n"
    )


def build_emotion_study_prompt() -> str:
    """让模型自学「文字→情绪」映射，只输出 JSON 数组。"""
    return (
        "你在扩充自己的情绪词库，目标是更准确地理解人类语言里的情绪。\n\n"
        "请输出一个 JSON 数组，每个元素格式为：\n"
        '{"emotion": "情绪名（中文，例如 喜悦/悲伤/愤怒/焦虑/温柔/兴奋/失落/好奇/害羞/疲惫）",'
        ' "cues": ["能触发这种情绪的中文关键词或短语，2-4 个"],'
        ' "expressions": ["第一人称的情绪表达示例，1-2 条"]}\n\n'
        "要求：\n"
        "1. 只输出 JSON 数组本身，不要输出解释、标题或代码块。\n"
        "2. 可以补充新的情绪类别，也可以细化已有的。\n"
        "3. 内容健康、自然、贴近日常对话。\n"
    )


def last_learned_at(kind: str):
    """读取某类自学的上次时间（persona / emotion）。"""
    kind = str(kind or "").strip().lower()
    if kind == "emotion":
        return _load_emotion().get("last_learned_at")
    return _load_self().get("last_learned_at")


def mark_learned(kind: str):
    """记录某类自学完成时间，用于空闲引擎的频率限制。"""
    kind = str(kind or "").strip().lower()
    now_iso = _iso(_now())
    with _LOCK:
        if kind == "emotion":
            data = _load_emotion()
            data["last_learned_at"] = now_iso
            _save_json(_EMOTION_FILE, data)
        else:
            data = _load_self()
            data["last_learned_at"] = now_iso
            _save_json(_SELF_FILE, data)


def should_learn(kind: str, interval_seconds: float) -> bool:
    """距上次学习是否已超过 interval_seconds（从未学过时返回 True）。"""
    last = _parse_dt(last_learned_at(kind))
    if last is None:
        return True
    return (_now() - last).total_seconds() >= float(interval_seconds)
