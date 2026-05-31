"""
Humanaize v2.0 - CLI Chat Interface
"""

import os
import sys
import re
import shutil
import threading

from thinking_engine import ThinkingEngine
from memory import load_memory, save_memory, add
from personality import load_personality
from idle import IdleEngine
from llm import chat
import config


class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ORANGE = '\033[38;5;208m'
    BLUE = '\033[38;5;39m'
    GREEN = '\033[38;5;46m'
    RED = '\033[38;5;196m'
    YELLOW = '\033[38;5;226m'
    MAGENTA = '\033[38;5;201m'
    CYAN = '\033[38;5;51m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'


class HumanaizeCLI:
    def __init__(self):
        self.memory = load_memory()
        self.personality = load_personality()
        self.settings = self._load_settings()
        self.gan_enabled = self.settings.get("gan_enabled", True)
        self.auto_break_silence = self.settings.get("auto_break_silence", True)
        
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
        
        self.width = 80
        self.height = 24
        self._detect_size()
        
        self._initial_lines = []

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

    def _build_divider(self):
        return f"{Colors.DIM}{'─' * self.width}{Colors.RESET}"

    def _build_status_line(self):
        msgs = len(self.memory.get('messages', []))
        thoughts = len(self.memory.get('thoughts', []))
        gan_status = f"{Colors.GREEN}●{Colors.RESET}" if self.gan_enabled else f"{Colors.RED}○{Colors.RESET}"
        
        status = f"  {Colors.BOLD}{Colors.ORANGE}Humanaize{Colors.RESET}  {Colors.DIM}v2.0{Colors.RESET}"
        status += f"  {gan_status} GAN"
        status += f"  {Colors.DIM}│{Colors.RESET}"
        status += f"  {Colors.BLUE}{msgs} msgs{Colors.RESET}"
        status += f"  {Colors.MAGENTA}{thoughts} thoughts{Colors.RESET}"
        
        status_stripped = self._strip(status)
        if len(status_stripped) < self.width:
            status += " " * (self.width - len(status_stripped))
        
        return status

    def _build_header_line(self, chat_width, thought_width):
        chat_label = f"{Colors.BOLD}{Colors.BLUE}Chat{Colors.RESET}"
        thought_label = f"{Colors.BOLD}{Colors.MAGENTA}Thoughts{Colors.RESET}"
        
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
            header += f" {Colors.DIM}{'─' * chat_div_len}{Colors.RESET}"
        header += f"  {Colors.DIM}│{Colors.RESET}  {thought_label}"
        if thought_div_len > 0:
            header += f" {Colors.DIM}{'─' * thought_div_len}{Colors.RESET}"
        
        return header

    def _render(self):
        with self.render_lock:
            self._clear_screen()
            
            w = self.width
            h = self.height
            
            chat_w = int(w * 0.55)
            thought_w = w - chat_w - 5
            
            lines_to_render = []
            lines_to_render.append(self._build_divider())
            lines_to_render.append(self._build_status_line())
            lines_to_render.append(self._build_divider())
            lines_to_render.append(self._build_header_line(chat_w, thought_w))
            
            header_rows = 4
            content_rows = h - header_rows
            if content_rows < 1:
                content_rows = 1
            
            all_chat_lines = []
            for entry in self.chat_history:
                wrapped = self._wrap_text(entry, chat_w)
                all_chat_lines.extend(wrapped)
            
            all_thought_lines = []
            for entry in self.thought_history:
                wrapped = self._wrap_text(entry, thought_w)
                all_thought_lines.extend(wrapped)
            
            chat_lines = all_chat_lines[-content_rows:]
            thought_lines = all_thought_lines[-content_rows:]
            
            for i in range(content_rows):
                chat_line = chat_lines[i] if i < len(chat_lines) else ""
                thought_line = thought_lines[i] if i < len(thought_lines) else ""
                
                chat_clean = self._strip(chat_line)[:chat_w]
                thought_clean = self._strip(thought_line)[:thought_w]
                
                chat_padded = chat_clean.ljust(chat_w)
                thought_padded = thought_clean.ljust(thought_w)
                
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
                
                full_line = "".join(line_parts)
                lines_to_render.append(full_line)
            
            lines_to_render.append(self._build_divider())
            
            for line in lines_to_render:
                line_stripped = self._strip(line)
                if len(line_stripped) < w:
                    line += " " * (w - len(line_stripped))
                print(line)
            
            sys.stdout.write(f"  {Colors.BOLD}{Colors.BLUE}You:{Colors.RESET} ")
            sys.stdout.flush()

    def _add_chat(self, msg):
        self.chat_history.append(msg)
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-100:]

    def _add_thought(self, msg):
        self.thought_history.append(msg)
        if len(self.thought_history) > 100:
            self.thought_history = self.thought_history[-100:]

    def _on_response(self, response):
        rtype = response.get("type", "")
        if rtype == "chat":
            r = response.get("response", "")
            r = " ".join(r.split())
            if r:
                self._add_chat(f"{Colors.GREEN}AI:{Colors.RESET} {r}")
            self._resume()
        elif rtype == "error":
            err = response.get("error", "")
            if err:
                self._add_chat(f"{Colors.RED}Error:{Colors.RESET} {err}")
            self._resume()
        elif rtype == "internal_thought":
            t = response.get("thought", "")
            if t:
                self._add_thought(f"{Colors.YELLOW}{t}{Colors.RESET}")
        elif rtype == "autonomous_message":
            msg = response.get("message", "")
            if msg:
                self._add_chat(f"{Colors.CYAN}AI:{Colors.RESET} {msg}")
        elif rtype == "gan_complete":
            gan_result = response.get("gan_result", {})
            should, msg = self.thinking_engine.should_proactively_speak(self.memory, gan_result)
            if should and msg:
                self._add_chat(f"{Colors.CYAN}AI:{Colors.RESET} {msg}")
        self._render()

    def _on_idle_callback(self, response):
        rtype = response.get("type", "")
        if rtype == "internal_thought":
            t = response.get("thought", "")
            if t:
                self._add_thought(f"{Colors.YELLOW}{t}{Colors.RESET}")
        elif rtype == "gan_topic":
            topic = response.get("topic", "")
            if topic:
                self._add_thought(f"{Colors.CYAN}[T]{Colors.RESET} {topic}")
        elif rtype == "gan_argument":
            arg = response.get("argument", "")
            if arg:
                self._add_thought(f"{Colors.GREEN}[A]{Colors.RESET} {arg}")
        elif rtype == "gan_counter":
            counter = response.get("counter", "")
            if counter:
                self._add_thought(f"{Colors.RED}[C]{Colors.RESET} {counter}")
        elif rtype == "gan_rebuttal":
            rebuttal = response.get("rebuttal", "")
            if rebuttal:
                self._add_thought(f"{Colors.MAGENTA}[R]{Colors.RESET} {rebuttal}")
        elif rtype == "gan_complete":
            gan_result = response.get("gan_result", {})
            should, msg = self.thinking_engine.should_proactively_speak(self.memory, gan_result)
            if should and msg:
                self._add_chat(f"{Colors.CYAN}AI:{Colors.RESET} {msg}")
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

        self._add_chat(f"{Colors.BLUE}You:{Colors.RESET} {text}")
        add(self.memory, "user", text)
        save_memory(self.memory)
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
        cmd = cmd.lower().strip()
        
        if cmd == "/help":
            self._add_chat(f"{Colors.ORANGE}Commands:{Colors.RESET} /help /mem /status /quit")
        elif cmd == "/mem":
            msgs = self.memory.get("messages", [])[-3:]
            if msgs:
                for m in msgs:
                    self._add_chat(f"{Colors.GRAY}{m.get('role')}: {m.get('content', '')[:50]}{Colors.RESET}")
            else:
                self._add_chat(f"{Colors.GRAY}No memory{Colors.RESET}")
        elif cmd == "/status":
            self._add_chat(f"GAN: {'ON' if self.gan_enabled else 'OFF'} | Msgs: {len(self.memory.get('messages', []))}")
        elif cmd == "/quit":
            self.running = False
        else:
            self._add_chat(f"{Colors.RED}Unknown: {cmd}{Colors.RESET}")

    def _shutdown(self):
        save_memory(self.memory)
        
        self._clear_screen()
        for line in self._initial_lines:
            print(line)
        print()
        print(f"  {Colors.ORANGE}Goodbye!{Colors.RESET}")
        print()


if __name__ == "__main__":
    cli = HumanaizeCLI()
    cli.run()
