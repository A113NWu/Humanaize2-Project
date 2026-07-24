"""
Humanaize 日志模块
将所有程序输出记录到日志文件中
"""

import os
import sys
import time
import threading
from datetime import datetime


class Logger:
    """日志记录器"""
    
    def __init__(self, log_dir: str = "log"):
        """
        初始化日志记录器
        :param log_dir: 日志目录，默认为根目录下的log文件夹
        """
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.log_dir = os.path.join(self.root_dir, log_dir)
        
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.log_file = self._generate_log_filename()
        
        self._file_handle = None
        self._enabled = True
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._redirected = False
        
        self._lock = threading.Lock()
        self._writing = False
    
    def _generate_log_filename(self) -> str:
        """生成日志文件名，格式：当前时间_humanaize2.log"""
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.log_dir, f"{current_time}_humanaize2.log")
    
    def _open_file(self):
        """打开日志文件"""
        if self._file_handle is None:
            self._file_handle = open(self.log_file, "a", encoding="utf-8", buffering=1)
    
    def _close_file(self):
        """关闭日志文件"""
        if self._file_handle is not None:
            try:
                self._file_handle.flush()
                self._file_handle.close()
            except:
                pass
            self._file_handle = None
    
    def _write_log_line(self, line: str):
        """写入日志行"""
        if not self._enabled:
            return
        
        try:
            self._open_file()
            self._file_handle.write(line)
            self._file_handle.flush()
        except Exception as e:
            try:
                self._original_stdout.write(f"[LOGGER ERROR] Failed to write log: {e}\n")
                self._original_stdout.flush()
            except:
                pass
    
    def log(self, message: str, level: str = "INFO"):
        """
        记录日志
        :param message: 日志消息
        :param level: 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        if not self._enabled:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{level}] {message}\n"
        
        with self._lock:
            self._write_log_line(log_line)
            
            try:
                self._original_stdout.write(log_line)
                self._original_stdout.flush()
            except:
                pass
    
    def debug(self, message: str):
        """记录DEBUG级别日志"""
        self.log(message, "DEBUG")
    
    def info(self, message: str):
        """记录INFO级别日志"""
        self.log(message, "INFO")
    
    def warning(self, message: str):
        """记录WARNING级别日志"""
        self.log(message, "WARNING")
    
    def error(self, message: str):
        """记录ERROR级别日志"""
        self.log(message, "ERROR")
    
    def critical(self, message: str):
        """记录CRITICAL级别日志"""
        self.log(message, "CRITICAL")
    
    def redirect_output(self):
        """重定向stdout和stderr到日志文件"""
        if self._redirected:
            return
        
        self._open_file()
        self._redirected = True
        
        class LoggingStream:
            def __init__(self, logger, original_stream, prefix=""):
                self.logger = logger
                self.original_stream = original_stream
                self.prefix = prefix
            
            def write(self, message):
                if message.strip():
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    log_line = f"[{timestamp}] [INFO] {self.prefix}{message.strip()}\n"
                    
                    with self.logger._lock:
                        self.logger._write_log_line(log_line)
                
                try:
                    self.original_stream.write(message)
                    self.original_stream.flush()
                except:
                    pass
            
            def flush(self):
                try:
                    self.original_stream.flush()
                except:
                    pass
        
        sys.stdout = LoggingStream(self, self._original_stdout, "[STDOUT] ")
        sys.stderr = LoggingStream(self, self._original_stderr, "[STDERR] ")
    
    def restore_output(self):
        """恢复stdout和stderr"""
        if self._redirected:
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr
            self._redirected = False
    
    def enable(self):
        """启用日志记录"""
        self._enabled = True
    
    def disable(self):
        """禁用日志记录"""
        self._enabled = False
    
    def get_log_file_path(self) -> str:
        """获取日志文件路径"""
        return self.log_file
    
    def __del__(self):
        """析构函数，确保关闭文件"""
        self._close_file()
        self.restore_output()


def setup_unbuffered_output():
    """设置无缓冲输出，确保日志实时显示"""
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    if hasattr(sys.stdout, 'flush'):
        sys.stdout.flush()
    if hasattr(sys.stderr, 'flush'):
        sys.stderr.flush()


setup_unbuffered_output()

logger = Logger()


def get_logger() -> Logger:
    """获取全局日志实例"""
    return logger


if __name__ == "__main__":
    log = Logger()
    log.info("测试日志模块启动")
    log.debug("这是一条调试消息")
    log.warning("这是一条警告消息")
    log.error("这是一条错误消息")
    log.critical("这是一条严重错误消息")
    
    log.redirect_output()
    print("这是通过print输出的内容")
    log.restore_output()
    
    log.info("测试完成")
    print(f"日志文件路径: {log.get_log_file_path()}")