---
name: firewall
description: AI自动防火墙技能，实现实时攻击检测、自动防御策略生成和效果评估
metadata:
  category: security
  self_developed: true
  version: 1.0
---

AI Firewall Skill

功能描述:
- 实时网络流量监控和攻击检测
- AI驱动的攻击分析和防御策略生成
- 自动执行防御命令（封禁IP、端口等）
- 防御效果评估和自适应优化
- 形成"问题解决→效果检验→问题定位→再次解决"的完整逻辑闭环

使用方法:
输出JSON格式调用技能:
{"skill": "firewall", "input": {"action": "<action>", "params": {...}}}

支持的动作:
- start: 启动防火墙（完整启动监控）
- stop: 停止防火墙
- enable: 启用防火墙（仅初始化iptables规则）
- disable: 禁用防火墙（清理iptables规则）
- status: 获取防火墙状态
- block_ip: 封禁IP地址
- unblock_ip: 解除IP封禁
- block_port: 封禁端口
- unblock_port: 解除端口封禁
- detect_attack: 检测攻击
- scan_packet: 扫描数据包
- get_attack_history: 获取攻击历史
- analyze_attack: AI分析攻击
- execute_command: 执行防火墙命令

输入参数:
- block_ip: {"ip": "192.168.1.100", "duration": 3600}
- unblock_ip: {"ip": "192.168.1.100"}
- block_port: {"port": 8080}
- unblock_port: {"port": 8080}
- detect_attack: {"data": "<payload>", "source_ip": "<ip>"}
- scan_packet: {"payload": "<data>", "source_ip": "<ip>", "source_port": 0, "target_ip": "<ip>", "target_port": 0}
- analyze_attack: {"attack_type": "<type>", "source_ip": "<ip>", "severity": "<level>"}
- execute_command: {"command": "block_ip 192.168.1.100"}

输出格式:
仅输出执行命令，不包含任何解释说明。