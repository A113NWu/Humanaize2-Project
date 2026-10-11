"""
Humanaize v2.0 - CLI 聊天介面（Claude Code 風格）

滾動式輸出 + 底部圓角輸入框，不整屏重繪，
支持背景線程安全輸出（主線程統一打印）。
"""

import os
import sys
import re
import shutil
import threading
import time
import queue as queue_mod

from core.thinking_engine import ThinkingEngine
from memory import load_memory, save_memory, add
from core.personality import load_personality
from ui.idle import IdleEngine

try:
    from version import get_version
except ImportError:
    from core.version import get_version

def _load_qq_skill():
    """Optional QQ skill is intentionally never required for CLI startup."""
    try:
        import importlib.util
        spec = importlib.util.find_spec('skills.qq-chat')
        if spec is None:
            return None
        import importlib
        qq_module = importlib.import_module('skills.qq-chat')
        return getattr(qq_module, '_qq_skill', None)
    except Exception:
        return None


_qq_skill = _load_qq_skill()
QQ_SKILL_AVAILABLE = _qq_skill is not None


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
        return True


# 思考類型 → (前綴, 顏色)
THOUGHT_STYLES = {
    "gan_decision": ("GAN", Colors.PURPLE),
    "gan_topic": ("Topic", Colors.GOLD),
    "gan_argument": ("Arg A", Colors.BLUE),
    "gan_counter_argument": ("Arg B", Colors.PINK),
    "gan_synthesis": ("Syn", Colors.GREEN),
    "web_search": ("Search", Colors.CYAN),
    "break_silence": ("Silence", Colors.ORANGE),
    "reflection": ("Reflect", Colors.LIGHT_PURPLE),
    "internal": ("Think", Colors.YELLOW),
}


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
        self.show_commands = False  # 是否顯示命令提示

        # Claude Code 風格：滾動輸出。所有打印集中在主線程，
        # 背景線程只把 (kind, text) 放進隊列。
        self._queue = queue_mod.Queue()
        self._response_done = threading.Event()

        self.thinking_engine = ThinkingEngine(on_response_callback=self._on_response)

        try:
            from core.thinking_engine_api import ThinkingEngineState, start_api_server
            state = ThinkingEngineState()
            state.set_thinking_engine(self.thinking_engine)
            state.set_memory(self.memory)
            state.set_personality(self.personality)
            start_api_server(host='127.0.0.1', port=8082)
            self._emit("sys", "ThinkingEngine API server started on port 8082")
        except Exception as e:
            self._emit("sys", f"Failed to start ThinkingEngine API server: {e}")

        if QQ_SKILL_AVAILABLE:
            _qq_skill.set_thinking_engine(self.thinking_engine)
            _qq_skill.set_memory(self.memory)
            _qq_skill.set_ui_callback(self._handle_qq_message)
            _qq_skill.start_listener()
            self._emit("sys", "QQ skill initialized and listener started")

        self.idle_engine = None
        if self.gan_enabled:
            self.idle_engine = IdleEngine(
                memory=self.memory,
                callback=self._on_idle_callback,
                idle_interval=300,
                gan_enabled=True
            )

        self._use_color = Colors.support_color()

    # ==================== 基礎工具 ====================

    def _t(self, key):
        translations = {
            "English": {
                "cli_start": "Humanaize v{version} CLI started",
                "you": "You", "ai": "Aize", "error": "Error",
                "no_reply": "Aize chose not to respond",
                "available_commands": "Commands",
                "show_help": "Show help", "show_memory": "Show memories",
                "show_status": "Show status", "toggle_gan": "Toggle GAN",
                "clear_screen": "Clear screen", "quit_program": "Quit",
                "no_memory_data": "No memory data",
                "system_status": "System Status",
                "enabled": "ON", "disabled": "OFF",
                "message_count": "Messages", "thought_count": "Thoughts",
                "gan_toggled": "GAN mode {}",
                "shutdown": "Aize shut down. Chat history saved. Bye!",
            },
            "Chinese": {
                "cli_start": "Humanaize v{version} CLI 已启动",
                "you": "你", "ai": "Aize", "error": "错误",
                "no_reply": "Aize 選擇不回應這次輸入",
                "available_commands": "可用命令",
                "show_help": "显示帮助", "show_memory": "显示记忆",
                "show_status": "显示状态", "toggle_gan": "切换GAN",
                "clear_screen": "清屏", "quit_program": "退出",
                "no_memory_data": "无记忆数据",
                "system_status": "系统状态",
                "enabled": "开启", "disabled": "关闭",
                "message_count": "消息", "thought_count": "思考",
                "gan_toggled": "GAN模式已{}",
                "shutdown": "Aize 已關閉，對話歷史已保存，再見！",
            }
        }
        lang = self.language if self.language in translations else "English"
        text = translations[lang].get(key, key)
        if "{version}" in text:
            text = text.replace("{version}", get_version())
        return text

    def _load_settings(self):
        try:
            import json
            path = os.path.join(os.path.dirname(__file__), "data", "settings.json")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"gan_enabled": True, "auto_break_silence": True}

    def _c(self, code, text):
        if not self._use_color:
            return text
        return f"{code}{text}{Colors.RESET}"

    def _term_width(self):
        try:
            return shutil.get_terminal_size().columns
        except Exception:
            return 80

    # ==================== 事件入隊（任意線程可調用） ====================

    def _emit(self, kind, text, prefix="", color=None):
        if text:
            self._queue.put((kind, str(text), prefix, color))

    # ==================== 打印（僅主線程） ====================

    def _flush(self):
        """Claude Code 風格的輸出顯示"""
        printed = False
        while True:
            try:
                kind, text, prefix, color = self._queue.get_nowait()
            except queue_mod.Empty:
                break
            printed = True

            if kind == "user":
                # 用戶輸入 - Claude Code 風格
                print(f"{self._c(Colors.WHITE, '┌' + '─' * (min(self._term_width() - 2, 100)) + '┐')}")
                print(f"{self._c(Colors.CYAN, '│')} {self._c(Colors.BOLD, 'You:')} {text}")
                print(f"{self._c(Colors.WHITE, '└' + '─' * (min(self._term_width() - 2, 100)) + '┘')}")
                print()

            elif kind == "ai":
                # AI 回覆 - Claude Code 風格
                lines = text.split('\n')
                print(f"{self._c(Colors.ORANGE, '┌' + '─' * (min(self._term_width() - 2, 100)) + '┐')}")
                for i, line in enumerate(lines):
                    if i == 0:
                        print(f"{self._c(Colors.ORANGE, '│')} {self._c(Colors.BOLD, 'Aize:')} {line}")
                    else:
                        print(f"{self._c(Colors.ORANGE, '│')}    {line}")
                print(f"{self._c(Colors.ORANGE, '└' + '─' * (min(self._term_width() - 2, 100)) + '┘')}")
                print()

            elif kind == "ai_auto":
                # AI 自動消息 - 較小的框架
                print(f"{self._c(Colors.CYAN, '┌──────────────────────────────────────────────┐')}")
                print(f"{self._c(Colors.CYAN, '│')} {self._c(Colors.BOLD, 'Auto:')} {text}")
                print(f"{self._c(Colors.CYAN, '└──────────────────────────────────────────────┘')}")
                print()

            elif kind == "thought":
                # 思考過程 - Claude Code 思考風格
                style = THOUGHT_STYLES.get(prefix, ("Think", Colors.YELLOW))
                col = color or style[1]
                icon = "🤔" if prefix == "gan_synthesis" else "💭"

                print(f"{self._c(col, '┌─────────────────────────────────────────────┐')}")
                print(f"{self._c(col, '│')} {icon} {style[0]}: {text}")
                print(f"{self._c(col, '└─────────────────────────────────────────────┘')}")
                print()

            elif kind == "command":
                # 命令執行
                print(f"{self._c(Colors.YELLOW, '┌─────────────────────────────────────────────┐')}")
                print(f"{self._c(Colors.YELLOW, '│')} {self._c(Colors.BOLD, 'Command:')} {text}")
                print(f"{self._c(Colors.YELLOW, '└─────────────────────────────────────────────┘')}")
                print()

            elif kind == "output":
                # 輸出結果 - Claude Code 輸出風格
                lines = text.splitlines() or [text]
                print(f"{self._c(Colors.DIM, '┌' + '─' * (min(self._term_width() - 2, 100)) + '┐')}")
                for i, ln in enumerate(lines, 1):
                    print(f"{self._c(Colors.DIM, '│')} {self._c(Colors.BLUE, f'$ {i:02d}')}: {ln}")
                print(f"{self._c(Colors.DIM, '└' + '─' * (min(self._term_width() - 2, 100)) + '┘')}")
                print()

            elif kind == "error":
                # 錯誤信息 - Claude Code 錯誤風格
                print(f"{self._c(Colors.RED, '┌─────────────────────────────────────────────┐')}")
                print(f"{self._c(Colors.RED, '│')} {self._c(Colors.BOLD, 'Error:')} {text}")
                print(f"{self._c(Colors.RED, '└─────────────────────────────────────────────┘')}")
                print()

            elif kind == "sys":
                # 系統信息 - Claude Code 系統風格
                print(f"{self._c(Colors.GRAY, '┌─────────────────────────────────────────────┐')}")
                print(f"{self._c(Colors.GRAY, '│')} {self._c(Colors.BLUE, '•')} {text}")
                print(f"{self._c(Colors.GRAY, '└─────────────────────────────────────────────┘')}")
                print()

        return printed

    def _print_banner(self):
        """Claude Code 風格的標題欄"""
        w = min(self._term_width() - 2, 100)
        print()
        print("╭" + "─" * w + "╮")
        print(f"│{self._c(Colors.BOLD + Colors.BLUE, '  Humanaize')} {self._c(Colors.DIM, f'v{get_version()} CLI')}{' ' * (w - 14 - len(get_version()))}│")
        print("├" + "─" * w + "┤")

        name = self.personality.get("name", "Aize")
        gan_status = "GAN" if self.gan_enabled else "OFF"
        gan_color = Colors.GREEN if self.gan_enabled else Colors.GRAY

        status_line = f"│{self._c(Colors.CYAN, f'  > {name}')}{self._c(Colors.DIM, ' | ')}{self._c(gan_color, f'GAN: {gan_status}')}{' ' * (w - 16 - len(name) - 9 - len(gan_status))}│"
        print(status_line)

        # 顯示提示
        hint = "Type /help for commands or start chatting"
        print(f"│{self._c(Colors.DIM, f'  {hint}')}{' ' * (w - 5 - len(hint))}│")

        print("╰" + "─" * w + "╯")
        print()

    def _draw_input_box(self):
        """Claude Code 風格的輸入框"""
        w = min(self._term_width() - 2, 100)

        if self.show_commands:
            # Claude Code 風格的命令提示
            print(self._c(Colors.DIM, "┌" + "─" * w + "┐"))
            print(self._c(Colors.DIM, "│") + " Commands: " +
                  self._c(Colors.BLUE, "/help") + " " +
                  self._c(Colors.CYAN, "/mem") + " " +
                  self._c(Colors.GREEN, "/status") + " " +
                  self._c(Colors.YELLOW, "/gan") + " " +
                  self._c(Colors.MAGENTA, "/clear") + " " +
                  self._c(Colors.RED, "/quit"))
            print(self._c(Colors.DIM, "└" + "─" * w + "┘"))
            print()

        # Claude Code 風格的輸入提示
        if self.thinking_paused:
            # 顯示 AI 思考狀態
            print(f"{self._c(Colors.YELLOW, '┌─────────────────────────────────────────────────────────────┐')}")
            print(f"{self._c(Colors.YELLOW, '│')} 🤖 AI is thinking... {' ' * (65 - 20)} {self._c(Colors.YELLOW, '│')}")
            print(f"{self._c(Colors.YELLOW, '└─────────────────────────────────────────────────────────────┘')}")
            print()

        # 輸入框
        print(f"{self._c(Colors.DIM, '┌' + '─' * w + '┐')}")
        print(f"{self._c(Colors.DIM, '│')} {self._c(Colors.ORANGE, '❯')} ", end="")
        sys.stdout.flush()

    def _finish_input_box(self):
        """完成輸入框顯示"""
        print()  # 換行
        print(f"{self._c(Colors.DIM, f'└{'─' * (min(self._term_width() - 2, 100))}┘')}")

    # ==================== 背景事件 → 隊列 ====================

    def _handle_qq_message(self, msg):
        try:
            sender = msg.get('from', 'Unknown')
            message = msg.get('message', '')
            msg_type = msg.get('type', 'received')
            arrow = "QQ→" if msg_type == 'sent' else "QQ←"
            self._emit("output", f"[{arrow}] {sender}: {message}")
        except Exception:
            pass

    def _on_response(self, response):
        rtype = response.get("type", "")

        if rtype in ("chat_response", "chat"):
            r = response.get("reply", "") if rtype == "chat_response" else response.get("response", "")
            r = " ".join(r.split())
            if r:
                self._emit("ai", r)
            self._resume()
            self._response_done.set()

        elif rtype == "bug_repair":
            status = response.get("status", "reported")
            message = response.get("message", "已记录问题。")
            self._emit("output", f"bug 狀態={status}，{message}")
            self._response_done.set()

        elif rtype == "error":
            err = response.get("error", "")
            if err:
                self._emit("error", err)
            self._resume()
            self._response_done.set()

        elif rtype == "internal_thought":
            t = response.get("thought", "")
            thought_type = response.get("thought_type", "internal")
            if t:
                self._emit("thought", t, prefix=thought_type)

        elif rtype == "autonomous_message":
            msg = response.get("message", "")
            if msg:
                self._emit("ai_auto", msg)

        elif rtype == "gan_complete":
            gan_result = response.get("gan_result", {})
            should, msg = self.thinking_engine.should_proactively_speak(self.memory, gan_result)
            if should and msg:
                self._emit("ai_auto", msg)

        elif rtype == "gan_topic":
            topic = response.get("gan_topic", response.get("topic", ""))
            if topic:
                self._emit("thought", topic, prefix="gan_topic")

        elif rtype == "gan_argument":
            arg = response.get("gan_argument", response.get("argument", ""))
            if arg:
                self._emit("thought", arg, prefix="gan_argument")

        elif rtype == "gan_counter_argument":
            counter = response.get("gan_counter_argument", response.get("counter", ""))
            if counter:
                self._emit("thought", counter, prefix="gan_counter_argument")

        elif rtype == "gan_synthesis":
            synthesis = response.get("gan_synthesis", "")
            if synthesis:
                self._emit("thought", synthesis, prefix="gan_synthesis")

        elif rtype == "command_start":
            msg = response.get("message", "")
            if msg:
                self._emit("command", msg)

        elif rtype == "command_result":
            output = response.get("output", "")
            if output:
                self._emit("output", output)

    def _on_idle_callback(self, response):
        rtype = response.get("type", "")

        if rtype == "internal_thought":
            t = response.get("thought", "")
            thought_type = response.get("thought_type", "internal")
            if t:
                self._emit("thought", t, prefix=thought_type)

        elif rtype == "gan_topic":
            topic = response.get("gan_topic", response.get("topic", ""))
            if topic:
                self._emit("thought", topic, prefix="gan_topic")

        elif rtype == "gan_argument":
            arg = response.get("gan_argument", response.get("argument", ""))
            if arg:
                self._emit("thought", arg, prefix="gan_argument")

        elif rtype == "gan_counter":
            counter = response.get("gan_counter", response.get("counter", ""))
            if counter:
                self._emit("thought", counter, prefix="gan_counter_argument")

        elif rtype == "gan_rebuttal":
            rebuttal = response.get("gan_rebuttal", response.get("rebuttal", ""))
            if rebuttal:
                self._emit("thought", rebuttal, prefix="gan_counter_argument")

        elif rtype == "gan_complete":
            gan_result = response.get("gan_result", {})
            should, msg = self.thinking_engine.should_proactively_speak(self.memory, gan_result)
            if should and msg:
                self._emit("ai_auto", msg)

    # ==================== 主流程 ====================

    def _pause(self):
        self.thinking_paused = True
        if self.idle_engine:
            self.idle_engine.pause()

    def _resume(self):
        self.thinking_paused = False
        if self.idle_engine:
            self.idle_engine.resume()

    def send(self, text):
        self._pause()

        should, _ = self.thinking_engine.should_answer_user(text)
        if not should:
            self._emit("sys", self._t("no_reply"))
            self._resume()
            self._response_done.set()
            return

        add(self.memory, "user", text)
        save_memory(self.memory)

        prompt = f"\n\nUser: {text}\nAssistant:"
        try:
            if self.gan_enabled:
                self.thinking_engine.queue_chat_task(prompt, memory=self.memory, use_gan_decision=True, user_text=text)
            else:
                self.thinking_engine.queue_chat_task(prompt, memory=self.memory)
        except TypeError:
            self.thinking_engine.queue_chat_task(prompt)

    def _wait_response(self):
        """等待 AI 回覆完成，期間持續打印隊列內容"""
        self._response_done.clear()
        while not self._response_done.wait(timeout=0.12):
            self._flush()
        self._flush()
        time.sleep(0.05)
        self._flush()

    def _cmd(self, raw):
        """Claude Code 風格的命令處理"""
        cmd = raw.lower().strip()

        if cmd == "/help":
            # Claude Code 風格的幫助界面
            w = min(self._term_width() - 4, 90)
            print(f"{self._c(Colors.BLUE, '┌' + '─' * w + '┐')}")
            print(f"{self._c(Colors.BLUE, '│')} {self._c(Colors.BOLD + Colors.WHITE, ' Commands ').center(w)} {self._c(Colors.BLUE, '│')}")
            print(f"{self._c(Colors.BLUE, '├' + '─' * w + '┤')}")

            commands = [
                ("/help", "Show available commands", "List all CLI commands"),
                ("/mem", "Show conversation history", "Display recent messages"),
                ("/status", "Show system status", "View current system state"),
                ("/gan", "Toggle GAN mode", "Switch thinking mode on/off"),
                ("/clear", "Clear screen", "Clear the terminal display"),
                ("/quit", "Exit program", "Close Humanaize CLI")
            ]

            for c, d, desc in commands:
                cmd_line = f"│ {self._c(Colors.CYAN, c.ljust(12))} {self._c(Colors.WHITE, d)} - {self._c(Colors.GRAY, desc)}"
                padding = w - len(cmd_line.rstrip()) + 1
                print(f"{cmd_line}{' ' * padding}{self._c(Colors.BLUE, '│')}")

            print(f"{self._c(Colors.BLUE, '└' + '─' * w + '┘')}")
            print()

        elif cmd == "/mem":
            # Claude Code 風格的記憶顯示
            w = min(self._term_width() - 4, 90)
            print(f"{self._c(Colors.CYAN, '┌' + '─' * w + '┐')}")
            print(f"{self._c(Colors.CYAN, '│')} {self._c(Colors.BOLD + Colors.WHITE, ' Recent Conversations ').center(w)} {self._c(Colors.CYAN, '│')}")
            print(f"{self._c(Colors.CYAN, '├' + '─' * w + '┤')}")

            msgs = self.memory.get("messages", [])[-5:]
            if msgs:
                for i, m in enumerate(msgs, 1):
                    role = m.get('role', 'unknown')
                    content = m.get('content', '')[:80]
                    t = m.get('time', '')[:16] if m.get('time') else ''
                    role_icon = "👤" if role == "user" else "🤖"
                    role_color = Colors.GREEN if role == "user" else Colors.ORANGE

                    print(f"{self._c(Colors.CYAN, '│')} {self._c(Colors.YELLOW, f'#{i:2d}')} "
                          f"{role_icon} {self._c(role_color, role)} "
                          f"{self._c(Colors.DIM, f'@{t}')}")
                    # 縮排內容
                    content_lines = self._wrap_text(content, w - 8)
                    for j, line in enumerate(content_lines):
                        if j == 0:
                            print(f"{self._c(Colors.CYAN, '│')}    {line}")
                        else:
                            print(f"{self._c(Colors.CYAN, '│')}    {line}")
                    if i < len(msgs):
                        print(f"{self._c(Colors.CYAN, '├' + '─' * w + '┤')}")
            else:
                print(f"{self._c(Colors.CYAN, '│')}  {self._t('no_memory_data')}")

            print(f"{self._c(Colors.CYAN, '└' + '─' * w + '┘')}")
            print()

        elif cmd == "/status":
            # Claude Code 風格的狀態顯示
            w = min(self._term_width() - 4, 90)
            print(f"{self._c(Colors.GREEN, '┌' + '─' * w + '┐')}")
            print(f"{self._c(Colors.GREEN, '│')} {self._c(Colors.BOLD + Colors.WHITE, ' System Status ').center(w)} {self._c(Colors.GREEN, '│')}")
            print(f"{self._c(Colors.GREEN, '├' + '─' * w + '┤')}")

            gan_status = "Enabled" if self.gan_enabled else "Disabled"
            msg_count = len(self.memory.get('messages', []))
            thought_count = len(self.memory.get('thoughts', []))
            name = self.personality.get("name", "Aize")

            # 狀態項目 - Claude Code 風格
            status_items = [
                ("AI Name", name, Colors.CYAN),
                ("GAN Mode", gan_status, Colors.GREEN if self.gan_enabled else Colors.RED),
                ("Message Count", str(msg_count), Colors.BLUE),
                ("Thought Count", str(thought_count), Colors.MAGENTA)
            ]

            for label, value, color in status_items:
                print(f"{self._c(Colors.GREEN, '│')}  {self._c(Colors.WHITE, f'{label}:')} "
                      f"{self._c(color, f'[{value}]')}")

            print(f"{self._c(Colors.GREEN, '└' + '─' * w + '┘')}")
            print()

        elif cmd == "/gan":
            self.gan_enabled = not self.gan_enabled
            status = "Enabled" if self.gan_enabled else "Disabled"
            # Claude Code 風格的狀態切換
            w = min(self._term_width() - 4, 70)
            color = Colors.GREEN if self.gan_enabled else Colors.YELLOW
            print(f"{self._c(color, '┌' + '─' * w + '┐')}")
            print(f"{self._c(color, '│')} {self._c(Colors.BOLD + Colors.WHITE, ' GAN Mode ')} "
                  f"{self._c(color, status.upper())} {self._c(color, '│')}")
            print(f"{self._c(color, '└' + '─' * w + '┘')}")
            print()

        elif cmd == "/clear":
            if sys.platform == "win32":
                os.system('cls')
            else:
                sys.stdout.write('\033[2J\033[H')
                sys.stdout.flush()
            self._print_banner()

        elif cmd == "/quit":
            # Claude Code 風格的退出
            w = min(self._term_width() - 4, 60)
            print(f"{self._c(Colors.ORANGE, '┌' + '─' * w + '┐')}")
            print(f"{self._c(Colors.ORANGE, '│')} {self._t('shutdown')} {self._c(Colors.ORANGE, '│')}")
            print(f"{self._c(Colors.ORANGE, '└' + '─' * w + '┘')}")
            self.running = False

        else:
            # Claude Code 風格的錯誤提示
            w = min(self._term_width() - 4, 70)
            print(f"{self._c(Colors.RED, '┌' + '─' * w + '┐')}")
            print(f"{self._c(Colors.RED, '│')} {self._c(Colors.BOLD, 'Error:')} Unknown command '{cmd}'")
            print(f"{self._c(Colors.RED, '│')} Type {self._c(Colors.CYAN, '/help')} for available commands")
            print(f"{self._c(Colors.RED, '└' + '─' * w + '┘')}")

    def _wrap_text(self, text, width):
        """文本自動換行輔助函數"""
        if len(text) <= width:
            return [text]

        words = text.split()
        lines = []
        current_line = []

        for word in words:
            if len(' '.join(current_line + [word])) <= width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def run(self):
        """運行 CLI 界面 - Claude Code 風格"""
        if sys.stdin is None:
            print("無法取得控制台輸入。請在命令提示符（cmd）中執行：humanaize2 boot -m cli")
            return

        # 顯示歡迎界面
        self._print_welcome()
        self._print_banner()

        while self.running:
            try:
                self._flush()
                self._draw_input_box()
                user_input = input()
                self._finish_input_box()

                if not user_input.strip():
                    # 空行時的友好提示
                    self._show_empty_input_hint()
                    continue

                if user_input.startswith("/"):
                    self.show_commands = False
                    self._cmd(user_input)
                    # /help 命令後暫時顯示命令提示
                    if user_input == "/help":
                        self.show_commands = True
                else:
                    # 處理用戶對話
                    self._handle_user_input(user_input)

            except (KeyboardInterrupt, EOFError):
                self._handle_exit()
                break
            except RuntimeError:
                self._show_runtime_error()
                break

        self._shutdown()

    def _print_welcome(self):
        """Claude Code 風格的歡迎界面"""
        w = min(self._term_width() - 4, 80)
        print(f"{self._c(Colors.BLUE, '┌' + '─' * w + '┐')}")
        print(f"{self._c(Colors.BLUE, '│')} {self._c(Colors.BOLD + Colors.WHITE, ' Welcome to Humanaize CLI ').center(w)} {self._c(Colors.BLUE, '│')}")
        print(f"{self._c(Colors.BLUE, '├' + '─' * w + '┤')}")
        print(f"{self._c(Colors.BLUE, '│')} {self._c(Colors.DIM, '  Chat with AI, manage settings, and more.').center(w)} {self._c(Colors.BLUE, '│')}")
        print(f"{self._c(Colors.BLUE, '│')} {self._c(Colors.DIM, '  Type your message or use commands below.').center(w)} {self._c(Colors.BLUE, '│')}")
        print(f"{self._c(Colors.BLUE, '└' + '─' * w + '┘')}")
        print()

    def _show_empty_input_hint(self):
        """空行時的提示"""
        print(f"{self._c(Colors.DIM, '┌' + '─' * (min(self._term_width() - 2, 80)) + '┐')}")
        print(f"{self._c(Colors.DIM, '│')} {self._c(Colors.YELLOW, '💡')} Tip: {self._c(Colors.CYAN, '/help')} for commands | {self._c(Colors.CYAN, '/quit')} to exit")
        print(f"{self._c(Colors.DIM, '└' + '─' * (min(self._term_width() - 2, 80)) + '┘')}")
        print()

    def _handle_user_input(self, user_input):
        """處理用戶輸入"""
        self._queue.put(("user", user_input.strip(), "", None))
        self.send(user_input)
        self._wait_response()
        # 對話後添加分隔線
        print(f"{self._c(Colors.DIM, '─' * (min(self._term_width() - 2, 100)))}")
        print()

    def _handle_exit(self):
        """處理退出"""
        print()
        print(self._c(Colors.YELLOW, '┌───────────────────────────────────────────────────────┐'))
        print(self._c(Colors.YELLOW, '│') + ' Press ' + self._c(Colors.BOLD, 'Enter') + ' to exit Humanaize CLI ' + self._c(Colors.YELLOW, '│'))
        print(self._c(Colors.YELLOW, '└───────────────────────────────────────────────────────┘'))
        try:
            input()
        except:
            pass

    def _show_runtime_error(self):
        """顯示運行時錯誤"""
        print()
        print(self._c(Colors.RED, '┌───────────────────────────────────────────────────────┐'))
        print(self._c(Colors.RED, '│') + ' Console input lost. Please run in a new command prompt: ' + self._c(Colors.RED, '│'))
        print(self._c(Colors.RED, '│') + '   humanaize2 boot -m cli ' + self._c(Colors.RED, '│'))
        print(self._c(Colors.RED, '└───────────────────────────────────────────────────────┘'))

    def _shutdown(self):
        save_memory(self.memory)
        print()
        print(self._c(Colors.DIM, f"{'─' * min(self._term_width() - 2, 64)}"))
        print(f"{self._c(Colors.GRAY, '✻')} {self._c(Colors.GRAY, self._t('shutdown'))}")
        print(self._c(Colors.DIM, f"{'─' * min(self._term_width() - 2, 64)}"))


if __name__ == "__main__":
    cli = HumanaizeCLI()
    cli.run()
