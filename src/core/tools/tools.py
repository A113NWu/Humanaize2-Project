"""
Humanaize v2.0 - 工具函式庫

提供系統所需的各種工具函式
"""

import time
import random
import json
from datetime import datetime, timedelta
from pathlib import Path


# ═══════════ 時間工具 ═══════════

def get_current_time_str() -> str:
    """取得當前時間字串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_time_period() -> str:
    """取得當前時間段（早上/中午/下午/晚上）"""
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
    將秒數轉換為人類可讀的時間字串
    
    Args:
        seconds: 秒數
        
    Returns:
        字串，如"2小時30分鐘"
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


def stop_llm_server(port: int = 8080):
    """
    停止运行在指定端口的LLM服务器进程
    
    Args:
        port: 服务器端口
    """
    import os
    import signal
    
    try:
        if os.name == 'nt':
            # Windows 使用 taskkill
            os.system(f'taskkill /f /im llama-server.exe')
        else:
            # Linux/Mac 使用 lsof 和 kill
            import subprocess
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True
            )
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        time.sleep(1)
                        os.kill(int(pid), signal.SIGKILL)
                    except:
                        pass
    except Exception as e:
        print(f"[WARN] Error stopping server: {e}")


def restart_llm_server(model_path: str = None):
    """
    重启LLM服务器
    
    Args:
        model_path: 新的模型路径，如果为None则使用默认路径
        
    Returns:
        bool: 是否成功
    """
    import os
    import subprocess
    import threading
    import sys
    
    # 确保模型路径是绝对路径
    if model_path and not os.path.isabs(model_path):
        # 尝试转换为绝对路径
        abs_path = os.path.abspath(model_path)
        if os.path.exists(abs_path):
            model_path = abs_path
        else:
            print(f"[WARN] Absolute path does not exist: {abs_path}, keeping original: {model_path}")
    
    # 停止现有服务器
    print("[INFO] Stopping existing LLM server...")
    stop_llm_server()
    time.sleep(2)
    
    # 获取服务器路径
    server_path = None
    if sys.platform != "win32" and os.name != "nt":
        system_paths = [
            "/usr/bin/llama-server",
            "/usr/local/bin/llama-server",
            "/opt/llama.cpp/llama-server"
        ]
        for path in system_paths:
            if os.path.exists(path):
                server_path = path
                break
    
    if not server_path:
        # tools.py 在 src/core/tools/ 下，需要4次dirname才能到项目根目录
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        llama_dir = os.path.join(base_dir, "llama")
        
        if sys.platform == "win32" or os.name == "nt":
            server_path = os.path.join(llama_dir, "llama-server.exe")
        elif sys.platform == "darwin":
            server_path = os.path.join(llama_dir, "llama-server")
        else:
            server_path = os.path.join(llama_dir, "llama-server")
    
    # 获取模型路径
    if model_path is None:
        model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "model")
        exact_path = os.path.join(model_dir, "tinyllama.gguf")
        if os.path.exists(exact_path):
            model_path = exact_path
        elif os.path.exists(model_dir):
            for f in os.listdir(model_dir):
                if f.endswith('.gguf'):
                    model_path = os.path.join(model_dir, f)
                    break
    
    if not os.path.exists(server_path):
        print("[ERROR] llama-server not found at:", server_path)
        return False
    
    if not model_path or not os.path.exists(model_path):
        print("[ERROR] Model file not found at:", model_path)
        return False
    
    try:
        cmd = [server_path, "-m", model_path, "-c", "4096", "-ngl", "999", "--host", "127.0.0.1", "--port", "8080", "-n", "256"]
        print(f"[INFO] Starting llama-server with command: {' '.join(cmd)}")
        
        if sys.platform == "win32" or os.name == "nt":
            subprocess.Popen(
                cmd,
                cwd=os.path.dirname(server_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        else:
            subprocess.Popen(
                cmd,
                cwd=os.path.dirname(server_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        def _wait_for_server():
            for i in range(30):
                time.sleep(1)
                if check_llm_server():
                    print("[INFO] LLM server restarted successfully!")
                    return
            print("[WARN] Server process started but not responding yet.")

        threading.Thread(target=_wait_for_server, daemon=True).start()
        return True

    except Exception as e:
        print("[ERROR] Failed to restart server:", str(e))
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
