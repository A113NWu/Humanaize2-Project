"""
Humanaize v2.0 - CLI 聊天介面
"""

import os
import sys
import re
import shutil
import threading

from core.thinking_engine import ThinkingEngine
from memory import load_memory, save_memory, add
from core.personality import load_personality
from ui.idle import IdleEngine
from llm import chat
import config


class Colors:
    """CLI 颜色定义"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ORANGE = '\033[38;5;208m'
    BLUE = '\033[38;5;39m'
    PRIMARY = '\033[38;5;39m'  # 主色调，与 BLUE 相同
    GREEN = '\033[38;5;46m'
    RED = '\033[38;5;196m'
    YELLOW = '\033[38;5;226m'
    MAGENTA = '\033[38;5;201m'
    CYAN = '\033[38;5;51m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'
    
    @classmethod
    def support_color(cls) -> bool:
        """檢查終端是否支援 ANSI 顏色碼"""
        if sys.platform == "win32":
            try:
                import subprocess
                result = subprocess.run(
                    ["reg", "query", "HKCU\\Console", "/v", "VirtualTerminalLevel"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and "0x1" in result.stdout:
                    return True
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    hStdOut = kernel32.GetStdHandle(-11)
                    mode = ctypes.c_ulong()
                    kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode))
                    mode.value |= 4
                    kernel32.SetConsoleMode(hStdOut, mode)
                    return True
                except:
                    return False
            except:
                return False
        return True


class HumanaizeCLI:
    def __init__(self):
        self.memory = load_memory()
        self.personality = load_personality()
        self.settings = self._load_settings()
        self.gan_enabled = self.settings.get("gan_enabled", True)
        self.auto_break_silence = self.settings.get("auto_break_silence", True)
        self.language = self.settings.get("language", "English")  # 預設英文
        
        self.running = True
        self.thinking_paused = False
        self.render_lock = threading.Lock()
        
        self.thinking_engine = ThinkingEngine(on_response_callback=self._on_response)
        
        self.idle_engine = None
        if self.gan_enabled:
            self.idle_engine = IdleEngine(
                memory=self.memory,
                callback=self._on_idle_callback,
                idle_interval=300,
                gan_enabled=True
            )
        
        self.chat_history = []
        self.thought_history = []
        self.system_logs = []
        
        self.width = 80
        self.height = 24
        self._detect_size()
        
        self._initial_lines = []
        self._use_color = Colors.support_color()
        
        self._init_welcome_message()

    def _t(self, key):
        """翻譯函數"""
        translations = {
            "English": {
                "cli_start": "Humanaize v2.0 CLI started",
                "gan_enabled": "GAN Mode: Enabled",
                "gan_disabled": "GAN Mode: Disabled",
                "chat": "Chat",
                "thought": "Thought",
                "you": "You",
                "ai": "AI",
                "thinking": "Thinking",
                "response_generated": "Response generated",
                "internal_thinking": "Internal thinking in progress",
                "gan_thinking_complete": "GAN thinking complete",
                "error": "Error",
                "info": "Info",
                "success": "Success",
                "warning": "Warning",
                "thought_count": "Thoughts",
                "message_count": "Messages",
                "status": "Status",
                "memory": "Memory",
                "personality": "Personality",
                "curiosity": "Curiosity",
                "empathy": "Empathy",
                "creativity": "Creativity",
                "gan_mode": "GAN Mode",
                "gan_enabled_short": "●",
                "gan_disabled_short": "○",
                "available_commands": "Available commands:",
                "show_help": "Show this help message",
                "show_memory": "Show last 3 memories",
                "show_status": "Show system status",
                "toggle_gan": "Toggle GAN mode",
                "clear_screen": "Clear screen",
                "quit_program": "Exit program",
                "no_memory_data": "No memory data",
                "system_status": "System Status",
                "enabled": "Enabled",
                "disabled": "Disabled",
                "trait_info": "Personality Traits: Curiosity={}, Empathy={}, Creativity={}",
                "gan_toggled": "GAN mode toggled to {}",
                "topic": "Topic",
                "argument": "Argument",
                "counter_argument": "Counter",
                "rebuttal": "Rebuttal",
            },
            "Chinese": {
                "cli_start": "Humanaize v2.0 CLI 已啟動",
                "gan_enabled": "GAN 模式: 啟用",
                "gan_disabled": "GAN 模式: 停用",
                "chat": "對話",
                "thought": "思考",
                "you": "你",
                "ai": "AI",
                "thinking": "思考中",
                "response_generated": "回應已生成",
                "internal_thinking": "正在進行內部思考",
                "gan_thinking_complete": "GAN 思考完成",
                "error": "錯誤",
                "info": "資訊",
                "success": "成功",
                "warning": "警告",
                "thought_count": "思考",
                "message_count": "訊息",
                "status": "狀態",
                "memory": "記憶",
                "personality": "人格",
                "curiosity": "好奇心",
                "empathy": "同理心",
                "creativity": "創造力",
                "gan_mode": "GAN 模式",
                "gan_enabled_short": "●",
                "gan_disabled_short": "○",
                "available_commands": "可用命令:",
                "show_help": "顯示此幫助訊息",
                "show_memory": "顯示最近3條記憶",
                "show_status": "顯示系統狀態",
                "toggle_gan": "切換GAN模式",
                "clear_screen": "清空畫面",
                "quit_program": "退出程式",
                "no_memory_data": "無記憶資料",
                "system_status": "系統狀態",
                "enabled": "啟用",
                "disabled": "停用",
                "trait_info": "人格特質: 好奇心={}, 同理心={}, 創造力={}",
                "gan_toggled": "GAN模式已{}",
                "topic": "主題",
                "argument": "論點",
                "counter_argument": "反論",
                "rebuttal": "反駁",
            }
        }
        lang = self.language if self.language in translations else "English"
        return translations[lang].get(key, key)

    def _init_welcome_message(self):
        """Initialize welcome message"""
        self.system_logs.append({
            "type": "info",
            "message": self._t("cli_start"),
            "time": self._get_time_str()
        })
        self.system_logs.append({
            "type": "info",
            "message": self._t("gan_enabled") if self.gan_enabled else self._t("gan_disabled"),
            "time": self._get_time_str()
        })

    def _get_time_str(self):
        """取得當前時間字串"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def _detect_size(self):
        w, h = 80, 24
        
        try:
            size = shutil.get_terminal_size((w, h))
            w = size.columns
            h = size.lines
        except Exception:
            pass
        
        if h > 50:
            h = 30
        if h < 10:
            h = 10
        if w < 40:
            w = 40
        
        self.width = w
        self.height = h
        
    def _should_use_single_column(self):
        """判斷是否應該使用單列模式"""
        return self.width < 80

    def _load_settings(self):
        try:
            import json
            path = os.path.join(os.path.dirname(__file__), "data", "settings.json")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"gan_enabled": True, "auto_break_silence": True}

    def _strip(self, text):
        return re.sub(r'\x1b\[[0-9;]*m', '', text)

    def _clear_screen(self):
        if sys.platform == "win32":
            os.system('cls')
        else:
            sys.stdout.write('\033[2J\033[H')
            sys.stdout.flush()

    def _wrap_text(self, text, max_width):
        lines = text.split('\n')
        wrapped_lines = []
        
        for line in lines:
            if not line:
                wrapped_lines.append("")
                continue
            
            current_line = ""
            current_length = 0
            
            words = line.split(' ')
            for word in words:
                word_length = len(self._strip(word))
                
                if current_line:
                    if current_length + 1 + word_length <= max_width:
                        current_line += " " + word
                        current_length += 1 + word_length
                    else:
                        wrapped_lines.append(current_line)
                        current_line = word
                        current_length = word_length
                else:
                    current_line = word
                    current_length = word_length
            
            if current_line:
                wrapped_lines.append(current_line)
        
        return wrapped_lines

    def _save_initial_state(self):
        self._initial_lines = []
        self._initial_lines.append(self._build_divider())
        self._initial_lines.append(self._build_status_line())
        self._initial_lines.append(self._build_divider())

    def _build_divider(self, style="="):
        """建構分隔線"""
        divider = style * self.width
        if self._use_color:
            return f"{Colors.DIM}{divider}{Colors.RESET}"
        return divider

    def _build_status_line(self):
        """Build status line"""
        msgs = len(self.memory.get('messages', []))
        thoughts = len(self.memory.get('thoughts', []))
        gan_status = "●" if self.gan_enabled else "○"
        personality = self.personality.get("name", "Default")
        
        if self._use_color:
            gan_color = Colors.GREEN if self.gan_enabled else Colors.RED
            status = f"  {Colors.BOLD}{Colors.ORANGE}Humanaize{Colors.RESET}"
            status += f" {Colors.DIM}v2.1{Colors.RESET}"
            status += f"  {Colors.BOLD}{Colors.BLUE}[{personality}]{Colors.RESET}"
            status += f"  {gan_color}{gan_status}{Colors.RESET} GAN"
            status += f"  {Colors.DIM}│{Colors.RESET}"
            status += f"  {Colors.BLUE}{msgs} {self._t('message_count')}{Colors.RESET}"
            status += f"  {Colors.MAGENTA}{thoughts} {self._t('thought_count')}{Colors.RESET}"
        else:
            status = f"  Humanaize v2.1 [{personality}]  {gan_status} GAN"
            status += f"  │  {msgs} {self._t('message_count')}  {thoughts} {self._t('thought_count')}"
        
        status_stripped = self._strip(status)
        if len(status_stripped) < self.width:
            status += " " * (self.width - len(status_stripped))
        
        return status

    def _build_header_line(self, chat_width, thought_width):
        """Build header line"""
        if self._use_color:
            chat_label = f"{Colors.BOLD}{Colors.BLUE}{self._t('chat')}{Colors.RESET}"
            thought_label = f"{Colors.BOLD}{Colors.MAGENTA}{self._t('thought')}{Colors.RESET}"
        else:
            chat_label = self._t('chat')
            thought_label = self._t('thought')
        
        chat_label_stripped = self._strip(chat_label)
        thought_label_stripped = self._strip(thought_label)
        
        chat_div_len = chat_width - len(chat_label_stripped) - 2
        thought_div_len = thought_width - len(thought_label_stripped) - 2
        
        if chat_div_len < 0:
            chat_div_len = 0
        if thought_div_len < 0:
            thought_div_len = 0
        
        header = f"  {chat_label}"
        if chat_div_len > 0:
            if self._use_color:
                header += f" {Colors.DIM}{'─' * chat_div_len}{Colors.RESET}"
            else:
                header += f" {'─' * chat_div_len}"
        if self._use_color:
            header += f"  {Colors.DIM}│{Colors.RESET}  {thought_label}"
        else:
            header += f"  │  {thought_label}"
        if thought_div_len > 0:
            if self._use_color:
                header += f" {Colors.DIM}{'─' * thought_div_len}{Colors.RESET}"
            else:
                header += f" {'─' * thought_div_len}"
        
        return header

    def _build_system_log_line(self):
        """建構系統日誌列"""
        if not self.system_logs:
            return ""
        
        recent_logs = self.system_logs[-3:]
        log_line = ""
        
        for log in recent_logs:
            log_time = log.get("time", "")
            log_type = log.get("type", "")
            log_msg = log.get("message", "")
            
            if self._use_color:
                if log_type == "info":
                    log_line += f"{Colors.GRAY}[{log_time}] {log_msg}{Colors.RESET} | "
                elif log_type == "success":
                    log_line += f"{Colors.GREEN}[{log_time}] {log_msg}{Colors.RESET} | "
                elif log_type == "warning":
                    log_line += f"{Colors.YELLOW}[{log_time}] {log_msg}{Colors.RESET} | "
                elif log_type == "error":
                    log_line += f"{Colors.RED}[{log_time}] {log_msg}{Colors.RESET} | "
            else:
                log_line += f"[{log_time}] {log_msg} | "
        
        return log_line[:-3]  # 移除最後的 " | "

    def _build_status_line_small(self):
        """建構小窗口模式的簡化狀態列"""
        personality = self.personality.get("name", "Default")[:8]  # 限制長度
        gan_status = "●" if self.gan_enabled else "○"
        
        if self._use_color:
            gan_color = Colors.GREEN if self.gan_enabled else Colors.RED
            status = f"  {Colors.BOLD}{Colors.ORANGE}Humanaize{Colors.RESET}"
            status += f" {Colors.DIM}v2.1{Colors.RESET}"
            status += f" [{personality}]"
            status += f" {gan_color}{gan_status}{Colors.RESET}"
        else:
            status = f"  Humanaize v2.1 [{personality}] {gan_status}"
        
        status_stripped = self._strip(status)
        if len(status_stripped) < self.width:
            status += " " * (self.width - len(status_stripped))
        
        return status

    def _build_system_log_line_small(self):
        """建構小窗口模式的簡化系統日誌列"""
        if not self.system_logs:
            return ""
        
        recent_log = self.system_logs[-1]
        log_time = recent_log.get("time", "")
        log_type = recent_log.get("type", "")
        log_msg = recent_log.get("message", "")[:40]  # 限制長度
        
        if self._use_color:
            if log_type == "info":
                return f"{Colors.GRAY}[{log_time}] {log_msg}{Colors.RESET}"
            elif log_type == "success":
                return f"{Colors.GREEN}[{log_time}] {log_msg}{Colors.RESET}"
            elif log_type == "warning":
                return f"{Colors.YELLOW}[{log_time}] {log_msg}{Colors.RESET}"
            elif log_type == "error":
                return f"{Colors.RED}[{log_time}] {log_msg}{Colors.RESET}"
        else:
            return f"[{log_time}] {log_msg}"

    def _render(self):
        """渲染CLI介面"""
        with self.render_lock:
            self._clear_screen()
            
            w = self.width
            h = self.height
            single_column = self._should_use_single_column()
            
            lines_to_render = []
            
            # 頂部標題區
            lines_to_render.append(self._build_divider("="))
            lines_to_render.append(self._build_status_line_small() if single_column else self._build_status_line())
            lines_to_render.append(self._build_divider("─"))
            
            if not single_column:
                # 雙列模式：標頭列
                chat_w = int(w * 0.55)
                thought_w = w - chat_w - 5
                lines_to_render.append(self._build_header_line(chat_w, thought_w))
                lines_to_render.append(self._build_divider("─"))
            
            # 極小窗口模式：隱藏非必要元素
            tiny_mode = h < 15  # 小於15行時進入極簡模式
            
            # 計算各區域行數
            # 頂部：分隔線 + 狀態行 + 分隔線 = 3行（極簡模式只保留狀態行）
            header_rows = 1 if tiny_mode else 3
            
            # 底部：分隔線 + 系統日誌 = 2行（極簡模式只保留分隔線）
            # 雙列模式底部還有一個分隔線
            footer_rows = 1 if tiny_mode else (3 if not single_column else 2)
            
            # 雙列模式額外增加：標頭列 + 分隔線 = 2行（極小窗口強制單列）
            extra_rows = 0 if tiny_mode else (2 if not single_column else 0)
            
            # 計算內容區域行數
            content_rows = h - header_rows - footer_rows - extra_rows - 1  # 減1給輸入提示行
            if content_rows < 1:
                content_rows = 1
            
            # 極小窗口強制單列模式
            if tiny_mode:
                single_column = True
            
            if single_column:
                # 單列模式：交替顯示聊天和思考
                all_lines = []
                chat_w = w - 4  # 減去邊距
                
                # 合併聊天和思考內容
                for i in range(max(len(self.chat_history), len(self.thought_history))):
                    if i < len(self.chat_history):
                        wrapped = self._wrap_text(self.chat_history[i], chat_w)
                        all_lines.extend(wrapped)
                    if i < len(self.thought_history):
                        wrapped = self._wrap_text(self.thought_history[i], chat_w)
                        all_lines.extend(wrapped)
                
                display_lines = all_lines[-content_rows:]
                
                for line in display_lines:
                    line_clean = self._strip(line)[:chat_w]
                    # 填充到终端宽度
                    line_padded = line_clean.ljust(chat_w)
                    lines_to_render.append("  " + line_padded)
            else:
                # 雙列模式
                chat_w = int(w * 0.55)
                thought_w = w - chat_w - 5
                
                # 處理聊天內容
                all_chat_lines = []
                for entry in self.chat_history:
                    wrapped = self._wrap_text(entry, chat_w)
                    all_chat_lines.extend(wrapped)
                
                # 處理思考內容
                all_thought_lines = []
                for entry in self.thought_history:
                    wrapped = self._wrap_text(entry, thought_w)
                    all_thought_lines.extend(wrapped)
                
                chat_lines = all_chat_lines[-content_rows:]
                thought_lines = all_thought_lines[-content_rows:]
                
                # 合併顯示
                for i in range(content_rows):
                    chat_line = chat_lines[i] if i < len(chat_lines) else ""
                    thought_line = thought_lines[i] if i < len(thought_lines) else ""
                    
                    chat_clean = self._strip(chat_line)[:chat_w]
                    thought_clean = self._strip(thought_line)[:thought_w]
                    
                    chat_padded = chat_clean.ljust(chat_w)
                    thought_padded = thought_clean.ljust(thought_w)
                    
                    if self._use_color:
                        line_parts = [
                            "  ",
                            chat_padded,
                            "  ",
                            Colors.DIM,
                            "│",
                            Colors.RESET,
                            "  ",
                            thought_padded
                        ]
                    else:
                        line_parts = [
                            "  ",
                            chat_padded,
                            "  ",
                            "│",
                            "  ",
                            thought_padded
                        ]
                    
                    full_line = "".join(line_parts)
                    lines_to_render.append(full_line)
            
            # 底部狀態區
            lines_to_render.append(self._build_divider("─"))
            
            # 系統日誌列（小窗口時只顯示最近一條）
            sys_log = self._build_system_log_line_small() if single_column else self._build_system_log_line()
            if sys_log:
                sys_log_stripped = self._strip(sys_log)
                # 填充到终端宽度
                if len(sys_log_stripped) < w:
                    sys_log = sys_log + " " * (w - len(sys_log_stripped))
                elif len(sys_log_stripped) > w:
                    sys_log = sys_log_stripped[:w-3] + "..."
                lines_to_render.append(sys_log)
            
            if not single_column:
                lines_to_render.append(self._build_divider("─"))
            
            # 輸出所有行
            for line in lines_to_render:
                line_stripped = self._strip(line)
                if len(line_stripped) < w:
                    line += " " * (w - len(line_stripped))
                print(line)
            
            # 輸入提示 - 使用现代化配色
            if self._use_color:
                sys.stdout.write(f"\n  {Colors.BOLD}{Colors.PRIMARY}> {Colors.RESET}")
            else:
                sys.stdout.write("\n  > ")
            sys.stdout.flush()

    def _add_chat(self, msg):
        """添加聊天訊息"""
        self.chat_history.append(msg)
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-100:]

    def _add_thought(self, msg):
        """添加思考訊息"""
        self.thought_history.append(msg)
        if len(self.thought_history) > 100:
            self.thought_history = self.thought_history[-100:]

    def _add_system_log(self, type, message):
        """添加系統日誌"""
        self.system_logs.append({
            "type": type,
            "message": message,
            "time": self._get_time_str()
        })
        if len(self.system_logs) > 20:
            self.system_logs = self.system_logs[-20:]

    def _on_response(self, response):
        """處理回應回呼"""
        rtype = response.get("type", "")
        
        if rtype == "chat":
            r = response.get("response", "")
            r = " ".join(r.split())
            if r:
                if self._use_color:
                    self._add_chat(f"{Colors.GREEN}AI:{Colors.RESET} {r}")
                else:
                    self._add_chat(f"AI: {r}")
            self._resume()
            self._add_system_log("success", self._t("response_generated"))
        
        elif rtype == "error":
            err = response.get("error", "")
            if err:
                if self._use_color:
                    self._add_chat(f"{Colors.RED}{self._t('error')}:{Colors.RESET} {err}")
                else:
                    self._add_chat(f"{self._t('error')}: {err}")
            self._resume()
            self._add_system_log("error", f"{self._t('error')}: {err}")
        
        elif rtype == "internal_thought":
            t = response.get("thought", "")
            if t:
                if self._use_color:
                    self._add_thought(f"{Colors.YELLOW}{self._t('thinking')}:{Colors.RESET} {t}")
                else:
                    self._add_thought(f"[{self._t('thinking')}] {t}")
            self._add_system_log("info", self._t("internal_thinking"))
        
        elif rtype == "autonomous_message":
            msg = response.get("message", "")
            if msg:
                if self._use_color:
                    self._add_chat(f"{Colors.CYAN}{self._t('ai')}:{Colors.RESET} {msg}")
                else:
                    self._add_chat(f"{self._t('ai')}: {msg}")
            self._add_system_log("info", "Autonomous message sent")
        
        elif rtype == "gan_complete":
            gan_result = response.get("gan_result", {})
            should, msg = self.thinking_engine.should_proactively_speak(self.memory, gan_result)
            if should and msg:
                if self._use_color:
                    self._add_chat(f"{Colors.CYAN}{self._t('ai')}:{Colors.RESET} {msg}")
                else:
                    self._add_chat(f"{self._t('ai')}: {msg}")
            self._add_system_log("success", self._t("gan_thinking_complete"))
        
        self._render()

    def _on_idle_callback(self, response):
        """處理閒置引擎回呼"""
        rtype = response.get("type", "")
        
        if rtype == "internal_thought":
            t = response.get("thought", "")
            if t:
                if self._use_color:
                    self._add_thought(f"{Colors.YELLOW}{self._t('thinking')}:{Colors.RESET} {t}")
                else:
                    self._add_thought(f"[{self._t('thinking')}] {t}")
        
        elif rtype == "gan_topic":
            topic = response.get("topic", "")
            if topic:
                if self._use_color:
                    self._add_thought(f"{Colors.CYAN}[{self._t('topic')}]{Colors.RESET} {topic}")
                else:
                    self._add_thought(f"[{self._t('topic')}] {topic}")
            self._add_system_log("info", f"GAN Topic: {topic[:30]}...")
        
        elif rtype == "gan_argument":
            arg = response.get("argument", "")
            if arg:
                if self._use_color:
                    self._add_thought(f"{Colors.GREEN}[{self._t('argument')}]{Colors.RESET} {arg}")
                else:
                    self._add_thought(f"[{self._t('argument')}] {arg}")
        
        elif rtype == "gan_counter":
            counter = response.get("counter", "")
            if counter:
                if self._use_color:
                    self._add_thought(f"{Colors.RED}[{self._t('counter_argument')}]{Colors.RESET} {counter}")
                else:
                    self._add_thought(f"[{self._t('counter_argument')}] {counter}")
        
        elif rtype == "gan_rebuttal":
            rebuttal = response.get("rebuttal", "")
            if rebuttal:
                if self._use_color:
                    self._add_thought(f"{Colors.MAGENTA}[{self._t('rebuttal')}]{Colors.RESET} {rebuttal}")
                else:
                    self._add_thought(f"[{self._t('rebuttal')}] {rebuttal}")
        
        elif rtype == "gan_complete":
            gan_result = response.get("gan_result", {})
            should, msg = self.thinking_engine.should_proactively_speak(self.memory, gan_result)
            if should and msg:
                if self._use_color:
                    self._add_chat(f"{Colors.CYAN}{self._t('ai')}:{Colors.RESET} {msg}")
                else:
                    self._add_chat(f"{self._t('ai')}: {msg}")
        
        self._render()

    def _pause(self):
        """暫停思考"""
        self.thinking_paused = True
        if self.idle_engine:
            self.idle_engine.pause()

    def _resume(self):
        """恢復思考"""
        self.thinking_paused = False
        if self.idle_engine:
            self.idle_engine.resume()

    def send(self, text):
        """發送訊息"""
        if not text.strip():
            return

        if self._use_color:
            self._add_chat(f"{Colors.BLUE}{self._t('you')}:{Colors.RESET} {text}")
        else:
            self._add_chat(f"{self._t('you')}: {text}")
        
        add(self.memory, "user", text)
        save_memory(self.memory)
        self._add_system_log("info", f"Message sent: {text[:30]}...")
        
        self._render()
        self._pause()

        should, _ = self.thinking_engine.should_answer_user(text)
        if not should:
            self._resume()
            self._render()
            return

        prompt = f"\n\nUser: {text}\nAssistant:"
        try:
            if self.gan_enabled:
                self.thinking_engine.queue_chat_task(prompt, memory=self.memory, use_gan_decision=True, user_text=text)
            else:
                self.thinking_engine.queue_chat_task(prompt, memory=self.memory)
        except TypeError:
            self.thinking_engine.queue_chat_task(prompt)

    def run(self):
        """執行CLI主迴圈"""
        self._save_initial_state()
        self._render()
        
        while self.running:
            try:
                user_input = input()
                
                if not user_input.strip():
                    self._render()
                    continue
                
                if user_input.startswith("/"):
                    self._cmd(user_input)
                    self._render()
                else:
                    self.send(user_input)
                    
            except (KeyboardInterrupt, EOFError):
                break

        self._shutdown()

    def _cmd(self, cmd):
        """處理命令"""
        cmd = cmd.lower().strip()
        
        if cmd == "/help":
            if self._use_color:
                help_text = f"{Colors.ORANGE}{self._t('available_commands')}{Colors.RESET}\n"
                help_text += f"  {Colors.BLUE}/help{Colors.RESET}    - {self._t('show_help')}\n"
                help_text += f"  {Colors.BLUE}/mem{Colors.RESET}     - {self._t('show_memory')}\n"
                help_text += f"  {Colors.BLUE}/status{Colors.RESET}  - {self._t('show_status')}\n"
                help_text += f"  {Colors.BLUE}/gan{Colors.RESET}     - {self._t('toggle_gan')}\n"
                help_text += f"  {Colors.BLUE}/clear{Colors.RESET}   - {self._t('clear_screen')}\n"
                help_text += f"  {Colors.BLUE}/quit{Colors.RESET}    - {self._t('quit_program')}"
                self._add_chat(help_text)
            else:
                help_text = f"{self._t('available_commands')}\n"
                help_text += f"  /help    - {self._t('show_help')}\n"
                help_text += f"  /mem     - {self._t('show_memory')}\n"
                help_text += f"  /status  - {self._t('show_status')}\n"
                help_text += f"  /gan     - {self._t('toggle_gan')}\n"
                help_text += f"  /clear   - {self._t('clear_screen')}\n"
                help_text += f"  /quit    - {self._t('quit_program')}"
                self._add_chat(help_text)
        
        elif cmd == "/mem":
            msgs = self.memory.get("messages", [])[-3:]
            if msgs:
                for m in msgs:
                    role = m.get('role', 'unknown')
                    content = m.get('content', '')[:50]
                    time = m.get('time', '')[:19]
                    if self._use_color:
                        self._add_chat(f"{Colors.GRAY}[{time}] {role}: {content}{Colors.RESET}")
                    else:
                        self._add_chat(f"[{time}] {role}: {content}")
            else:
                if self._use_color:
                    self._add_chat(f"{Colors.GRAY}{self._t('no_memory_data')}{Colors.RESET}")
                else:
                    self._add_chat(self._t('no_memory_data'))
        
        elif cmd == "/status":
            gan_status = self._t('enabled') if self.gan_enabled else self._t('disabled')
            msg_count = len(self.memory.get('messages', []))
            thought_count = len(self.memory.get('thoughts', []))
            trait_info = self.personality.get("traits", {})
            
            if self._use_color:
                status_text = f"{Colors.BLUE}{self._t('system_status')}{Colors.RESET}\n"
                status_text += f"  GAN: {Colors.GREEN if self.gan_enabled else Colors.RED}{gan_status}{Colors.RESET}\n"
                status_text += f"  {self._t('message_count')}: {Colors.BLUE}{msg_count}{Colors.RESET}\n"
                status_text += f"  {self._t('thought_count')}: {Colors.MAGENTA}{thought_count}{Colors.RESET}\n"
                status_text += f"  {self._t('trait_info').format(trait_info.get('curiosity', 0), trait_info.get('empathy', 0), trait_info.get('creativity', 0))}"
                self._add_chat(status_text)
            else:
                status_text = f"{self._t('system_status')}\n"
                status_text += f"  GAN: {gan_status}\n"
                status_text += f"  {self._t('message_count')}: {msg_count}\n"
                status_text += f"  {self._t('thought_count')}: {thought_count}\n"
                status_text += f"  {self._t('trait_info').format(trait_info.get('curiosity', 0), trait_info.get('empathy', 0), trait_info.get('creativity', 0))}"
                self._add_chat(status_text)
        
        elif cmd == "/gan":
            self.gan_enabled = not self.gan_enabled
            status = self._t('enabled') if self.gan_enabled else self._t('disabled')
            if self._use_color:
                self._add_chat(f"{Colors.ORANGE}{self._t('gan_toggled').format(status)}{Colors.RESET}")
            else:
                self._add_chat(self._t('gan_toggled').format(status))
            self._add_system_log("info", f"GAN mode toggled to {status}")
        
        elif cmd == "/clear":
            self.chat_history = []
            self.thought_history = []
            self._render()
        
        elif cmd == "/quit":
            self.running = False
        
        else:
            if self._use_color:
                self._add_chat(f"{Colors.RED}未知命令: {cmd}{Colors.RESET}")
            else:
                self._add_chat(f"未知命令: {cmd}")

    def _shutdown(self):
        """關閉程式"""
        save_memory(self.memory)
        
        self._clear_screen()
        for line in self._initial_lines:
            print(line)
        print()
        if self._use_color:
            print(f"  {Colors.ORANGE}再見！感謝使用 Humanaize v2.0{Colors.RESET}")
        else:
            print("  再見！感謝使用 Humanaize v2.0")
        print()


if __name__ == "__main__":
    cli = HumanaizeCLI()
    cli.run()
