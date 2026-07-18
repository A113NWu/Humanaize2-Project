#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI防火墙集成模块
实现AI驱动的攻击分析和防御策略生成
形成"问题解决→效果检验→问题定位→再次解决"的完整逻辑闭环
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from llm import chat
except ImportError:
    chat = None

try:
    from .firewall import FirewallAPI, AttackRecord
except ImportError:
    from core.tools.firewall import FirewallAPI, AttackRecord


class DefenseStrategy:
    """防御策略"""
    
    def __init__(self, attack_type: str, severity: str, actions: List[str], priority: int = 1):
        self.attack_type = attack_type
        self.severity = severity
        self.actions = actions
        self.priority = priority
        self.executed = False
        self.effective = False
    
    def to_dict(self) -> Dict:
        return {
            "attack_type": self.attack_type,
            "severity": self.severity,
            "actions": self.actions,
            "priority": self.priority,
            "executed": self.executed,
            "effective": self.effective
        }


class AIFirewall:
    """AI驱动防火墙"""
    
    def __init__(self):
        self.firewall_api = FirewallAPI()
        self.analysis_loop_running = False
        self.analysis_thread = None
        self.defense_history: List[Dict] = []
        self.optimization_rules: Dict = {}
        
        self._load_optimization_rules()
        self._start_analysis_loop()
    
    def _load_optimization_rules(self):
        """加载优化规则"""
        rules_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "ai_selfdevelop",
            "learning",
            "firewall_rules.json"
        )
        
        try:
            if os.path.exists(rules_file):
                with open(rules_file, 'r', encoding='utf-8') as f:
                    self.optimization_rules = json.load(f)
            else:
                self.optimization_rules = self._get_default_rules()
                self._save_optimization_rules()
        except:
            self.optimization_rules = self._get_default_rules()
    
    def _get_default_rules(self) -> Dict:
        """获取默认规则"""
        return {
            "sql_injection": {
                "block_duration": 3600,
                "response_level": "high",
                "actions": ["block_ip", "log_attack", "notify_admin"]
            },
            "xss_attack": {
                "block_duration": 3600,
                "response_level": "high",
                "actions": ["block_ip", "log_attack"]
            },
            "command_injection": {
                "block_duration": 7200,
                "response_level": "critical",
                "actions": ["block_ip", "block_port", "log_attack", "notify_admin"]
            },
            "brute_force": {
                "block_duration": 1800,
                "response_level": "medium",
                "actions": ["block_ip", "log_attack"]
            },
            "port_scan": {
                "block_duration": 1800,
                "response_level": "medium",
                "actions": ["block_ip", "log_attack"]
            },
            "default": {
                "block_duration": 1800,
                "response_level": "medium",
                "actions": ["block_ip", "log_attack"]
            }
        }
    
    def _save_optimization_rules(self):
        """保存优化规则"""
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "ai_selfdevelop",
            "learning"
        )
        os.makedirs(rules_dir, exist_ok=True)
        
        rules_file = os.path.join(rules_dir, "firewall_rules.json")
        with open(rules_file, 'w', encoding='utf-8') as f:
            json.dump(self.optimization_rules, f, indent=4, ensure_ascii=False)
    
    def _start_analysis_loop(self):
        """启动分析循环"""
        if self.analysis_loop_running:
            return
        
        self.analysis_loop_running = True
        self.analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self.analysis_thread.start()
    
    def _analysis_loop(self):
        """分析循环"""
        while self.analysis_loop_running:
            self._analyze_attacks()
            time.sleep(5)
    
    def _analyze_attacks(self):
        """分析攻击并生成防御策略"""
        history = self.firewall_api.get_attack_history(10)
        new_attacks = [a for a in history.get("attacks", []) if not a.get("blocked")]
        
        for attack in new_attacks:
            firewall_status = self.firewall_api.get_status()
            if not firewall_status.get("iptables_setup", False):
                self.firewall_api.enable_firewall()
            
            strategy = self._generate_defense_strategy(attack)
            if strategy:
                self._execute_strategy(strategy, attack)
                self._evaluate_effectiveness(strategy, attack)
    
    def _generate_defense_strategy(self, attack: Dict) -> Optional[DefenseStrategy]:
        """生成防御策略"""
        attack_type = attack.get("attack_type", "").lower()
        severity = attack.get("severity", "medium")
        
        rules = self.optimization_rules.get(attack_type, self.optimization_rules["default"])
        
        return DefenseStrategy(
            attack_type=attack_type,
            severity=severity,
            actions=rules.get("actions", ["block_ip", "log_attack"]),
            priority=self._calculate_priority(severity)
        )
    
    def _calculate_priority(self, severity: str) -> int:
        """计算优先级"""
        priority_map = {
            "low": 3,
            "medium": 2,
            "high": 1,
            "critical": 0
        }
        return priority_map.get(severity, 2)
    
    def _execute_strategy(self, strategy: DefenseStrategy, attack: Dict):
        """执行防御策略"""
        source_ip = attack.get("source_ip", "")
        target_port = attack.get("target_port", 0)
        
        for action in strategy.actions:
            if action == "block_ip" and source_ip:
                duration = self.optimization_rules.get(
                    strategy.attack_type, {}
                ).get("block_duration", 1800)
                self.firewall_api.block_ip(source_ip, duration)
            
            elif action == "block_port" and target_port:
                self.firewall_api.block_port(target_port)
            
            elif action == "log_attack":
                self._log_attack(attack)
            
            elif action == "notify_admin":
                self._notify_admin(attack)
        
        strategy.executed = True
        
        record = {
            "timestamp": time.time(),
            "attack": attack,
            "strategy": strategy.to_dict(),
            "phase": "executed"
        }
        self.defense_history.append(record)
    
    def _evaluate_effectiveness(self, strategy: DefenseStrategy, attack: Dict):
        """评估防御效果"""
        time.sleep(2)
        
        history = self.firewall_api.get_attack_history(5)
        source_ip = attack.get("source_ip", "")
        
        repeat_attacks = [
            a for a in history.get("attacks", [])
            if a.get("source_ip") == source_ip and a.get("timestamp") > attack.get("timestamp", 0)
        ]
        
        strategy.effective = len(repeat_attacks) == 0
        
        if not strategy.effective:
            self._reoptimize_strategy(strategy, attack)
        
        record = {
            "timestamp": time.time(),
            "attack": attack,
            "strategy": strategy.to_dict(),
            "phase": "evaluated",
            "effective": strategy.effective,
            "repeat_attack_count": len(repeat_attacks)
        }
        self.defense_history.append(record)
    
    def _reoptimize_strategy(self, strategy: DefenseStrategy, attack: Dict):
        """重新优化策略"""
        new_actions = strategy.actions.copy()
        
        if "block_port" not in new_actions and attack.get("target_port"):
            new_actions.append("block_port")
        
        if "notify_admin" not in new_actions:
            new_actions.append("notify_admin")
        
        new_duration = self.optimization_rules.get(
            strategy.attack_type, {}
        ).get("block_duration", 1800) * 2
        
        self.optimization_rules[strategy.attack_type] = {
            "block_duration": new_duration,
            "response_level": "critical",
            "actions": new_actions
        }
        self._save_optimization_rules()
        
        source_ip = attack.get("source_ip", "")
        if source_ip:
            self.firewall_api.block_ip(source_ip, new_duration)
        
        record = {
            "timestamp": time.time(),
            "attack": attack,
            "strategy": strategy.to_dict(),
            "phase": "reoptimized",
            "new_duration": new_duration,
            "new_actions": new_actions
        }
        self.defense_history.append(record)
    
    def _log_attack(self, attack: Dict):
        """记录攻击"""
        log_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "ai_selfdevelop",
            "learning",
            "attack_logs.json"
        )
        
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            logs.append({
                "timestamp": time.time(),
                "attack": attack
            })
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(logs[-1000:], f, indent=4, ensure_ascii=False)
        except:
            pass
    
    def _notify_admin(self, attack: Dict):
        """通知管理员"""
        try:
            from notify import send_notification
            message = f"严重攻击检测: {attack.get('attack_type')} 来自 {attack.get('source_ip')}"
            send_notification("security_alert", message)
        except:
            pass
    
    def ai_analyze_attack(self, attack_data: Dict) -> Dict:
        """使用AI分析攻击"""
        prompt = self._build_analysis_prompt(attack_data)
        
        try:
            response = chat(prompt)
            analysis = self._parse_ai_response(response)
            
            if analysis:
                strategy = self._convert_analysis_to_strategy(analysis, attack_data)
                return {
                    "status": "success",
                    "analysis": analysis,
                    "strategy": strategy.to_dict() if strategy else None
                }
            return {"status": "success", "analysis": {"raw": response}, "strategy": None}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _build_analysis_prompt(self, attack_data: Dict) -> str:
        """构建分析提示词"""
        prompt = f"""分析以下攻击数据并生成防御命令：

攻击类型: {attack_data.get('attack_type', '')}
来源IP: {attack_data.get('source_ip', '')}
来源端口: {attack_data.get('source_port', 0)}
目标IP: {attack_data.get('target_ip', '')}
目标端口: {attack_data.get('target_port', 0)}
严重程度: {attack_data.get('severity', '')}
时间戳: {attack_data.get('timestamp', '')}

请分析攻击特征，判断攻击意图和可能的后续行为，然后输出需要执行的防火墙命令。

输出格式要求：
仅输出命令，每行一个，不包含任何解释说明或格式标记。

可用命令：
- enable_firewall
- disable_firewall
- block_ip <IP> [duration]
- unblock_ip <IP>
- block_port <port>
- unblock_port <port>
- drop_connection <IP>
- alert <message>

示例输出：
enable_firewall
block_ip 192.168.1.100 3600
block_port 8080
"""
        return prompt
    
    def _parse_ai_response(self, response: str) -> Optional[Dict]:
        """解析AI响应"""
        try:
            lines = response.strip().split('\n')
            commands = []
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    commands.append(line)
            
            if commands:
                return {"commands": commands, "raw_response": response}
            return None
        except:
            return None
    
    def _convert_analysis_to_strategy(self, analysis: Dict, attack_data: Dict) -> Optional[DefenseStrategy]:
        """将分析转换为策略"""
        commands = analysis.get("commands", [])
        actions = []
        
        for cmd in commands:
            parts = cmd.split()
            if len(parts) >= 2:
                action = parts[0]
                if action in ["block_ip", "block_port", "unblock_ip", "unblock_port", "alert"]:
                    actions.append(action)
        
        if not actions:
            actions = ["block_ip", "log_attack"]
        
        return DefenseStrategy(
            attack_type=attack_data.get("attack_type", ""),
            severity=attack_data.get("severity", "medium"),
            actions=actions,
            priority=self._calculate_priority(attack_data.get("severity", "medium"))
        )
    
    def execute_ai_command(self, command: str) -> Dict:
        """执行AI命令"""
        try:
            parts = command.strip().split()
            if not parts:
                return {"status": "error", "message": "Empty command"}
            
            action = parts[0].lower()
            
            if action == "block_ip":
                ip = parts[1] if len(parts) > 1 else ""
                duration = int(parts[2]) if len(parts) > 2 else 3600
                return self.firewall_api.block_ip(ip, duration)
            
            elif action == "unblock_ip":
                ip = parts[1] if len(parts) > 1 else ""
                return self.firewall_api.unblock_ip(ip)
            
            elif action == "block_port":
                port = int(parts[1]) if len(parts) > 1 else 0
                return self.firewall_api.block_port(port)
            
            elif action == "unblock_port":
                port = int(parts[1]) if len(parts) > 1 else 0
                return self.firewall_api.unblock_port(port)
            
            elif action == "drop_connection":
                ip = parts[1] if len(parts) > 1 else ""
                return self.firewall_api.block_ip(ip, 60)
            
            elif action == "alert":
                message = " ".join(parts[1:]) if len(parts) > 1 else ""
                return {"status": "success", "action": "alert", "message": message}
            
            elif action == "enable_firewall":
                return self.firewall_api.enable_firewall()
            
            elif action == "disable_firewall":
                return self.firewall_api.disable_firewall()
            
            else:
                return {"status": "error", "message": f"Unknown command: {action}"}
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_defense_history(self, limit: int = 20) -> List[Dict]:
        """获取防御历史"""
        return self.defense_history[-limit:]
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "analysis_loop_running": self.analysis_loop_running,
            "defense_history_count": len(self.defense_history),
            "optimization_rules_count": len(self.optimization_rules),
            "firewall": self.firewall_api.get_status()
        }
    
    def stop(self):
        """停止AI防火墙"""
        self.analysis_loop_running = False
        self.firewall_api.stop_firewall()


ai_firewall = AIFirewall()