#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Guard Mode - 独立守护模式模块
提供实时安全监控和防御功能，支持前台和后台运行
"""

import os
import sys
import time
import json
import signal
import subprocess
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    import daemon
    HAS_DAEMON = True
except ImportError:
    HAS_DAEMON = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .tools import SimpleLogger
    from .ai_firewall import ai_firewall
    HAS_AI_FIREWALL = True
except ImportError:
    try:
        from .firewall import firewall_api
        HAS_AI_FIREWALL = False
    except ImportError:
        from tools import SimpleLogger
        from firewall import firewall_api
        HAS_AI_FIREWALL = False


class GuardMode:
    """Guard 模式核心类"""
    
    def __init__(self, background: bool = False, start_on_boot: bool = False):
        self.background = background
        self.start_on_boot = start_on_boot
        self.running = False
        self.logger = None
        self.monitor_thread = None
        self._init_logger()
        
        self.config = self._load_config()
        self.status = {
            "running": False,
            "mode": "background" if background else "foreground",
            "start_on_boot": start_on_boot,
            "firewall_active": False,
            "attacks_detected": 0,
            "ips_blocked": 0,
            "last_check": None,
            "uptime": 0
        }
        
        self._start_time = None
    
    def _init_logger(self):
        """初始化日志记录器"""
        try:
            from .color_logger import color_logger
            self.logger = color_logger
        except ImportError:
            from tools import SimpleLogger
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            if self.background:
                log_file = os.path.join(log_dir, "guard_mode.log")
                self.logger = SimpleLogger(log_file)
            else:
                self.logger = SimpleLogger("guard_mode.log")
    
    def _load_config(self) -> Dict:
        """加载 Guard 模式配置"""
        config_path = self._get_config_path()
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return self._get_default_config()
    
    def _get_config_path(self) -> str:
        """获取配置文件路径"""
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "guard_config.json")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "enabled": True,
            "auto_start": False,
            "monitor_interval": 5,
            "alert_threshold": 3,
            "max_block_duration": 3600,
            "log_level": "info",
            "firewall_enabled": False,
            "network_monitoring": True,
            "system_monitoring": True,
            "attack_signatures": True,
            "auto_defense": True
        }
    
    def _save_config(self):
        """保存配置"""
        config_path = self._get_config_path()
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
    
    def log(self, message: str, level: str = "info"):
        """日志输出"""
        if self.logger:
            if level == "error":
                self.logger.error(message)
            elif level == "warn":
                self.logger.warn(message)
            elif level == "success":
                if hasattr(self.logger, 'success'):
                    self.logger.success(message)
                else:
                    self.logger.info(message)
            elif level == "attack":
                if hasattr(self.logger, 'attack_detected'):
                    self.logger.attack_detected(message, "", "high")
                else:
                    self.logger.warn(message)
            elif level == "defense":
                if hasattr(self.logger, 'defense_action'):
                    self.logger.defense_action(message)
                else:
                    self.logger.info(message)
            else:
                self.logger.info(message)
    
    def start(self):
        """启动 Guard 模式"""
        if self.running:
            self.log("Guard mode is already running", "warn")
            return {"status": "error", "message": "Guard mode is already running"}
        
        self.log("Starting Guard mode...")
        self.running = True
        self._start_time = time.time()
        
        self._apply_startup_config()
        
        if self.config.get("firewall_enabled", False):
            self._start_firewall()
            self.status["firewall_active"] = True
        else:
            self.log("Firewall is disabled by default. It will be activated when Aize detects security threats.", "info")
            self.status["firewall_active"] = False
        
        self._start_monitoring()
        
        self.status["running"] = True
        self.log("Guard mode started successfully", "success")
        
        if not self.background:
            self._run_foreground()
        else:
            return {"status": "success", "message": "Guard mode started in background"}
    
    def stop(self):
        """停止 Guard 模式"""
        if not self.running:
            self.log("Guard mode is not running", "warn")
            return {"status": "error", "message": "Guard mode is not running"}
        
        self.log("Stopping Guard mode...")
        self.running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        if HAS_AI_FIREWALL:
            if ai_firewall.firewall_api.firewall.running:
                ai_firewall.firewall_api.stop_firewall()
                ai_firewall.stop()
                self.log("AI Firewall stopped", "success")
        else:
            if firewall_api and firewall_api.firewall.running:
                firewall_api.stop_firewall()
                self.log("Firewall stopped")
        
        self.status["running"] = False
        self.status["firewall_active"] = False
        self.log("Guard mode stopped successfully", "success")
        return {"status": "success", "message": "Guard mode stopped"}
    
    def _apply_startup_config(self):
        """应用启动配置"""
        if self.start_on_boot:
            self.config["auto_start"] = True
            self._save_config()
            self._setup_auto_start()
            self.log("Auto-start configuration updated")
    
    def _setup_auto_start(self):
        """设置系统启动时自动运行"""
        try:
            service_path = "/etc/systemd/system/humanaize-guard.service"
            
            if os.path.exists(service_path):
                self.log("Guard service already exists")
                return
            
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config",
                "humanaize-guard.service.template"
            )
            
            if os.path.exists(template_path):
                with open(template_path, 'r') as f:
                    template = f.read()
                
                install_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                home_dir = os.path.expanduser("~")
                
                service_content = template.replace("@@INSTALL_DIR@@", install_dir)
                service_content = service_content.replace("@@HOME_DIR@@", home_dir)
                
                with open(service_path, 'w') as f:
                    f.write(service_content)
                
                subprocess.run(["systemctl", "daemon-reload"], check=True)
                subprocess.run(["systemctl", "enable", "humanaize-guard"], check=True)
                self.log("Guard service registered for auto-start", "success")
            else:
                self.log("Service template not found", "warn")
                
        except Exception as e:
            self.log(f"Failed to setup auto-start: {e}", "error")
    
    def _remove_auto_start(self):
        """移除系统启动自动运行"""
        try:
            subprocess.run(["systemctl", "disable", "humanaize-guard"], check=False)
            service_path = "/etc/systemd/system/humanaize-guard.service"
            if os.path.exists(service_path):
                os.remove(service_path)
            subprocess.run(["systemctl", "daemon-reload"], check=False)
            self.log("Auto-start disabled", "success")
        except Exception as e:
            self.log(f"Failed to remove auto-start: {e}", "error")
    
    def _start_firewall(self):
        """启动防火墙"""
        try:
            if HAS_AI_FIREWALL:
                result = ai_firewall.firewall_api.start_firewall()
                if result.get("status") == "success":
                    self.log("AI Firewall started successfully", "success")
                    self.log("AI分析循环已启动，将自动分析攻击并优化防御策略", "info")
                else:
                    self.log(f"Failed to start AI firewall: {result.get('message')}", "error")
            else:
                result = firewall_api.start_firewall()
                if result.get("status") == "success":
                    self.log("Firewall started successfully")
                else:
                    self.log(f"Failed to start firewall: {result.get('message')}", "error")
        except Exception as e:
            self.log(f"Firewall startup error: {e}", "error")
    
    def _start_monitoring(self):
        """启动监控线程"""
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def _monitor_loop(self):
        """监控主循环"""
        while self.running:
            try:
                self._perform_checks()
            except Exception as e:
                self.log(f"Monitoring loop error: {e}", "error")
            
            interval = self.config.get("monitor_interval", 5)
            time.sleep(interval)
    
    def _perform_checks(self):
        """执行安全检查"""
        if self.config.get("firewall_enabled", True):
            self._check_firewall_status()
        
        if self.config.get("network_monitoring", True):
            self._check_network_activity()
        
        if self.config.get("system_monitoring", True):
            self._check_system_health()
        
        self._update_status()
    
    def _check_firewall_status(self):
        """检查防火墙状态"""
        try:
            if HAS_AI_FIREWALL:
                status = ai_firewall.get_status()
                fw_status = status.get("firewall", {})
                if fw_status.get("running"):
                    self.status["firewall_active"] = True
                    self.status["attacks_detected"] = fw_status.get("attack_records_count", 0)
                    self.status["ips_blocked"] = fw_status.get("blocked_ips_count", 0)
                    self.status["ai_analysis_running"] = status.get("analysis_loop_running", False)
                    self.status["defense_history_count"] = status.get("defense_history_count", 0)
                    
                    recent_attacks = fw_status.get("recent_attacks", [])
                    for attack in recent_attacks:
                        self.log(f"Attack detected: {attack.get('attack_type')} from {attack.get('source_ip')}", "attack")
                else:
                    self.status["firewall_active"] = False
            else:
                status = firewall_api.get_status()
                if status.get("running"):
                    self.status["firewall_active"] = True
                    self.status["attacks_detected"] = status.get("attack_records_count", 0)
                    self.status["ips_blocked"] = status.get("blocked_ips_count", 0)
                    
                    recent_attacks = status.get("recent_attacks", [])
                    for attack in recent_attacks:
                        self.log(f"Attack detected: {attack.get('attack_type')} from {attack.get('source_ip')}", "attack")
                else:
                    self.status["firewall_active"] = False
                self.log("Firewall is not running", "warn")
        except Exception as e:
            self.log(f"Firewall status check failed: {e}", "error")
    
    def _check_network_activity(self):
        """检查网络活动"""
        try:
            result = subprocess.run(
                ["netstat", "-tn"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            connections = result.stdout.strip().split('\n')[2:]
            active_connections = len(connections)
            
            if active_connections > 50:
                self.log(f"High network activity detected: {active_connections} connections", "warn")
            
        except Exception as e:
            pass
    
    def _check_system_health(self):
        """检查系统健康状态"""
        try:
            result = subprocess.run(
                ["free", "-m"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                mem_line = lines[1]
                parts = mem_line.split()
                if len(parts) >= 3:
                    used = int(parts[2])
                    total = int(parts[1])
                    percentage = (used / total) * 100
                    
                    if percentage > 80:
                        self.log(f"High memory usage detected: {percentage:.1f}%", "warn")
            
        except Exception as e:
            pass
    
    def _update_status(self):
        """更新状态信息"""
        if self._start_time:
            self.status["uptime"] = int(time.time() - self._start_time)
        self.status["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _run_foreground(self):
        """前台运行模式"""
        self.log("Running in foreground mode. Press Ctrl+C to stop.")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.log("Received interrupt signal, stopping...")
            self.stop()
    
    def run_in_background(self):
        """后台运行模式"""
        pid_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "guard_mode.pid"
        )
        
        def signal_handler(signum, frame):
            self.stop()
        
        if HAS_DAEMON:
            context = daemon.DaemonContext(
                working_directory=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                pidfile=daemon.pidfile.PIDLockFile(pid_file),
                stdout=None,
                stderr=None,
                stdin=None,
            )
            
            with context:
                signal.signal(signal.SIGTERM, signal_handler)
                signal.signal(signal.SIGINT, signal_handler)
                
                self.start()
                
                while self.running:
                    time.sleep(1)
        else:
            self._run_in_background_fallback(pid_file, signal_handler)
    
    def _run_in_background_fallback(self, pid_file: str, signal_handler):
        """后台运行的降级方案（当daemon模块不可用时）"""
        if os.fork():
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            sys.exit(0)
        
        os.setsid()
        
        if os.fork():
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        self.start()
        
        while self.running:
            time.sleep(1)
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            "running": self.running,
            "mode": "background" if self.background else "foreground",
            "start_on_boot": self.start_on_boot,
            "firewall_active": self.status.get("firewall_active", False),
            "attacks_detected": self.status.get("attacks_detected", 0),
            "ips_blocked": self.status.get("ips_blocked", 0),
            "last_check": self.status.get("last_check"),
            "uptime": self.status.get("uptime", 0),
            "config": self.config
        }
    
    def update_config(self, config_updates: Dict):
        """更新配置"""
        self.config.update(config_updates)
        self._save_config()
        self.log("Configuration updated")
        return {"status": "success", "message": "Configuration updated"}
    
    def test_connection(self) -> Dict:
        """测试连接"""
        return {"status": "success", "message": "Guard mode connection test successful"}


class GuardModeAPI:
    """Guard 模式 API 接口"""
    
    def __init__(self):
        self.guard_mode = None
    
    def start(self, background: bool = False, start_on_boot: bool = False) -> Dict:
        """启动 Guard 模式"""
        try:
            self.guard_mode = GuardMode(background=background, start_on_boot=start_on_boot)
            
            if background:
                self.guard_mode.run_in_background()
                return {"status": "success", "message": "Guard mode started in background"}
            else:
                self.guard_mode.start()
                return {"status": "success", "message": "Guard mode started in foreground"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def stop(self) -> Dict:
        """停止 Guard 模式"""
        if self.guard_mode:
            return self.guard_mode.stop()
        return {"status": "error", "message": "Guard mode is not running"}
    
    def get_status(self) -> Dict:
        """获取状态"""
        if self.guard_mode:
            return {"status": "success", "data": self.guard_mode.get_status()}
        return {"status": "error", "message": "Guard mode is not running"}
    
    def update_config(self, config_updates: Dict) -> Dict:
        """更新配置"""
        if self.guard_mode:
            return self.guard_mode.update_config(config_updates)
        return {"status": "error", "message": "Guard mode is not running"}
    
    def enable_auto_start(self) -> Dict:
        """启用开机自启"""
        try:
            config = GuardMode._get_default_config()
            config["auto_start"] = True
            
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config",
                "guard_config.json"
            )
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            guard = GuardMode()
            guard._setup_auto_start()
            
            return {"status": "success", "message": "Auto-start enabled"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def disable_auto_start(self) -> Dict:
        """禁用开机自启"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config",
                "guard_config.json"
            )
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                config["auto_start"] = False
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
            
            guard = GuardMode()
            guard._remove_auto_start()
            
            return {"status": "success", "message": "Auto-start disabled"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


guard_mode_api = GuardModeAPI()