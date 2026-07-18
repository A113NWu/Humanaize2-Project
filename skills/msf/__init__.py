#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSF数据库技能执行模块
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.core.tools.msf_db import msf_db
from src.core.tools.msf_operations import msf_ops


def execute(input_data: dict) -> dict:
    """执行MSF数据库技能"""
    action = input_data.get('action', '')
    
    if action == 'connect':
        return msf_db.connect()
    
    elif action == 'disconnect':
        return msf_db.disconnect()
    
    elif action == 'test_connection':
        return msf_db.test_connection()
    
    elif action == 'get_status':
        return msf_db.get_status()
    
    elif action == 'get_hosts':
        filters = input_data.get('params', {}).get('filters', {})
        return msf_ops.get_hosts(filters)
    
    elif action == 'get_host_details':
        host_id = input_data.get('params', {}).get('host_id', 0)
        return msf_ops.get_host_details(host_id)
    
    elif action == 'add_host':
        host_data = input_data.get('params', {})
        return msf_ops.add_host(host_data)
    
    elif action == 'update_host':
        host_id = input_data.get('params', {}).get('host_id', 0)
        host_data = {k: v for k, v in input_data.get('params', {}).items() if k != 'host_id'}
        return msf_ops.update_host(host_id, host_data)
    
    elif action == 'delete_host':
        host_id = input_data.get('params', {}).get('host_id', 0)
        return msf_ops.delete_host(host_id)
    
    elif action == 'get_services':
        filters = input_data.get('params', {}).get('filters', {})
        return msf_ops.get_services(filters)
    
    elif action == 'add_service':
        service_data = input_data.get('params', {})
        return msf_ops.add_service(service_data)
    
    elif action == 'get_vulnerabilities':
        filters = input_data.get('params', {}).get('filters', {})
        return msf_ops.get_vulnerabilities(filters)
    
    elif action == 'add_vulnerability':
        vuln_data = input_data.get('params', {})
        return msf_ops.add_vulnerability(vuln_data)
    
    elif action == 'get_credentials':
        filters = input_data.get('params', {}).get('filters', {})
        return msf_ops.get_credentials(filters)
    
    elif action == 'add_credential':
        cred_data = input_data.get('params', {})
        return msf_ops.add_credential(cred_data)
    
    elif action == 'get_sessions':
        filters = input_data.get('params', {}).get('filters', {})
        return msf_ops.get_sessions(filters)
    
    elif action == 'execute_query':
        query = input_data.get('params', {}).get('query', '')
        params = input_data.get('params', {}).get('params', {})
        return msf_db.execute_query(query, params)
    
    elif action == 'execute_command':
        query = input_data.get('params', {}).get('query', '')
        params = input_data.get('params', {}).get('params', {})
        return msf_db.execute_command(query, params)
    
    elif action == 'get_summary':
        return msf_ops.get_summary()
    
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}