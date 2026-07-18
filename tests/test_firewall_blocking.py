#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP封禁机制单元测试
验证Guard模式IP封禁功能是否正确工作
"""

import unittest
import sys
import os
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.firewall import Firewall, AttackRecord

class TestIPBlocking(unittest.TestCase):
    """测试IP封禁功能"""
    
    def setUp(self):
        """设置测试环境"""
        with patch('tools.firewall.subprocess.run'):
            self.firewall = Firewall()
            self.firewall.logger = MagicMock()
            self.firewall.ai_notifier = None
    
    def test_block_ip_rule_priority(self):
        """测试IP封禁规则优先级 - 使用-I插入到链开头"""
        with patch('tools.firewall.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            self.firewall.has_root = True
            self.firewall.use_sudo = False
            self.firewall.block_ip("192.168.1.100", 3600)
            
            calls = mock_run.call_args_list
            
            delete_call = calls[0]
            insert_call = calls[1]
            
            self.assertIn('-D', delete_call[0][0], "Should delete existing rule first")
            self.assertIn('-I', insert_call[0][0], "Should insert rule with -I")
            self.assertIn('1', insert_call[0][0], "Should insert at position 1")
            
            cmd_str = ' '.join(insert_call[0][0])
            self.assertIn('HUMANAIZE_FW', cmd_str, "Should use HUMANAIZE_FW chain")
            self.assertIn('192.168.1.100', cmd_str, "Should block correct IP")
            self.assertIn('DROP', cmd_str, "Should use DROP target")
    
    def test_block_ip_already_blocked(self):
        """测试已封禁IP的处理"""
        self.firewall.blocked_ips["192.168.1.100"] = {
            "blocked_at": time.time() - 100,
            "duration": 1800,
            "expires_at": time.time() + 1700
        }
        
        with patch('tools.firewall.subprocess.run') as mock_run:
            original_expires = self.firewall.blocked_ips["192.168.1.100"]["expires_at"]
            
            self.firewall.block_ip("192.168.1.100", 3600)
            
            mock_run.assert_not_called()
            
            new_expires = self.firewall.blocked_ips["192.168.1.100"]["expires_at"]
            self.assertGreater(new_expires, original_expires, "Expiration time should be updated")
            self.assertEqual(self.firewall.blocked_ips["192.168.1.100"]["duration"], 3600)
    
    def test_block_ip_sudo(self):
        """测试使用sudo封禁IP"""
        with patch('tools.firewall.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            self.firewall.has_root = False
            self.firewall.use_sudo = True
            self.firewall.block_ip("10.0.0.1", 1800)
            
            calls = mock_run.call_args_list
            self.assertIn('sudo', calls[0][0][0], "Should use sudo")
            self.assertIn('sudo', calls[1][0][0], "Should use sudo for insert")
    
    def test_block_port_rule_priority(self):
        """测试端口封禁规则优先级"""
        with patch('tools.firewall.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            self.firewall.has_root = True
            self.firewall.use_sudo = False
            self.firewall.block_port(8080)
            
            calls = mock_run.call_args_list
            
            insert_call = calls[1]
            cmd_str = ' '.join(insert_call[0][0])
            
            self.assertIn('-I', insert_call[0][0], "Should insert rule with -I")
            self.assertIn('1', insert_call[0][0], "Should insert at position 1")
            self.assertIn('8080', cmd_str, "Should block correct port")
    
    def test_setup_ip_tables_priority(self):
        """测试iptables规则初始化优先级"""
        with patch('tools.firewall.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            self.firewall.has_root = True
            self.firewall.use_sudo = False
            self.firewall._setup_ip_tables()
            
            calls = mock_run.call_args_list
            
            drop_call = calls[1]
            insert_call = calls[2]
            
            self.assertIn('-D', drop_call[0][0], "Should delete existing jump rule")
            self.assertIn('-I', insert_call[0][0], "Should insert jump rule with -I")
            self.assertIn('INPUT', insert_call[0][0], "Should insert into INPUT chain")
            self.assertIn('1', insert_call[0][0], "Should insert at position 1")
    
    def test_unblock_ip(self):
        """测试解除IP封禁"""
        with patch('tools.firewall.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            self.firewall.has_root = True
            self.firewall.use_sudo = False
            self.firewall.blocked_ips["192.168.1.200"] = {
                "blocked_at": time.time(),
                "duration": 3600,
                "expires_at": time.time() + 3600
            }
            
            self.firewall.unblock_ip("192.168.1.200")
            
            mock_run.assert_called_once()
            cmd_str = ' '.join(mock_run.call_args[0][0])
            self.assertIn('-D', cmd_str, "Should delete rule")
            self.assertNotIn("192.168.1.200", self.firewall.blocked_ips)
    
    def test_trigger_defense_blocks_ip(self):
        """测试触发防御机制时正确封禁IP"""
        attack = AttackRecord(
            attack_type="SQL注入",
            source_ip="172.16.0.50",
            source_port=12345,
            target_ip="192.168.1.1",
            target_port=80,
            severity="high"
        )
        
        with patch.object(self.firewall, 'block_ip') as mock_block_ip:
            self.firewall.trigger_defense(attack)
            
            mock_block_ip.assert_called_once()
            called_ip = mock_block_ip.call_args[0][0]
            self.assertEqual(called_ip, "172.16.0.50", "Should block correct IP")

if __name__ == '__main__':
    unittest.main()