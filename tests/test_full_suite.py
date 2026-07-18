#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试套件
测试网络访问功能和所有新增功能模块
"""

import unittest
import sys
import os
import time
import socket
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestLLMModule(unittest.TestCase):
    """测试LLM模块"""
    
    def test_llm_import(self):
        """测试LLM模块导入"""
        try:
            from llm.llm import chat, chat_stream, is_server_ready, health_check
            self.assertIsNotNone(chat)
            self.assertIsNotNone(chat_stream)
            self.assertIsNotNone(is_server_ready)
            self.assertIsNotNone(health_check)
        except ImportError as e:
            self.fail(f"LLM模块导入失败: {e}")
    
    def test_health_check_function(self):
        """测试健康检查函数"""
        from llm.llm import health_check
        result = health_check()
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
    
    def test_is_server_ready(self):
        """测试服务器就绪检查"""
        from llm.llm import is_server_ready
        result = is_server_ready()
        self.assertIsInstance(result, bool)
    
    def test_llm_config_import(self):
        """测试配置导入容错"""
        with patch.dict('sys.modules', {'config': None}):
            try:
                import importlib
                import llm.llm
                importlib.reload(llm.llm)
                from llm.llm import LLAMA_SERVER_URL, MAX_TOKENS
                self.assertEqual(LLAMA_SERVER_URL, "http://127.0.0.1:8080/completion")
                self.assertEqual(MAX_TOKENS, 512)
            except Exception as e:
                self.fail(f"配置导入容错失败: {e}")
    
    def test_chat_function_structure(self):
        """测试chat函数结构"""
        from llm.llm import chat
        import inspect
        sig = inspect.signature(chat)
        params = list(sig.parameters.keys())
        self.assertIn('prompt', params)
        self.assertIn('max_tokens', params)
        self.assertIn('temperature', params)
    
    def test_chat_stream_function_structure(self):
        """测试chat_stream函数结构"""
        from llm.llm import chat_stream
        import inspect
        sig = inspect.signature(chat_stream)
        params = list(sig.parameters.keys())
        self.assertIn('prompt', params)
        self.assertIn('max_tokens', params)

class TestNetworkAccess(unittest.TestCase):
    """测试网络访问功能"""
    
    def test_http_request_basic(self):
        """测试HTTP请求基础功能"""
        import requests
        try:
            response = requests.get("http://www.google.com", timeout=5)
            self.assertTrue(200 <= response.status_code < 400)
        except requests.exceptions.RequestException:
            pass
    
    def test_socket_connection(self):
        """测试Socket连接"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                result = s.connect_ex(('127.0.0.1', 8080))
                self.assertIsInstance(result, int)
        except Exception as e:
            self.fail(f"Socket连接测试失败: {e}")
    
    def test_port_availability(self):
        """测试端口可用性检测"""
        from main import _is_port_in_use
        result = _is_port_in_use(8080)
        self.assertIsInstance(result, bool)
        
        result = _is_port_in_use(9999)
        self.assertIsInstance(result, bool)
    
    def test_requests_retry_strategy(self):
        """测试请求重试策略"""
        from llm.llm import RETRY_STRATEGY, create_session
        session = create_session()
        self.assertIsNotNone(session)
        self.assertEqual(RETRY_STRATEGY.total, 3)

