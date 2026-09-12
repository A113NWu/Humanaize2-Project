"""Humanaize Windows 浏览器管理面板启动入口。"""

import sys
import os

# PyInstaller --windowed 模式下 sys.stdout/stderr 可能为 None，需要修复
# 否则 loguru 等库尝试添加 sys.stdout 作为 sink 时会报 TypeError
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# 打包（onefile）環境：把捆綁的 ui_settings.json 補到各模組以 __file__ 相對路徑查找的位置，
# 否則 llm/ui/cli_settings/thinking_engine 等在解包目錄中讀不到設定。
if getattr(sys, "_MEIPASS", None):
    import shutil as _shutil
    _bundled_settings = os.path.join(sys._MEIPASS, "src", "core", "ui", "data", "ui_settings.json")
    if os.path.exists(_bundled_settings):
        for _rel in ("core/ui/data/ui_settings.json", "data/ui_settings.json", "ui/data/ui_settings.json"):
            _dst = os.path.join(sys._MEIPASS, *_rel.split("/"))
            try:
                if not os.path.exists(_dst):
                    _shutil.copy2(_bundled_settings, _dst)
            except OSError:
                pass


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


def _attach_parent_console():
    """打包的 --windowed exe 沒有控制台，CLI 模式需附加調用者所在的控制台，
    優先附加進程樹上的 cmd/PowerShell（兼容 onefile bootloader 派生場景），
    其次 ATTACH_PARENT_PROCESS；都失敗時才 AllocConsole 新建窗口。"""
    import ctypes
    kernel32 = ctypes.windll.kernel32
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


def main():
    """啟動後端服務並打開瀏覽器管理面板；帶參數時路由到 core.main 的模式分發。"""
    # 帶參數（boot -m cli / boot -m gui / settings / solve 等）時交給 core/main.py
    # 的 dispatch，修復打包版 CLI 模式無法啟動的問題（argv 之前被完全忽略）。
    if len(sys.argv) > 1:
        _attach_parent_console()
        from main import main as core_main
        core_main()
        return

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
    server = start_api_server(host='127.0.0.1', port=8082)
    dashboard_url = f"http://{server.host}:{server.port}/"
    print(f"[INFO] Browser dashboard started: {dashboard_url}")
    webbrowser.open(dashboard_url)

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()