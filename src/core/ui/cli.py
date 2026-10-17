"""
Humanaize v2.0 - CLI 聊天介面（Claude Code 風格 TUI）

設計要點：
- 啟動清屏 + 簡潔 banner，對話內容正常滾動（不清屏）。
- 主線程唯一負責渲染：引擎/閒置/QQ 回調全部只入事件隊列。
- 輸入用原生 input()：IME/粘貼/退格由 Windows 自己處理，
  光標不做任何上移，輸入位置永不錯位；打字期間後台事件只入隊，
  回車後先播完再進入本輪對話。
- braille spinner + 流式句子：思考/正文隨產生隨顯示。
- 思考用彩色標籤行、閒置思考用 ├─/└─ 因果樹；
  技能調用是 ⏺ 膠囊行，緊跟縮進的 ⎿ 輸出，表達因果關係。
"""

import os
import sys
import shutil
import threading
import time
import unicodedata
import queue as queue_mod

from core.thinking_engine import ThinkingEngine
from memory import load_memory, save_memory, add
from core.personality import load_personality
from ui.idle import IdleEngine

try:
    from tools.logger import get_logger
except ImportError:
    from core.tools.logger import get_logger

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


class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    ORANGE = '\033[38;5;208m'
    BLUE = '\033[38;5;39m'
    GREEN = '\033[38;5;46m'
    RED = '\033[38;5;196m'
    YELLOW = '\033[38;5;226m'
    CYAN = '\033[38;5;51m'
    GRAY = '\033[90m'
    PURPLE = '\033[38;5;147m'
    GOLD = '\033[38;5;220m'
    PINK = '\033[38;5;213m'
    WHITE = '\033[97m'

    @classmethod
    def enable_vt(cls):
        if sys.platform != "win32":
            return True
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            k.GetConsoleMode(h, ctypes.byref(mode))
            mode.value |= 0x0004 | 0x0001  # VT_PROCESSING | PROCESSED_OUTPUT
            k.SetConsoleMode(h, mode)
            # 僅輸出改 UTF-8（box/braille 不亂碼）；
            # 輸入 CP 絕對不能動，否則中文 IME 候選詞送不進來
            try:
                k.SetConsoleOutputCP(65001)
            except Exception:
                pass
            return True
        except Exception:
            return False


def dwidth(ch: str) -> int:
    """字符的終端顯示寬度（列）。東亞全角/寬字符記 2 列。

    East Asian Width = Ambiguous 的字符（✻ ● · │ 等）在 Windows 下：
    Windows Terminal(xterm) 按 1 列，傳統 conhost(CJK 代碼頁) 按 2 列。
    WT 會設 WT_SESSION 環境變量，藉此區分，避免框線錯位。
    """
    if not ch:
        return 0
    ea = unicodedata.east_asian_width(ch)
    if ea in ("W", "F"):
        return 2
    if ea == "A" and sys.platform == "win32" and not os.environ.get("WT_SESSION"):
        o = ord(ch)
        # Box/Block/Braille/Misc Technical/Arrows 在傳統 conhost 下仍為 1 列；
        # 其餘 ambiguous（● ✻ · 等幾何/Dingbats 符號）才按 2 列計
        if ((0x2500 <= o <= 0x259F) or (0x2800 <= o <= 0x28FF)
                or (0x2300 <= o <= 0x23FF) or (0x2190 <= o <= 0x21FF)):
            return 1
        return 2
    if ord(ch) < 32:
        return 0
    return 1


def text_width(s: str) -> int:
    return sum(dwidth(ch) for ch in s)


SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# internal_thought 文本自帶 [Xxx] 前綴時的中文標籤
BRACKET_LABELS = [
    ("Idle Activity", "活動"),
    ("Thinking Direction", "方向"),
    ("Self-thought", "結論"),
    ("Social", "社交"),
    ("Solve Mode", "Solve"),
    ("Self-Optimization", "優化"),
    ("Auto-Optimization", "優化"),
    ("Break Silence", "閒置"),
]
TYPE_LABELS = {
    "gan_topic": ("議題", C.GOLD),
    "gan_argument": ("正方", C.BLUE),
    "gan_counter_argument": ("反方", C.PINK),
    "gan_counter": ("反方", C.PINK),
    "gan_rebuttal": ("反方", C.PINK),
    "gan_synthesis": ("綜合", C.GREEN),
    "break_silence": ("閒置", C.ORANGE),
    "reflection": ("反思", C.PURPLE),
    "solve_mode": ("Solve", C.CYAN),
    "internal": ("思考", C.YELLOW),
}


def parse_thought(text: str, ttype: str = "internal"):
    """從思考文本提取 (標籤, 正文)。"""
    t = (text or "").strip()
    label, color = TYPE_LABELS.get(ttype, ("思考", C.YELLOW))
    if t.startswith("["):
        close = t.find("]")
        if 0 < close < 40:
            tag = t[1:close]
            body = t[close + 1:].strip()
            for eng, zh in BRACKET_LABELS:
                if eng.lower() in tag.lower():
                    label = zh
                    break
            else:
                label = tag[:12]
            return label, color, body
    return label, color, t


class Render:
    """live 區渲染器：spinner 恆為最後一行，永久內容打印在其上方。"""

    def __init__(self, ui):
        self.ui = ui
        self.spinner_on = False
        self.phase = "Aize 思考中…"
        self.reply_active = False   # 光標是否停在正文流式行尾
        self.frame = 0
        self.last_tick = 0.0

    def c(self, code, s):
        return self.ui.c(code, s)

    def _erase_spinner(self):
        if self.spinner_on:
            sys.stdout.write("\r\033[K")
            self.spinner_on = False

    def _break_reply(self):
        """流式正文行結束：補一個換行，後續內容另起一行。"""
        if self.reply_active:
            sys.stdout.write("\n")
            self.reply_active = False

    def set_phase(self, text):
        self.phase = text

    def tick(self, force=False):
        # 正文流式輸出期間不顯示 spinner（否則幀文字會殘留在句子中間）
        if self.reply_active:
            return
        now = time.monotonic()
        if not force and now - self.last_tick < 0.07:
            return
        self.last_tick = now
        glyph = SPINNER_FRAMES[self.frame % len(SPINNER_FRAMES)]
        self.frame += 1
        sys.stdout.write("\r\033[K" + self.c(C.ORANGE + C.BOLD, glyph)
                         + " " + self.c(C.GRAY, self.phase))
        sys.stdout.flush()
        self.spinner_on = True

    def line(self, text):
        """普通永久行。"""
        self._erase_spinner()
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    def thought(self, label, color, body, tree=None):
        """思考行：縮進 + 彩色標籤。tree=None 普通；'mid'/'end' 為因果樹接頭。"""
        self._break_reply()
        self._erase_spinner()
        tag = self.c(color + C.BOLD, label)
        if tree == "mid":
            prefix = self.c(C.GRAY, " ├─ ")
        elif tree == "end":
            prefix = self.c(C.GRAY, " └─ ")
        else:
            prefix = "  "
        sys.stdout.write(prefix + self.c(C.DIM + C.PURPLE, tag)
                         + self.c(C.GRAY, "  " + body) + "\n")
        sys.stdout.flush()

    def tool(self, name, hint=""):
        self._break_reply()
        self._erase_spinner()
        s = "  " + self.c(C.ORANGE + C.BOLD, "⏺ " + name)
        if hint:
            s += self.c(C.GRAY, "  " + hint)
        sys.stdout.write(s + "\n")
        sys.stdout.flush()

    def result(self, text):
        self._erase_spinner()
        lines = [ln for ln in (text or "").splitlines() if ln.strip()]
        if not lines:
            lines = ["（無輸出）"]
        for i, ln in enumerate(lines[:6]):
            if len(ln) > 110:
                ln = ln[:110] + "…"
            sys.stdout.write(self.c(C.GRAY, "    ⎿ " + ln) + "\n")
        if len(lines) > 6:
            sys.stdout.write(self.c(C.GRAY, f"    ⎿ …（其餘 {len(lines) - 6} 行已省略）") + "\n")
        sys.stdout.flush()

    def sentence(self, text, user_turn=True):
        """流式句子：用戶 turn 正文直接出；主動開口用 ✦ 前綴。"""
        if not text:
            return
        if not self.reply_active:
            self._erase_spinner()
            if not user_turn:
                sys.stdout.write(self.c(C.CYAN + C.BOLD, "✦ "))
        sys.stdout.write(text)
        sys.stdout.flush()
        self.reply_active = True

    def error(self, text):
        self._break_reply()
        self._erase_spinner()
        sys.stdout.write(self.c(C.RED, "  ✗ " + text) + "\n")
        sys.stdout.flush()

    def sys(self, text):
        self._break_reply()
        self._erase_spinner()
        sys.stdout.write(self.c(C.DIM, "· " + text) + "\n")
        sys.stdout.flush()

    def finish(self):
        self._break_reply()
        self._erase_spinner()


