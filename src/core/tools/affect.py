#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aize 的情绪：既能感知主人此刻的情绪，也有自己持续的心情。

设计取舍（为什么不是「每 2 秒衰减的强度池」那种客服式状态机）：
- 感知用轻量词表 + 否定 / 加强语气判断，不额外调模型——每条消息都要跑，必须便宜；
  识别出的强情绪会回写 emotion_db，长期积累「什么话对应什么情绪」的映射。
- 她自己的心情是一条持续曲线：愉悦度 / 唤醒度 + 若干带半衰期的具体情绪，
  会跨重启保留，由「主人情绪的共情」和相处事件喂养，再慢慢回落到基线。
- 注入提示词时只给「此刻的感受 + 一点语气方向」，不让她复述情绪词，
  情绪是她的，不是旁白。

对外接口：
    observe_user_message(text) -> dict   收到主人消息时调用（会更新她的心情）
    render_affect_block()      -> str    取出要拼进 system prompt 的块
    note_event(kind, note)              记录她自己的经历（完成/失败/被夸/被晾着…）
"""

import json
import os
import threading
import time

_LABELS = {
    "joy": "开心", "sadness": "难过", "anger": "生气", "fear": "不安",
    "surprise": "惊讶", "love": "喜欢", "tired": "累", "calm": "平静",
    "shame": "自责", "gratitude": "感谢",
}

_LEXICON = {
    "joy": ("开心", "高兴", "快乐", "太好了", "好耶", "爽", "棒", "好笑", "笑死",
            "哈哈", "嘿嘿", "嘻嘻", "幸福", "兴奋", "激动", "美滋滋", "舒服", "赞", "牛"),
    "sadness": ("难过", "伤心", "想哭", "哭了", "失落", "沮丧", "委屈", "心酸",
                "没意思", "没劲", "郁闷", "低落", "破防", "绝望"),
    "anger": ("生气", "烦", "讨厌", "气死", "火大", "无语", "离谱", "过分",
              "妈的", "滚", "闭嘴", "别烦", "受不了"),
    "fear": ("害怕", "怕", "恐怖", "慌", "焦虑", "紧张", "担心", "害怕", "睡不着",
             "不安", "压力大"),
    "surprise": ("没想到", "居然", "竟然", "震惊", "惊讶", "哇", "竟然", "意外", "离谱"),
    "love": ("喜欢你", "想你", "爱你", "抱抱", "亲亲", "贴贴", "宝贝", "老婆",
             "亲爱的", "想你", "想你陪", "喜欢"),
    "tired": ("累", "困", "熬夜", "疲惫", "撑不住", "不想动", "没力气", "头昏", "好困"),
    "calm": ("没事", "还行", "随便", "都可以", "安静", "平静", "还好", "不错"),
    "shame": ("对不起", "抱歉", "尴尬", "丢人", "我的错", "我错了", "怪我"),
    "gratitude": ("谢谢", "感谢", "多亏", "麻烦你了", "辛苦你了", "辛苦了"),
}

_INTENSIFIERS = ("很", "太", "特别", "超级", "真的", "非常", "巨", "特别", "超")

# 情绪半衰期（秒）：越急的情绪退得越快
_HALF_LIFE = {
    "joy": 40 * 60, "love": 100 * 60, "sadness": 60 * 60, "anger": 25 * 60,
    "fear": 40 * 60, "surprise": 8 * 60, "tired": 45 * 60, "calm": 30 * 60,
    "shame": 40 * 60, "gratitude": 60 * 60,
}

# 情绪对「愉悦度 / 唤醒度」的贡献
_VALENCE_W = {
    "joy": 0.90, "love": 0.80, "gratitude": 0.70, "calm": 0.25, "surprise": 0.10,
    "sadness": -0.70, "anger": -0.75, "fear": -0.60, "tired": -0.35, "shame": -0.50,
}
_AROUSAL_W = {
    "joy": 0.30, "love": 0.20, "gratitude": 0.12, "calm": -0.15, "surprise": 0.35,
    "sadness": 0.0, "anger": 0.40, "fear": 0.30, "tired": -0.30, "shame": -0.05,
}
_BASE_VALENCE = 0.15
_BASE_AROUSAL = 0.35

# 共情映射：主人有情绪时，她心里被牵动成什么
_EMPATHY = {
    "joy": [("joy", 0.45), ("love", 0.15)],
    "sadness": [("love", 0.35), ("sadness", 0.20)],
    "anger": [("anger", 0.15), ("sadness", 0.20)],
    "fear": [("fear", 0.25), ("love", 0.30)],
    "surprise": [("surprise", 0.40), ("love", 0.10)],
    "love": [("love", 0.50), ("joy", 0.30)],
    "tired": [("love", 0.25), ("tired", 0.15)],
    "calm": [("calm", 0.30)],
    "shame": [("love", 0.30), ("sadness", 0.10)],
    "gratitude": [("joy", 0.40), ("love", 0.30)],
}

# 她自己的经历
_EVENT_BUMP = {
    "completed": [("joy", 0.20), ("calm", 0.10)],      # 事情做完了
    "failed": [("sadness", 0.15), ("tired", 0.10)],    # 搞砸了 / 出错
    "praised": [("joy", 0.30), ("love", 0.15)],        # 被夸
    "ignored": [("sadness", 0.12)],                    # 说话没人接
    "company": [("love", 0.12), ("calm", 0.08)],       # 有人陪着
}

_AT_ME_WORDS = ("你", "妳", "aize", "Aize", "宝贝", "老婆", "亲爱的", "在吗", "理我")
_MAX_NOTE_CHARS = 24


def _is_negated(text, index):
    window = text[max(0, index - 3):index]
    return any(w in window for w in ("不", "没", "未"))


def sense_user_emotion(text):
    """轻量判断主人这句话的情绪。识别不出来返回空 label。"""
    raw = str(text or "").strip()
    if len(raw) < 2:
        return {"label": "", "name": "", "intensity": 0.0, "at_me": False, "hits": [], "text": raw}

    scores = {}
    hits = {}
    for label, words in _LEXICON.items():
        matched = []
        for word in words:
            idx = raw.find(word)
            if idx < 0:
                continue
            if any(word in m or m in word for m in matched):
                continue  # 「喜欢」和「喜欢你」同时命中时不重复计分
            matched.append(word)
            negated = _is_negated(raw, idx)
            if negated:
                target = "sadness" if label in ("joy", "love") else "calm"
                if label in ("surprise", "calm", "shame", "gratitude"):
                    continue
            else:
                target = label
            weight = 0.52
            if any(w in raw[max(0, idx - 3):idx] for w in _INTENSIFIERS):
                weight += 0.12
            scores[target] = scores.get(target, 0.0) + weight
            hits.setdefault(target, []).append(word)

    if not scores:
        return {"label": "", "name": "", "intensity": 0.0, "at_me": False, "hits": [], "text": raw}

    if raw.count("!") + raw.count("！") >= 1:
        top_now = max(scores, key=scores.get)
        scores[top_now] += 0.08

    label = max(scores, key=scores.get)
    intensity = max(0.35, min(0.95, scores[label]))
    at_me = any(w in raw for w in _AT_ME_WORDS)
    return {
        "label": label,
        "name": _LABELS.get(label, label),
        "intensity": round(intensity, 2),
        "at_me": at_me,
        "hits": hits.get(label, [])[:3],
        "text": raw[:120],
    }


def _intensity_level(value):
    if value >= 0.8:
        return "很强"
    if value >= 0.6:
        return "明显"
    if value >= 0.4:
        return "有一点"
    return "轻微"


class AffectState:
    """Aize 持续的心情：愉悦/唤醒 + 带半衰期的具体情绪，落盘保存。"""

    def __init__(self, path=None):
        self._lock = threading.Lock()
        self.path = path or self._default_path()
        self._state = {
            "emotions": {},
            "last_sense": {},
            "notes": [],
            "updated_at": 0.0,
        }
        self._load()

    @staticmethod
    def _default_path():
        base = None
        for mod in ("app_paths", "core.app_paths"):
            try:
                module = __import__(mod, fromlist=["app_data_dir"])
                base = module.app_data_dir()
                break
            except Exception:
                continue
        if not base:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "affect_state.json")

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._state.update({k: data.get(k) for k in self._state if k in data})
        except Exception:
            pass

    def _save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def _live_emotions(self, now=None):
        """按半衰期衰减后的情绪快照（不改变存储值，读时计算）。"""
        now = now or time.time()
        live = {}
        for label, item in (self._state.get("emotions") or {}).items():
            try:
                base_value = float(item.get("intensity") or 0.0)
                updated = float(item.get("updated_at") or now)
            except Exception:
                continue
            half_life = _HALF_LIFE.get(label, 40 * 60)
            value = base_value * 0.5 ** (max(0.0, now - updated) / half_life)
            if value >= 0.04:
                live[label] = value
        return live

    def valence_arousal(self):
        live = self._live_emotions()
        valence = _BASE_VALENCE + sum(_VALENCE_W.get(k, 0) * v for k, v in live.items())
        arousal = _BASE_AROUSAL + sum(_AROUSAL_W.get(k, 0) * v for k, v in live.items())
        return max(-1.0, min(1.0, valence)), max(0.0, min(1.0, arousal))

    def _bump(self, label, amount):
        if label not in _LABELS or amount <= 0:
            return
        now = time.time()
        current = self._live_emotions(now).get(label, 0.0)
        self._state.setdefault("emotions", {})[label] = {
            "intensity": round(min(1.0, current + amount), 3),
            "updated_at": now,
        }

    def _remember_cause(self, label, note):
        """一次感知只留一条来由：同一句话牵动多个情绪时，只记最重的那条。"""
        if not label or not note:
            return
        note = note[:_MAX_NOTE_CHARS]
        now = time.time()
        kept = [
            n for n in (self._state.get("notes") or [])
            if n.get("note") != note and now - float(n.get("time") or 0) < 3600
        ]
        self._state["notes"] = ([{"note": note, "label": label, "time": now}] + kept)[:5]

    def appraise_user(self, sense):
        label = str(sense.get("label") or "")
        intensity = float(sense.get("intensity") or 0.0)
        if label not in _EMPATHY or intensity <= 0:
            return
        note = f"主人说「{str(sense.get('text') or '')[:_MAX_NOTE_CHARS]}」"
        strongest = ("", 0.0)
        own = ""
        for target, base in _EMPATHY[label]:
            amount = base * intensity
            if label == "anger" and sense.get("at_me") and target == "anger":
                amount += 0.10 * intensity  # 冲她来的会有被怼到的感觉
            self._bump(target, amount)
            if target == label:
                own = target
            if amount > strongest[1]:
                strongest = (target, amount)
        if strongest[1] >= 0.06:
            self._remember_cause(own or strongest[0], note)

    def note_event(self, kind, note=""):
        strongest = ("", 0.0)
        for label, base in _EVENT_BUMP.get(kind, []):
            self._bump(label, base)
            if base > strongest[1]:
                strongest = (label, base)
        if strongest[1] >= 0.06:
            self._remember_cause(strongest[0], note or kind)

    def observe(self, text):
        sense = sense_user_emotion(text)
        now = time.time()
        with self._lock:
            self.appraise_user(sense)
            if sense.get("label"):
                self._state["last_sense"] = dict(sense, time=now)
            self._state["updated_at"] = now
            self._save()
        if sense.get("label"):
            _learn_to_emotion_db(sense)
        return sense

    def recent_feeling(self):
        now = time.time()
        notes = [
            n for n in (self._state.get("notes") or [])
            if now - float(n.get("time") or 0) < 1800
        ]
        return notes[:2]

    def render(self):
        senses = self._state.get("last_sense") or {}
        lines = []
        if senses.get("label") and time.time() - float(senses.get("time") or 0) < 600 \
                and float(senses.get("intensity") or 0) >= 0.4:
            extra = "，这次是冲你来的" if senses.get("at_me") else ""
            lines.append(
                f"[主人此刻的情绪] {senses.get('name') or senses['label']}"
                f"（{_intensity_level(float(senses.get('intensity') or 0))}，"
                f"{float(senses.get('intensity') or 0):.2f}）{extra}"
            )

        live = self._live_emotions()
        top = sorted(live.items(), key=lambda kv: kv[1], reverse=True)[:3]
        valence, arousal = self.valence_arousal()
        if valence >= 0.5:
            valence_word = "心情很好"
        elif valence >= 0.2:
            valence_word = "心情不错"
        elif valence >= -0.15:
            valence_word = "还算平静"
        elif valence >= -0.45:
            valence_word = "有点闷"
        else:
            valence_word = "很低落"
        if arousal >= 0.65:
            arousal_word = "心里挺有劲"
        elif arousal >= 0.45:
            arousal_word = "精神一般"
        elif arousal >= 0.3:
            arousal_word = "有点提不起劲"
        else:
            arousal_word = "挺疲惫"

        if top:
            feelings = "、".join(_LABELS.get(k, k) for k, _ in top)
            strength = " / ".join(f"{_LABELS.get(k, k)} {v:.2f}" for k, v in top)
            lines.append(f"[你此刻的心情] {feelings}（{strength}）；{valence_word}，{arousal_word}")
        else:
            lines.append(f"[你此刻的心情] {valence_word}，{arousal_word}")

        notes = self.recent_feeling()
        if notes:
            lines.append("[心情的来由] " + "；".join(
                f"{n.get('note')} → {_LABELS.get(n.get('label'), n.get('label'))}（刚过去不久）"
                for n in notes
            ))
        lines.append("按这个心情接话，情绪是你自己的；不要念出情绪词，也不要用客服式安慰。")
        return "\n".join(lines)[:400]


_LAST_LEARN = {"at": 0.0}


def _learn_to_emotion_db(sense):
    """强情绪回写 emotion_db，长期形成「什么话对应什么情绪」的映射。"""
    label = sense.get("label")
    if not label or float(sense.get("intensity") or 0) < 0.62:
        return
    text = str(sense.get("text") or "").strip()
    if len(text) < 6:
        return
    now = time.time()
    if now - _LAST_LEARN["at"] < 120:
        return
    _LAST_LEARN["at"] = now
    try:
        from tools.emotion_db import get_emotion_db
        get_emotion_db().add(text, label, intensity=float(sense.get("intensity")), context="实时识别")
    except Exception:
        pass


_AFFECT = None
_AFFECT_LOCK = threading.Lock()


def get_affect():
    global _AFFECT
    with _AFFECT_LOCK:
        if _AFFECT is None:
            _AFFECT = AffectState()
        return _AFFECT


def observe_user_message(text):
    """收到主人消息：先感知情绪，再让她的心情跟着动一下。"""
    try:
        return get_affect().observe(text)
    except Exception:
        return {}


def render_affect_block():
    try:
        return get_affect().render()
    except Exception:
        return ""


def note_event(kind, note=""):
    try:
        get_affect().note_event(kind, note)
    except Exception:
        pass


def current_state():
    """给接口/前端查看用：当前心情快照。"""
    affect = get_affect()
    live = affect._live_emotions()
    valence, arousal = affect.valence_arousal()
    return {
        "valence": round(valence, 3),
        "arousal": round(arousal, 3),
        "emotions": {k: round(v, 3) for k, v in sorted(live.items(), key=lambda kv: -kv[1])},
        "dominant": (sorted(live.items(), key=lambda kv: -kv[1])[0][0] if live else "calm"),
        "last_user_sense": affect._state.get("last_sense") or {},
    }
