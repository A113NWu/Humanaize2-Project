#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反制措施模块
实现攻击警告、攻击计数和防御等级升级功能

注意：此模块仅提供防御性反制措施，所有主动攻击功能（如远程关机）
仅在实验室模式下可用，并需要明确的授权确认。
"""

import os
import sys
import time
import socket
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .tools import SimpleLogger
except ImportError:
    from tools import SimpleLogger


class AttackTracker:
    """攻击跟踪器"""
    
    def __init__(self):
        self.attackers: Dict[str, Dict] = {}
        self.max_warnings = 2
        self.cooldown_period = 300
    
    def record_attack(self, ip: str, attack_type: str = "unknown") -> int:
        """记录攻击并返回当前警告次数"""
        now = time.time()
        
        if ip not in self.attackers:
            self.attackers[ip] = {
                "attack_count": 0,
                "warning_count": 0,
                "last_attack_time": 0,
                "last_warning_time": 0,
                "attack_types": [],
                "blocked": False,
                "countered": False
            }
        
        attacker = self.attackers[ip]
        
        if now - attacker["last_attack_time"] > self.cooldown_period:
            attacker["warning_count"] = 0
        
        attacker["attack_count"] += 1
        attacker["last_attack_time"] = now
        
        if attack_type not in attacker["attack_types"]:
            attacker["attack_types"].append(attack_type)
        
        return attacker["warning_count"]
    
    def increment_warning(self, ip: str) -> int:
        """增加警告计数"""
        if ip in self.attackers:
            self.attackers[ip]["warning_count"] += 1
            self.attackers[ip]["last_warning_time"] = time.time()
            return self.attackers[ip]["warning_count"]
        return 0
    
    def should_counter(self, ip: str) -> bool:
        """判断是否应该执行反制"""
        if ip not in self.attackers:
            return False
        
        attacker = self.attackers[ip]
        return attacker["warning_count"] >= self.max_warnings and not attacker["countered"]
    
    def mark_countered(self, ip: str):
        """标记已执行反制"""
        if ip in self.attackers:
            self.attackers[ip]["countered"] = True
    
    def mark_blocked(self, ip: str):
        """标记已封禁"""
        if ip in self.attackers:
            self.attackers[ip]["blocked"] = True
    
    def get_attacker_info(self, ip: str) -> Optional[Dict]:
        """获取攻击者信息"""
        return self.attackers.get(ip)
    
    def get_all_attackers(self) -> List[Dict]:
        """获取所有攻击者列表"""
        result = []
        for ip, info in self.attackers.items():
            result.append({
                "ip": ip,
                **info
            })
        return result
    
    def reset_attacker(self, ip: str):
        """重置攻击者计数"""
        if ip in self.attackers:
            del self.attackers[ip]


class WarningSender:
    """警告发送器"""
    
    def __init__(self):
        try:
            from .color_logger import color_logger
            self.logger = color_logger
        except ImportError:
            from tools import SimpleLogger
            self.logger = SimpleLogger("counter_measure.log")
    
    def send_warning(self, target_ip: str, warning_level: int = 1, async_mode: bool = True) -> bool:
        """发送警告消息"""
        messages = {
            1: "WARNING: Your IP address has been detected performing malicious activities. "
               "Please cease all unauthorized access attempts immediately. "
               "This is warning 1 of 2.",
            
            2: "FINAL WARNING: Your IP address has been detected performing repeated malicious activities. "
               "Immediate cessation is required. Failure to comply will result in enhanced defensive measures. "
               "This is warning 2 of 2."
        }
        
        message = messages.get(warning_level, messages[1])
        
        if async_mode:
            thread = threading.Thread(target=self._send_message, args=(target_ip, message), daemon=True)
            thread.start()
            return True
        else:
            return self._send_message(target_ip, message)
    
    def _send_message(self, target_ip: str, message: str) -> bool:
        """通过socket发送消息"""
        try:
            for port in [80, 443, 22]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                
                try:
                    if sock.connect_ex((target_ip, port)) == 0:
                        sock.sendall(f"[HUMANAIZE SECURITY] {message}\n".encode('utf-8'))
                        sock.close()
                        self.logger.info(f"Warning sent to {target_ip} on port {port}")
                        return True
                except Exception:
                    pass
                finally:
                    sock.close()
            
            self.logger.warn(f"Failed to send warning to {target_ip}: No open ports found")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to send warning to {target_ip}: {e}")
            return False


class CounterMeasure:
    """反制措施核心类"""
    
    def __init__(self, lab_mode: bool = False):
        try:
            from .color_logger import color_logger, ai_notifier
            self.logger = color_logger
            self.ai_notifier = ai_notifier
        except ImportError:
            from tools import SimpleLogger
            self.logger = SimpleLogger("counter_measure.log")
            self.ai_notifier = None
        
        self.tracker = AttackTracker()
        self.sender = WarningSender()
        self.lab_mode = lab_mode
        self.enabled = True
        
        self._legal_disclaimer()
    
    def _legal_disclaimer(self):
        """法律免责声明"""
        self.logger.info("=" * 60)
        self.logger.info("COUNTER MEASURE MODULE - LEGAL DISCLAIMER")
        self.logger.info("=" * 60)
        self.logger.info("This module is designed for DEFENSIVE purposes only.")
        self.logger.info("All counter measures are non-destructive and compliant with")
        self.logger.info("applicable laws and regulations.")
        self.logger.info("=" * 60)
    
    def process_attack(self, ip: str, attack_type: str = "unknown") -> Dict:
        """处理攻击事件"""
        if not self.enabled:
            return {"status": "disabled", "message": "Counter measure is disabled"}
        
        warning_count = self.tracker.record_attack(ip, attack_type)
        
        if warning_count < self.tracker.max_warnings:
            new_warning_count = self.tracker.increment_warning(ip)
            self.sender.send_warning(ip, new_warning_count)
            
            self.logger.warning_sent(ip, new_warning_count, self.tracker.max_warnings)
            
            if self.ai_notifier:
                self.ai_notifier.notify(
                    action_type="警告发送",
                    description=f"向攻击者发送第{new_warning_count}次警告",
                    target=ip,
                    result="success",
                    details={
                        "警告次数": f"{new_warning_count}/{self.tracker.max_warnings}",
                        "攻击类型": attack_type
                    }
                )
            
            return {
                "status": "warning_sent",
                "ip": ip,
                "warning_count": new_warning_count,
                "max_warnings": self.tracker.max_warnings,
                "message": f"Warning {new_warning_count} of {self.tracker.max_warnings} sent to {ip}"
            }
        
        elif self.tracker.should_counter(ip):
            return self._execute_counter_measure(ip)
        
        else:
            return {
                "status": "already_countered",
                "ip": ip,
                "message": f"Counter measure already executed for {ip}"
            }
    
    def _execute_counter_measure(self, ip: str) -> Dict:
        """执行反制措施"""
        self.tracker.mark_countered(ip)
        
        if self.lab_mode:
            result = self._simulate_shutdown(ip)
        else:
            result = self._logical_counter(ip)
        
        if self.ai_notifier:
            action_type = "远程关机" if self.lab_mode else "反制措施"
            description = result.get("message", "执行反制措施")
            
            self.ai_notifier.notify(
                action_type=action_type,
                description=description,
                target=ip,
                result="success",
                details={
                    "实验室模式": str(self.lab_mode),
                    "操作方式": result.get("method", "unknown"),
                    "操作详情": result.get("message", "")
                }
            )
        
        return {
            "status": "counter_executed",
            "ip": ip,
            "lab_mode": self.lab_mode,
            **result
        }
    
    def _logical_counter(self, ip: str) -> Dict:
        """逻辑反制（非破坏性）"""
        self.tracker.mark_blocked(ip)
        
        self.logger.info(f"Logical counter executed for {ip}: Enhanced defensive measures activated")
        
        return {
            "action": "logical_counter",
            "method": "defense_escalation",
            "message": f"Enhanced defensive measures activated for attacker IP: {ip}"
        }
    
    def _simulate_shutdown(self, ip: str) -> Dict:
        """模拟关机（实验室模式）"""
        self.logger.warn(f"[LAB MODE] Simulating shutdown command for attacker IP: {ip}")
        
        shutdown_commands = [
            f"echo 'SHUTDOWN command simulated for {ip}'",
            f"logger -t humanaize 'ATTACKER {ip} WOULD BE SHUT DOWN NOW'"
        ]
        
        for cmd in shutdown_commands:
            try:
                subprocess.run(cmd, shell=True, check=False)
            except Exception:
                pass
        
        return {
            "action": "simulated_shutdown",
            "method": "lab_mode_shutdown",
            "message": f"[LAB MODE] Shutdown command simulated for attacker IP: {ip}",
            "warning": "This is a SIMULATION - no actual shutdown was performed"
        }
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "enabled": self.enabled,
            "lab_mode": self.lab_mode,
            "max_warnings": self.tracker.max_warnings,
            "attackers_count": len(self.tracker.get_all_attackers()),
            "attackers": self.tracker.get_all_attackers()
        }
    
    def enable(self):
        """启用反制措施"""
        self.enabled = True
        self.logger.info("Counter measure enabled")
    
    def disable(self):
        """禁用反制措施"""
        self.enabled = False
        self.logger.info("Counter measure disabled")
    
    def set_lab_mode(self, enabled: bool):
        """设置实验室模式"""
        self.lab_mode = enabled
        if enabled:
            self.logger.warn("LAB MODE ENABLED - Simulated counter measures will be executed")
        else:
            self.logger.info("LAB MODE DISABLED - Only logical counter measures will be executed")


class CounterMeasureAPI:
    """反制措施API接口"""
    
    def __init__(self):
        self.counter = CounterMeasure()
    
    def process_attack(self, ip: str, attack_type: str = "unknown") -> Dict:
        """处理攻击事件"""
        return self.counter.process_attack(ip, attack_type)
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {"status": "success", "data": self.counter.get_status()}
    
    def enable(self) -> Dict:
        """启用反制措施"""
        self.counter.enable()
        return {"status": "success", "message": "Counter measure enabled"}
    
    def disable(self) -> Dict:
        """禁用反制措施"""
        self.counter.disable()
        return {"status": "success", "message": "Counter measure disabled"}
    
    def set_lab_mode(self, enabled: bool) -> Dict:
        """设置实验室模式"""
        self.counter.set_lab_mode(enabled)
        return {
            "status": "success",
            "message": f"Lab mode {'enabled' if enabled else 'disabled'}",
            "lab_mode": enabled
        }
    
    def get_attacker_info(self, ip: str) -> Dict:
        """获取攻击者信息"""
        info = self.counter.tracker.get_attacker_info(ip)
        if info:
            return {"status": "success", "ip": ip, "data": info}
        return {"status": "error", "message": f"No attacker info found for {ip}"}
    
    def reset_attacker(self, ip: str) -> Dict:
        """重置攻击者计数"""
        self.counter.tracker.reset_attacker(ip)
        return {"status": "success", "message": f"Attacker {ip} reset"}


counter_measure_api = CounterMeasureAPI()