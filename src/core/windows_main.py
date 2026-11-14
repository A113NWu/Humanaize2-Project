"""Humanaize Windows 浏览器管理面板启动入口。"""

import sys
import os
import re
from datetime import datetime, timedelta

# PyInstaller --windowed 模式下 sys.stdout/stderr 可能为 None，需要修复
# 否则 loguru 等库尝试添加 sys.stdout 作为 sink 时会报 TypeError
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")


def _sanitize_sys_path():
    """避免脏的旧 QQ/AstrBot 路径覆盖项目本身的 main 模块。"""
    blocked_tokens = ("qq-chat", "astrbot")
    cleaned = []
    for entry in sys.path:
        if not entry:
            continue
        normalized = os.path.normcase(os.path.normpath(entry))
        if any(token in normalized for token in blocked_tokens):
            continue
        cleaned.append(entry)
    sys.path[:] = cleaned

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    sys.path.insert(0, src_dir)


_sanitize_sys_path()

# Source modules use both ``tools.*`` and ``core.tools.*`` depending on the
# startup path. Keep one package identity in the frozen Windows process.
try:
    import core.tools as _core_tools
    sys.modules.setdefault("tools", _core_tools)
except ImportError:
    pass

for _package_name in ("llm", "memory", "Prompt", "data", "config"):
    try:
        _package = __import__(f"core.{_package_name}", fromlist=[_package_name])
        sys.modules.setdefault(_package_name, _package)
    except ImportError:
        pass


def _find_ancestor_console_pid():
    """沿進程樹向上尋找命令列 shell（cmd/powershell/WindowsTerminal）的 PID。

    onefile 的 bootloader 會派生真正的應用進程，此時直接 AttachConsole(-1)
    只會附加到沒有控制台的 bootloader，導彈新窗口。跳過它附加到調用者的
    cmd/PowerShell 控制台，才能在原窗口內運行 CLI。
    """
    import ctypes
    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    kernel32 = ctypes.windll.kernel32

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE_VALUE:
        return None

    parents = {}
    names = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            names[entry.th32ProcessID] = entry.szExeFile.lower()
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)

    shell_names = ("cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe")
    pid = kernel32.GetCurrentProcessId()
    for _ in range(8):
        pid = parents.get(pid)
        if not pid:
            break
        if names.get(pid) in shell_names:
            return pid
    return None


def _enable_ansi_colors():
    """附加到既有控制台後開啟 VT 轉義，保證 CLI 顏色正常。"""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass


def _show_log_window():
    """無參數默認啟動時彈出日誌窗口（AllocConsole），重定向標準流並開啟 VT 顏色。

    攔截窗口關閉（CTRL_CLOSE_EVENT）：點 X 不殺進程，而是 FreeConsole 藏起窗口，
    進程留在系統托盤。返回是否成功掛上控制台。"""
    import ctypes
    kernel32 = ctypes.windll.kernel32

    if not kernel32.GetConsoleWindow():
        try:
            if not kernel32.AllocConsole():
                return False
        except Exception:
            return False

    kernel32.SetConsoleTitleW("Humanaize2 日誌")

    def _on_console_close(ctrl_type):
        # CTRL_CLOSE_EVENT=2 / CTRL_LOGOFF_EVENT=5 / CTRL_SHUTDOWN_EVENT=6
        if ctrl_type in (2, 5, 6):
            try:
                sys.stdout = open(os.devnull, "w")
                sys.stderr = open(os.devnull, "w")
            except Exception:
                pass
            kernel32.FreeConsole()
            return True  # 阻止默認的進程終止
        return False

    global _console_close_handler  # 必須保持引用，防 GC 回收回調
    _console_close_handler = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(_on_console_close)
    kernel32.SetConsoleCtrlHandler(_console_close_handler, True)

    try:
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1, errors="replace")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1, errors="replace")
        _enable_ansi_colors()
        return True
    except Exception:
        return False


_console_close_handler = None


def _attach_parent_console():
    """打包的 --windowed exe 沒有控制台，CLI 模式需附加調用者所在的控制台，
    優先附加進程樹上的 cmd/PowerShell（兼容 onefile bootloader 派生場景），
    其次 ATTACH_PARENT_PROCESS；都失敗時才 AllocConsole 新建窗口。

    注意：通過 `start /b` 啟動時進程可能已直接繼承 cmd 的控制台，此時
    AttachConsole 會報 ERROR_ACCESS_DENIED——用 GetConsoleWindow 判斷，
    已擁有控制台就跳過附加，統一走後面的重開標準流邏輯。"""
    import ctypes
    kernel32 = ctypes.windll.kernel32

    if not kernel32.GetConsoleWindow():
        targets = [pid for pid in (_find_ancestor_console_pid(),) if pid]
        targets.append(-1)  # ATTACH_PARENT_PROCESS
        attached = False
        for target in targets:
            try:
                if kernel32.AttachConsole(target):
                    attached = True
                    break
            except Exception:
                continue
        if not attached:
            try:
                attached = bool(kernel32.AllocConsole())
                if attached:
                    kernel32.SetConsoleTitleW("Humanaize2 CLI")
            except Exception:
                attached = False
        if not attached:
            return False

    try:
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1, errors="replace")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1, errors="replace")
        _enable_ansi_colors()
        return True
    except Exception:
        return False


