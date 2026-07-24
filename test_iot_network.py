#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IoT 算力网络测试脚本

测试分布式设备接入、任务提交和结果获取功能。
可独立运行验证 IoT 模块的正确性。
"""

import sys
import os
import time
import json
import threading

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src', 'core'))

# 配置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

from tools.iot_compute_network import (
    IoTComputeNetwork,
    DeviceType,
    DeviceStatus,
    TaskStatus,
    get_network,
    init_network,
    stop_network
)


def test_network_initialization():
    """测试网络初始化"""
    print("\n" + "=" * 60)
    print("测试 1: 网络初始化")
    print("=" * 60)
    
    network = IoTComputeNetwork(host='127.0.0.1', port=9876)
    assert network.is_running == False
    print("  ✓ 网络实例创建成功")
    
    network.start()
    assert network.is_running == True
    print("  ✓ 网络启动成功")
    print(f"    监听地址: {network.host}:{network.port}")
    
    network.stop()
    assert network.is_running == False
    print("  ✓ 网络停止成功")


def test_device_management():
    """测试设备管理"""
    print("\n" + "=" * 60)
    print("测试 2: 设备管理")
    print("=" * 60)
    
    network = IoTComputeNetwork()
    
    # 添加模拟设备
    from tools.iot_compute_network import DeviceInfo, DeviceCapabilities
    
    device = DeviceInfo(
        device_id='test-device-001',
        device_name='Test Android Phone',
        device_type=DeviceType.ANDROID_PHONE,
        status=DeviceStatus.ONLINE,
        capabilities=DeviceCapabilities(
            can_compute=True,
            max_concurrent_tasks=2,
            cpu_cores=8,
            memory_gb=4.0,
            supported_task_types=['general', 'compute', 'nlp']
        ),
        registered_at=time.time(),
        last_heartbeat=time.time()
    )
    
    network.devices['test-device-001'] = device
    
    device_list = network.get_device_list()
    assert len(device_list) == 1
    assert device_list[0]['device_id'] == 'test-device-001'
    print(f"  ✓ 设备添加成功")
    print(f"    设备: {device_list[0]['device_name']}")
    print(f"    类型: {device_list[0]['device_type']}")
    print(f"    状态: {device_list[0]['status']}")
    
    online = network.get_online_devices()
    assert len(online) == 1
    assert online[0]['status'] == 'online'
    print("  ✓ 在线设备查询成功")
    
    stats = network.get_network_stats()
    assert stats['total_devices'] == 1
    assert stats['online_devices'] == 1
    print(f"  ✓ 网络统计正确")
    print(f"    总设备: {stats['total_devices']}")
    print(f"    在线设备: {stats['online_devices']}")


def test_task_submission():
    """测试任务提交"""
    print("\n" + "=" * 60)
    print("测试 3: 任务提交和结果")
    print("=" * 60)
    
    network = IoTComputeNetwork()
    
    # 先添加一个设备
    from tools.iot_compute_network import DeviceInfo, DeviceCapabilities
    
    device = DeviceInfo(
        device_id='test-device-001',
        device_name='Test Android Phone',
        device_type=DeviceType.ANDROID_PHONE,
        status=DeviceStatus.ONLINE,
        capabilities=DeviceCapabilities(
            can_compute=True,
            max_concurrent_tasks=2,
            cpu_cores=8,
            memory_gb=4.0,
            supported_task_types=['general', 'compute', 'nlp']
        ),
        registered_at=time.time(),
        last_heartbeat=time.time()
    )
    network.devices['test-device-001'] = device
    
    # 提交任务
    task_id = network.submit_task(
        task_type='compute',
        payload={'data': 'test data', 'operation': 'process'},
        preferred_device_id='test-device-001'
    )
    
    assert task_id is not None
    print(f"  ✓ 任务提交成功")
    print(f"    任务 ID: {task_id[:8]}...")
    
    # 查询任务状态
    status = network.get_task_status(task_id)
    assert status is not None
    assert status['task_id'] == task_id
    print(f"  ✓ 任务状态查询成功")
    print(f"    状态: {status['status']}")
    print(f"    类型: {status['task_type']}")
    
    # 模拟任务完成
    network.tasks[task_id].status = TaskStatus.COMPLETED
    network.tasks[task_id].result = {'output': 'processed result'}
    
    result = network.get_result(task_id)
    assert result is not None
    assert result['output'] == 'processed result'
    print(f"  ✓ 任务结果获取成功")
    print(f"    结果: {result}")


def test_configuration():
    """测试配置管理"""
    print("\n" + "=" * 60)
    print("测试 4: 配置管理")
    print("=" * 60)
    
    network = IoTComputeNetwork()
    
    network.configure(
        heartbeat_interval=20,
        device_timeout=60,
        auto_assign=False
    )
    
    assert network._config['heartbeat_interval'] == 20
    assert network._config['device_timeout'] == 60
    assert network._config['auto_assign'] == False
    print("  ✓ 配置更新成功")
    print(f"    心跳间隔: {network._config['heartbeat_interval']}秒")
    print(f"    设备超时: {network._config['device_timeout']}秒")
    print(f"    自动分配: {network._config['auto_assign']}")


def test_event_handlers():
    """测试事件处理器"""
    print("\n" + "=" * 60)
    print("测试 5: 事件处理")
    print("=" * 60)
    
    network = IoTComputeNetwork()
    events_received = []
    
    def on_device_connected(device):
        events_received.append(('device_connected', device))
    
    def on_task_completed(task):
        events_received.append(('task_completed', task))
    
    def on_chat_message(data):
        events_received.append(('chat_message', data))
    
    network.on('device_connected', on_device_connected)
    network.on('task_completed', on_task_completed)
    network.on('chat_message', on_chat_message)
    
    # 触发事件
    network._emit('device_connected', {'device_id': 'test'})
    network._emit('task_completed', {'task_id': 'task-001'})
    network._emit('chat_message', {'message': 'hello'})
    
    assert len(events_received) == 3
    assert events_received[0][0] == 'device_connected'
    assert events_received[1][0] == 'task_completed'
    assert events_received[2][0] == 'chat_message'
    print(f"  ✓ 事件处理器正常工作")
    print(f"    接收到 {len(events_received)} 个事件")
    
    for event_type, data in events_received:
        print(f"      - {event_type}: {list(data.keys()) if isinstance(data, dict) else data}")


def test_global_instance():
    """测试全局实例"""
    print("\n" + "=" * 60)
    print("测试 6: 全局实例管理")
    print("=" * 60)
    
    from tools.iot_compute_network import _network_instance, get_network
    
    # 清除全局实例（如果存在）
    import tools.iot_compute_network as iot_module
    iot_module._network_instance = None
    
    instance1 = get_network(host='127.0.0.1', port=9001)
    instance2 = get_network(host='127.0.0.1', port=9001)
    
    assert instance1 is instance2
    print("  ✓ 全局实例获取成功")
    print(f"    同一实例: {instance1 is instance2}")
    
    # 清理
    iot_module._network_instance = None
    print("  ✓ 全局实例重置成功")


def test_wait_for_result():
    """测试等待结果功能"""
    print("\n" + "=" * 60)
    print("测试 7: 等待结果")
    print("=" * 60)
    
    network = IoTComputeNetwork()
    
    # 先添加一个设备
    from tools.iot_compute_network import DeviceInfo, DeviceCapabilities
    
    device = DeviceInfo(
        device_id='test-device-001',
        device_name='Test Device',
        device_type=DeviceType.ANDROID_PHONE,
        status=DeviceStatus.ONLINE,
        capabilities=DeviceCapabilities(
            can_compute=True,
            max_concurrent_tasks=1,
            supported_task_types=['general', 'compute']
        ),
        registered_at=time.time(),
        last_heartbeat=time.time()
    )
    network.devices['test-device-001'] = device
    
    # 创建一个任务并在另一个线程完成它
    task_id = network.submit_task('general', {'test': True})
    
    def complete_task():
        time.sleep(0.5)
        if task_id in network.tasks:
            network.tasks[task_id].status = TaskStatus.COMPLETED
            network.tasks[task_id].result = {'success': True, 'data': 'test'}
    
    thread = threading.Thread(target=complete_task, daemon=True)
    thread.start()
    
    result = network.wait_for_result(task_id, timeout=5.0)
    assert result is not None
    assert result['success'] == True
    print(f"  ✓ 等待结果成功")
    print(f"    结果: {result}")


def test_data_models():
    """测试数据模型"""
    print("\n" + "=" * 60)
    print("测试 8: 数据模型序列化")
    print("=" * 60)
    
    from tools.iot_compute_network import (
        DeviceInfo, DeviceCapabilities, ComputeTask
    )
    
    # 序列化/反序列化设备信息
    device = DeviceInfo(
        device_id='test-001',
        device_name='Test Device',
        device_type=DeviceType.ANDROID_PHONE,
        capabilities=DeviceCapabilities(
            can_compute=True,
            max_concurrent_tasks=2,
            gpu_available=False,
            memory_gb=4.0,
            cpu_cores=8
        )
    )
    
    d = device.to_dict()
    assert d['device_id'] == 'test-001'
    assert d['device_type'] == 'android_phone'
    print(f"  ✓ DeviceInfo 序列化成功")
    print(f"    设备 ID: {d['device_id']}")
    print(f"    设备类型: {d['device_type']}")
    
    # 序列化任务
    task = ComputeTask(
        task_id='task-001',
        task_type='compute',
        payload={'key': 'value'}
    )
    
    t = task.to_dict()
    assert t['task_id'] == 'task-001'
    assert t['status'] == 'pending'
    print(f"  ✓ ComputeTask 序列化成功")
    print(f"    任务 ID: {t['task_id']}")
    print(f"    状态: {t['status']}")


def test_iot_compute_manager():
    """測試獨立的 IoT 算力管理器"""
    print("\n" + "=" * 60)
    print("測試 9: 獨立 IoT 算力管理器")
    print("=" * 60)
    
    from tools.iot_compute_manager import IoTComputeManager
    
    manager = IoTComputeManager()
    
    # 初始化
    initialized = manager.initialize()
    assert initialized == True
    print("  ✓ 管理器初始化成功")
    
    # 添加模擬設備
    from tools.iot_compute_network import DeviceInfo, DeviceCapabilities, DeviceType, DeviceStatus
    
    device = DeviceInfo(
        device_id='manager-test-device',
        device_name='Manager Test Device',
        device_type=DeviceType.ANDROID_PHONE,
        status=DeviceStatus.ONLINE,
        capabilities=DeviceCapabilities(
            can_compute=True,
            max_concurrent_tasks=1,
            supported_task_types=['general', 'compute']
        ),
        registered_at=time.time(),
        last_heartbeat=time.time()
    )
    
    if manager._network:
        manager._network.devices['manager-test-device'] = device
    
    # 檢查設備
    online = manager.get_online_devices()
    assert len(online) == 1
    print(f"  ✓ 設備管理正常")
    print(f"    在線設備: {manager.get_online_count()}")
    print(f"    總設備: {manager.get_device_count()}")
    
    # 提交任務
    task_id = manager.submit_task('general', {'test': 'manager'})
    assert task_id is not None
    print(f"  ✓ 任務提交成功: {task_id[:8]}...")
    
    # 查詢狀態
    status = manager.get_task_status(task_id)
    assert status is not None
    print(f"  ✓ 任務狀態查詢正常")
    
    # 獲取統計
    stats = manager.get_stats()
    assert 'is_running' in stats
    print(f"  ✓ 統計信息正確")
    
    # 配置更新
    manager.configure(heartbeat_interval=20)
    print(f"  ✓ 配置更新成功")
    
    print("  ✓ IoT Compute Manager 獨立運行正常")


def main():
    """運行所有測試"""
    print("=" * 60)
    print("  IoT 算力網絡模塊測試")
    print("  Humanaize 2.0 Agent")
    print("=" * 60)
    
    tests = [
        test_network_initialization,
        test_device_management,
        test_task_submission,
        test_configuration,
        test_event_handlers,
        test_global_instance,
        test_wait_for_result,
        test_data_models,
        test_iot_compute_manager,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
            print(f"\n  ✅ {test.__name__} PASSED")
        except Exception as e:
            failed += 1
            print(f"\n  ❌ {test.__name__} FAILED")
            print(f"      錯誤: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"  測試結果: {passed} 通過, {failed} 失敗")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
