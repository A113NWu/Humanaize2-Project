"""
Humanaize v2.0 - 主要進入點

命令:
    python main.py boot         - 啟動 CLI 聊天介面
    python main.py boot -m gui  - 啟動 GUI 介面
    python main.py boot -m win-gui  - 啟動 Windows 現代化 GUI 介面
    python main.py boot -m solve -r <file> -enable HSN - 啟動解決模式
    python main.py boot -m guard [--background] [--start-when-boot] - 啟動守護模式
    python main.py boot -m iot [--host <ip>] [--port <n>] - 啟動 IoT 算力網絡
    python main.py settings     - 開啟設定介面
    python main.py update       - 檢查並安裝更新
"""

import sys
import os
import random
import subprocess
import threading

# 添加项目根目录和 src 目录到 Python 路径
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(src_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入并初始化日志模块
from tools.logger import get_logger
logger = get_logger()
logger.redirect_output()
logger.info("Humanaize v2.0 starting...")

import warnings
warnings.filterwarnings("ignore", message=".*iCCP.*known incorrect sRGB profile.*")


def _get_llama_server_path():
    """取得當前平台的正確 llama-server 路徑"""
    if sys.platform != "win32":
        system_paths = [
            "/usr/bin/llama-server",
            "/usr/local/bin/llama-server",
            "/opt/llama.cpp/llama-server"
        ]
        for path in system_paths:
            if os.path.exists(path):
                return path
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    llama_dir = os.path.join(base_dir, "llama")

    if sys.platform == "win32":
        return os.path.join(llama_dir, "llama-server.exe")
    else:
        return os.path.join(llama_dir, "llama-server")


def _get_model_path():
    """取得當前平台的模型路徑"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    settings_path = os.path.join(base_dir, "src", "core", "ui", "data", "ui_settings.json")
    if os.path.exists(settings_path):
        try:
            import json
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            custom_model_path = settings.get("model_path", "")
            if custom_model_path:
                if os.path.isabs(custom_model_path):
                    if os.path.exists(custom_model_path):
                        print(f"[INFO] Using custom model path from settings: {custom_model_path}")
                        return custom_model_path
                    else:
                        print(f"[WARN] Custom model path not found: {custom_model_path}, falling back to default")
                else:
                    abs_path = os.path.join(base_dir, custom_model_path)
                    if os.path.exists(abs_path):
                        print(f"[INFO] Using custom model path from settings: {abs_path}")
                        return abs_path
                    else:
                        print(f"[WARN] Custom model path not found: {abs_path}, falling back to default")
        except Exception as e:
            print(f"[WARN] Failed to read settings: {e}")
    
    env_model_path = os.environ.get("HUMANIZE2_MODEL_PATH", "")
    if env_model_path and os.path.exists(env_model_path):
        print(f"[INFO] Using model path from environment: {env_model_path}")
        return env_model_path
    
    for model_dir_name in ["models", "model"]:
        model_dir = os.path.join(base_dir, model_dir_name)
        
        exact_path = os.path.join(model_dir, "tinyllama.gguf")
        if os.path.exists(exact_path):
            return exact_path
        
        if os.path.exists(model_dir):
            for f in os.listdir(model_dir):
                if f.endswith('.gguf'):
                    return os.path.join(model_dir, f)
    
    return os.path.join(base_dir, "models", "tinyllama.gguf")


def _is_port_in_use(port: int = 8080) -> bool:
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _kill_process_on_port(port: int = 8080) -> bool:
    """终止占用指定端口的进程"""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'tcp'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if f':{port}' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            try:
                                subprocess.run(
                                    ['taskkill', '/F', '/PID', pid],
                                    capture_output=True,
                                    text=True
                                )
                                print(f"[INFO] Killed process {pid} on port {port}")
                            except:
                                pass
                return True
        except:
            pass
    else:
        try:
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid], check=True)
                        print(f"[INFO] Killed process {pid} on port {port}")
                    except:
                        pass
                return True
        except:
            pass
        
        try:
            result = subprocess.run(
                ['ss', '-tlnp', f'sport = :{port}'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) > 5:
                        pid_info = parts[5]
                        if '=' in pid_info:
                            pid = pid_info.split('=')[1].split(',')[0]
                            try:
                                subprocess.run(['kill', '-9', pid], check=True)
                                print(f"[INFO] Killed process {pid} on port {port}")
                            except:
                                pass
                return True
        except:
            pass
    
    return False


def _check_and_start_server(max_wait: int = 120, force_restart: bool = False) -> bool:
    """檢查LLM伺服器是否執行，若未執行則自動啟動，並等待伺服器完全啟動
    
    Args:
        max_wait: 最大等待时间（秒）
        force_restart: 是否强制重启服务器（用于模型切换）
    """
    from tools.tools import check_llm_server
    import time

    print("[INFO] Checking LLM server...")
    
    target_model_path = _get_model_path()
    model_name = os.path.basename(target_model_path)
    
    print("=" * 60)
    print(f"[MODEL] Model Name: {model_name}")
    print(f"[MODEL] Model Path: {target_model_path}")
    print(f"[MODEL] File Exists: {'Yes' if os.path.exists(target_model_path) else 'No'}")
    print("=" * 60)
    
    if check_llm_server() and not force_restart:
        print("[INFO] LLM server is already running.")
        return True

    if _is_port_in_use(8080):
        print("[WARN] Port 8080 is occupied")
        print("[INFO] Attempting to clear port and restart...")
        if _kill_process_on_port(8080):
            time.sleep(2)
        else:
            print("[ERROR] Failed to clear port 8080")
            return False

    print("[INFO] Starting LLM server...")

    server_path = _get_llama_server_path()
    model_path = target_model_path

    if not os.path.exists(server_path):
        print("[ERROR] llama-server not found at:", server_path)
        print("[INFO] Please download llama-server from https://github.com/ggerganov/llama.cpp/releases")
        print("[INFO] Place the binary in:", os.path.dirname(server_path))
        return False

    if not os.path.exists(model_path):
        print("[ERROR] Model file not found at:", model_path)
        return False

    try:
        if sys.platform == "win32" or os.name == "nt":
            process = subprocess.Popen(
                [server_path, "-m", model_path, "-c", "4096", "-ngl", "999", "--host", "127.0.0.1", "--port", "8080", "-n", "256"],
                cwd=os.path.dirname(server_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        else:
            process = subprocess.Popen(
                [server_path, "-m", model_path, "-c", "4096", "-ngl", "999", "--host", "127.0.0.1", "--port", "8080", "-n", "256"],
                cwd=os.path.dirname(server_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        print("[INFO] Waiting for LLM server to start...")
        for attempt in range(max_wait):
            time.sleep(1)
            
            if process.poll() is not None:
                print("[ERROR] LLM server crashed on startup")
                return False
                
            if check_llm_server():
                print("[INFO] LLM server started successfully!")
                return True
            if (attempt + 1) % 10 == 0:
                print(f"[INFO] Waiting for LLM server... ({attempt + 1}/{max_wait}s)")

        print("[ERROR] LLM server failed to start within timeout.")
        process.terminate()
        return False

    except Exception as e:
        print("[ERROR] Failed to start server:", str(e))
        return False


def _read_ascii():
    ascii_path = os.path.join(os.path.dirname(__file__), "ascii.txt")
    try:
        with open(ascii_path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""


def _auto_start_iot_network():
    """在後台自動啟動 IoT 算力網絡（如果配置啟用）"""
    def _start():
        try:
            settings_path = os.path.join(os.path.dirname(__file__), "ui", "data", "ui_settings.json")
            
            # 讀取配置
            import json
            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            auto_start = settings.get("iot_auto_start", True)
            if not auto_start:
                return
            
            host = settings.get("iot_host", "0.0.0.0")
            port = settings.get("iot_port", 8765)
            scan_enabled = settings.get("iot_scan_enabled", True)
            scan_interval = settings.get("iot_scan_interval", 30)
            
            from tools.iot_compute_manager import start_iot_network
            manager = start_iot_network(host=host, port=port)
            print(f"[IoT] 算力網絡後台啟動成功: ws://{host}:{port}")
            
            # 啟動設備掃描
            if scan_enabled:
                from tools.iot_device_scanner import IoTDeviceScanner
                scanner = IoTDeviceScanner(port=port, scan_interval=scan_interval)
                
                # 保存掃描到的設備到配置
                def on_device_found(device):
                    saved = settings.get("iot_discovered_devices", [])
                    saved_ids = {d.get("ip") for d in saved}
                    if device.get("ip") not in saved_ids:
                        saved.append(device)
                        settings["iot_discovered_devices"] = saved
                        try:
                            with open(settings_path, 'w', encoding='utf-8') as f:
                                json.dump(settings, f, indent=4, ensure_ascii=False)
                        except Exception:
                            pass
                
                scanner.on_device_found(on_device_found)
                scanner.start_scanning()
                print(f"[IoT] 設備掃描已啟動（間隔: {scan_interval}s）")
            
        except ImportError as e:
            logger.debug(f"IoT network dependencies not available: {e}")
        except Exception as e:
            logger.error(f"Auto start IoT network failed: {e}")
    
    thread = threading.Thread(target=_start, daemon=True)
    thread.start()


def boot_cli():
    _check_and_start_server()
    _auto_start_iot_network()
    from ui.cli import HumanaizeCLI
    cli = HumanaizeCLI()
    cli.run()


def _check_updates_background():
    """后台检查更新并发送通知"""
    import threading
    from tools.notify import notify_update
    
    def check():
        try:
            from utils.auto_updater import AutoUpdater
            updater = AutoUpdater("https://github.com/A113NWu/Humanaize2-Project.git")
            update_info = updater.check_for_updates()
            
            if update_info.get("has_update"):
                # 使用标准 Release tag 名（vX.X.X）传给通知和显示
                current_tag = update_info.get("current_tag") or updater._format_release_tag(update_info["current_version"])
                latest_tag = update_info.get("latest_tag") or updater._format_release_tag(update_info["latest_version"])
                notify_update(latest_tag, current_tag)
        except Exception:
            pass
    
    thread = threading.Thread(target=check, daemon=True)
    thread.start()


def boot_gui():
    _check_and_start_server()
    _auto_start_iot_network()
    
    # 后台检查更新
    _check_updates_background()
    
    import warnings
    warnings.filterwarnings("ignore")
    
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
    
    try:
        import tensorflow as tf
        tf.get_logger().setLevel('ERROR')
    except:
        pass
    
    import customtkinter as ctk
    from ui import HumanaizeUI
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")
    root = ctk.CTk()
    app = HumanaizeUI(root)
    root.mainloop()


def boot_windows_gui():
    """启动 Windows 专属现代化 GUI"""
    _check_and_start_server()
    _auto_start_iot_network()
    
    # 后台检查更新
    _check_updates_background()
    
    import warnings
    warnings.filterwarnings("ignore")
    
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
    
    try:
        import tensorflow as tf
        tf.get_logger().setLevel('ERROR')
    except:
        pass
    
    import customtkinter as ctk
    from ui.windows_gui import ModernWindowsUI
    root = ctk.CTk()
    app = ModernWindowsUI(root)
    root.mainloop()


def boot_solve(args):
    """啟動問題解決模式"""
    if not _check_and_start_server():
        print("[ERROR] Failed to start LLM server. Exiting...")
        return
    
    _auto_start_iot_network()

    from tools.solve_mode import SolveMode
    
    solver = SolveMode()
    
    problem = ""
    mode_args = []
    
    i = 0
    while i < len(args):
        if args[i].startswith("-"):
            mode_args.append(args[i])
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                mode_args.append(args[i + 1])
                i += 2
                continue
            i += 1
            continue
        if not problem:
            problem = " ".join(args[i:])
        break
    
    solver.parse_args(mode_args)
    
    if not problem.strip():
        print("Enter the problem you want to solve:")
        problem = input("> ")
    
    if not problem.strip():
        print("[ERROR] No problem specified")
        return
    
    solver.set_problem(problem)
    
    try:
        result = solver.run()
    except KeyboardInterrupt:
        print("\n[INFO] Solve mode interrupted")
        solver.stop()


def boot_guard(args):
    """啟動守護模式"""
    background = "--background" in args or "-b" in args
    start_on_boot = "--start-when-boot" in args or "-s" in args
    
    print("[INFO] Starting Guard mode...")
    
    try:
        from tools.guard_mode import GuardMode, guard_mode_api
        
        if background:
            print("[INFO] Running in background mode")
            result = guard_mode_api.start(background=True, start_on_boot=start_on_boot)
            if result.get("status") == "success":
                print("[INFO] Guard mode started successfully in background")
            else:
                print(f"[ERROR] Failed to start Guard mode: {result.get('message')}")
        else:
            print("[INFO] Running in foreground mode (press Ctrl+C to stop)")
            guard = GuardMode(background=False, start_on_boot=start_on_boot)
            guard.start()
                
    except ImportError as e:
        print(f"[ERROR] Failed to import guard_mode module: {e}")
    except Exception as e:
        print(f"[ERROR] Failed to start Guard mode: {e}")


def boot_iot(args):
    """啟動 IoT 算力網絡（獨立於 HSN）"""
    print("[IoT] 正在啟動算力網絡...")
    
    # 解析參數
    host = "0.0.0.0"
    port = 8765
    
    for i, arg in enumerate(args):
        if arg == "--host" and i + 1 < len(args):
            host = args[i + 1]
        elif arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
    
    try:
        from tools.iot_compute_manager import start_iot_network
        
        manager = start_iot_network(host=host, port=port)
        
        print(f"[IoT] 算力網絡已啟動")
        print(f"[IoT] WebSocket 地址: ws://{host}:{port}")
        print(f"[IoT] 等待設備連接中...")
        print(f"[IoT] 按 Ctrl+C 停止服務")
        
        # 顯示狀態
        import time
        try:
            while True:
                time.sleep(5)
                stats = manager.get_stats()
                online = stats.get('online_devices', 0)
                total = stats.get('total_devices', 0)
                tasks = stats.get('completed_tasks', 0)
                print(f"[IoT] 狀態: 在線={online}/{total} | 已完成任務={tasks}")
        except KeyboardInterrupt:
            print("\n[IoT] 正在停止算力網絡...")
            from tools.iot_compute_manager import stop_iot_network
            stop_iot_network()
            print("[IoT] 已停止")
            
    except ImportError as e:
        print(f"[ERROR] Failed to import IoT module: {e}")
        print("[INFO] 請安裝 websockets 庫: pip install websockets>=12.0")
    except Exception as e:
        print(f"[ERROR] Failed to start IoT network: {e}")


def open_settings():
    from ui.cli_settings import SettingsCLI
    settings_cli = SettingsCLI()
    settings_cli.run()


def handle_skills():
    from tools.skills_cli import SkillsCLI
    skills_cli = SkillsCLI()
    skills_cli.process_command(["skills"] + sys.argv[2:])


def handle_update(args):
    """Handle update command"""
    from utils.auto_updater import AutoUpdater
    from tools.notify import notify_update, notify_info
    
    force_update = "-f" in args or "--force" in args
    
    updater = AutoUpdater("https://github.com/A113NWu/Humanaize2-Project.git")
    
    def progress_callback(msg):
        print(f"[UPDATE] {msg}")
    
    print("Checking for updates...")
    update_info = updater.check_for_updates()
    
    if update_info.get("error"):
        print(f"[ERROR] Failed to check for updates: {update_info['error']}")
        return
    
    current_tag = update_info.get("current_tag") or updater._format_release_tag(update_info["current_version"])
    latest_tag = update_info.get("latest_tag") or updater._format_release_tag(update_info["latest_version"])
    current_version = update_info["current_version"]
    latest_version = update_info["latest_version"]
    
    print(f"Current version: {current_tag}")
    print(f"Latest release: {latest_tag}")
    
    if update_info.get("release_notes"):
        print(f"\nRelease Notes:\n{update_info['release_notes']}")
    
    if update_info.get("has_update") or force_update:
        # 发送更新通知（使用 vX.X.X 标准标签名）
        if update_info.get("has_update"):
            notify_update(latest_tag, current_tag)
        
        if not update_info.get("has_update"):
            print("\n[INFO] Already up to date, but forcing update...")
        
        print("\nStarting update installation...")
        
        # Try git pull first if available, otherwise download zip
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
            is_git_repo = result.returncode == 0
        except:
            is_git_repo = False
        
        if is_git_repo:
            print("[INFO] Git repository detected, using git pull method...")
            result = updater.pull_latest_from_git(progress_callback, force=force_update)
        else:
            print("[INFO] Using download and install method...")
            result = updater.download_and_install_update(progress_callback, force=force_update)
        
        if result.get("success"):
            print(f"\n{result['message']}")
            notify_info("Humanaize 更新完成", f"已更新到版本 {latest_tag}")
        else:
            print(f"\n[ERROR] Update failed: {result.get('error', result.get('message'))}")
    else:
        print("\n[INFO] You are already on the latest version.")
        print("Use 'humanaize2 update -f' to force update.")


def main():
    args = sys.argv[1:]
    
    if not args:
        print(__doc__)
        print("Usage:")
        print("  humanaize2 boot         - Start CLI chat interface")
        print("  humanaize2 boot -m gui  - Start GUI interface")
        print("  humanaize2 boot -m win-gui  - Start Windows modern GUI interface")
        print("  humanaize2 boot -m solve [--hsn] [--sandbox <dir>] [-gan] - Start problem solving mode")
        print("  humanaize2 boot -m guard [--background] [--start-when-boot] - Start guard mode")
        print("  humanaize2 settings     - Open settings interface")
        print("\nOptions for solve mode:")
        print("  --hsn          Enable HSN (Human Swarm Network)")
        print("  --sandbox <dir>  Enable sandbox mode, restrict AI to specified directory")
        print("  -gan           Enable enhanced GAN mode")
        print("\nOptions for guard mode:")
        print("  --background          Run in background mode")
        print("  --start-when-boot     Enable auto-start on system boot")
        print("\nOr use directly:")
        print("  python main.py boot")
        print("  python main.py boot -m gui")
        print("  python main.py boot -m win-gui")
        print("  python main.py boot -m solve")
        print("  python main.py boot -m guard")
        print("  python main.py settings")
        return
    
    command = args[0].lower()
    
    speeches = [
        "Android or Apple, this is a question.",
        "I'll never treat my users as a human >_*",
        "I see dead code... Just kidding, it's alive!",
        "I'm a robot, are you a robot?",
        "Talking to a human today. Novel experience!"
    ]
    
    ascii_art = _read_ascii()
    
    if command == "boot":
        # Check for mode parameter
        mode = None
        mode_args = []
        i = 1
        while i < len(args):
            if args[i] == "-m" or args[i] == "-mode":
                if i + 1 < len(args):
                    mode = args[i + 1].lower()
                    mode_args = args[i + 2:]
                    break
            i += 1
        
        if mode == "gui":
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting GUI interface...")
            boot_gui()
        elif mode == "win-gui":
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting Windows modern GUI interface...")
            boot_windows_gui()
        elif mode == "solve":
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting CLI chat interface...")
            print("Starting SOLVE mode...")
            boot_solve(mode_args)
        elif mode == "guard":
            print("Starting Guard mode...")
            boot_guard(mode_args)
        elif mode == "iot":
            print("Starting IoT Compute Network...")
            boot_iot(mode_args)
        else:
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting CLI chat interface...")
            boot_cli()
    elif command == "settings":
        choice = random.randint(0, 4)
        if choice == 3 and ascii_art:
            print(ascii_art)
        else:
            print(speeches[choice])
        print("Opening settings interface...")
        open_settings()
    elif command == "skills":
        handle_skills()
    elif command == "update":
        choice = random.randint(0, 4)
        if choice == 3 and ascii_art:
            print(ascii_art)
        else:
            print(speeches[choice])
        handle_update(args[1:])
    else:
        print(f"Unknown command: {command}")
        print("Usage:")
        print("  humanaize2 boot         - Start CLI chat interface")
        print("  humanaize2 boot -m gui  - Start GUI interface")
        print("  humanaize2 boot -m solve [--hsn] [--sandbox <dir>] [-gan] - Start problem solving mode")
        print("  humanaize2 boot -m iot [--host <ip>] [--port <n>] - Start IoT compute network")
        print("  humanaize2 settings     - Open settings interface")
        print("  humanaize2 skills      - Manage skills")
        print("  humanaize2 update      - Check for and install updates")
        print("  humanaize2 update -f   - Force update even if already up to date")


if __name__ == "__main__":
    main()