class HumanaizeCLI:
    def __init__(self):
        self.memory = load_memory()
        self.personality = load_personality()
        self.settings = self._load_settings()
        self.gan_enabled = self.settings.get("gan_enabled", True)
        self.language = self.settings.get("language", "Chinese")

        self.running = True
        self._evq = queue_mod.Queue()   # 所有外部回調的統一事件隊列

        # 句子去重：chat_response 與 stream callback 往往成對攜帶同一句
        self._last_chat_sentence = None
        self._last_stream_sentence = None

        self.thinking_engine = ThinkingEngine(on_response_callback=self._on_engine_response)
        self.thinking_engine.register_stream_callback(self._on_stream_sentence)

        try:
            from core.thinking_engine_api import ThinkingEngineState, start_api_server
            # CLI 模式下屏蔽 web API 的 HTTP 請求日誌，避免干擾聊天介面；
            # 日誌仍會寫入文件，不影響排查。
            get_logger().suppress_console_patterns(["[http]"])
            state = ThinkingEngineState()
            state.set_thinking_engine(self.thinking_engine)
            state.set_memory(self.memory)
            state.set_personality(self.personality)
            start_api_server(host='127.0.0.1', port=8082)
            self._emit(("sys", "ThinkingEngine API: http://127.0.0.1:8082"))
        except Exception as e:
            self._emit(("sys", f"API server 未啟動: {e}"))

        if QQ_SKILL_AVAILABLE:
            _qq_skill.set_thinking_engine(self.thinking_engine)
            _qq_skill.set_memory(self.memory)
            _qq_skill.set_ui_callback(self._handle_qq_message)
            _qq_skill.start_listener()
            self._emit(("sys", "QQ skill 已啟動"))

        self.idle_engine = None
        if self.gan_enabled:
            self.idle_engine = IdleEngine(
                memory=self.memory,
                callback=self._on_idle_response,
                idle_interval=300,
                gan_enabled=True
            )

        self.use_color = C.enable_vt()

    # ==================== 基礎 ====================

    def _load_settings(self):
        try:
            import json
            path = os.path.join(os.path.dirname(__file__), "data", "settings.json")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"gan_enabled": True, "auto_break_silence": True}

    def c(self, code, text):
        if not self.use_color:
            return text
        return f"{code}{text}{C.RESET}"

    def term_width(self):
        try:
            return max(40, shutil.get_terminal_size().columns)
        except Exception:
            return 80

    def box_width(self):
        return min(self.term_width() - 2, 72)

    def _emit(self, event):
        self._evq.put(event)

    # ==================== 回調（任意線程，只入隊） ====================

    def _on_stream_sentence(self, sentence, target_info=None):
        if sentence:
            self._emit(("stream", str(sentence)))

    def _map_response(self, response):
        """引擎/閒置回調 dict → 標準事件 tuple（或 None 忽略）。"""
        rtype = response.get("type", "")

        if rtype == "task_done":
            return ("done",)
        if rtype in ("chat_response", "chat"):
            r = response.get("reply", "") if rtype == "chat_response" else response.get("response", "")
            r = " ".join(str(r).split())
            return ("sentence", r) if r else None
        if rtype == "error":
            return ("error", str(response.get("error", ""))) if response.get("error") else None
        if rtype == "bug_repair":
            return ("sys", f"bug 狀態={response.get('status', 'reported')}，{response.get('message', '')}")
        if rtype == "autonomous_message":
            msg = str(response.get("message", "")).strip()
            return ("auto", msg) if msg else None
        if rtype == "internal_thought":
            t = str(response.get("thought", ""))
            label, color, body = parse_thought(t, response.get("thought_type", "internal"))
            return ("thought", label, color, body) if body or label else None
        if rtype in ("gan_topic", "gan_argument", "gan_counter_argument",
                     "gan_counter", "gan_rebuttal", "gan_synthesis"):
            key = rtype
            val = (response.get("gan_" + rtype.replace("gan_", ""))
                   or response.get(rtype.replace("gan_", ""), "")
                   or response.get("topic", ""))
            val = str(val).strip()
            if not val:
                return None
            label, color = TYPE_LABELS[key][0], TYPE_LABELS[key][1]
            return ("thought", label, color, val)
        if rtype == "gan_complete":
            return ("gan_complete", response.get("gan_result", {}))
        if rtype == "command_start":
            msg = str(response.get("message", ""))
            if "next step" in msg:
                import re as _re
                m = _re.search(r"round\s*(\d+)", msg)
                return ("phase", f"思考下一步（第 {m.group(1)} 輪）…" if m else "思考下一步…")
            return ("tool", "Skill", "執行中…")
        if rtype == "command_result":
            out = str(response.get("output", ""))
            return ("result", out) if out.strip() else None
        if rtype == "idle_begin":
            return ("idle_begin",)
        if rtype == "idle_end":
            return ("idle_end",)
        return None

    def _on_engine_response(self, response):
        try:
            ev = self._map_response(response)
            if ev:
                self._emit(ev)
        except Exception:
            pass

    def _on_idle_response(self, response):
        try:
            rtype = response.get("type", "")
            if rtype == "gan_complete":
                # 閒置 GAN 完成：由 Aize 決定是否主動開口
                gan_result = response.get("gan_result", {})
                self._emit(("gan_complete_idle", gan_result))
                return
            ev = self._map_response(response)
            if ev:
                self._emit(ev)
        except Exception:
            pass

    def _handle_qq_message(self, msg):
        try:
            sender = msg.get('from', 'Unknown')
            text = msg.get('message', '')
            arrow = "QQ→" if msg.get('type') == 'sent' else "QQ←"
            self._emit(("external", f"[{arrow}] {sender}: {text}"))
        except Exception:
            pass

    # ==================== 事件消費（主線程） ====================

    def _drain_queue(self):
        events = []
        while True:
            try:
                events.append(self._evq.get_nowait())
            except queue_mod.Empty:
                break
        return events

    def _apply_event(self, ev, r: Render, state: dict):
        """在 live 區中渲染一條事件。返回 False 表示應結束 live。"""
        kind = ev[0]

        if kind == "done":
            return False
        if kind == "idle_end":
            state["idle"] = False
            r.thought("完成", C.GREEN, "本次閒置思考結束", tree="end")
            return False
        if kind == "phase":
            r.set_phase(ev[1])
        elif kind == "sentence":
            if self._last_stream_sentence == ev[1]:
                return True
            self._last_chat_sentence = ev[1]
            r.sentence(ev[1], user_turn=state.get("user_turn", True))
        elif kind == "stream":
            if self._last_chat_sentence == ev[1]:
                return True
            self._last_stream_sentence = ev[1]
            r.sentence(ev[1], user_turn=state.get("user_turn", True))
        elif kind == "thought":
            _, label, color, body = ev
            tree = "mid" if state.get("idle") else None
            r.thought(label, color, body, tree=tree)
            if state.get("idle"):
                r.set_phase("閒置思考中…")
            elif label in ("議題", "正方", "反方", "綜合"):
                r.set_phase("GAN 思考中…")
        elif kind == "tool":
            r.tool(ev[1], ev[2] if len(ev) > 2 else "")
            r.set_phase("執行技能中…")
        elif kind == "result":
            r.result(ev[1])
        elif kind == "error":
            r.error(ev[1])
        elif kind == "sys":
            r.sys(ev[1])
        elif kind == "auto":
            r.sentence(ev[1], user_turn=False)
        elif kind == "external":
            r.sys(ev[1])
        elif kind == "gan_complete":
            # 用戶 turn 中的 GAN 完成（少見路徑）
            try:
                should, msg = self.thinking_engine.should_proactively_speak(self.memory, ev[1])
                if should and msg:
                    r.sentence(str(msg), user_turn=True)
            except Exception:
                pass
        elif kind == "gan_complete_idle":
            try:
                should, msg = self.thinking_engine.should_proactively_speak(self.memory, ev[1])
                if should and msg:
                    r.sentence(str(msg), user_turn=False)
            except Exception:
                pass
        return True

    def _live(self, user_turn=False, idle=False, seed_events=None):
        """消費事件並實時渲染。

        user_turn=True：跑到 task_done。
        外部事件（閒置/QQ/主動開口）：idle 模式跑到 idle_end；
        其餘分片在 2 秒安靜後暫停，把控制權交回輸入行（後續事件再開新分片）。
        """
        r = Render(self)
        state = {"idle": idle, "user_turn": user_turn}
        r.set_phase("閒置思考中…" if idle else "Aize 思考中…")

        pending = list(seed_events or [])
        if idle:
            r.line("  " + self.c(C.CYAN + C.BOLD, "✻ 閒置思考"))
            r.thought("開始", C.CYAN, "Aize 開始自主思考", tree="mid")

        last_event = time.monotonic()
        while True:
            if pending:
                ev = pending.pop(0)
            else:
                try:
                    ev = self._evq.get(timeout=0.05)
                except queue_mod.Empty:
                    r.tick()
                    if not user_turn and not state["idle"] and \
                            time.monotonic() - last_event > 2.0:
                        break
                    continue
            last_event = time.monotonic()
            if ev[0] == "idle_begin":
                if not state["idle"]:
                    state["idle"] = True
                    r.line("  " + self.c(C.CYAN + C.BOLD, "✻ 閒置思考"))
                    r.thought("開始", C.CYAN, "Aize 開始自主思考", tree="mid")
                continue
            if not self._apply_event(ev, r, state):
                break
            r.tick(force=True)
        r.finish()

    # ==================== 輸入行（原生 input，IME/粘貼/退格由系統處理） ====================

    def _prompt_prefix(self):
        """輸入前綴：│ > （4 列窄字符，與頂邊 ╭ 同列起，天然對齊）。"""
        return self.c(C.DIM, "│") + " " + self.c(C.BOLD + C.ORANGE, ">") + " "

    def _draw_input_top(self):
        w = self.box_width()
        sys.stdout.write(self.c(C.DIM, "╭" + "─" * w + "╮") + "\n")
        sys.stdout.flush()

    def _draw_input_bottom(self):
        w = self.box_width()
        sys.stdout.write(self.c(C.DIM, "╰" + "─" * w + "╯") + "\n")
        sys.stdout.flush()

    # ==================== 對話流程 ====================

    def _pause_idle(self):
        if self.idle_engine:
            self.idle_engine.pause()

    def _resume_idle(self):
        if self.idle_engine:
            self.idle_engine.resume()

    def _start_user_turn(self, text):
        """後台線程做「要不要回答」決策 + 入隊；live 期間 spinner 不卡。"""
        self._pause_idle()
        self._last_chat_sentence = None
        self._last_stream_sentence = None

        def worker():
            try:
                should, _reason = self.thinking_engine.should_answer_user(text)
            except Exception:
                should = True
            if not should:
                self._emit(("sys", "Aize 選擇不回應這次輸入"))
                self._emit(("done",))
                self._resume_idle()
                return
            add(self.memory, "user", text)
            save_memory(self.memory)
            prompt = f"\n\nUser: {text}\nAssistant:"
            try:
                if self.gan_enabled:
                    self.thinking_engine.queue_chat_task(
                        prompt, memory=self.memory,
                        use_gan_decision=True, user_text=text)
                else:
                    self.thinking_engine.queue_chat_task(prompt, memory=self.memory)
            except TypeError:
                self.thinking_engine.queue_chat_task(prompt)

        threading.Thread(target=worker, daemon=True).start()

    # ==================== 斜槓指令 ====================

    def _t(self, key):
        zh = {
            "no_reply": "Aize 選擇不回應這次輸入",
            "available_commands": "可用指令",
            "show_help": "說明", "show_memory": "最近記憶",
            "show_status": "系統狀態", "toggle_gan": "切換 GAN",
            "clear_screen": "清屏", "quit_program": "退出",
            "no_memory_data": "無記憶資料",
            "system_status": "系統狀態",
            "enabled": "開啟", "disabled": "關閉",
            "message_count": "消息", "thought_count": "思考",
            "gan_toggled": "GAN 已{}",
            "shutdown": "Aize 已關閉，對話已保存，再見！",
        }
        return zh.get(key, key)

    def _cmd(self, raw):
        cmd = raw.lower().strip()
        if cmd == "/help":
            print(self.c(C.BOLD + C.ORANGE, "  " + self._t('available_commands')))
            for ctext, d in [("/help", "show_help"), ("/mem", "show_memory"),
                             ("/status", "show_status"), ("/gan", "toggle_gan"),
                             ("/clear", "clear_screen"), ("/quit", "quit_program")]:
                print(f"    {self.c(C.BLUE, ctext.ljust(8))} {self.c(C.GRAY, self._t(d))}")
        elif cmd == "/mem":
            msgs = self.memory.get("messages", [])[-5:]
            if msgs:
                for m in msgs:
                    content = (m.get('content', '') or '')[:60]
                    t = (m.get('time', '') or '')[:19]
                    print(self.c(C.GRAY, f"  [{t}] {m.get('role', '?')}: {content}"))
            else:
                print(self.c(C.GRAY, "  " + self._t('no_memory_data')))
        elif cmd == "/status":
            gan_status = self._t('enabled') if self.gan_enabled else self._t('disabled')
            print(self.c(C.BOLD, "  " + self._t('system_status')))
            print(f"    GAN:          {self.c(C.GREEN if self.gan_enabled else C.RED, gan_status)}")
            print(f"    {self._t('message_count')}:        {self.c(C.BLUE, str(len(self.memory.get('messages', []))))}")
            print(f"    {self._t('thought_count')}:        {self.c(C.MAGENTA, str(len(self.memory.get('thoughts', []))))}")
            print(f"    Name:         {self.c(C.CYAN, self.personality.get('name', 'Aize'))}")
        elif cmd == "/gan":
            self.gan_enabled = not self.gan_enabled
            status = self._t('enabled') if self.gan_enabled else self._t('disabled')
            print("  " + self.c(C.ORANGE, self._t('gan_toggled').format(status)))
        elif cmd == "/clear":
            self._clear_screen()
            self._print_banner()
        elif cmd == "/quit":
            self.running = False
        else:
            print(self.c(C.RED, f"  未知指令: {cmd}（/help 查看可用指令）"))

    # ==================== 啟動外觀 ====================

    def _clear_screen(self):
        if self.use_color:
            sys.stdout.write("\033[2J\033[3J\033[H")
            sys.stdout.flush()
        elif sys.platform == "win32":
            os.system("cls")

    def _print_banner(self):
        w = min(max(self.term_width() - 4, 40), 52)
        name = self.personality.get("name", "Aize")
        gan = "ON" if self.gan_enabled else "OFF"
        gan_col = C.GREEN if self.gan_enabled else C.GRAY
        rows = [
            self.c(C.BOLD + C.ORANGE, "✻ ") + self.c(C.BOLD, f"Welcome to Humanaize v{get_version()}"),
            "",
            self.c(C.GRAY, f"{name}   ")
            + self.c(gan_col, f"GAN: {gan}")
            + self.c(C.GRAY, "   /help 查看指令   Ctrl+C 退出"),
        ]
        top = self.c(C.DIM, "╭" + "─" * w + "╮")
        bot = self.c(C.DIM, "╰" + "─" * w + "╯")
        print(top)
        for row in rows:
            pad = w - 2 - text_width(self._strip_ansi(row))
            print(self.c(C.DIM, "│") + " " + row + " " * max(pad - 1, 1) + self.c(C.DIM, "│"))
        print(bot)
        print()

    @staticmethod
    def _strip_ansi(s):
        import re
        return re.sub(r"\033\[[0-9;]*m", "", s)

    # ==================== 主循環 ====================

    def run(self):
        if sys.stdin is None:
            print("無法取得控制台輸入。請在命令提示符（cmd）中執行：humanaize2 boot -m cli")
            return

        # 關鍵：穿透 logger.redirect_output() 的按行包裝器，直達真實控制台。
        # 包裝器把每個無換行 write 在 flush 時強制補 \n——spinner 會刷屏、
        # input 提示符與系統回顯錯位；TUI 的 \r/ANSI 必須直寫真實控制台。
        sys.stdout = getattr(sys.stdout, "original_stream", None) or sys.__stdout__ or sys.stdout

        self._clear_screen()
        self._print_banner()

        # 啟動階段遲到的系統事件（API/QQ 提示）在進入輸入框前顯示
        seed = self._drain_queue()
        if seed:
            self._live(user_turn=False, idle=False, seed_events=seed)
            print()

        while self.running:
            try:
                self._draw_input_top()
                # 原生 input：先直寫前綴並 flush，系統回顯的字符必然緊跟其後；
                # 打字期間後台事件只入隊，回車後先播完再進入本輪
                sys.stdout.write(self._prompt_prefix())
                sys.stdout.flush()
                user_input = input()
                self._draw_input_bottom()

                ext = self._drain_queue()
                if ext:
                    idle = any(e[0] == "idle_begin" for e in ext)
                    self._live(user_turn=False, idle=idle, seed_events=ext)
                    print()

                text = user_input.strip()
                if not text:
                    continue
                if text.startswith("/"):
                    self._cmd(text)
                    continue

                # 用戶氣泡（Claude Code 風格：⏺ + 白色粗體）
                print("  " + self.c(C.BOLD + C.ORANGE, "⏺") + " "
                      + self.c(C.BOLD + C.WHITE, text))
                self._start_user_turn(text)
                self._live(user_turn=True)
                self._resume_idle()

            except KeyboardInterrupt:
                print()
                break
            except EOFError:
                break
            except RuntimeError:
                print("控制台輸入已斷開，請在命令提示符（cmd）中重新執行：humanaize2 boot -m cli")
                break

        self._shutdown()

    def _shutdown(self):
        save_memory(self.memory)
        print()
        print(self.c(C.GRAY, "✻ " + self._t('shutdown')))


if __name__ == "__main__":
    HumanaizeCLI().run()
