"""
Language Adapter Module
Handles language detection and response adaptation for multi-language support
"""

import re
from typing import Dict, List, Optional


class LanguageAdapter:
    """Handles language detection and adaptation for AI responses"""
    
    def __init__(self):
        self.current_language = "en"
        self.supported_languages = ["en", "zh", "zh-TW"]
        self._chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        
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
                "searching": "Searching the web...",
                "reading_file": "Reading file...",
                "writing_file": "Writing file...",
                "executing_command": "Executing command...",
                "memory_recalled": "Memory recalled successfully",
                "reminder_set": "Reminder has been set",
                "skill_not_found": "Skill '{skill_name}' not found",
                "skill_disabled": "Skill '{skill_name}' is disabled",
                "invalid_input": "Invalid input provided",
                "connection_established": "Connection established",
                "connection_failed": "Connection failed",
                "data_saved": "Data saved successfully",
                "data_loaded": "Data loaded successfully",
                "operation_cancelled": "Operation cancelled",
                "waiting_for_input": "Waiting for your input...",
                "analyzing": "Analyzing...",
                "completed": "Completed",
                "in_progress": "In progress",
                "pending": "Pending",
                "failed": "Failed",
                "retrying": "Retrying...",
                "timeout": "Operation timed out",
                "permission_denied": "Permission denied",
                "file_not_found": "File not found",
                "directory_not_found": "Directory not found",
                "invalid_path": "Invalid path provided",
                "disk_full": "Disk space full",
                "network_error": "Network error occurred",
                "unknown_error": "An unknown error occurred",
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
                "searching": "正在搜索网络...",
                "reading_file": "正在读取文件...",
                "writing_file": "正在写入文件...",
                "executing_command": "正在执行命令...",
                "memory_recalled": "记忆召回成功",
                "reminder_set": "提醒已设置",
                "skill_not_found": "未找到技能 '{skill_name}'",
                "skill_disabled": "技能 '{skill_name}' 已禁用",
                "invalid_input": "提供了无效的输入",
                "connection_established": "连接已建立",
                "connection_failed": "连接失败",
                "data_saved": "数据保存成功",
                "data_loaded": "数据加载成功",
                "operation_cancelled": "操作已取消",
                "waiting_for_input": "等待你的输入...",
                "analyzing": "分析中...",
                "completed": "已完成",
                "in_progress": "进行中",
                "pending": "待处理",
                "failed": "失败",
                "retrying": "重试中...",
                "timeout": "操作超时",
                "permission_denied": "权限被拒绝",
                "file_not_found": "文件未找到",
                "directory_not_found": "目录未找到",
                "invalid_path": "提供了无效的路径",
                "disk_full": "磁盘空间已满",
                "network_error": "发生网络错误",
                "unknown_error": "发生未知错误",
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
                "searching": "正在搜索網絡...",
                "reading_file": "正在讀取文件...",
                "writing_file": "正在寫入文件...",
                "executing_command": "正在執行命令...",
                "memory_recalled": "記憶召回成功",
                "reminder_set": "提醒已設置",
                "skill_not_found": "未找到技能 '{skill_name}'",
                "skill_disabled": "技能 '{skill_name}' 已停用",
                "invalid_input": "提供了無效的輸入",
                "connection_established": "連接已建立",
                "connection_failed": "連接失敗",
                "data_saved": "數據保存成功",
                "data_loaded": "數據加載成功",
                "operation_cancelled": "操作已取消",
                "waiting_for_input": "等待你的輸入...",
                "analyzing": "分析中...",
                "completed": "已完成",
                "in_progress": "進行中",
                "pending": "待處理",
                "failed": "失敗",
                "retrying": "重試中...",
                "timeout": "操作超時",
                "permission_denied": "權限被拒絕",
                "file_not_found": "文件未找到",
                "directory_not_found": "目錄未找到",
                "invalid_path": "提供了無效的路徑",
                "disk_full": "磁盤空間已滿",
                "network_error": "發生網絡錯誤",
                "unknown_error": "發生未知錯誤",
            }
        }
    
    def detect_language(self, text: str) -> str:
        """Detect language from input text"""
        if not text:
            return self.current_language
        
        chinese_chars = len(self._chinese_pattern.findall(text))
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
    
    def translate_error(self, error_key: str, **kwargs) -> str:
        """Translate an error message"""
        return self.get_message(error_key, **kwargs)
    
    def adapt_response(self, response: str) -> str:
        """Adapt response to match current language"""
        if self.current_language == "en":
            return response
        
        return response
    
    def should_respond_in_chinese(self, text: str) -> bool:
        """Determine if response should be in Chinese"""
        detected = self.detect_language(text)
        return detected in ["zh", "zh-TW"]
    
    def format_success_message(self, operation: str, details: str = "") -> str:
        """Format a success message in the current language"""
        msg = self.get_message("success")
        if details:
            return f"{msg} - {details}"
        return msg
    
    def format_error_message(self, error_type: str, **kwargs) -> str:
        """Format an error message in the current language"""
        return self.get_message(error_type, **kwargs)
    
    def format_status_message(self, status: str) -> str:
        """Format a status message in the current language"""
        status_map = {
            "completed": "completed",
            "in_progress": "in_progress",
            "pending": "pending",
            "failed": "failed"
        }
        
        msg_key = status_map.get(status, "unknown_error")
        return self.get_message(msg_key)
    
    def get_all_translations(self, language: str = None) -> Dict:
        """Get all translations for a language"""
        lang = language or self.current_language
        return self.translations.get(lang, self.translations["en"])
    
    def add_translation(self, language: str, key: str, value: str):
        """Add a new translation"""
        if language not in self.translations:
            self.translations[language] = {}
        self.translations[language][key] = value
    
    def remove_translation(self, language: str, key: str):
        """Remove a translation"""
        if language in self.translations and key in self.translations[language]:
            del self.translations[language][key]


class MultiLanguageProcessor:
    """Processes text in multiple languages"""
    
    def __init__(self):
        self.adapter = LanguageAdapter()
        self._mixed_pattern = re.compile(r'[\u4e00-\u9fff]|[a-zA-Z]+')
    
    def split_mixed_text(self, text: str) -> List[Dict]:
        """Split mixed language text into segments"""
        segments = []
        
        chinese_chars = self._mixed_pattern.findall(text)
        
        current_lang = None
        current_text = []
        
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                lang = "zh"
            elif char.isalpha():
                lang = "en"
            else:
                current_text.append(char)
                continue
            
            if lang != current_lang and current_text:
                segments.append({
                    "language": current_lang or "en",
                    "text": "".join(current_text)
                })
                current_text = []
            
            current_lang = lang
            current_text.append(char)
        
        if current_text:
            segments.append({
                "language": current_lang or "en",
                "text": "".join(current_text)
            })
        
        return segments
    
    def count_languages(self, text: str) -> Dict[str, int]:
        """Count occurrences of each language in text"""
        counts = {"en": 0, "zh": 0, "other": 0}
        
        chinese_chars = len(self._mixed_pattern.findall(text))
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return counts
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            counts["zh"] = chinese_chars
            counts["en"] = total_chars - chinese_chars
        else:
            counts["en"] = total_chars
        
        return counts
    
    def is_mixed_language(self, text: str) -> bool:
        """Check if text contains mixed languages"""
        counts = self.count_languages(text)
        return counts["en"] > 10 and counts["zh"] > 10