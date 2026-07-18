#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
彩色日志记录器模块
提供带颜色的控制台输出和AI操作通知功能
"""

import os
import sys
from datetime import datetime
from typing import Dict, Optional


class ColorCodes:
    """ANSI颜色代码"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'


class ColorLogger:
    """彩色日志记录器"""
    
    def __init__(self, log_file: str = "humanaize.log", use_color: bool = True):
        self.log_file = log_file
        
        try:
            self.use_color = use_color and hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        except Exception:
            self.use_color = False
        
        os.makedirs(os.path.dirname(log_file), exist_ok=True) if os.path.dirname(log_file) else None
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _colorize(self, text: str, color: str) -> str:
        """给文本添加颜色"""
        if self.use_color:
            return f"{color}{text}{ColorCodes.RESET}"
        return text
    
    def log(self, level: str, message: str, color: str = ColorCodes.WHITE):
        """记录日志"""
        timestamp = self._get_timestamp()
        
        level_colors = {
            "INFO": ColorCodes.BLUE,
            "WARN": ColorCodes.YELLOW,
            "ERROR": ColorCodes.RED,
            "SUCCESS": ColorCodes.GREEN,
            "AI": ColorCodes.MAGENTA,
            "ATTACK": ColorCodes.RED,
            "DEFENSE": ColorCodes.CYAN,
            "WARNING": ColorCodes.YELLOW
        }
        
        level_color = level_colors.get(level, ColorCodes.WHITE)
        colored_level = self._colorize(f"[{level}]", level_color)
        colored_message = self._colorize(message, color)
        
        log_msg = f"[{timestamp}] {colored_level} {colored_message}"
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                plain_msg = f"[{timestamp}] [{level}] {message}"
                f.write(plain_msg + "\n")
        except Exception:
            pass
        
        print(log_msg)
    
    def info(self, message: str):
        """记录信息日志"""
        self.log("INFO", message)
    
    def warn(self, message: str):
        """记录警告日志"""
        self.log("WARN", message)
    
    def error(self, message: str):
        """记录错误日志"""
        self.log("ERROR", message)
    
    def success(self, message: str):
        """记录成功日志"""
        self.log("SUCCESS", message, ColorCodes.GREEN)
    
    def ai_action(self, action: str, detail: str = ""):
        """记录AI操作"""
        if detail:
            message = f"AI执行操作: {action} - {detail}"
        else:
            message = f"AI执行操作: {action}"
        self.log("AI", message, ColorCodes.MAGENTA)
    
    def attack_detected(self, attack_type: str, source_ip: str, severity: str = "medium"):
        """记录攻击检测"""
        severity_color = {
            "low": ColorCodes.YELLOW,
            "medium": ColorCodes.RED,
            "high": ColorCodes.BOLD + ColorCodes.RED,
            "critical": ColorCodes.BOLD + ColorCodes.BG_RED + ColorCodes.WHITE
        }
        
        color = severity_color.get(severity, ColorCodes.RED)
        message = f"检测到攻击: {attack_type} 来自 {source_ip} (严重程度: {severity})"
        self.log("ATTACK", message, color)
    
    def defense_action(self, action: str, target: str = ""):
        """记录防御操作"""
        if target:
            message = f"执行防御: {action} -> {target}"
        else:
            message = f"执行防御: {action}"
        self.log("DEFENSE", message, ColorCodes.CYAN)
    
    def warning_sent(self, target_ip: str, warning_number: int, max_warnings: int):
        """记录警告发送"""
        message = f"发送警告 {warning_number}/{max_warnings} 到攻击者 {target_ip}"
        self.log("WARNING", message, ColorCodes.YELLOW)


class AIActionNotifier:
    """AI操作通知器"""
    
    def __init__(self):
        self.logger = ColorLogger("ai_actions.log")
        self.action_history = []
    
    def notify(self, action_type: str, description: str, target: str = "", 
               result: str = "success", details: Dict = None):
        """通知AI操作"""
        action_info = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action_type": action_type,
            "description": description,
            "target": target,
            "result": result,
            "details": details or {}
        }
        
        self.action_history.append(action_info)
        
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]
        
        result_color = ColorCodes.GREEN if result == "success" else ColorCodes.RED
        
        if target:
            print(f"\n{ColorCodes.MAGENTA}{ColorCodes.BOLD}[AI 操作]{ColorCodes.RESET}")
            print(f"{ColorCodes.CYAN}类型:{ColorCodes.RESET} {action_type}")
            print(f"{ColorCodes.CYAN}描述:{ColorCodes.RESET} {description}")
            print(f"{ColorCodes.CYAN}目标:{ColorCodes.RESET} {target}")
            print(f"{ColorCodes.CYAN}结果:{ColorCodes.RESET} {result_color}{result}{ColorCodes.RESET}")
            if details:
                print(f"{ColorCodes.CYAN}详情:{ColorCodes.RESET}")
                for key, value in details.items():
                    print(f"  - {key}: {value}")
            print("")
        else:
            print(f"\n{ColorCodes.MAGENTA}{ColorCodes.BOLD}[AI 操作]{ColorCodes.RESET}")
            print(f"{ColorCodes.CYAN}类型:{ColorCodes.RESET} {action_type}")
            print(f"{ColorCodes.CYAN}描述:{ColorCodes.RESET} {description}")
            print(f"{ColorCodes.CYAN}结果:{ColorCodes.RESET} {result_color}{result}{ColorCodes.RESET}")
            print("")
        
        self.logger.ai_action(action_type, description)
    
    def get_history(self, limit: int = 20) -> list:
        """获取操作历史"""
        return self.action_history[-limit:]


color_logger = ColorLogger()
ai_notifier = AIActionNotifier()