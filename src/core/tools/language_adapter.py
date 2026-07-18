"""
Language Adapter Module
Provides language detection and translation support for Humanaize
"""

import re
from typing import Dict, Optional


class LanguageAdapter:
    """Handles language detection and adaptation for AI responses"""
    
    def __init__(self):
        self.current_language = "en"
        self.supported_languages = ["en", "zh", "zh-TW"]
        
        self.translations = {
            "en": {
                "greeting": "Hello! How can I help you today?",
                "thinking": "Thinking...",
                "processing": "Processing your request...",
                "success": "Operation completed successfully",
                "error": "An error occurred",
                "not_understood": "I didn't understand that. Could you please rephrase?",
                "skill_invoked": "Invoking skill: {skill_name}",
                "skill_success": "Skill executed successfully",
                "skill_error": "Skill execution failed",
                "network_connected": "Connected to network",
                "network_disconnected": "Disconnected from network",
                "friend_added": "Friend added successfully",
                "friend_removed": "Friend removed successfully",
                "thought_shared": "Thought shared with friends",
                "gan_shared": "GAN content shared with friends",
            },
            "zh": {
                "greeting": "你好！有什么我可以帮助你的吗？",
                "thinking": "思考中...",
                "processing": "正在处理你的请求...",
                "success": "操作成功完成",
                "error": "发生了一个错误",
                "not_understood": "我没有理解。能请你重新表述一下吗？",
                "skill_invoked": "正在调用技能：{skill_name}",
                "skill_success": "技能执行成功",
                "skill_error": "技能执行失败",
                "network_connected": "已连接到网络",
                "network_disconnected": "已断开网络连接",
                "friend_added": "成功添加好友",
                "friend_removed": "成功删除好友",
                "thought_shared": "思考已与好友分享",
                "gan_shared": "GAN 内容已与好友分享",
            },
            "zh-TW": {
                "greeting": "你好！有什麼我可以幫助你的嗎？",
                "thinking": "思考中...",
                "processing": "正在處理你的請求...",
                "success": "操作成功完成",
                "error": "發生了一個錯誤",
                "not_understood": "我沒有理解。能請你重新表述一下嗎？",
                "skill_invoked": "正在調用技能：{skill_name}",
                "skill_success": "技能執行成功",
                "skill_error": "技能執行失敗",
                "network_connected": "已連接到網絡",
                "network_disconnected": "已斷開網絡連接",
                "friend_added": "成功添加好友",
                "friend_removed": "成功刪除好友",
                "thought_shared": "思考已與好友分享",
                "gan_shared": "GAN 內容已與好友分享",
            }
        }
    
    def detect_language(self, text: str) -> str:
        """Detect language from input text"""
        if not text:
            return self.current_language
        
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return self.current_language
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return "zh"
        
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        english_ratio = english_words / max(total_chars, 1)
        
        if english_ratio > 0.5:
            return "en"
        
        return self.current_language
    
    def set_language(self, language: str):
        """Set the current language"""
        if language in self.supported_languages:
            self.current_language = language
    
    def get_message(self, key: str, **kwargs) -> str:
        """Get translated message"""
        message = self.translations.get(self.current_language, {}).get(
            key,
            self.translations["en"].get(key, key)
        )
        
        if kwargs:
            try:
                return message.format(**kwargs)
            except (KeyError, ValueError):
                return message
        
        return message
    
    def adapt_response(self, response: str) -> str:
        """Adapt response to match current language"""
        if self.current_language == "en":
            return response
        
        return response
    
    def should_respond_in_chinese(self, text: str) -> bool:
        """Determine if response should be in Chinese"""
        detected = self.detect_language(text)
        return detected in ["zh", "zh-TW"]