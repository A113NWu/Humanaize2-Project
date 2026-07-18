"""
Humanaize v2.0 - CLI Settings Interface
"""

import os
import json
import sys


class SettingsCLI:
    def __init__(self):
        self.settings_path = os.path.join(os.path.dirname(__file__), "data", "settings.json")
        self.settings = self._load_settings()

    def _load_settings(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self):
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def _print_header(self):
        print("\n" + "=" * 60)
        print("  Humanaize v2.0 - Settings")
        print("=" * 60)

    def _print_menu(self):
        print("\n┌─────────────────────────────────────────────┐")
        print("│  Settings Menu                              │")
        print("├─────────────────────────────────────────────┤")
        print("│  1. Language               (当前: {})".format(self.settings.get("language", "English")[:20].ljust(20)))
        print("│  2. Theme                  (当前: {})".format(self.settings.get("theme", "Dark")[:20].ljust(20)))
        print("│  3. Model Name             (当前: {})".format(self.settings.get("model_name", "tinyllama")[:20].ljust(20)))
        print("│  4. Custom Model Path      (当前: {})".format(self.settings.get("model_path", "None")[:20].ljust(20)))
        print("│  5. GAN Enabled            (当前: {})".format(str(self.settings.get("gan_enabled", True))[:20].ljust(20)))
        print("│  6. Auto Break Silence     (当前: {})".format(str(self.settings.get("auto_break_silence", True))[:20].ljust(20)))
        print("│  7. Skills Prompt          (当前: {})".format("configured" if self.settings.get("skills_prompt") else "None")[:20].ljust(20))
        print("│  8. LLM Server URL         (当前: {})".format(self.settings.get("llm_server_url", "http://127.0.0.1:8080")[:20].ljust(20)))
        print("│  9. Max Tokens             (当前: {})".format(str(self.settings.get("max_tokens", 256))[:20].ljust(20)))
        print("│  10. Temperature           (当前: {})".format(str(self.settings.get("temperature", 0.7))[:20].ljust(20)))
        print("│  11. Guard Mode Enabled    (当前: {})".format(str(self.settings.get("guard_enabled", False))[:20].ljust(20)))
        print("│  12. Guard Auto Start      (当前: {})".format(str(self.settings.get("guard_auto_start", False))[:20].ljust(20)))
        print("│  13. Guard Monitor Interval(当前: {}s)".format(str(self.settings.get("guard_interval", 5))[:18].ljust(18)))
        print("│  14. Guard Firewall        (当前: {})".format(str(self.settings.get("guard_firewall", True))[:20].ljust(20)))
        print("│  15. Guard Network Monitor (当前: {})".format(str(self.settings.get("guard_network_monitor", True))[:20].ljust(20)))
        print("│  16. Guard System Monitor  (当前: {})".format(str(self.settings.get("guard_system_monitor", True))[:20].ljust(20)))
        print("│  17. Counter Measure        (当前: {})".format(str(self.settings.get("counter_measure_enabled", True))[:20].ljust(20)))
        print("│  18. Counter Lab Mode       (当前: {})".format(str(self.settings.get("counter_lab_mode", False))[:20].ljust(20)))
        print("│  19. Counter Max Warnings   (当前: {})".format(str(self.settings.get("counter_max_warnings", 2))[:20].ljust(20)))
        print("│  20. Counter Cooldown       (当前: {}s)".format(str(self.settings.get("counter_cooldown", 300))[:18].ljust(18)))
        print("├─────────────────────────────────────────────┤")
        print("│  S. Save & Exit                             │")
        print("│  Q. Quit Without Saving                     │")
        print("└─────────────────────────────────────────────┘")

    def _get_input(self, prompt, default="", is_password=False):
        try:
            if is_password:
                import getpass
                value = getpass.getpass(prompt)
            else:
                value = input(prompt)
            return value.strip() if value.strip() else default
        except (KeyboardInterrupt, EOFError):
            return default

    def _edit_language(self):
        print("\n选择语言:")
        print("  1. English")
        print("  2. 中文")
        choice = self._get_input("Enter choice (1-2, default: 1): ", "1")
        if choice == "2":
            self.settings["language"] = "Chinese"
        else:
            self.settings["language"] = "English"

    def _edit_theme(self):
        print("\n选择主题:")
        print("  1. Dark")
        print("  2. Light")
        print("  3. System")
        choice = self._get_input("Enter choice (1-3, default: 1): ", "1")
        themes = {"1": "Dark", "2": "Light", "3": "System"}
        self.settings["theme"] = themes.get(choice, "Dark")

    def _edit_model_name(self):
        print("\n输入模型名称 (例如: tinyllama, llama2, mistral):")
        default = self.settings.get("model_name", "tinyllama")
        value = self._get_input(f"Model name (default: {default}): ", default)
        self.settings["model_name"] = value

    def _edit_model_path(self):
        print("\n输入自定义模型路径 (留空使用默认):")
        default = self.settings.get("model_path", "")
        value = self._get_input(f"Custom model path (default: {default or 'None'}): ", default)
        self.settings["model_path"] = value

    def _edit_gan_enabled(self):
        print("\n是否启用GAN思考?")
        print("  1. Yes (启用)")
        print("  2. No (禁用)")
        choice = self._get_input("Enter choice (1-2, default: 1): ", "1")
        self.settings["gan_enabled"] = (choice == "1")

    def _edit_auto_break_silence(self):
        print("\n是否允许AI主动打破沉默?")
        print("  1. Yes")
        print("  2. No")
        choice = self._get_input("Enter choice (1-2, default: 1): ", "1")
        self.settings["auto_break_silence"] = (choice == "1")

    def _edit_skills_prompt(self):
        print("\n输入Skills配置 (输入多行, 空行结束):")
        print("(按Enter开始新行, 输入空行结束输入)")
        lines = []
        while True:
            try:
                line = input()
                if not line.strip():
                    break
                lines.append(line)
            except (KeyboardInterrupt, EOFError):
                break
        self.settings["skills_prompt"] = "\n".join(lines)

    def _edit_llm_server_url(self):
        print("\n输入LLM服务器URL:")
        default = self.settings.get("llm_server_url", "http://127.0.0.1:8080")
        value = self._get_input(f"LLM Server URL (default: {default}): ", default)
        self.settings["llm_server_url"] = value

    def _edit_max_tokens(self):
        print("\n输入最大Token数:")
        default = self.settings.get("max_tokens", 256)
        value = self._get_input(f"Max tokens (default: {default}): ", str(default))
        try:
            self.settings["max_tokens"] = int(value)
        except ValueError:
            print("Invalid number, keeping previous value.")

    def _edit_temperature(self):
        print("\n输入Temperature (0.0-2.0):")
        default = self.settings.get("temperature", 0.7)
        value = self._get_input(f"Temperature (default: {default}): ", str(default))
        try:
            temp = float(value)
            if 0.0 <= temp <= 2.0:
                self.settings["temperature"] = temp
            else:
                print("Temperature must be between 0.0 and 2.0")
        except ValueError:
            print("Invalid number, keeping previous value.")

    def _edit_guard_enabled(self):
        print("\n是否启用Guard模式?")
        print("  1. Yes (启用)")
        print("  2. No (禁用)")
        choice = self._get_input("Enter choice (1-2, default: 2): ", "2")
        self.settings["guard_enabled"] = (choice == "1")

    def _edit_guard_auto_start(self):
        print("\n是否启用Guard模式开机自启?")
        print("  1. Yes (启用)")
        print("  2. No (禁用)")
        choice = self._get_input("Enter choice (1-2, default: 2): ", "2")
        self.settings["guard_auto_start"] = (choice == "1")

    def _edit_guard_interval(self):
        print("\n输入Guard模式监控间隔(秒):")
        default = self.settings.get("guard_interval", 5)
        value = self._get_input(f"Monitor interval (default: {default}): ", str(default))
        try:
            interval = int(value)
            if interval >= 1 and interval <= 60:
                self.settings["guard_interval"] = interval
            else:
                print("Interval must be between 1 and 60 seconds")
        except ValueError:
            print("Invalid number, keeping previous value.")

    def _edit_guard_firewall(self):
        print("\n是否启用Guard模式防火墙?")
        print("  1. Yes (启用)")
        print("  2. No (禁用)")
        choice = self._get_input("Enter choice (1-2, default: 1): ", "1")
        self.settings["guard_firewall"] = (choice == "1")

    def _edit_guard_network_monitor(self):
        print("\n是否启用Guard模式网络监控?")
        print("  1. Yes (启用)")
        print("  2. No (禁用)")
        choice = self._get_input("Enter choice (1-2, default: 1): ", "1")
        self.settings["guard_network_monitor"] = (choice == "1")

    def _edit_guard_system_monitor(self):
        print("\n是否启用Guard模式系统监控?")
        print("  1. Yes (启用)")
        print("  2. No (禁用)")
        choice = self._get_input("Enter choice (1-2, default: 1): ", "1")
        self.settings["guard_system_monitor"] = (choice == "1")

    def _edit_counter_measure_enabled(self):
        print("\n是否启用反制措施?")
        print("  1. Yes (启用)")
        print("  2. No (禁用)")
        choice = self._get_input("Enter choice (1-2, default: 1): ", "1")
        self.settings["counter_measure_enabled"] = (choice == "1")

    def _edit_counter_lab_mode(self):
        print("\n是否启用实验室模式?")
        print("  1. Yes (启用 - 仅用于测试环境)")
        print("  2. No (禁用 - 默认生产环境)")
        choice = self._get_input("Enter choice (1-2, default: 2): ", "2")
        self.settings["counter_lab_mode"] = (choice == "1")

    def _edit_counter_max_warnings(self):
        print("\n输入最大警告次数:")
        default = self.settings.get("counter_max_warnings", 2)
        value = self._get_input(f"Max warnings (default: {default}): ", str(default))
        try:
            max_warnings = int(value)
            if max_warnings >= 1 and max_warnings <= 10:
                self.settings["counter_max_warnings"] = max_warnings
            else:
                print("Max warnings must be between 1 and 10")
        except ValueError:
            print("Invalid number, keeping previous value.")

    def _edit_counter_cooldown(self):
        print("\n输入冷却时间(秒):")
        default = self.settings.get("counter_cooldown", 300)
        value = self._get_input(f"Cooldown seconds (default: {default}): ", str(default))
        try:
            cooldown = int(value)
            if cooldown >= 60 and cooldown <= 3600:
                self.settings["counter_cooldown"] = cooldown
            else:
                print("Cooldown must be between 60 and 3600 seconds")
        except ValueError:
            print("Invalid number, keeping previous value.")

    def run(self):
        self._print_header()
        
        while True:
            self._print_menu()
            choice = self._get_input("\nEnter choice (1-20, S to save, Q to quit): ").upper()
            
            if choice == "Q":
                print("\n[Settings] Quit without saving.")
                return False
            elif choice == "S":
                self._save_settings()
                print("\n[Settings] Settings saved successfully!")
                return True
            elif choice == "1":
                self._edit_language()
            elif choice == "2":
                self._edit_theme()
            elif choice == "3":
                self._edit_model_name()
            elif choice == "4":
                self._edit_model_path()
            elif choice == "5":
                self._edit_gan_enabled()
            elif choice == "6":
                self._edit_auto_break_silence()
            elif choice == "7":
                self._edit_skills_prompt()
            elif choice == "8":
                self._edit_llm_server_url()
            elif choice == "9":
                self._edit_max_tokens()
            elif choice == "10":
                self._edit_temperature()
            elif choice == "11":
                self._edit_guard_enabled()
            elif choice == "12":
                self._edit_guard_auto_start()
            elif choice == "13":
                self._edit_guard_interval()
            elif choice == "14":
                self._edit_guard_firewall()
            elif choice == "15":
                self._edit_guard_network_monitor()
            elif choice == "16":
                self._edit_guard_system_monitor()
            elif choice == "17":
                self._edit_counter_measure_enabled()
            elif choice == "18":
                self._edit_counter_lab_mode()
            elif choice == "19":
                self._edit_counter_max_warnings()
            elif choice == "20":
                self._edit_counter_cooldown()
            else:
                print("\n[Settings] Invalid choice. Please try again.")


def main():
    settings_cli = SettingsCLI()
    settings_cli.run()


if __name__ == "__main__":
    main()