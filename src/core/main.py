"""
Humanaize v2.0 - 主要進入點

命令:
    python main.py boot         - 啟動 CLI 聊天介面
    python main.py boot -m gui  - 啟動 GUI 介面
    python main.py boot -m solve -r <file> -enable HSN - 啟動解決模式
    python main.py settings     - 開啟設定介面
    python main.py update       - 檢查並安裝更新
"""

import sys
import os
import random
import subprocess
import threading

# 添加 src 目录到 Python 路径
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, src_dir)

import warnings
warnings.filterwarnings("ignore", message=".*iCCP.*known incorrect sRGB profile.*")


def _get_llama_server_path():
    """取得當前平台的正確 llama-server 路徑"""
    # 首先檢查系統安裝的 llama-server (Linux)
    if sys.platform != "win32" and os.name != "nt":
        system_paths = [
            "/usr/bin/llama-server",
            "/usr/local/bin/llama-server",
            "/opt/llama.cpp/llama-server"
        ]
        for path in system_paths:
            if os.path.exists(path):
                return path
    
    # 如果系統沒有，則檢查專案目錄
    # 取得專案根目錄 (src/core 的父目錄)
    # main.py 在 src/core 中，所以需要 2 次 dirname 呼叫:
    # src/core/main.py -> src/core -> src -> project_root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    llama_dir = os.path.join(base_dir, "llama")

    if sys.platform == "win32" or os.name == "nt":
        return os.path.join(llama_dir, "llama-server.exe")
    elif sys.platform == "darwin":
        return os.path.join(llama_dir, "llama-server")
    else:
        return os.path.join(llama_dir, "llama-server")


def _get_model_path():
    """取得當前平台的模型路徑"""
    # 取得專案根目錄 (src/core 的父目錄)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    models_dir = os.path.join(base_dir, "models")
    
    # 首先檢查精確匹配
    exact_path = os.path.join(models_dir, "tinyllama.gguf")
    if os.path.exists(exact_path):
        return exact_path
    
    # 如果精確匹配不存在，查找任何 GGUF 文件
    if os.path.exists(models_dir):
        for f in os.listdir(models_dir):
            if f.endswith('.gguf'):
                return os.path.join(models_dir, f)
    
    # 如果都找不到，返回預設路徑（讓調用者處理錯誤）
    return exact_path


def _check_and_start_server():
    """檢查LLM伺服器是否執行，若未執行則自動啟動"""
    from tools.tools import check_llm_server

    print("[INFO] Checking LLM server...")
    if check_llm_server():
        print("[INFO] LLM server is already running.")
        return True

    print("[INFO] LLM server not detected. Starting server...")

    server_path = _get_llama_server_path()
    model_path = _get_model_path()

    if not os.path.exists(server_path):
        print("[ERROR] llama-server not found at:", server_path)
        return False

    if not os.path.exists(model_path):
        print("[ERROR] Model file not found at:", model_path)
        return False

    try:
        if sys.platform == "win32" or os.name == "nt":
            subprocess.Popen(
                [server_path, "-m", model_path, "-c", "4096", "-ngl", "999", "--host", "127.0.0.1", "--port", "8080", "-n", "256"],
                cwd=os.path.dirname(server_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        else:
            import time

            subprocess.Popen(
                [server_path, "-m", model_path, "-c", "4096", "-ngl", "999", "--host", "127.0.0.1", "--port", "8080", "-n", "256"],
                cwd=os.path.dirname(server_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            def _wait_for_server():
                from tools.tools import check_llm_server
                for _ in range(30):
                    time.sleep(1)
                    if check_llm_server():
                        print("[INFO] LLM server started successfully!")
                        return
                print("[WARN] Server process started but not responding yet.")

            threading.Thread(target=_wait_for_server, daemon=True).start()
        return True

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


def boot_cli():
    _check_and_start_server()
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
                current_version = update_info["current_version"]
                latest_version = update_info["latest_version"]
                notify_update(latest_version, current_version)
        except Exception:
            pass
    
    thread = threading.Thread(target=check, daemon=True)
    thread.start()


def boot_gui():
    _check_and_start_server()
    
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


def boot_solve(args):
    """啟動問題解決模式"""
    _check_and_start_server()
    
    # 等待服务器完全启动
    import time
    time.sleep(1)
    
    # 清屏并重新显示标题
    print("\n" * 20)
    
    from tools.solve_mode import SolveMode
    
    solver = SolveMode()
    solver.parse_args(args)
    
    # Get problem from user
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
    
    current_version = update_info["current_version"]
    latest_version = update_info["latest_version"]
    
    print(f"Current version: {current_version}")
    print(f"Latest version: {latest_version}")
    
    if update_info.get("release_notes"):
        print(f"\nRelease Notes:\n{update_info['release_notes']}")
    
    if update_info.get("has_update") or force_update:
        # 发送更新通知
        if update_info.get("has_update"):
            notify_update(latest_version, current_version)
        
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
            result = updater.pull_latest_from_git(progress_callback)
        else:
            print("[INFO] Using download and install method...")
            result = updater.download_and_install_update(progress_callback)
        
        if result.get("success"):
            print(f"\n{result['message']}")
            notify_info("Humanaize 更新完成", f"已更新到版本 {latest_version}")
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
        print("  humanaize2 boot -m solve [-r <file>] [-enable HSN] - Start problem solving mode")
        print("  humanaize2 settings     - Open settings interface")
        print("\nOr use directly:")
        print("  python main.py boot")
        print("  python main.py boot -m gui")
        print("  python main.py boot -m solve")
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
        elif mode == "solve":
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting CLI chat interface...")
            print("Starting SOLVE mode...")
            boot_solve(mode_args)
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
        print("  humanaize2 boot -m solve [-r <file>] [-enable HSN] - Start problem solving mode")
        print("  humanaize2 settings     - Open settings interface")
        print("  humanaize2 skills      - Manage skills")
        print("  humanaize2 update      - Check for and install updates")
        print("  humanaize2 update -f   - Force update even if already up to date")


if __name__ == "__main__":
    main()