class TestFirewallBlocking(unittest.TestCase):
    """测试防火墙封禁功能"""
    
    def setUp(self):
        """设置测试环境"""
        with patch('tools.firewall.subprocess.run'):
            from tools.firewall import Firewall
            self.firewall = Firewall()
            self.firewall.logger = MagicMock()
            self.firewall.ai_notifier = None
    
    def test_block_ip_rule_priority(self):
        """测试IP封禁规则优先级"""
        with patch('tools.firewall.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            self.firewall.has_root = True
            self.firewall.use_sudo = False
            self.firewall.block_ip("192.168.1.100", 3600)
            
            calls = mock_run.call_args_list
            insert_call = calls[1]
            
            self.assertIn('-I', insert_call[0][0])
            self.assertIn('1', insert_call[0][0])
    
    def test_block_port_rule_priority(self):
        """测试端口封禁规则优先级"""
        with patch('tools.firewall.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            self.firewall.has_root = True
            self.firewall.use_sudo = False
            self.firewall.block_port(8080)
            
            calls = mock_run.call_args_list
            insert_call = calls[1]
            
            self.assertIn('-I', insert_call[0][0])
            self.assertIn('1', insert_call[0][0])
    
    def test_setup_ip_tables_priority(self):
        """测试iptables规则初始化优先级"""
        with patch('tools.firewall.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            self.firewall.has_root = True
            self.firewall.use_sudo = False
            self.firewall._setup_ip_tables()
            
            calls = mock_run.call_args_list
            insert_call = calls[2]
            
            self.assertIn('-I', insert_call[0][0])
            self.assertIn('INPUT', insert_call[0][0])
            self.assertIn('1', insert_call[0][0])

class TestServerManagement(unittest.TestCase):
    """测试服务器管理功能"""
    
    def test_server_path_detection(self):
        """测试服务器路径检测"""
        from main import _get_llama_server_path
        path = _get_llama_server_path()
        self.assertIsInstance(path, str)
    
    def test_model_path_detection(self):
        """测试模型路径检测"""
        from main import _get_model_path
        path = _get_model_path()
        self.assertIsInstance(path, str)
    
    def test_kill_process_on_port(self):
        """测试端口进程终止功能"""
        from main import _kill_process_on_port
        result = _kill_process_on_port(9999)
        self.assertIsInstance(result, bool)

class TestEdgeCases(unittest.TestCase):
    """边界条件测试"""
    
    def test_empty_prompt(self):
        """测试空prompt"""
        from llm.llm import chat
        with patch('llm.llm.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"content": ""}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            result = chat("")
            self.assertIsInstance(result, str)
    
    def test_large_prompt(self):
        """测试大prompt"""
        from llm.llm import chat
        large_prompt = "Hello " * 1000
        
        with patch('llm.llm.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"content": "response"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            result = chat(large_prompt)
            self.assertIsInstance(result, str)
    
    def test_invalid_ip_format(self):
        """测试无效IP格式"""
        from tools.firewall import Firewall
        with patch('tools.firewall.subprocess.run'):
            firewall = Firewall()
            firewall.logger = MagicMock()
            
            try:
                firewall.block_ip("invalid-ip", 3600)
            except Exception:
                pass
    
    def test_negative_timeout(self):
        """测试负超时值"""
        from llm.llm import chat
        with patch('llm.llm.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"content": "response"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            result = chat("test", max_tokens=-1)
            self.assertIsInstance(result, str)

class TestPerformance(unittest.TestCase):
    """性能测试"""
    
    def test_chat_performance_basic(self):
        """测试chat函数基本性能"""
        from llm.llm import chat
        import time
        
        with patch('llm.llm.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"content": "response"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            start = time.time()
            chat("test")
            elapsed = time.time() - start
            
            self.assertLess(elapsed, 1.0)
    
    def test_health_check_performance(self):
        """测试健康检查性能"""
        from llm.llm import health_check
        import time
        
        start = time.time()
        health_check()
        elapsed = time.time() - start
        
        self.assertLess(elapsed, 1.0)

class TestCompatibility(unittest.TestCase):
    """兼容性测试"""
    
    def test_python_version(self):
        """测试Python版本兼容性"""
        self.assertGreaterEqual(sys.version_info, (3, 8))
    
    def test_json_compatibility(self):
        """测试JSON兼容性"""
        import json
        test_data = {"prompt": "test", "n_predict": 512, "temperature": 0.7}
        json_str = json.dumps(test_data)
        parsed = json.loads(json_str)
        self.assertEqual(test_data, parsed)
    
    def test_utf8_encoding(self):
        """测试UTF-8编码兼容性"""
        test_str = "你好世界 こんにちは mundo"
        encoded = test_str.encode('utf-8')
        decoded = encoded.decode('utf-8')
        self.assertEqual(test_str, decoded)

if __name__ == '__main__':
    unittest.main()