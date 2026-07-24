#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSF数据库测试脚本
验证SQLite回退功能是否正常工作
"""

import sys
sys.path.insert(0, 'src')

from core.tools.msf_db import msf_db, MSFDBError, USE_SQLITE
from core.tools.msf_operations import msf_ops


def test_msf_database():
    """测试MSF数据库功能"""
    print("=" * 60)
    print("MSF数据库测试")
    print("=" * 60)
    
    print(f"\n[INFO] 使用数据库类型: {'SQLite' if USE_SQLITE else 'PostgreSQL'}")
    
    # 测试连接
    print("\n1. 测试数据库连接...")
    connect_result = msf_db.connect()
    print(f"   结果: {connect_result['status']}")
    if connect_result['status'] == 'success':
        print(f"   消息: {connect_result['message']}")
        if 'version' in connect_result:
            print(f"   版本: {connect_result['version']}")
    else:
        print(f"   错误: {connect_result['message']}")
        return False
    
    # 测试状态
    print("\n2. 获取数据库状态...")
    status = msf_db.get_status()
    print(f"   已连接: {status['connected']}")
    print(f"   连接数: {status['connection_count']}")
    
    # 测试表名
    print("\n3. 获取表名列表...")
    tables = msf_db.get_table_names()
    if tables['status'] == 'success':
        print(f"   表数量: {tables['count']}")
        for table in tables['data'][:5]:
            print(f"   - {table.get('name', table.get('table_name', 'unknown'))}")
    else:
        print(f"   错误: {tables['message']}")
    
    # 测试添加主机
    print("\n4. 测试添加主机...")
    host_result = msf_ops.add_host({
        "host": "192.168.1.100",
        "os_name": "Linux",
        "state": "alive",
        "info": "Ubuntu 22.04",
        "mac": "00:11:22:33:44:55"
    })
    print(f"   结果: {host_result['status']}")
    if host_result['status'] == 'success':
        print(f"   影响行数: {host_result['rowcount']}")
    
    # 测试获取主机列表
    print("\n5. 获取主机列表...")
    hosts = msf_ops.get_hosts(filters={"limit": 5})
    if hosts['status'] == 'success':
        print(f"   主机数量: {hosts['count']}")
        for host in hosts['data']:
            print(f"   - {host['host']} ({host['os_name']}, {host['state']})")
    else:
        print(f"   错误: {hosts['message']}")
    
    # 测试获取数据库摘要
    print("\n6. 获取数据库摘要...")
    summary = msf_ops.get_summary()
    if summary['status'] == 'success':
        for key, value in summary['summary'].items():
            print(f"   {key}: {value}")
    else:
        print(f"   错误: {summary['message']}")
    
    # 测试服务添加
    print("\n7. 测试添加服务...")
    service_result = msf_ops.add_service({
        "host_id": 1,
        "port": 80,
        "proto": "tcp",
        "name": "http",
        "state": "open"
    })
    print(f"   结果: {service_result['status']}")
    
    # 测试断开连接
    print("\n8. 测试断开连接...")
    disconnect_result = msf_db.disconnect()
    print(f"   结果: {disconnect_result['status']}")
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_msf_database()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)