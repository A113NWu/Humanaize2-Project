#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
防火墙技能执行模块
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.core.tools.ai_firewall import ai_firewall


def execute(input_data: dict) -> dict:
    """执行防火墙技能"""
    action = input_data.get('action', '')
    
    if action == 'start':
        return ai_firewall.firewall_api.start_firewall()
    
    elif action == 'stop':
        return ai_firewall.firewall_api.stop_firewall()
    
    elif action == 'enable':
        return ai_firewall.firewall_api.enable_firewall()
    
    elif action == 'disable':
        return ai_firewall.firewall_api.disable_firewall()
    
    elif action == 'status':
        return ai_firewall.get_status()
    
    elif action == 'block_ip':
        ip = input_data.get('params', {}).get('ip', '')
        duration = input_data.get('params', {}).get('duration', 3600)
        return ai_firewall.firewall_api.block_ip(ip, duration)
    
    elif action == 'unblock_ip':
        ip = input_data.get('params', {}).get('ip', '')
        return ai_firewall.firewall_api.unblock_ip(ip)
    
    elif action == 'block_port':
        port = input_data.get('params', {}).get('port', 0)
        return ai_firewall.firewall_api.block_port(port)
    
    elif action == 'unblock_port':
        port = input_data.get('params', {}).get('port', 0)
        return ai_firewall.firewall_api.unblock_port(port)
    
    elif action == 'detect_attack':
        data = input_data.get('params', {}).get('data', '')
        source_ip = input_data.get('params', {}).get('source_ip', '')
        return ai_firewall.firewall_api.detect_attack(data, source_ip)
    
    elif action == 'scan_packet':
        packet_data = input_data.get('params', {})
        return ai_firewall.firewall_api.scan_packet(packet_data)
    
    elif action == 'get_attack_history':
        limit = input_data.get('params', {}).get('limit', 20)
        return ai_firewall.firewall_api.get_attack_history(limit)
    
    elif action == 'analyze_attack':
        attack_data = input_data.get('params', {})
        return ai_firewall.ai_analyze_attack(attack_data)
    
    elif action == 'execute_command':
        command = input_data.get('params', {}).get('command', '')
        return ai_firewall.execute_ai_command(command)
    
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}