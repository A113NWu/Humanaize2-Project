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

try:
    import importlib
    qq_module = importlib.import_module('skills.qq-chat')
    _qq_skill = qq_module._qq_skill
    QQ_SKILL_AVAILABLE = True
except ImportError:
    QQ_SKILL_AVAILABLE = False


class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ORANGE = '\033[38;5;208m'
    BLUE = '\033[38;5;39m'
    PRIMARY = '\033[38;5;39m'
    GREEN = '\033[38;5;46m'
    RED = '\033[38;5;196m'
    YELLOW = '\033[38;5;226m'
    MAGENTA = '\033[38;5;201m'
    CYAN = '\033[38;5;51m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'
    
    PURPLE = '\033[38;5;147m'
    GOLD = '\033[38;5;220m'
    PINK = '\033[38;5;213m'
    LIGHT_PURPLE = '\033[38;5;183m'
    
    @classmethod
    def support_color(cls) -> bool:
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
        self.language = self.settings.get("language", "Chinese")
        
        self.running = True
        self.thinking_paused = False
        self.render_lock = threading.Lock()
        
        self.thinking_engine = ThinkingEngine(on_response_callback=self._on_response)

        try:
            from core.thinking_engine_api import ThinkingEngineState, start_api_server
            state = ThinkingEngineState()
            state.set_thinking_engine(self.thinking_engine)
            state.set_memory(self.memory)
            state.set_personality(self.personality)
            start_api_server(host='127.0.0.1', port=8082)
            print(f"[INFO] ThinkingEngine API server started on port 8082")
        except Exception as e:
            print(f"[WARN] Failed to start ThinkingEngine API server: {e}")

        if QQ_SKILL_AVAILABLE:
            _qq_skill.set_thinking_engine(self.thinking_engine)
            _qq_skill.set_memory(self.memory)
            _qq_skill.set_ui_callback(self._handle_qq_message)
            _qq_skill.start_listener()
            print(f"[INFO] QQ skill initialized and listener started")
        
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
        
        self._use_color = Colors.support_color()
        
        self._init_welcome_message()

    def _t(self, key):
        translations = {
            "English": {
                "cli_start": "Humanaize v2.0 CLI started",
                "gan_enabled": "GAN: ON",
                "gan_disabled": "GAN: OFF",
                "chat": "Chat",
                "thought": "Thought",
                "you": "You",
                "ai": "Aize",
                "thinking": "Thinking",
                "response_generated": "Response generated",
                "internal_thinking": "Internal thinking",
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
                "available_commands": "Commands:",
                "show_help": "Show help",
                "show_memory": "Show memories",
                "show_status": "Show status",
                "toggle_gan": "Toggle GAN",
                "clear_screen": "Clear screen",
                "quit_program": "Quit",
                "no_memory_data": "No memory data",
                "system_status": "System Status",
                "enabled": "ON",
                "disabled": "OFF",
                "trait_info": "Traits: C={}, E={}, Cr={}",
                "gan_toggled": "GAN mode {}",
                "topic": "Topic",
                "argument": "Arg",
                "counter_argument": "Counter",
                "rebuttal": "Rebuttal",
            },
            "Chinese": {
                "cli_start": "Humanaize v2.0 CLI 已启动",
                "gan_enabled": "GAN: 开启",
                "gan_disabled": "GAN: 关闭",
                "chat": "对话",
                "thought": "思考",
                "you": "你",
                "ai": "Aize",
                "thinking": "思考中",
                "response_generated": "回复已生成",
                "internal_thinking": "内部思考",
                "gan_thinking_complete": "GAN思考完成",
                "error": "错误",
                "info": "信息",
                "success": "成功",
                "warning": "警告",
                "thought_count": "思考",
                "message_count": "消息",
                "status": "状态",
                "memory": "记忆",
                "personality": "人格",
                "curiosity": "好奇心",
                "empathy": "同理心",
                "creativity": "创造力",
                "gan_mode": "GAN模式",
                "gan_enabled_short": "●",
                "gan_disabled_short": "○",
                "available_commands": "可用命令:",
                "show_help": "显示帮助",
                "show_memory": "显示记忆",
                "show_status": "显示状态",
                "toggle_gan": "切换GAN",
                "clear_screen": "清屏",
                "quit_program": "退出",
                "no_memory_data": "无记忆数据",
                "system_status": "系统状态",
                "enabled": "开启",
                "disabled": "关闭",
                "trait_info": "特质: 好奇={}, 同理={}, 创造={}",
                "gan_toggled": "GAN模式已{}",
                "topic": "主题",
                "argument": "论点",
                "counter_argument": "反论",
                "rebuttal": "反驳",
            }
        }
        lang = self.language if self.language in translations else "English"
        return translations[lang].get(key, key)

    def _init_welcome_message(self):
        self.system_logs.append({
            "type": "info",
            "message": self._t("cli_start"),
            "time": self._get_time_str()
        })

    def _get_time_str(self):
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
        if h > 40:
            h = 25
        if h < 15:
            h = 15
        if w < 60:
            w = 60
        self.width = w
        self.height = h

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

    def _build_status_line(self):
        msgs = len(self.memory.get('messages', []))
        thoughts = len(self.memory.get('thoughts', []))
        gan_status = "●" if self.gan_enabled else "○"
        personality = self.personality.get("name", "Aize")
        
        if self._use_color:
            gan_color = Colors.GREEN if self.gan_enabled else Colors.RED
            status = f" {Colors.BOLD}{Colors.ORANGE}{personality}{Colors.RESET}"
            status += f" {Colors.DIM}v2.1{Colors.RESET}"
            status += f"  {gan_color}{gan_status}{Colors.RESET} GAN"
            status += f"  {Colors.BLUE}{msgs}{Colors.RESET} {self._t('message_count')}"
            status += f"  {Colors.MAGENTA}{thoughts}{Colors.RESET} {self._t('thought_count')}"
        else:
            status = f" {personality} v2.1  {gan_status} GAN  {msgs} Messages  {thoughts} Thoughts"
        
        return status

    def _build_system_log_line(self):
        if not self.system_logs:
            return ("", "")
        
        recent_log = self.system_logs[-1]
        log_time = recent_log.get("time", "")
        log_type = recent_log.get("type", "")
        log_msg = recent_log.get("message", "")[:60]
        
        prefix = ""
        if log_type == "success":
            prefix = "✓"
        elif log_type == "warning":
            prefix = "⚠"
        elif log_type == "error":
            prefix = "✗"
        
        if prefix:
            content = f"[{log_time}] {prefix} {log_msg}"
        else:
            content = f"[{log_time}] {log_msg}"
        
        return (content, log_type)

    def _render(self):
        with self.render_lock:
            self._clear_screen()
            
            w = self.width
            h = self.height
            
            lines_to_render = []
            
            lines_to_render.append(self._build_status_line())
            
            lines_to_render.append("─" * w)
            
            header_rows = 2
            footer_rows = 1
            content_rows = h - header_rows - footer_rows - 2
            if content_rows < 3:
                content_rows = 3
            
            all_lines = []
            chat_w = w - 4
            
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
                lines_to_render.append(f" {line_clean}")
            
            lines_to_render.append("─" * w)
            
            sys_log_content, log_type = self._build_system_log_line()
            if sys_log_content:
                content_w = w - 4
                if len(sys_log_content) > content_w:
                    sys_log_content = sys_log_content[:content_w]
                
                if self._use_color:
                    color_map = {
                        "success": Colors.GREEN,
                        "warning": Colors.YELLOW,
                        "error": Colors.RED,
                        "info": Colors.GRAY
                    }
                    log_color = color_map.get(log_type, Colors.GRAY)
                    lines_to_render.append(f" {log_color}{sys_log_content}{Colors.RESET}")
                else:
                    lines_to_render.append(f" {sys_log_content}")
            
            for line in lines_to_render:
                line_stripped = self._strip(line)
                if len(line_stripped) < w:
                    line += " " * (w - len(line_stripped))
                print(line)
            
            if self._use_color:
                sys.stdout.write(f"\n{Colors.BOLD}{Colors.PRIMARY}> {Colors.RESET}")
            else:
                sys.stdout.write("\n> ")
            sys.stdout.flush()

    def _add_chat(self, msg):
        self.chat_history.append(msg)
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-100:]

    def _add_thought(self, msg):
        self.thought_history.append(msg)
        if len(self.thought_history) > 100:
            self.thought_history = self.thought_history[-100:]

    def _add_system_log(self, type, message):
        self.system_logs.append({
            "type": type,
            "message": message,
            "time": self._get_time_str()
        })
        if len(self.system_logs) > 20:
            self.system_logs = self.system_logs[-20:]

    def _handle_qq_message(self, msg):
        try:
            sender = msg.get('from', 'Unknown')
            message = msg.get('message', '')
            msg_type = msg.get('type', 'received')
            if msg_type == 'sent':
                print(f"{Colors.CYAN}[QQ→] {sender}: {message}{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}[QQ←] {sender}: {message}{Colors.RESET}")
        except Exception:
            pass

    def _on_response(self, response):
        rtype = response.get("type", "")
        
        if rtype == "chat_response":
            r = response.get("reply", "")
            r = " ".join(r.split())
            if r:
                if self._use_color:
                    self._add_chat(f"{Colors.GREEN}{self._t('ai')}:{Colors.RESET} {r}")
                else:
                    self._add_chat(f"{self._t('ai')}: {r}")
            self._resume()
            self._add_system_log("success", self._t("response_generated"))
        
        elif rtype == "chat":
            r = response.get("response", "")
            r = " ".join(r.split())
            if r:
                if self._use_color:
                    self._add_chat(f"{Colors.GREEN}{self._t('ai')}:{Colors.RESET} {r}")
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
            thought_type = response.get("thought_type", "internal")
            
            if t:
                type_config = {
                    "gan_decision": {"prefix": "GAN", "color": Colors.PURPLE},
                    "gan_topic": {"prefix": "Topic", "color": Colors.GOLD},
                    "gan_argument": {"prefix": "Arg A", "color": Colors.BLUE},
                    "gan_counter_argument": {"prefix": "Arg B", "color": Colors.PINK},
                    "gan_synthesis": {"prefix": "Syn", "color": Colors.GREEN},
                    "web_search": {"prefix": "Search", "color": Colors.CYAN},
                    "break_silence": {"prefix": "Silence", "color": Colors.ORANGE},
                    "reflection": {"prefix": "Reflect", "color": Colors.LIGHT_PURPLE},
                    "internal": {"prefix": "Think", "color": Colors.YELLOW}
                }
                
                config = type_config.get(thought_type, type_config["internal"])
                
                if self._use_color:
                    self._add_thought(f"{config['color']}[{config['prefix']}]{Colors.RESET} {t}")
                else:
                    self._add_thought(f"[{config['prefix']}] {t}")
            self._add_system_log("info", self._t("internal_thinking"))
        
        elif rtype == "autonomous_message":
            msg = response.get("message", "")
            if msg:
                if self._use_color:
                    self._add_chat(f"{Colors.CYAN}{self._t('ai')}:{Colors.RESET} {msg}")
                else:
                    self._add_chat(f"{self._t('ai')}: {msg}")
            self._add_system_log("info", "Autonomous message")
        
        elif rtype == "gan_complete":
            gan_result = response.get("gan_result", {})
            should, msg = self.thinking_engine.should_proactively_speak(self.memory, gan_result)
            if should and msg:
                if self._use_color:
                    self._add_chat(f"{Colors.CYAN}{self._t('ai')}:{Colors.RESET} {msg}")
                else:
                    self._add_chat(f"{self._t('ai')}: {msg}")
            self._add_system_log("success", self._t("gan_thinking_complete"))
        
        elif rtype == "gan_topic":
            topic = response.get("gan_topic", response.get("topic", ""))
            if topic:
                if self._use_color:
                    self._add_thought(f"{Colors.GOLD}[{self._t('topic')}]{Colors.RESET} {topic}")
                else:
                    self._add_thought(f"[{self._t('topic')}] {topic}")
            self._add_system_log("info", f"GAN Topic: {topic[:30]}...")
        
        elif rtype == "gan_argument":
            arg = response.get("gan_argument", response.get("argument", ""))
            if arg:
                if self._use_color:
                    self._add_thought(f"{Colors.BLUE}[{self._t('argument')}]{Colors.RESET} {arg}")
                else:
                    self._add_thought(f"[{self._t('argument')}] {arg}")
        
        elif rtype == "gan_counter_argument":
            counter = response.get("gan_counter_argument", response.get("counter", ""))
            if counter:
                if self._use_color:
                    self._add_thought(f"{Colors.PINK}[{self._t('counter_argument')}]{Colors.RESET} {counter}")
                else:
                    self._add_thought(f"[{self._t('counter_argument')}] {counter}")
        
        elif rtype == "gan_synthesis":
            synthesis = response.get("gan_synthesis", "")
            if synthesis:
                if self._use_color:
                    self._add_thought(f"{Colors.GREEN}[Syn]{Colors.RESET} {synthesis}")
                else:
                    self._add_thought(f"[Syn] {synthesis}")
        
        elif rtype == "command_start":
            msg = response.get("message", "")
            if msg:
                if self._use_color:
                    self._add_chat(f"{Colors.YELLOW}[Command]{Colors.RESET} {msg}")
                else:
                    self._add_chat(f"[Command] {msg}")
        
        elif rtype == "command_result":
            output = response.get("output", "")
            if output:
                if self._use_color:
                    self._add_chat(f"{Colors.CYAN}[Output]{Colors.RESET}\n{output}")
                else:
                    self._add_chat(f"[Output]\n{output}")
        
        self._render()

    def _on_idle_callback(self, response):
        rtype = response.get("type", "")
        
        if rtype == "internal_thought":
            t = response.get("thought", "")
            thought_type = response.get("thought_type", "internal")
            
            if t:
                type_config = {
                    "gan_decision": {"prefix": "GAN", "color": Colors.PURPLE},
                    "gan_topic": {"prefix": "Topic", "color": Colors.GOLD},
                    "gan_argument": {"prefix": "Arg A", "color": Colors.BLUE},
                    "gan_counter_argument": {"prefix": "Arg B", "color": Colors.PINK},
                    "gan_synthesis": {"prefix": "Syn", "color": Colors.GREEN},
                    "web_search": {"prefix": "Search", "color": Colors.CYAN},
                    "break_silence": {"prefix": "Silence", "color": Colors.ORANGE},
                    "reflection": {"prefix": "Reflect", "color": Colors.LIGHT_PURPLE},
                    "internal": {"prefix": "Think", "color": Colors.YELLOW}
                }
                
                config = type_config.get(thought_type, type_config["internal"])
                
                if self._use_color:
                    self._add_thought(f"{config['color']}[{config['prefix']}]{Colors.RESET} {t}")
                else:
                    self._add_thought(f"[{config['prefix']}] {t}")
        
        elif rtype == "gan_topic":
            topic = response.get("gan_topic", response.get("topic", ""))
            if topic:
                if self._use_color:
                    self._add_thought(f"{Colors.GOLD}[{self._t('topic')}]{Colors.RESET} {topic}")
                else:
                    self._add_thought(f"[{self._t('topic')}] {topic}")
            self._add_system_log("info", f"GAN Topic: {topic[:30]}...")
        
        elif rtype == "gan_argument":
            arg = response.get("gan_argument", response.get("argument", ""))
            if arg:
                if self._use_color:
                    self._add_thought(f"{Colors.BLUE}[{self._t('argument')}]{Colors.RESET} {arg}")
                else:
                    self._add_thought(f"[{self._t('argument')}] {arg}")
        
        elif rtype == "gan_counter":
            counter = response.get("gan_counter", response.get("counter", ""))
            if counter:
                if self._use_color:
                    self._add_thought(f"{Colors.PINK}[{self._t('counter_argument')}]{Colors.RESET} {counter}")
                else:
                    self._add_thought(f"[{self._t('counter_argument')}] {counter}")
        
        elif rtype == "gan_rebuttal":
            rebuttal = response.get("gan_rebuttal", response.get("rebuttal", ""))
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
        self.thinking_paused = True
        if self.idle_engine:
            self.idle_engine.pause()

    def _resume(self):
        self.thinking_paused = False
        if self.idle_engine:
            self.idle_engine.resume()

    def send(self, text):
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
            name = self.personality.get("name", "Aize")

            if self._use_color:
                status_text = f"{Colors.BLUE}{self._t('system_status')}{Colors.RESET}\n"
                status_text += f"  GAN: {Colors.GREEN if self.gan_enabled else Colors.RED}{gan_status}{Colors.RESET}\n"
                status_text += f"  {self._t('message_count')}: {Colors.BLUE}{msg_count}{Colors.RESET}\n"
                status_text += f"  {self._t('thought_count')}: {Colors.MAGENTA}{thought_count}{Colors.RESET}\n"
                status_text += f"  Name: {Colors.CYAN}{name}{Colors.RESET}"
                self._add_chat(status_text)
            else:
                status_text = f"{self._t('system_status')}\n"
                status_text += f"  GAN: {gan_status}\n"
                status_text += f"  {self._t('message_count')}: {msg_count}\n"
                status_text += f"  {self._t('thought_count')}: {thought_count}\n"
                status_text += f"  Name: {name}"
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
                self._add_chat(f"{Colors.RED}Unknown command: {cmd}{Colors.RESET}")
            else:
                self._add_chat(f"Unknown command: {cmd}")

    def _shutdown(self):
        save_memory(self.memory)
        
        self._clear_screen()
        
        if self._use_color:
            print(f"\n{'=' * self.width}")
            print(f"  {Colors.BOLD}{Colors.GREEN}Aize 已关闭{Colors.RESET}")
            print(f"  {Colors.GRAY}对话历史已保存，再见！👋{Colors.RESET}")
            print(f"{'=' * self.width}")
        else:
            print(f"\n{'=' * self.width}")
            print("  Aize 已关闭")
            print("  对话历史已保存，再见！👋")
            print(f"{'=' * self.width}")


if __name__ == "__main__":
    cli = HumanaizeCLI()
    cli.run()