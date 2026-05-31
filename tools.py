"""
Humanaize v2.0 - 工具函数库

提供系统所需的各种工具函数
"""

import time
import random
import json
from datetime import datetime, timedelta
from pathlib import Path


# ═══════════ 时间工具 ═══════════

def get_current_time_str() -> str:
    """获取当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_time_period() -> str:
    """获取当前时间段（早上/中午/下午/晚上）"""
    hour = datetime.now().hour
    
    if 5 <= hour < 12:
        return "早上"
    elif 12 <= hour < 14:
        return "中午"
    elif 14 <= hour < 18:
        return "下午"
    elif 18 <= hour < 22:
        return "晚上"
    else:
        return "深夜"


def seconds_to_human(seconds: int) -> str:
    """
    将秒数转换为人类可读的时间字符串
    
    Args:
        seconds: 秒数
        
    Returns:
        字符串，如"2小时30分钟"
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    if secs > 0 and not parts:
        parts.append(f"{secs}秒")
    
    return "".join(parts) if parts else "不到1秒"


# ═══════════ 随机工具 ═══════════

def weighted_choice(options: dict) -> str:
    """
    根据权重进行加权随机选择
    
    Args:
        options: 字典 {"选项": 权重, ...}
        
    Returns:
        选中的选项
    """
    items = list(options.items())
    choices = [item[0] for item in items]
    weights = [item[1] for item in items]
    return random.choices(choices, weights=weights, k=1)[0]


def random_element(lst: list):
    """从列表中随机选择一个元素"""
    return random.choice(lst) if lst else None


def should_happen(probability: float) -> bool:
    """
    根据概率判断事件是否发生
    
    Args:
        probability: 概率 (0.0-1.0)
        
    Returns:
        bool: 是否发生
    """
    return random.random() < probability


# ═══════════ 文本工具 ═══════════

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    截断文本，超过长度时添加省略号
    
    Args:
        text: 原始文本
        max_length: 最大长度
        
    Returns:
        截断后的文本
    """
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def clean_text(text: str) -> str:
    """清理文本，移除多余空白"""
    return " ".join(text.split())


def extract_sentences(text: str, count: int = 3) -> list:
    """
    提取文本中的句子
    
    Args:
        text: 文本
        count: 提取的句子数
        
    Returns:
        句子列表
    """
    # 简单的句子分割
    sentences = text.replace("！", "。").replace("？", "。").split("。")
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences[:count]


# ═══════════ 统计工具 ═══════════

def calculate_average(values: list) -> float:
    """计算平均值"""
    return sum(values) / len(values) if values else 0.0


def calculate_trend(values: list) -> str:
    """
    计算趋势
    
    Args:
        values: 数值列表
        
    Returns:
        "上升" / "下降" / "稳定"
    """
    if len(values) < 2:
        return "稳定"
    
    avg_first = sum(values[:-len(values)//2]) / (len(values)//2 + 1) if len(values) > 1 else values[0]
    avg_last = sum(values[-len(values)//2:]) / (len(values)//2) if len(values) > 1 else values[-1]
    
    if avg_last > avg_first * 1.1:
        return "上升"
    elif avg_last < avg_first * 0.9:
        return "下降"
    else:
        return "稳定"


# ═══════════ 字典/JSON工具 ═══════════

def merge_dicts(dict1: dict, dict2: dict) -> dict:
    """
    合并两个字典
    
    Args:
        dict1: 第一个字典
        dict2: 第二个字典
        
    Returns:
        合并后的字典
    """
    result = dict1.copy()
    result.update(dict2)
    return result


def filter_dict(d: dict, keys: list) -> dict:
    """
    从字典中筛选指定的键
    
    Args:
        d: 原字典
        keys: 要保留的键列表
        
    Returns:
        筛选后的字典
    """
    return {k: v for k, v in d.items() if k in keys}


# ═══════════ 验证工具 ═══════════

def is_valid_emotion(emotion: str) -> bool:
    """检查情绪名称是否有效"""
    valid_emotions = [
        "happy", "sad", "angry", "neutral", "fear",
        "surprise", "disgust", "confused", "frustrated", "bored"
    ]
    return emotion.lower() in valid_emotions


def is_valid_trait(trait: str) -> bool:
    """检查人格特征是否有效"""
    valid_traits = [
        "curiosity", "empathy", "creativity", "introversion",
        "impulsiveness", "skepticism", "trust_level"
    ]
    return trait.lower() in valid_traits


def is_valid_probability(value: float) -> bool:
    """检查是否为有效的概率"""
    return 0.0 <= value <= 1.0


# ═══════════ 日志工具 ═══════════

class SimpleLogger:
    """简单的日志记录器"""
    
    def __init__(self, log_file: str = "humanaize.log"):
        self.log_file = Path(log_file)
    
    def log(self, level: str, message: str):
        """记录日志"""
        timestamp = get_current_time_str()
        log_msg = f"[{timestamp}] [{level}] {message}"
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_msg + "\n")
        except:
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


# ═══════════ 性能监测 ═══════════

class PerformanceMonitor:
    """性能监测"""
    
    def __init__(self):
        self.timings = {}
    
    def start(self, name: str):
        """开始计时"""
        self.timings[name] = time.time()
    
    def end(self, name: str) -> float:
        """结束计时，返回耗时秒数"""
        if name in self.timings:
            elapsed = time.time() - self.timings[name]
            del self.timings[name]
            return elapsed
        return 0.0
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "active_timings": len(self.timings),
            "timing_names": list(self.timings.keys())
        }


# ═══════════ 环境检查 ═══════════

def check_llm_server(url: str = "http://127.0.0.1:8080") -> bool:
    """
    检查LLM服务器是否运行
    
    Args:
        url: 服务器地址
        
    Returns:
        bool: 是否运行
    """
    try:
        import requests
        response = requests.get(url, timeout=2)
        return response.status_code == 200
    except:
        return False


def check_python_version() -> str:
    """检查Python版本"""
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def check_required_packages() -> dict:
    """检查必需的包是否安装"""
    packages = {
        "requests": False,
        "opencv-python": False,
        "deepface": False,
        "tkinter": False,
    }
    
    try:
        import requests
        packages["requests"] = True
    except:
        pass
    
    try:
        import cv2
        packages["opencv-python"] = True
    except:
        pass
    
    try:
        from deepface import DeepFace
        packages["deepface"] = True
    except:
        pass
    
    try:
        import tkinter
        packages["tkinter"] = True
    except:
        pass
    
    return packages