def _launch_desktop_window(dashboard_url):
    """啟動 MyGo 桌面端窗口（與網頁端 Dashboard 同界面）。

    桌面端是獨立的 WebView2 窗口，直接加載本地 Dashboard URL。
    找不到桌面端 exe 時（例如開發態）回退到瀏覽器打開，避免功能中斷。
    """
    import subprocess
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    desktop_exe = os.path.join(exe_dir, "Humanaize2-Desktop.exe")
    if os.path.exists(desktop_exe):
        try:
            subprocess.Popen([desktop_exe, dashboard_url], cwd=exe_dir)
            print(f"[INFO] Desktop window launched: {desktop_exe}")
            return
        except Exception as e:
            print(f"[WARN] failed to launch desktop window: {e}", file=sys.stderr)
    # 回退：開發態或桌面端未打包時，用瀏覽器打開
    try:
        webbrowser.open(dashboard_url)
    except Exception as e:
        print(f"[WARN] failed to open browser: {e}", file=sys.stderr)


def _setup_file_logging():
    """無日誌窗口啟動時，把 stdout/stderr 重定向到日誌文件，便於排查。

    日誌文件位於 data 目錄（開發態為項目 data/，安裝版為安裝目錄 data/），
    按日期滾動，保留最近 7 天。
    """
    # 日誌目錄：打包態為 exe 同級 data/logs，開發態為項目根 data/logs
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"humanaize2-{today}.log")

    # 清理 7 天前的日誌
    try:
        cutoff = datetime.now() - timedelta(days=7)
        for name in os.listdir(log_dir):
            m = re.match(r"humanaize2-(\d{4}-\d{2}-\d{2})\.log$", name)
            if m:
                try:
                    if datetime.strptime(m.group(1), "%Y-%m-%d") < cutoff:
                        os.remove(os.path.join(log_dir, name))
                except Exception:
                    pass
    except Exception:
        pass

    try:
        fp = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = fp
        sys.stderr = fp
        print(f"\n===== Humanaize2 启动 {datetime.now().isoformat(timespec='seconds')} =====")
        return log_path
    except Exception:
        return None


