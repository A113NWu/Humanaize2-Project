"""
Humanaize v2.0 - CLI Settings Interface
"""

import os
import json
import sys


class SettingsCLI:
    def __init__(self):
        self.settings_path = os.path.join(os.path.dirname(__file__), "data", "ui_settings.json")
        self.settings = self._load_settings()
        self._scanner = None
        self._scanner_thread = None

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
        # 設備掃描狀態
        device_count = len(self.settings.get("iot_discovered_devices", []))
        scan_status = "運行中" if (self._scanner and self._scanner.is_scanning()) else "已停止"
        
        print("\n┌─────────────────────────────────────────────┐")
        print("│  Settings Menu                              │")
        print("├─────────────────────────────────────────────┤")
        print("│  1. Language               (當前: {})".format(self.settings.get("language", "English")[:20].ljust(20)))
        print("│  2. Theme                  (當前: {})".format(self.settings.get("theme", "Dark")[:20].ljust(20)))
        print("│  3. Model Name             (當前: {})".format(self.settings.get("model_name", "tinyllama")[:20].ljust(20)))
        print("│  4. Custom Model Path      (當前: {})".format(self.settings.get("model_path", "None")[:20].ljust(20)))
        print("│  5. GAN Enabled            (當前: {})".format(str(self.settings.get("gan_enabled", True))[:20].ljust(20)))
        print("│  6. Auto Break Silence     (當前: {})".format(str(self.settings.get("auto_break_silence", True))[:20].ljust(20)))
        print("│  7. Skills Prompt          (當前: {})".format(("configured" if self.settings.get("skills_prompt") else "None")[:20].ljust(20)))
        print("│  8. LLM Server URL         (當前: {})".format(self.settings.get("llm_server_url", "http://127.0.0.1:8080")[:20].ljust(20)))
        print("│  9. Max Tokens             (當前: {})".format(str(self.settings.get("max_tokens", 256))[:20].ljust(20)))
        print("│  10. Temperature           (當前: {})".format(str(self.settings.get("temperature", 0.7))[:20].ljust(20)))
        print("│  11. Guard Mode Enabled    (當前: {})".format(str(self.settings.get("guard_enabled", False))[:20].ljust(20)))
        print("│  12. Guard Auto Start      (當前: {})".format(str(self.settings.get("guard_auto_start", False))[:20].ljust(20)))
        print("│  13. Guard Monitor Interval(當前: {}s)".format(str(self.settings.get("guard_interval", 5))[:18].ljust(18)))
        print("│  14. Guard Firewall        (當前: {})".format(str(self.settings.get("guard_firewall", True))[:20].ljust(20)))
        print("│  15. Guard Network Monitor (當前: {})".format(str(self.settings.get("guard_network_monitor", True))[:20].ljust(20)))
        print("│  16. Guard System Monitor  (當前: {})".format(str(self.settings.get("guard_system_monitor", True))[:20].ljust(20)))
        print("│  17. Counter Measure        (當前: {})".format(str(self.settings.get("counter_measure_enabled", True))[:20].ljust(20)))
        print("│  18. Counter Lab Mode       (當前: {})".format(str(self.settings.get("counter_lab_mode", False))[:20].ljust(20)))
        print("│  19. Counter Max Warnings   (當前: {})".format(str(self.settings.get("counter_max_warnings", 2))[:20].ljust(20)))
        print("│  20. Counter Cooldown       (當前: {}s)".format(str(self.settings.get("counter_cooldown", 300))[:18].ljust(18)))
        print("├─────────────────────────────────────────────┤")
        print("│  IoT 算力網絡                                │")
        print("│  21. IoT Auto Start        (當前: {})".format(str(self.settings.get("iot_auto_start", True))[:20].ljust(20)))
        print("│  22. IoT Host              (當前: {})".format(self.settings.get("iot_host", "0.0.0.0")[:20].ljust(20)))
        print("│  23. IoT Port              (當前: {})".format(str(self.settings.get("iot_port", 8765))[:20].ljust(20)))
        print("│  24. 設備掃描              (狀態: {})".format((scan_status + f" | 設備: {device_count}")[:20].ljust(20)))
        print("│  25. 手動掃描設備          (已發現: {})".format((str(device_count) + " 台")[:20].ljust(20)))
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

    # ========== IoT 設置 ==========
    
    def _edit_iot_auto_start(self):
        """設置 IoT 自動啟動"""
        print("\n是否啟動時自動啟動 IoT 算力網絡?")
        print("  1. Yes (啟動時自動啟動)")
        print("  2. No (手動啟動)")
        choice = self._get_input("Enter choice (1-2, default: 1): ", "1")
        self.settings["iot_auto_start"] = (choice == "1")
        if self.settings["iot_auto_start"]:
            print("  ✓ 啟動時將自動啟動 IoT 算力網絡")
        else:
            print("  ✓ 已禁用自動啟動")
    
    def _edit_iot_host(self):
        """設置 IoT 主機地址"""
        print("\n輸入 IoT 算力網絡監聽地址:")
        print("  0.0.0.0   - 接受所有網絡接口連接（推薦）")
        print("  127.0.0.1 - 僅本地連接")
        print("  <局域網IP> - 僅接受指定IP")
        default = self.settings.get("iot_host", "0.0.0.0")
        value = self._get_input(f"IoT Host (default: {default}): ", default)
        self.settings["iot_host"] = value
    
    def _edit_iot_port(self):
        """設置 IoT 端口"""
        print("\n輸入 IoT 算力網絡端口:")
        print("  8765  - 默認端口（推薦）")
        default = self.settings.get("iot_port", 8765)
        value = self._get_input(f"IoT Port (default: {default}): ", str(default))
        try:
            port = int(value)
            if 1024 <= port <= 65535:
                self.settings["iot_port"] = port
            else:
                print("端口必須在 1024-65535 之間")
        except ValueError:
            print("無效的端口號，保持原值")
    
    def _edit_device_scan(self):
        """設置設備掃描選項"""
        print("\n設備掃描設置:")
        print("  1. 啟用/禁用自動掃描")
        print("  2. 設置掃描間隔")
        print("  3. 查看已發現設備")
        print("  4. 返回")
        
        choice = self._get_input("Enter choice (1-4): ", "4")
        
        if choice == "1":
            enabled = self.settings.get("iot_scan_enabled", True)
            self.settings["iot_scan_enabled"] = not enabled
            status = "啟用" if self.settings["iot_scan_enabled"] else "禁用"
            print(f"  ✓ 設備掃描已{status}")
        
        elif choice == "2":
            default = self.settings.get("iot_scan_interval", 30)
            value = self._get_input(f"掃描間隔秒數 (default: {default}, 5-300): ", str(default))
            try:
                interval = int(value)
                if 5 <= interval <= 300:
                    self.settings["iot_scan_interval"] = interval
                    print(f"  ✓ 掃描間隔設為 {interval} 秒")
                else:
                    print("  間隔必須在 5-300 秒之間")
            except ValueError:
                print("  無效的數字")
        
        elif choice == "3":
            self._show_discovered_devices()
    
    def _show_discovered_devices(self):
        """顯示已發現設備列表"""
        devices = self.settings.get("iot_discovered_devices", [])
        
        if not devices:
            print("\n  尚未發現任何設備。請先執行手動掃描（選項 25）。")
            return
        
        print(f"\n  已發現 {len(devices)} 台設備:")
        print("  " + "-" * 50)
        for i, device in enumerate(devices, 1):
            ip = device.get("ip", "Unknown")
            port = device.get("port", "8765")
            name = device.get("device_name", "Unknown Device")
            print(f"  {i}. {name}")
            print(f"     地址: ws://{ip}:{port}")
            print(f"     IP: {ip}")
        print("  " + "-" * 50)
        
        # 允許連接
        print("\n  輸入設備編號進行連接（0 返回）:")
        try:
            num = self._get_input("  設備編號: ", "0")
            num = int(num)
            if 1 <= num <= len(devices):
                device = devices[num - 1]
                self._connect_to_device(device)
        except (ValueError, EOFError):
            pass
    
    def _connect_to_device(self, device: dict):
        """連接到選定設備"""
        ip = device.get("ip", "")
        port = device.get("port", 8765)
        name = device.get("device_name", "Unknown")
        
        print(f"\n  正在連接到 {name} ({ip}:{port})...")
        
        try:
            from tools.iot_compute_manager import get_manager
            manager = get_manager()
            
            if not manager.is_running():
                print("  啟動 IoT 算力網絡...")
                manager.start()
            
            # 嘗試連接（發送心跳測試）
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                print(f"  ✓ 設備 {name} 在線，可連接")
                device["is_connected"] = True
                self._save_settings()
            else:
                print(f"  ✗ 設備 {name} 離線或端口未開放")
                print(f"    請確保設備已安裝並啟動 Aize Companion")
                
        except ImportError:
            print("  ✗ IoT 模塊不可用，請安裝 websockets: pip install websockets>=12.0")
        except Exception as e:
            print(f"  ✗ 連接失敗: {e}")
    
    def _manual_scan_devices(self):
        """手動掃描設備"""
        print("\n  正在掃描局域網設備...")
        print("  （掃描可能需要幾秒鐘）")
        
        try:
            from tools.iot_device_scanner import IoTDeviceScanner
            
            port = self.settings.get("iot_port", 8765)
            scanner = IoTDeviceScanner(port=port, scan_interval=10)
            
            found = []
            
            def on_found(device):
                found.append(device)
            
            scanner.on_device_found(on_found)
            
            # 執行一次掃描
            scanner._do_scan()
            
            if found:
                print(f"\n  ✓ 掃描完成，發現 {len(found)} 台設備:")
                for i, device in enumerate(found, 1):
                    ip = device.get("ip", "Unknown")
                    port_num = device.get("port", "8765")
                    print(f"    {i}. {ip}:{port_num}")
                
                # 更新到設置
                existing = self.settings.get("iot_discovered_devices", [])
                existing_ids = {d.get("ip") for d in existing}
                
                for device in found:
                    if device.get("ip") not in existing_ids:
                        device["device_name"] = f"Aize Device ({device['ip']})"
                        existing.append(device)
                
                self.settings["iot_discovered_devices"] = existing
                self._save_settings()
                
                # 顯示並允許連接
                self._show_discovered_devices()
            else:
                print("\n  ✗ 未發現任何設備")
                print("    請確保:")
                print("    1. 手機已連接與電腦相同的 WiFi")
                print("    2. 手機已安裝 Aize Companion")
                print("    3. Aize Companion 已啟動並註冊")
                print("    4. 電腦防火牆未阻止入站連接")
        
        except ImportError:
            print("  ✗ IoT 模塊不可用")
        except Exception as e:
            print(f"  ✗ 掃描失敗: {e}")

    def run(self):
        self._print_header()
        
        while True:
            self._print_menu()
            choice = self._get_input("\nEnter choice (1-25, S to save, Q to quit): ").upper()
            
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
            elif choice == "21":
                self._edit_iot_auto_start()
            elif choice == "22":
                self._edit_iot_host()
            elif choice == "23":
                self._edit_iot_port()
            elif choice == "24":
                self._edit_device_scan()
            elif choice == "25":
                self._manual_scan_devices()
            else:
                print("\n[Settings] Invalid choice. Please try again.")


def main():
    settings_cli = SettingsCLI()
    settings_cli.run()


if __name__ == "__main__":
    main()
