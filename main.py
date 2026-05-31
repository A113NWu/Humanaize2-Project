"""
Humanaize v2.0 - Main Entry Point

Commands:
    python main.py boot         - Start CLI chat interface
    python main.py boot -m gui  - Start GUI interface
    python main.py settings     - Open settings interface
"""

import sys
import os
import random
import subprocess
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings
warnings.filterwarnings("ignore", message=".*iCCP.*known incorrect sRGB profile.*")


def _check_and_start_server():
    """检查LLM服务器是否运行，若未运行则自动启动"""
    from tools import check_llm_server
    
    print("[INFO] Checking LLM server...")
    if check_llm_server():
        print("[INFO] LLM server is already running.")
        return True
    
    print("[INFO] LLM server not detected. Starting server...")
    
    llama_dir = os.path.join(os.path.dirname(__file__), "llama")
    server_exe = os.path.join(llama_dir, "llama-server.exe")
    model_path = os.path.join(os.path.dirname(__file__), "models", "tinyllama.gguf")
    
    if not os.path.exists(server_exe):
        print("[ERROR] llama-server.exe not found at:", server_exe)
        return False
    
    if not os.path.exists(model_path):
        print("[ERROR] Model file not found at:", model_path)
        return False
    
    try:
        subprocess.Popen(
            [server_exe, "-m", model_path, "-c", "4096", "-ngl", "999", "--host", "127.0.0.1", "--port", "8080", "-n", "256"],
            cwd=llama_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        def _wait_for_server():
            import time
            from tools import check_llm_server
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
    from cli import HumanaizeCLI
    cli = HumanaizeCLI()
    cli.run()


def boot_gui():
    _check_and_start_server()
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


def open_settings():
    from cli_settings import SettingsCLI
    settings_cli = SettingsCLI()
    settings_cli.run()


def handle_skills():
    from skills_cli import SkillsCLI
    skills_cli = SkillsCLI()
    skills_cli.process_command(["skills"] + sys.argv[2:])


def main():
    args = sys.argv[1:]
    
    if not args:
        print(__doc__)
        print("Usage:")
        print("  humanaize2 boot         - Start CLI chat interface")
        print("  humanaize2 boot -m gui  - Start GUI interface")
        print("  humanaize2 settings     - Open settings interface")
        print("\nOr use directly:")
        print("  python main.py boot")
        print("  python main.py boot -m gui")
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
        if len(args) > 1 and (args[1] == "-m" or args[1] == "-mode") and len(args) > 2 and args[2].lower() == "gui":
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting GUI interface...")
            boot_gui()
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
    else:
        print(f"Unknown command: {command}")
        print("Usage:")
        print("  humanaize2 boot         - Start CLI chat interface")
        print("  humanaize2 boot -m gui  - Start GUI interface")
        print("  humanaize2 settings     - Open settings interface")
        print("  humanaize2 skills      - Manage skills")


if __name__ == "__main__":
    main()
