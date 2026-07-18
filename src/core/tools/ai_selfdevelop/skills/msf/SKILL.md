---
name: msf
description: MSF数据库接入技能，提供数据库连接、查询和数据操作功能
metadata:
  category: database
  self_developed: true
  version: 1.0
---

MSF Database Skill

功能描述:
- MSF数据库连接管理（连接、断开、测试）
- 主机信息管理（查询、添加、更新、删除）
- 服务信息管理（查询、添加）
- 漏洞信息管理（查询、添加）
- 凭据信息管理（查询、添加）
- 会话信息管理（查询）
- 原始SQL查询执行
- 数据库摘要统计

使用方法:
输出JSON格式调用技能:
{"skill": "msf", "input": {"action": "<action>", "params": {...}}}

支持的动作:
- connect: 连接数据库
- disconnect: 断开数据库连接
- test_connection: 测试数据库连接
- get_status: 获取数据库状态
- get_hosts: 获取主机列表
- get_host_details: 获取主机详细信息
- add_host: 添加主机
- update_host: 更新主机信息
- delete_host: 删除主机
- get_services: 获取服务列表
- add_service: 添加服务
- get_vulnerabilities: 获取漏洞列表
- add_vulnerability: 添加漏洞
- get_credentials: 获取凭据列表
- add_credential: 添加凭据
- get_sessions: 获取会话列表
- execute_query: 执行原始查询
- execute_command: 执行原始命令
- get_summary: 获取数据库摘要

输入参数:
- get_hosts: {"filters": {"host": "<pattern>", "os_name": "<pattern>", "state": "<state>", "limit": 10}}
- get_host_details: {"host_id": <id>}
- add_host: {"host": "<ip>", "os_name": "<os>", "state": "<state>", "info": "<info>", "mac": "<mac>"}
- update_host: {"host_id": <id>, "os_name": "<os>", "state": "<state>", "info": "<info>"}
- delete_host: {"host_id": <id>}
- get_services: {"filters": {"host_id": <id>, "port": <port>, "name": "<pattern>", "limit": 10}}
- add_service: {"host_id": <id>, "port": <port>, "proto": "<tcp/udp>", "name": "<name>", "state": "<state>"}
- get_vulnerabilities: {"filters": {"host_id": <id>, "severity": "<level>", "limit": 10}}
- add_vulnerability: {"host_id": <id>, "name": "<name>", "severity": "<level>", "description": "<desc>"}
- get_credentials: {"filters": {"host_id": <id>, "service": "<name>", "limit": 10}}
- add_credential: {"host_id": <id>, "service": "<name>", "username": "<user>", "password": "<pass>"}
- execute_query: {"query": "<sql>", "params": {...}}
- execute_command: {"query": "<sql>", "params": {...}}

输出格式:
返回JSON格式结果，包含status字段和数据内容。