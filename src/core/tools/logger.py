"""
Humanaize 日志模块
将所有程序输出记录到日志文件中
"""

import os
import sys
import time
from datetime import datetime
from typing import Optional


class Logger:
    """日志记录器"""
    
    def __init__(self, log_dir: str = "log"):
        """
        初始化日志记录器
        :param log_dir: 日志目录，默认为根目录下的log文件夹
        """
        # 获取项目根目录（当前文件的父目录的父目录的父目录）
        # src/core/tools/logger.py -> src/core/tools -> src/core -> src -> 项目根目录
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.log_dir = os.path.join(self.root_dir, log_dir)
        
        # 确保日志目录存在
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 生成日志文件名
        self.log_file = self._generate_log_filename()
        
        # 文件句柄
        self._file_handle = None
        
        # 是否启用
        self._enabled = True
        
        # 保存原始的stdout和stderr
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        
        # 是否重定向了输出
        self._redirected = False
        
        # 防止递归的标志
        self._writing_to_log = False
    
    def _generate_log_filename(self) -> str:
        """生成日志文件名，格式：当前时间_humanaize2.log"""
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.log_dir, f"{current_time}_humanaize2.log")
    
    def _open_file(self):
        """打开日志文件"""
        if self._file_handle is None:
            # 使用追加模式，编码为utf-8
            self._file_handle = open(self.log_file, "a", encoding="utf-8")
    
    def _close_file(self):
        """关闭日志文件"""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
    
    def _write_to_file(self, message: str):
        """写入日志文件（内部方法，不带时间戳）"""
        if self._writing_to_log:
            return
        
        self._writing_to_log = True
        try:
            self._open_file()
            self._file_handle.write(message)
            self._file_handle.flush()
        finally:
            self._writing_to_log = False
    
    def log(self, message: str, level: str = "INFO"):
        """
        记录日志
        :param message: 日志消息
        :param level: 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        if not self._enabled:
            return
        
        # 添加时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{level}] {message}\n"
        
        # 写入文件（使用内部方法避免递归）
        self._write_to_file(log_line)
        
        # 同时输出到控制台（使用原始stdout避免递归）
        self._original_stdout.write(log_line)
        self._original_stdout.flush()
    
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
        
        # 创建自定义的stdout和stderr类
        class LoggingStream:
            def __init__(self, logger: 'Logger', original_stream, prefix: str = ""):
                self.logger = logger
                self.original_stream = original_stream
                self.prefix = prefix
            
            def write(self, message):
                if message.strip():
                    # 使用原始文件句柄写入，避免调用log方法导致递归
                    if not self.logger._writing_to_log:
                        self.logger._writing_to_log = True
                        try:
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            log_line = f"[{timestamp}] [INFO] {self.prefix}{message.strip()}\n"
                            self.logger._file_handle.write(log_line)
                            self.logger._file_handle.flush()
                        finally:
                            self.logger._writing_to_log = False
                # 同时输出到原始流
                self.original_stream.write(message)
                self.original_stream.flush()
            
            def flush(self):
                self.original_stream.flush()
        
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


# 创建全局日志实例
logger = Logger()


def get_logger() -> Logger:
    """获取全局日志实例"""
    return logger


# 测试日志模块
if __name__ == "__main__":
    log = Logger()
    log.info("测试日志模块启动")
    log.debug("这是一条调试消息")
    log.warning("这是一条警告消息")
    log.error("这是一条错误消息")
    log.critical("这是一条严重错误消息")
    
    # 测试重定向
    log.redirect_output()
    print("这是通过print输出的内容")
    log.restore_output()
    
    log.info("测试完成")
    print(f"日志文件路径: {log.get_log_file_path()}")