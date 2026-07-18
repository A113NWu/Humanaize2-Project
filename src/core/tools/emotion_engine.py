#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
情感引擎模块
参考 ZerolanLiveRobot 的情感系统设计
实现多维度情感状态机、情绪强度和时间衰减机制
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .color_logger import color_logger
except ImportError:
    from tools import SimpleLogger
    color_logger = SimpleLogger("emotion_engine.log")


class EmotionType:
    """情绪类型枚举"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"
    LOVING = "loving"
    CONFIDENT = "confident"
    CONFUSED = "confused"
    EXCITED = "excited"
    ANXIOUS = "anxious"
    BORED = "bored"
    CURIOUS = "curious"


class Emotion:
    """情绪类"""
    
    def __init__(self, emotion_type: str, intensity: float = 0.5, source: str = ""):
        self.emotion_type = emotion_type
        self.intensity = max(0.0, min(1.0, intensity))
        self.source = source
        self.created_at = time.time()
        self.updated_at = time.time()
    
    def decay(self, decay_rate: float = 0.05):
        """情绪衰减"""
        self.intensity = max(0.0, self.intensity - decay_rate)
        self.updated_at = time.time()
    
    def amplify(self, amount: float):
        """增强情绪"""
        self.intensity = min(1.0, self.intensity + amount)
        self.updated_at = time.time()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "emotion_type": self.emotion_type,
            "intensity": self.intensity,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class EmotionEngine:
    """情感引擎核心类"""
    
    def __init__(self):
        self.logger = color_logger
        
        self.emotions: Dict[str, Emotion] = {}
        
        self.decay_rates = {
            EmotionType.NEUTRAL: 0.02,
            EmotionType.HAPPY: 0.08,
            EmotionType.SAD: 0.06,
            EmotionType.ANGRY: 0.1,
            EmotionType.FEARFUL: 0.12,
            EmotionType.SURPRISED: 0.15,
            EmotionType.DISGUSTED: 0.08,
            EmotionType.LOVING: 0.05,
            EmotionType.CONFIDENT: 0.04,
            EmotionType.CONFUSED: 0.06,
            EmotionType.EXCITED: 0.1,
            EmotionType.ANXIOUS: 0.07,
            EmotionType.BORED: 0.03,
            EmotionType.CURIOUS: 0.09
        }
        
        self.emotion_display_names = {
            EmotionType.NEUTRAL: "平静",
            EmotionType.HAPPY: "开心",
            EmotionType.SAD: "悲伤",
            EmotionType.ANGRY: "生气",
            EmotionType.FEARFUL: "害怕",
            EmotionType.SURPRISED: "惊讶",
            EmotionType.DISGUSTED: "厌恶",
            EmotionType.LOVING: "关爱",
            EmotionType.CONFIDENT: "自信",
            EmotionType.CONFUSED: "困惑",
            EmotionType.EXCITED: "兴奋",
            EmotionType.ANXIOUS: "焦虑",
            EmotionType.BORED: "无聊",
            EmotionType.CURIOUS: "好奇"
        }
        
        self._start_decay_loop()
    
    def _start_decay_loop(self):
        """启动情绪衰减循环"""
        import threading
        
        def decay_loop():
            while True:
                self.update_emotions()
                time.sleep(2)
        
        thread = threading.Thread(target=decay_loop, daemon=True)
        thread.start()
    
    def set_emotion(self, emotion_type: str, intensity: float = 0.5, source: str = ""):
        """设置情绪"""
        if emotion_type not in self.emotion_display_names:
            self.logger.warn(f"Unknown emotion type: {emotion_type}")
            return
        
        if emotion_type in self.emotions:
            self.emotions[emotion_type].intensity = max(0.0, min(1.0, intensity))
            self.emotions[emotion_type].source = source
            self.emotions[emotion_type].updated_at = time.time()
        else:
            self.emotions[emotion_type] = Emotion(emotion_type, intensity, source)
        
        self.logger.info(f"Emotion set: {emotion_type} ({intensity:.2f}) from {source}")
    
    def add_emotion(self, emotion_type: str, intensity: float = 0.3, source: str = ""):
        """添加情绪（叠加）"""
        if emotion_type not in self.emotion_display_names:
            self.logger.warn(f"Unknown emotion type: {emotion_type}")
            return
        
        if emotion_type in self.emotions:
            self.emotions[emotion_type].amplify(intensity)
            if source:
                self.emotions[emotion_type].source = source
        else:
            self.emotions[emotion_type] = Emotion(emotion_type, intensity, source)
        
        self.logger.info(f"Emotion added: {emotion_type} (+{intensity:.2f})")
    
    def update_emotions(self):
        """更新所有情绪（衰减）"""
        to_remove = []
        for emotion_type, emotion in self.emotions.items():
            decay_rate = self.decay_rates.get(emotion_type, 0.05)
            emotion.decay(decay_rate)
            
            if emotion.intensity <= 0.01:
                to_remove.append(emotion_type)
        
        for emotion_type in to_remove:
            del self.emotions[emotion_type]
    
    def get_dominant_emotion(self) -> Optional[Emotion]:
        """获取主导情绪"""
        if not self.emotions:
            return None
        
        dominant = max(self.emotions.values(), key=lambda e: e.intensity)
        
        if dominant.intensity < 0.1:
            return Emotion(EmotionType.NEUTRAL, 1.0)
        
        return dominant
    
    def get_emotion_state(self) -> Dict:
        """获取完整情绪状态"""
        dominant = self.get_dominant_emotion()
        
        return {
            "dominant_emotion": dominant.emotion_type if dominant else EmotionType.NEUTRAL,
            "dominant_intensity": dominant.intensity if dominant else 1.0,
            "dominant_display": self.emotion_display_names.get(
                dominant.emotion_type if dominant else EmotionType.NEUTRAL, "平静"
            ),
            "active_emotions": {
                et: e.to_dict() for et, e in self.emotions.items() if e.intensity > 0.05
            },
            "emotion_summary": self._generate_emotion_summary()
        }
    
    def _generate_emotion_summary(self) -> str:
        """生成情绪摘要"""
        dominant = self.get_dominant_emotion()
        if not dominant or dominant.emotion_type == EmotionType.NEUTRAL:
            return "情绪平静"
        
        intensity_level = self._get_intensity_level(dominant.intensity)
        return f"{self.emotion_display_names[dominant.emotion_type]}{intensity_level}"
    
    def _get_intensity_level(self, intensity: float) -> str:
        """获取强度级别"""
        if intensity >= 0.8:
            return "（强烈）"
        elif intensity >= 0.6:
            return "（明显）"
        elif intensity >= 0.4:
            return "（适中）"
        elif intensity >= 0.2:
            return "（轻微）"
        else:
            return ""
    
    def reset_emotions(self):
        """重置所有情绪"""
        self.emotions = {}
        self.logger.info("Emotions reset")
    
    def get_emotion_cue(self) -> str:
        """获取情绪提示词（用于prompt）"""
        state = self.get_emotion_state()
        
        if state["dominant_emotion"] == EmotionType.NEUTRAL:
            return "保持自然、平静的语气"
        
        cues = {
            EmotionType.HAPPY: "表现出开心和热情，使用积极向上的语气",
            EmotionType.SAD: "表现出关心和安慰，使用温和的语气",
            EmotionType.ANGRY: "保持冷静和专业，避免激化矛盾",
            EmotionType.FEARFUL: "表现出理解和支持，给予安全感",
            EmotionType.SURPRISED: "表达惊讶但保持镇定",
            EmotionType.DISGUSTED: "保持礼貌，适当表达理解",
            EmotionType.LOVING: "表现出温暖和关怀",
            EmotionType.CONFIDENT: "表现出自信和专业",
            EmotionType.CONFUSED: "耐心解释，提供清晰的指导",
            EmotionType.EXCITED: "分享用户的兴奋，表现出热情",
            EmotionType.ANXIOUS: "表现出理解和支持，给予信心",
            EmotionType.BORED: "尝试引入新话题，保持对话趣味性",
            EmotionType.CURIOUS: "满足用户的好奇心，提供详细信息"
        }
        
        return cues.get(state["dominant_emotion"], "保持自然的语气")


class EmotionEngineAPI:
    """情感引擎API"""
    
    def __init__(self):
        self.engine = EmotionEngine()
    
    def set_emotion(self, emotion_type: str, intensity: float = 0.5, source: str = "") -> Dict:
        """设置情绪"""
        self.engine.set_emotion(emotion_type, intensity, source)
        return {"status": "success", "data": self.engine.get_emotion_state()}
    
    def add_emotion(self, emotion_type: str, intensity: float = 0.3, source: str = "") -> Dict:
        """添加情绪"""
        self.engine.add_emotion(emotion_type, intensity, source)
        return {"status": "success", "data": self.engine.get_emotion_state()}
    
    def get_state(self) -> Dict:
        """获取情绪状态"""
        return {"status": "success", "data": self.engine.get_emotion_state()}
    
    def get_dominant(self) -> Dict:
        """获取主导情绪"""
        emotion = self.engine.get_dominant_emotion()
        if emotion:
            return {
                "status": "success",
                "emotion_type": emotion.emotion_type,
                "intensity": emotion.intensity,
                "display_name": self.engine.emotion_display_names.get(emotion.emotion_type, emotion.emotion_type)
            }
        return {"status": "success", "emotion_type": EmotionType.NEUTRAL, "intensity": 1.0, "display_name": "平静"}
    
    def reset(self) -> Dict:
        """重置情绪"""
        self.engine.reset_emotions()
        return {"status": "success", "message": "Emotions reset"}


emotion_engine = EmotionEngineAPI()