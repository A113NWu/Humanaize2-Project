"""
Live2D 動作策略：把「當下情緒」翻譯成「該不該動、動哪個、動多大」。

之前閒置動作與每次回覆的兜底動作都是純隨機（Idle 0~8 亂抽），
會出現講悲傷的事卻在點頭傻笑的情況。這裡集中定義一份映射規則，
閒置循環、回覆兜底、網頁手勢三處共用，動作不再無憑據。

Hiyori 模型實際可用動作：Idle = 0~8（m01/m02/m03/m05~m10），TapBody = 0（m04）。
模型沒有 Expressions，情緒只能透過動作幅度與是否使用 TapBody 表達。

回覆時的動作要比閒置大：非負向情緒在強度夠時優先給 TapBody 大動作，
其餘也用較高的 energy 讓點頭/歪頭更明顯；閒置仍維持小幅微動。
"""

import random

# 每種情緒的表現檔位
# energy：手勢幅度（0~1）；tap_from：達到此強度就改用 TapBody 大動作，None 表示不用
_PROFILES = {
    # 正向、有精神：動作大、常用 TapBody
    "happy":     {"energy": 1.00, "tap_from": 0.15, "idle": [2, 4, 7]},
    "excited":   {"energy": 1.00, "tap_from": 0.10, "idle": [4, 7, 2]},
    "loving":    {"energy": 0.90, "tap_from": 0.30, "idle": [2, 7]},
    "confident": {"energy": 0.85, "tap_from": 0.30, "idle": [2, 4]},
    # 負向、低落：不要點頭、不要大動作，只留細微姿態
    "sad":       {"energy": 0.15, "tap_from": None, "idle": [1, 5]},
    "angry":     {"energy": 0.30, "tap_from": None, "idle": [5, 1]},
    "fearful":   {"energy": 0.12, "tap_from": None, "idle": [1]},
    "anxious":   {"energy": 0.18, "tap_from": None, "idle": [1, 5]},
    "disgusted": {"energy": 0.22, "tap_from": None, "idle": [5]},
    # 中性/思考類：中等幅度，情緒夠強才給大動作
    "neutral":   {"energy": 0.55, "tap_from": 0.65, "idle": [0, 3, 6]},
    "bored":     {"energy": 0.30, "tap_from": None, "idle": [6, 0]},
    "curious":   {"energy": 0.70, "tap_from": 0.45, "idle": [3, 0]},
    "confused":  {"energy": 0.45, "tap_from": None, "idle": [6, 3]},
    "surprised": {"energy": 0.80, "tap_from": 0.35, "idle": [3, 2]},
}

_NEGATIVE = {"sad", "angry", "fearful", "anxious", "disgusted"}


def _profile(emotion_type):
    return _PROFILES.get(str(emotion_type or "neutral").lower(), _PROFILES["neutral"])


def current_mood():
    """返回 (情緒類型, 強度, 顯示名)；任何異常都退回 neutral。"""
    try:
        try:
            from tools.emotion_engine import emotion_engine
        except ImportError:
            from core.tools.emotion_engine import emotion_engine
        data = emotion_engine.get_dominant() or {}
        return (
            data.get("emotion_type", "neutral"),
            float(data.get("intensity", 0.3) or 0.3),
            data.get("display_name", "平静"),
        )
    except Exception:
        return ("neutral", 0.3, "平静")


def is_negative_emotion(emotion_type):
    return str(emotion_type or "").lower() in _NEGATIVE


def pick_idle_motion(force=False):
    """閒置時的身體微動：只用 Idle 組、不做 TapBody，低落時乾脆不動。

    返回 Live2D 命令 dict，或 None 表示這次不動。
    """
    emotion_type, intensity, _ = current_mood()
    prof = _profile(emotion_type)
    # 情緒很低落：寧可只有呼吸和眨眼，也不要有「開心」的姿態
    if is_negative_emotion(emotion_type) and intensity >= 0.45 and not force:
        return None
    pool = prof["idle"] or _PROFILES["neutral"]["idle"]
    return {
        "type": "motion",
        "group": "Idle",
        "index": random.choice(pool),
        # 閒置動作幅度要小，網頁據 micro 收掉額外手勢
        "energy": round(min(0.35, prof["energy"] * 0.4), 2),
        "micro": True,
    }


def pick_reply_motion():
    """回覆開頭的兜底動作（模型漏寫 [motion:] 時用）。

    與舊版 created % 9 的隨機不同：依主導情緒決定是否動、動哪組。
    負向情緒直接返回 None，避免「講難過的事還在點頭笑」。
    非負向情緒只要強度達到 tap_from 就給 TapBody 大動作，其餘動作也放大 energy。
    """
    emotion_type, intensity, _ = current_mood()
    prof = _profile(emotion_type)
    if is_negative_emotion(emotion_type):
        if intensity >= 0.35:      # 情緒明顯低落，不動比亂動好
            return None
        idx = random.choice(prof["idle"] or [1])
        return {"type": "motion", "group": "Idle", "index": idx, "energy": 0.25, "micro": True}
    tap_from = prof["tap_from"]
    if tap_from is not None and intensity >= tap_from:
        return {"type": "motion", "group": "TapBody", "index": 0,
                "energy": round(prof["energy"], 2)}
    return {"type": "motion", "group": "Idle",
            "index": random.choice(prof["idle"] or [0]),
            "energy": round(prof["energy"], 2)}
