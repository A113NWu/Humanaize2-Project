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
        # 控制台輸出抑制規則（小寫子串匹配）；命中的內容仍寫入日誌文件，
        # 只是不顯示在控制台。CLI 模式用於屏蔽 IoT 網絡的後台噪音。
        self._console_suppress_patterns = []

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

            if self._console_suppressed(message):
                return
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
            """按行緩衝的輸出流：每行都寫入日誌文件；命中控制台抑制
            規則的行只寫文件、不顯示到控制台。內部按行緩衝可正確處理
            print() 把文本和換行分兩次 write 的情況。"""
            def __init__(self, logger, original_stream, prefix=""):
                self.logger = logger
                self.original_stream = original_stream
                self.prefix = prefix
                self._buffer = ""

            def _emit_line(self, line):
                # 空行不進日誌文件，但保留控制台排版
                if not line.strip():
                    try:
                        self.original_stream.write("\n")
                        self.original_stream.flush()
                    except Exception:
                        pass
                    return

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_line = f"[{timestamp}] [INFO] {self.prefix}{line.strip()}\n"

                with self.logger._lock:
                    self.logger._write_log_line(log_line)
                    if self.logger._console_suppressed(line):
                        return
                    try:
                        self.original_stream.write(line + "\n")
                        self.original_stream.flush()
                    except Exception:
                        pass

            def write(self, message):
                if not message:
                    return
                self._buffer += message
                while "\n" in self._buffer:
                    line, self._buffer = self._buffer.split("\n", 1)
                    self._emit_line(line)
                # 防止無換行的長殘片長期滯留緩衝區
                if len(self._buffer) > 8192:
                    self._emit_line(self._buffer)
                    self._buffer = ""
            
            def flush(self):
                if self._buffer:
                    self._emit_line(self._buffer)
                    self._buffer = ""
                try:
                    self.original_stream.flush()
                except:
                    pass
        
        sys.stdout = LoggingStream(self, self._original_stdout, "[STDOUT] ")
        sys.stderr = LoggingStream(self, self._original_stderr, "[STDERR] ")
    
    def restore_output(self):
        """恢复stdout和stderr"""
        if self._redirected:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr
            self._redirected = False
    
    def enable(self):
        """启用日志记录"""
        self._enabled = True
    
    def disable(self):
        """禁用日志记录"""
        self._enabled = False

    def suppress_console_patterns(self, patterns):
        """設置控制台輸出抑制規則（小寫子串匹配，不分大小寫）。

        命中任意規則的輸出仍會寫入日誌文件，但不會顯示在控制台上。
        典型用途：CLI 模式屏蔽後台 IoT 網絡日誌。
        """
        self._console_suppress_patterns = [str(p).lower() for p in patterns if p]

    def clear_console_suppression(self):
        """清除控制台輸出抑制規則。"""
        self._console_suppress_patterns = []

    def _console_suppressed(self, text: str) -> bool:
        """判斷一行文本是否應抑制控制台輸出。"""
        if not self._console_suppress_patterns:
            return False
        low = (text or "").lower()
        return any(p in low for p in self._console_suppress_patterns)
    
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