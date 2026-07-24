#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模型切换功能
"""

import os
import sys
import json
import time

sys.path.insert(0, 'src')

def test_model_switch():
    print("=" * 60)
    print("测试模型切换功能")
    print("=" * 60)
    
    # 1. 测试配置文件读取
    print("\n1. 测试配置文件读取...")
    settings_path = os.path.join("src", "core", "ui", "data", "ui_settings.json")
    if os.path.exists(settings_path):
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        model_path = settings.get("model_path", "")
        model_name = settings.get("model_name", "")
        print(f"   ✓ 配置文件读取成功")
        print(f"   - model_name: {model_name}")
        print(f"   - model_path: {model_path}")
        print(f"   - 文件存在: {os.path.exists(model_path)}")
    else:
        print("   ✗ 配置文件不存在")
        return False
    
    # 2. 测试 _get_model_path 函数
    print("\n2. 测试 _get_model_path 函数...")
    from core.main import _get_model_path
    result_path = _get_model_path()
    print(f"   ✓ 获取到模型路径: {os.path.basename(result_path)}")
    print(f"   ✓ 路径匹配: {result_path == model_path}")
    
    # 3. 测试模型切换流程
    print("\n3. 测试模型切换流程...")
    from core.tools.tools import restart_llm_server, check_llm_server
    
    print("   - 检查当前服务器状态:", "运行中" if check_llm_server() else "未运行")
    
    # 模拟切换到另一个模型（临时）
    test_model = "D:/Humanaize 2.0 Agent/Humanaize2-Project/models/gemma-4-26B-A4B-it-ultra-uncensored-heretic-Q5_K_S.gguf"
    if os.path.exists(test_model):
        print(f"   - 测试模型: {os.path.basename(test_model)}")
        print("   - 开始重启服务器...")
        result = restart_llm_server(test_model)
        print(f"   ✓ 重启结果: {result}")
        
        # 等待服务器启动
        time.sleep(5)
        print("   - 服务器状态:", "运行中" if check_llm_server() else "未运行")
    else:
        print("   ! 测试模型不存在，跳过重启测试")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_model_switch()
    exit(0 if success else 1)