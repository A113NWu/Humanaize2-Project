#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 自动防火墙模块
实现实时攻击检测、流量监控和基础防御功能
"""

import os
import sys
import time
import json
import subprocess
import socket
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .tools import SimpleLogger
except ImportError:
    from tools import SimpleLogger


class AttackSignature:
    """攻击签名定义"""
    
    def __init__(self, name: str, pattern: str, severity: str = "medium", category: str = "unknown"):
        self.name = name
        self.pattern = pattern
        self.severity = severity
        self.category = category
    
    def match(self, data: str) -> bool:
        """检查数据是否匹配攻击签名"""
        import re
        try:
            return re.search(self.pattern, data, re.IGNORECASE) is not None
        except:
            return False


class AttackRecord:
    """攻击记录"""
    
    def __init__(self, attack_type: str, source_ip: str, source_port: int, 
                 target_ip: str, target_port: int, severity: str, timestamp: float = None):
        self.attack_type = attack_type
        self.source_ip = source_ip
        self.source_port = source_port
        self.target_ip = target_ip
        self.target_port = target_port
        self.severity = severity
        self.timestamp = timestamp or time.time()
        self.blocked = False
    
    def to_dict(self) -> Dict:
        return {
            "attack_type": self.attack_type,
            "source_ip": self.source_ip,
            "source_port": self.source_port,
            "target_ip": self.target_ip,
            "target_port": self.target_port,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "blocked": self.blocked
        }


class Firewall:
    """防火墙核心类"""
    
    def __init__(self):
        try:
            from .color_logger import color_logger, ai_notifier
            self.logger = color_logger
            self.ai_notifier = ai_notifier
        except ImportError:
            self.logger = SimpleLogger("firewall.log")
        
        self.has_root = self._check_root()
        self.use_sudo = False
        
        self.running = False
        self.monitor_thread = None
        self.iptables_setup = False
        
        self.blocked_ips = {}
        self.blocked_ports = set()
        self.attack_records: List[AttackRecord] = []
        self.traffic_stats: Dict[str, Dict] = {}
        
        self.signatures = self._load_signatures()
        self.max_block_duration = 3600
        self.max_attack_threshold = 5
        self.traffic_threshold = 1000
        
        self._init_counter_measure()
    
    def _init_counter_measure(self):
        """初始化反制措施模块"""
        try:
            from .counter_measure import counter_measure_api
            self.counter_measure = counter_measure_api
            self.logger.info("Counter measure module initialized")
        except ImportError as e:
            self.counter_measure = None
            self.logger.warn(f"Counter measure module not available: {e}")
    
    def _load_signatures(self) -> List[AttackSignature]:
        """加载攻击签名"""
        return [
            AttackSignature("SQL注入", r"(?i)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|OR\s+1=1|AND\s+1=1|' OR '1'='1)", "high", "sqli"),
            AttackSignature("XSS攻击", r"(?i)<script[^>]*>.*?</script>|<img[^>]*onerror=|<iframe[^>]*>", "high", "xss"),
            AttackSignature("命令注入", r"(?i)(;|&&|\|\||`.*`|\$\(.*\))", "high", "command"),
            AttackSignature("路径遍历", r"(?i)\.\./|\.\.\\|%2e%2e/", "high", "path"),
            AttackSignature("暴力破解", r"(?i)(admin|root|test)[^a-zA-Z0-9]", "medium", "bruteforce"),
            AttackSignature("端口扫描", r"(?i)nmap|scan|ping|traceroute", "medium", "scan"),
            AttackSignature("缓冲区溢出", r"(?i)(%00|%0d|%0a)+", "high", "overflow"),
            AttackSignature("拒绝服务", r"(?i)(SYN|ACK|FIN|UDP).*flood", "high", "dos"),
        ]
    
    def _check_root(self) -> bool:
        """检查是否有root权限"""
        try:
            return os.getuid() == 0
        except AttributeError:
            return False
    
    def _run_iptables(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """执行iptables命令（自动处理权限问题）"""
        if not self.has_root and not self.use_sudo:
            self._check_sudo()
        
        if self.use_sudo:
            full_command = ["sudo"] + command
        else:
            full_command = command
        
        return subprocess.run(full_command, check=check, capture_output=True, text=True)
    
    def _check_sudo(self):
        """检查sudo是否可用"""
        try:
            result = subprocess.run(["sudo", "-n", "true"], check=True, capture_output=True)
            self.use_sudo = True
            self.logger.info("Sudo available, will use for iptables commands")
        except subprocess.CalledProcessError:
            self.use_sudo = False
            self.logger.warn("Sudo not available without password, iptables commands may fail")
    
    def _setup_ip_tables(self):
        """初始化iptables规则"""
        if not self.has_root and not self.use_sudo:
            self._check_sudo()
        
        try:
            cmd_prefix = ["sudo"] if self.use_sudo else []
            
            result1 = subprocess.run(cmd_prefix + ["iptables", "-N", "HUMANAIZE_FW"], 
                                     check=False, capture_output=True, text=True)
            
            subprocess.run(cmd_prefix + ["iptables", "-D", "INPUT", "-j", "HUMANAIZE_FW"], 
                           check=False, capture_output=True, text=True)
            
            result2 = subprocess.run(cmd_prefix + ["iptables", "-I", "INPUT", "1", "-j", "HUMANAIZE_FW"], 
                                     check=False, capture_output=True, text=True)
            
            if result1.returncode != 0 or result2.returncode != 0:
                stderr = ""
                if result1.stderr:
                    stderr += result1.stderr
                if result2.stderr:
                    stderr += " " + result2.stderr
                
                if "Permission denied" in stderr or (result1.returncode == 4 or result2.returncode == 4):
                    self.logger.warn("权限不足，iptables规则可能未正确初始化。请以root用户运行或配置sudo免密码")
                elif "File exists" in stderr:
                    self.logger.info("Firewall chain already exists")
                else:
                    self.logger.warn(f"Failed to setup iptables: {stderr}")
            else:
                self.logger.info("Firewall rules initialized (HUMANAIZE_FW at INPUT chain position 1)")
            
            self.iptables_setup = True
        except Exception as e:
            self.logger.warn(f"Failed to setup iptables: {e}")
    
    def _cleanup_ip_tables(self):
        """清理iptables规则"""
        try:
            cmd_prefix = ["sudo"] if self.use_sudo else []
            
            subprocess.run(cmd_prefix + ["iptables", "-D", "INPUT", "-j", "HUMANAIZE_FW"], 
                           check=False, capture_output=True, text=True)
            
            for ip in list(self.blocked_ips.keys()):
                subprocess.run(cmd_prefix + ["iptables", "-D", "HUMANAIZE_FW", "-s", ip, "-j", "DROP"], 
                               check=False, capture_output=True, text=True)
            
            for port in list(self.blocked_ports):
                subprocess.run(cmd_prefix + ["iptables", "-D", "HUMANAIZE_FW", "-p", "tcp", "--dport", str(port), "-j", "DROP"], 
                               check=False, capture_output=True, text=True)
            
            subprocess.run(cmd_prefix + ["iptables", "-F", "HUMANAIZE_FW"], 
                           check=False, capture_output=True, text=True)
            
            subprocess.run(cmd_prefix + ["iptables", "-X", "HUMANAIZE_FW"], 
                           check=False, capture_output=True, text=True)
            
            self.iptables_setup = False
            self.blocked_ips.clear()
            self.blocked_ports.clear()
            self.logger.info("Firewall rules cleaned up")
        except Exception as e:
            self.logger.warn(f"Failed to cleanup iptables: {e}")
    
    def enable(self):
        """启用防火墙（初始化iptables规则）"""
        if not self.iptables_setup:
            self._setup_ip_tables()
        self.logger.info("Firewall enabled")
    
    def disable(self):
        """禁用防火墙（清理iptables规则）"""
        if self.iptables_setup:
            self._cleanup_ip_tables()
        self.logger.info("Firewall disabled")
    
    def start(self):
        """启动防火墙"""
        self.enable()
        self.running = True
        self.logger.info("AI Firewall started")
        
        self.monitor_thread = threading.Thread(target=self._monitor_traffic, daemon=True)
        self.monitor_thread.start()
        
        cleanup_thread = threading.Thread(target=self._cleanup_expired_blocks, daemon=True)
        cleanup_thread.start()
    
    def stop(self):
        """停止防火墙"""
        self.running = False
        self.logger.info("AI Firewall stopped")
    
    def _monitor_traffic(self):
        """监控网络流量"""
        while self.running:
            self._collect_traffic_stats()
            time.sleep(1)
    
    def _collect_traffic_stats(self):
        """收集流量统计"""
        try:
            result = subprocess.run(
                ["netstat", "-tn"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            
            lines = result.stdout.strip().split('\n')[2:]
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    local_addr = parts[3]
                    remote_addr = parts[4]
                    
                    ip = remote_addr.split(':')[0] if ':' in remote_addr else remote_addr
                    
                    if ip not in self.traffic_stats:
                        self.traffic_stats[ip] = {"count": 0, "last_seen": time.time()}
                    
                    self.traffic_stats[ip]["count"] += 1
                    self.traffic_stats[ip]["last_seen"] = time.time()
                    
                    if self.traffic_stats[ip]["count"] > self.traffic_threshold:
                        self._detect_anomaly(ip)
                        
        except Exception as e:
            pass
    
    def _detect_anomaly(self, ip: str):
        """检测异常流量"""
        if ip in self.blocked_ips:
            return
        
        self.logger.warn(f"Anomalous traffic detected from {ip}")
        
        attack = AttackRecord(
            attack_type="流量异常",
            source_ip=ip,
            source_port=0,
            target_ip="",
            target_port=0,
            severity="high"
        )
        self.attack_records.append(attack)
        
        self.trigger_defense(attack)
    
    def detect_attack(self, data: str, source_ip: str = "", source_port: int = 0,
                      target_ip: str = "", target_port: int = 0, 
                      auto_defense: bool = True) -> Optional[AttackRecord]:
        """检测攻击"""
        for signature in self.signatures:
            if signature.match(data):
                attack = AttackRecord(
                    attack_type=signature.name,
                    source_ip=source_ip,
                    source_port=source_port,
                    target_ip=target_ip,
                    target_port=target_port,
                    severity=signature.severity
                )
                self.attack_records.append(attack)
                
                self.logger.attack_detected(attack.attack_type, attack.source_ip, attack.severity)
                
                if self.ai_notifier:
                    self.ai_notifier.notify(
                        action_type="攻击检测",
                        description=f"发现{attack.attack_type}攻击",
                        target=attack.source_ip,
                        result="detected",
                        details={
                            "攻击类型": attack.attack_type,
                            "源IP": attack.source_ip,
                            "源端口": attack.source_port,
                            "目标IP": attack.target_ip,
                            "目标端口": attack.target_port,
                            "严重程度": attack.severity
                        }
                    )
                
                if auto_defense:
                    self.trigger_defense(attack)
                
                return attack
        return None
    
    def block_ip(self, ip: str, duration: int = 3600):
        """封禁IP"""
        if ip in self.blocked_ips:
            self.logger.warn(f"IP {ip} is already blocked, updating duration")
            self.blocked_ips[ip]["expires_at"] = time.time() + duration
            self.blocked_ips[ip]["duration"] = duration
            return
        
        try:
            cmd_prefix = ["sudo"] if self.use_sudo else []
            
            subprocess.run(cmd_prefix + ["iptables", "-D", "HUMANAIZE_FW", "-s", ip, "-j", "DROP"], 
                           check=False, capture_output=True, text=True)
            
            result = subprocess.run(cmd_prefix + ["iptables", "-I", "HUMANAIZE_FW", "1", "-s", ip, "-j", "DROP"], 
                                   check=True, capture_output=True, text=True)
            
            self.blocked_ips[ip] = {
                "blocked_at": time.time(),
                "duration": duration,
                "expires_at": time.time() + duration
            }
            
            self.logger.defense_action(f"IP封禁 {duration}秒", ip)
            
            if self.ai_notifier:
                self.ai_notifier.notify(
                    action_type="IP封禁",
                    description=f"封禁恶意IP地址",
                    target=ip,
                    result="success",
                    details={"封禁时长": f"{duration}秒"}
                )
        except subprocess.CalledProcessError as e:
            if "Permission denied" in str(e) or e.returncode == 4:
                error_msg = f"权限不足，无法执行iptables命令。请以root用户运行或配置sudo免密码"
                self.logger.warn(error_msg)
                if self.ai_notifier:
                    self.ai_notifier.notify(
                        action_type="IP封禁",
                        description=f"尝试封禁IP失败（权限不足）",
                        target=ip,
                        result="failed",
                        details={"错误信息": error_msg}
                    )
            else:
                self.logger.error(f"Failed to block IP {ip}: {e.stderr or str(e)}")
                if self.ai_notifier:
                    self.ai_notifier.notify(
                        action_type="IP封禁",
                        description=f"尝试封禁IP失败",
                        target=ip,
                        result="failed",
                        details={"错误信息": e.stderr or str(e)}
                    )
        except Exception as e:
            self.logger.error(f"Failed to block IP {ip}: {e}")
            if self.ai_notifier:
                self.ai_notifier.notify(
                    action_type="IP封禁",
                    description=f"尝试封禁IP失败",
                    target=ip,
                    result="failed",
                    details={"错误信息": str(e)}
                )
    
    def unblock_ip(self, ip: str):
        """解除IP封禁"""
        try:
            if self.use_sudo:
                subprocess.run(["sudo", "iptables", "-D", "HUMANAIZE_FW", "-s", ip, "-j", "DROP"], 
                               check=True, capture_output=True, text=True)
            else:
                subprocess.run(["iptables", "-D", "HUMANAIZE_FW", "-s", ip, "-j", "DROP"], 
                               check=True, capture_output=True, text=True)
            
            if ip in self.blocked_ips:
                del self.blocked_ips[ip]
            
            self.logger.info(f"IP unblocked: {ip}")
        except subprocess.CalledProcessError as e:
            if "Permission denied" in str(e) or e.returncode == 4:
                self.logger.warn(f"权限不足，无法解除IP封禁: {ip}")
            else:
                self.logger.error(f"Failed to unblock IP {ip}: {e.stderr or str(e)}")
        except Exception as e:
            self.logger.error(f"Failed to unblock IP {ip}: {e}")
    
    def block_port(self, port: int, protocol: str = "tcp"):
        """封禁端口"""
        if port in self.blocked_ports:
            return
        
        try:
            cmd_prefix = ["sudo"] if self.use_sudo else []
            
            subprocess.run(cmd_prefix + ["iptables", "-D", "HUMANAIZE_FW", "-p", protocol, "--dport", str(port), "-j", "DROP"], 
                           check=False, capture_output=True, text=True)
            
            subprocess.run(cmd_prefix + ["iptables", "-I", "HUMANAIZE_FW", "1", "-p", protocol, "--dport", str(port), "-j", "DROP"], 
                           check=True, capture_output=True, text=True)
            self.blocked_ports.add(port)
            self.logger.info(f"Port blocked: {port}/{protocol}")
        except subprocess.CalledProcessError as e:
            if "Permission denied" in str(e) or e.returncode == 4:
                self.logger.warn(f"权限不足，无法封禁端口: {port}")
            else:
                self.logger.error(f"Failed to block port {port}: {e.stderr or str(e)}")
        except Exception as e:
            self.logger.error(f"Failed to block port {port}: {e}")
    
    def unblock_port(self, port: int, protocol: str = "tcp"):
        """解除端口封禁"""
        try:
            if self.use_sudo:
                subprocess.run(["sudo", "iptables", "-D", "HUMANAIZE_FW", "-p", protocol, "--dport", str(port), "-j", "DROP"], 
                               check=True, capture_output=True, text=True)
            else:
                subprocess.run(["iptables", "-D", "HUMANAIZE_FW", "-p", protocol, "--dport", str(port), "-j", "DROP"], 
                               check=True, capture_output=True, text=True)
            self.blocked_ports.discard(port)
            self.logger.info(f"Port unblocked: {port}/{protocol}")
        except subprocess.CalledProcessError as e:
            if "Permission denied" in str(e) or e.returncode == 4:
                self.logger.warn(f"权限不足，无法解除端口封禁: {port}")
            else:
                self.logger.error(f"Failed to unblock port {port}: {e.stderr or str(e)}")
        except Exception as e:
            self.logger.error(f"Failed to unblock port {port}: {e}")
    
    def trigger_defense(self, attack: AttackRecord):
        """触发防御机制"""
        if attack.source_ip and attack.source_ip not in self.blocked_ips:
            duration = self._calculate_block_duration(attack)
            self.block_ip(attack.source_ip, duration)
            attack.blocked = True
            
            self._trigger_counter_measure(attack)
        
        if attack.target_port and attack.target_port not in self.blocked_ports:
            self.block_port(attack.target_port)
    
    def _trigger_counter_measure(self, attack: AttackRecord):
        """触发反制措施"""
        if self.counter_measure and attack.source_ip:
            try:
                result = self.counter_measure.process_attack(
                    attack.source_ip, 
                    attack.attack_type
                )
                
                if result.get("status") == "warning_sent":
                    self.logger.info(f"Warning sent to attacker {attack.source_ip}: "
                                   f"Warning {result['warning_count']} of {result['max_warnings']}")
                elif result.get("status") == "counter_executed":
                    self.logger.warn(f"Counter measure executed for {attack.source_ip}: "
                                    f"{result.get('message')}")
                
            except Exception as e:
                self.logger.error(f"Failed to trigger counter measure for {attack.source_ip}: {e}")
    
    def _calculate_block_duration(self, attack: AttackRecord) -> int:
        """计算封禁时长"""
        severity_map = {
            "low": 600,
            "medium": 1800,
            "high": 3600,
            "critical": 7200
        }
        return severity_map.get(attack.severity, 1800)
    
    def _cleanup_expired_blocks(self):
        """清理过期的封禁"""
        while self.running:
            now = time.time()
            expired_ips = [ip for ip, data in self.blocked_ips.items() if data["expires_at"] < now]
            
            for ip in expired_ips:
                self.unblock_ip(ip)
            
            time.sleep(60)
    
    def get_status(self) -> Dict:
        """获取防火墙状态"""
        return {
            "running": self.running,
            "iptables_setup": self.iptables_setup,
            "blocked_ips_count": len(self.blocked_ips),
            "blocked_ports_count": len(self.blocked_ports),
            "attack_records_count": len(self.attack_records),
            "recent_attacks": [a.to_dict() for a in self.attack_records[-10:]],
            "blocked_ips": list(self.blocked_ips.keys()),
            "blocked_ports": list(self.blocked_ports)
        }
    
    def get_attack_history(self, limit: int = 20) -> List[Dict]:
        """获取攻击历史"""
        return [a.to_dict() for a in self.attack_records[-limit:]]
    
    def scan_packet(self, packet_data: Dict) -> Optional[AttackRecord]:
        """扫描数据包"""
        payload = packet_data.get("payload", "")
        source_ip = packet_data.get("source_ip", "")
        source_port = packet_data.get("source_port", 0)
        target_ip = packet_data.get("target_ip", "")
        target_port = packet_data.get("target_port", 0)
        
        return self.detect_attack(payload, source_ip, source_port, target_ip, target_port)


class FirewallAPI:
    """防火墙API接口"""
    
    def __init__(self):
        self.firewall = Firewall()
    
    def start_firewall(self) -> Dict:
        """启动防火墙"""
        self.firewall.start()
        return {"status": "success", "message": "Firewall started"}
    
    def stop_firewall(self) -> Dict:
        """停止防火墙"""
        self.firewall.stop()
        return {"status": "success", "message": "Firewall stopped"}
    
    def enable_firewall(self) -> Dict:
        """启用防火墙（初始化iptables规则）"""
        self.firewall.enable()
        return {"status": "success", "message": "Firewall enabled"}
    
    def disable_firewall(self) -> Dict:
        """禁用防火墙（清理iptables规则）"""
        self.firewall.disable()
        return {"status": "success", "message": "Firewall disabled"}
    
    def get_status(self) -> Dict:
        """获取状态"""
        return self.firewall.get_status()
    
    def block_ip(self, ip: str, duration: int = 3600) -> Dict:
        """封禁IP"""
        self.firewall.block_ip(ip, duration)
        return {"status": "success", "ip": ip, "duration": duration}
    
    def unblock_ip(self, ip: str) -> Dict:
        """解除IP封禁"""
        self.firewall.unblock_ip(ip)
        return {"status": "success", "ip": ip}
    
    def block_port(self, port: int) -> Dict:
        """封禁端口"""
        self.firewall.block_port(port)
        return {"status": "success", "port": port}
    
    def unblock_port(self, port: int) -> Dict:
        """解除端口封禁"""
        self.firewall.unblock_port(port)
        return {"status": "success", "port": port}
    
    def detect_attack(self, data: str, source_ip: str = "", auto_defense: bool = True) -> Dict:
        """检测攻击"""
        attack = self.firewall.detect_attack(data, source_ip, auto_defense=auto_defense)
        if attack:
            return {"status": "attack_detected", "attack": attack.to_dict()}
        return {"status": "no_attack"}
    
    def scan_packet(self, packet_data: Dict) -> Dict:
        """扫描数据包"""
        attack = self.firewall.scan_packet(packet_data)
        if attack:
            return {"status": "attack_detected", "attack": attack.to_dict()}
        return {"status": "no_attack"}
    
    def get_attack_history(self, limit: int = 20) -> Dict:
        """获取攻击历史"""
        return {"status": "success", "attacks": self.firewall.get_attack_history(limit)}
    
    def execute_command(self, command: str) -> Dict:
        """执行防火墙命令"""
        try:
            result = subprocess.run(
                ["iptables"] + command.split(),
                capture_output=True,
                text=True,
                timeout=10
            )
            return {
                "status": "success" if result.returncode == 0 else "error",
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


firewall_api = FirewallAPI()