def main():
    """啟動後端服務並打開 MyGo 桌面端；默認不彈日誌窗口，日誌寫入文件。"""
    # --show-log：顯式彈出日誌控制台窗口（便於現場調試）
    _show_log = "--show-log" in sys.argv[1:]
    # --tray / --no-console：向後兼容，等同於默認行為（無日誌窗口）
    _tray_flags = {"--tray", "--no-console"}

    # 帶參數（boot -m cli / boot -m gui / settings / solve 等）時交給 core/main.py
    # 的 dispatch，修復打包版 CLI 模式無法啟動的問題。
    _other_args = [a for a in sys.argv[1:] if a not in _tray_flags and a != "--show-log"]
    if _other_args:
        _attach_parent_console()
        from main import main as core_main
        core_main()
        return

    # 默認啟動：隱藏日誌窗口，日誌寫文件；只有 --show-log 才彈控制台
    if _show_log:
        _show_log_window()
    else:
        _setup_file_logging()

    # 检查并启动 LLM 服务器
    from core.main import _check_and_start_server
    _check_and_start_server()
    
    # 后台检查更新
    from main import _check_updates_background
    _check_updates_background()
    
    import warnings
    warnings.filterwarnings("ignore")
    
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
    
    try:
        import tensorflow as tf
        tf.get_logger().setLevel('ERROR')
    except:
        pass
    
    from memory.memory import load_memory
    from core.personality import load_personality
    from core.thinking_engine import ThinkingEngine
    from thinking_engine_api import ThinkingEngineState, start_api_server
    import webbrowser

    memory = load_memory()
    personality = load_personality()
    thinking_engine = ThinkingEngine()
    thinking_engine.set_language("zh")

    state = ThinkingEngineState()
    state.set_thinking_engine(thinking_engine)
    state.set_memory(memory)
    state.set_personality(personality)
    # 綁定 0.0.0.0：局域網訪問由請求級門禁控制（設置→安全性，默認拒絕），開關熱生效
    server = start_api_server(host='0.0.0.0', port=8082)

    # 後台預熱本地 Kokoro TTS（模型加載約 15-25 秒，提前加載避免首次朗讀卡住）
    try:
        from voice.kokoro_tts import KokoroTTS
        KokoroTTS.instance().warmup_async()
    except Exception as _warm_err_1:
        try:
            from core.voice.kokoro_tts import KokoroTTS
            KokoroTTS.instance().warmup_async()
        except Exception as _warm_err_2:
            print("[TTS] 預熱調用失敗: %r / %r" % (_warm_err_1, _warm_err_2),
                  file=sys.stderr, flush=True)

    # 啟動閒置引擎：網頁模式過去缺少它，導致 Aize 的閒置 GAN 思考與
    # [Social] 社交事件完全不會發生，GAN 面板自然也沒有內容。
    # 回調把事件推進 API 進程級事件匯流排（/api/events SSE 即時推送網頁），
    # 閒置引擎自身的活動/社交/綜合結論同時寫入記憶（重新整理頁面仍有歷史）。
    import json as _json
    from ui.idle import IdleEngine
    from memory import add_thought, save_memory
    from thinking_engine_api import publish_engine_event, classify_idle_thought_type

    def _read_gan_enabled():
        try:
            from app_paths import get_settings_path
            with open(get_settings_path(), "r", encoding="utf-8") as settings_file:
                return bool(_json.load(settings_file).get("gan_enabled", True))
        except Exception:
            return True

    def _idle_event_callback(response):
        try:
            publish_engine_event(response)
            if not isinstance(response, dict):
                return
            if response.get("type") == "internal_thought":
                thought = response.get("thought", "") or ""
                # GAN 辯論子步驟（帶 original_event）只作臨時日誌，不寫入記憶；
                # 持久化閒置活動選擇、[Social]、綜合結論等引擎自身消息
                if thought and "original_event" not in response:
                    ttype = classify_idle_thought_type(thought, response.get("thought_type", ""))
                    add_thought(memory, thought, thought_type=ttype)
                    save_memory(memory)
        except Exception as e:
            print(f"[WARN] idle event callback failed: {e}")

    idle_engine = IdleEngine(
        memory,
        _idle_event_callback,
        idle_interval=300,
        gan_enabled=_read_gan_enabled(),
    )

    # 打破沉默（主動開口）看門狗：網頁模式的閒置引擎只在 GAN 隨機選到
    # 「找用戶說話」時才會開口，命中率低且被 GAN 拖得很慢，實際表現就是
    # 長期很安靜。這裡用輕量線程按「距上次用戶消息」判斷，決策後直接排
    # break_silence 任務，結果經事件匯流排推到網頁/手機。
    def _start_silence_watcher():
        import threading
        import time as _time
        import autonomous as _auto

        last_speak = {"t": 0.0}

        def _loop():
            while True:
                try:
                    _time.sleep(10)
                    # 10 分鐘內主動過一次就不再重複，避免刷屏
                    if _time.time() - last_speak["t"] < 600:
                        continue
                    res = _auto.check_silence_and_decide(memory, 600)
                    if not res:
                        continue
                    msgs = (memory or {}).get("messages", [])[-8:]
                    ctx = "最近對話:"
                    for m in msgs:
                        ctx += f"\n{m.get('role', '').capitalize()}: {str(m.get('content', ''))[:100]}"
                    recent = [str(m.get("content", ""))[:80] for m in msgs
                              if m.get("role") == "assistant"][-6:]
                    recent_self = "\n".join(f"- {t}" for t in recent) or "（暫無）"
                    prompt = (
                        f"{ctx}\n\n【最近你說過的話】\n{recent_self}\n\n"
                        f"【此刻的念頭】{res.get('message', '')}\n\n"
                        "主人已經一段時間沒說話了。現在主動開口，以開啟一個新話題為目的，"
                        "不要重複上面說過的句子，也不要每次都問同一類問題；一兩句話即可。"
                    )
                    thinking_engine.queue_break_silence_task(prompt, memory=memory)
                    last_speak["t"] = _time.time()
                    print(f"[INFO] 主動開口已排隊: {res.get('action')}")
                except Exception as e:
                    print(f"[WARN] silence watcher: {e}")

        threading.Thread(target=_loop, daemon=True, name="silence-watcher").start()

    _start_silence_watcher()

    # server.host 是監聽地址 0.0.0.0，不能直接給 WebView2/瀏覽器用；
    # 本機訪問一律走 127.0.0.1，局域網設備用自己的 IP 訪問 8082。
    dashboard_url = f"http://127.0.0.1:{server.port}/"
    print(f"[INFO] Dashboard started: {dashboard_url}")
    # 默認啟動 MyGo 桌面端窗口；用戶也可在瀏覽器訪問同 URL（局域網設備同理）
    _launch_desktop_window(dashboard_url)

    # 系統托盤：有日誌窗口時關閉窗口後靠托盤存活；--tray 啟動時只有托盤。
    # 消息循環必須跑在主線程（PumpMessages 阻塞），替代原先的 sleep 循環。
    from core.tray_icon import TrayIcon

    def _on_tray_exit():
        try:
            server.stop()
        except Exception:
            pass

    tray = TrayIcon(tooltip="Humanaize2", dashboard_url=dashboard_url, on_exit=_on_tray_exit)
    try:
        tray.run()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()