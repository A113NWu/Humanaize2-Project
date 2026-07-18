#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
情感分析器模块
参考 ZerolanLiveRobot 的情感分析管线设计
实现用户输入的情感识别和分类
"""

import os
import sys
import re
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .color_logger import color_logger
except ImportError:
    from tools import SimpleLogger
    color_logger = SimpleLogger("sentiment_analyzer.log")


class SentimentAnalyzer:
    """情感分析器"""
    
    def __init__(self):
        self.logger = color_logger
        
        self.emotion_keywords = {
            "happy": ["开心", "高兴", "快乐", "喜悦", "兴奋", "幸福", "满足", "愉快", "太棒", "太好了", "点赞", "喜欢", "爱"],
            "sad": ["难过", "伤心", "悲伤", "失望", "失落", "沮丧", "郁闷", "痛苦", "难受", "发愁", "烦恼"],
            "angry": ["生气", "愤怒", "恼火", "火大", "气死", "讨厌", "怒", "不满"],
            "fearful": ["害怕", "恐惧", "担心", "焦虑", "不安", "紧张", "恐慌"],
            "surprised": ["惊讶", "震惊", "没想到", "居然", "哇"],
            "disgusted": ["恶心", "讨厌", "反感", "嫌弃", "鄙视"],
            "loving": ["爱", "喜欢", "想你", "思念", "关心", "照顾", "温暖"],
            "confident": ["自信", "相信", "肯定", "确定", "没问题", "放心"],
            "confused": ["困惑", "迷茫", "不懂", "不明白", "奇怪", "疑惑"],
            "excited": ["兴奋", "激动", "期待", "迫不及待", "开心"],
            "anxious": ["焦虑", "着急", "担心", "忧虑", "不安"],
            "bored": ["无聊", "没意思", "枯燥", "乏味"],
            "curious": ["好奇", "想知道", "想问"]
        }
        
        self.intensity_modifiers = {
            "very": ["非常", "特别", "十分", "极其", "超级", "太"],
            "moderate": ["有点", "稍微", "略微", "一点点"],
            "less": ["不太", "不怎么", "稍微有点"]
        }
        
        self.emotion_patterns = {
            "happy": [r"(?:好|棒|赞|喜欢|爱)\s*(?:了|啊|呢|！)"],
            "sad": [r"(?:难过|伤心|失望)\s*(?:了|啊|呢)", r"😭|😢|😔"],
            "angry": [r"(?:气死|恼火|烦)\s*(?:了|啊)", r"😡|😤"],
            "excited": [r"(?:兴奋|激动)\s*(?:了|啊|！)", r"🎉|🎊"],
            "surprised": [r"(?:没想到|居然|哇)\s*(?:！|啊)", r"😲|😮"]
        }
    
    def analyze(self, text: str) -> Dict:
        """分析文本情感"""
        if not text:
            return self._neutral_result()
        
        text_lower = text.lower()
        
        emotion_scores = {}
        for emotion, keywords in self.emotion_keywords.items():
            score = 0.0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 0.3
            
            for pattern in self.emotion_patterns.get(emotion, []):
                if re.search(pattern, text):
                    score += 0.3
            
            if score > 0:
                score = min(1.0, score)
                emotion_scores[emotion] = score
        
        if not emotion_scores:
            return self._neutral_result()
        
        max_emotion = max(emotion_scores, key=emotion_scores.get)
        max_score = emotion_scores[max_emotion]
        
        score_adjustment = self._adjust_by_modifiers(text_lower, max_emotion)
        max_score = min(1.0, max(0.2, max_score + score_adjustment))
        
        dominant_emotion = self._map_to_emotion_type(max_emotion)
        
        sentiment_polarity = self._determine_polarity(dominant_emotion)
        
        return {
            "status": "success",
            "dominant_emotion": dominant_emotion,
            "intensity": max_score,
            "sentiment": sentiment_polarity,
            "all_emotions": emotion_scores,
            "matched_keywords": self._extract_keywords(text_lower),
            "analysis": self._generate_analysis(dominant_emotion, max_score, sentiment_polarity)
        }
    
    def _neutral_result(self) -> Dict:
        """返回中性结果"""
        return {
            "status": "success",
            "dominant_emotion": "neutral",
            "intensity": 0.5,
            "sentiment": "neutral",
            "all_emotions": {},
            "matched_keywords": [],
            "analysis": "用户情绪中性"
        }
    
    def _adjust_by_modifiers(self, text: str, emotion: str) -> float:
        """根据修饰词调整强度"""
        adjustment = 0.0
        
        for modifier in self.intensity_modifiers["very"]:
            if modifier in text:
                adjustment += 0.2
                break
        
        for modifier in self.intensity_modifiers["moderate"]:
            if modifier in text:
                adjustment -= 0.15
                break
        
        for modifier in self.intensity_modifiers["less"]:
            if modifier in text:
                adjustment -= 0.25
                break
        
        return adjustment
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取匹配的关键词"""
        keywords = []
        for emotion, emotion_keywords in self.emotion_keywords.items():
            for keyword in emotion_keywords:
                if keyword in text:
                    keywords.append(keyword)
        return keywords
    
    def _map_to_emotion_type(self, emotion_key: str) -> str:
        """映射到情绪类型"""
        emotion_map = {
            "happy": "happy",
            "sad": "sad",
            "angry": "angry",
            "fearful": "fearful",
            "surprised": "surprised",
            "disgusted": "disgusted",
            "loving": "loving",
            "confident": "confident",
            "confused": "confused",
            "excited": "excited",
            "anxious": "anxious",
            "bored": "bored",
            "curious": "curious"
        }
        return emotion_map.get(emotion_key, "neutral")
    
    def _determine_polarity(self, emotion: str) -> str:
        """确定情感极性"""
        positive_emotions = ["happy", "loving", "confident", "excited", "curious", "surprised"]
        negative_emotions = ["sad", "angry", "fearful", "disgusted", "confused", "anxious", "bored"]
        
        if emotion in positive_emotions:
            return "positive"
        elif emotion in negative_emotions:
            return "negative"
        else:
            return "neutral"
    
    def _generate_analysis(self, emotion: str, intensity: float, polarity: str) -> str:
        """生成分析文本"""
        intensity_desc = ""
        if intensity >= 0.8:
            intensity_desc = "非常"
        elif intensity >= 0.6:
            intensity_desc = "比较"
        elif intensity >= 0.4:
            intensity_desc = "略微"
        
        emotion_names = {
            "happy": "开心",
            "sad": "悲伤",
            "angry": "生气",
            "fearful": "害怕",
            "surprised": "惊讶",
            "disgusted": "厌恶",
            "loving": "关爱",
            "confident": "自信",
            "confused": "困惑",
            "excited": "兴奋",
            "anxious": "焦虑",
            "bored": "无聊",
            "curious": "好奇",
            "neutral": "中性"
        }
        
        return f"用户情绪{intensity_desc}{emotion_names.get(emotion, emotion)}（{polarity}）"


class SentimentAnalyzerAPI:
    """情感分析器API"""
    
    def __init__(self):
        self.analyzer = SentimentAnalyzer()
    
    def analyze(self, text: str) -> Dict:
        """分析文本情感"""
        return self.analyzer.analyze(text)
    
    def analyze_and_update(self, text: str) -> Dict:
        """分析并更新情感引擎"""
        result = self.analyzer.analyze(text)
        
        try:
            from .emotion_engine import emotion_engine
            
            emotion_engine.add_emotion(
                result["dominant_emotion"],
                result["intensity"],
                "user_input"
            )
        except ImportError:
            pass
        
        return result


sentiment_analyzer = SentimentAnalyzerAPI()