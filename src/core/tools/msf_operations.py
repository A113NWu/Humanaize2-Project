#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSF数据操作封装模块
提供针对MSF数据库的常用数据读写操作
"""

import os
import sys
import logging
import re
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .msf_db import msf_db

logger = logging.getLogger(__name__)


class MSFOperations:
    """MSF数据库操作类"""
    
    def get_hosts(self, filters: Optional[Dict] = None) -> Dict:
        """获取主机列表"""
        query = """
            SELECT id, address, os_name, os_flavor, os_sp, os_lang, 
                   state, updated_at, info
            FROM hosts
        """
        
        conditions = []
        params = {}
        limit = None
        
        if filters:
            if "host" in filters:
                conditions.append("address LIKE %(host)s")
                params["host"] = f"%{filters['host']}%"
            if "os_name" in filters:
                conditions.append("os_name LIKE %(os_name)s")
                params["os_name"] = f"%{filters['os_name']}%"
            if "state" in filters:
                conditions.append("state = %(state)s")
                params["state"] = filters["state"]
            if "limit" in filters:
                limit = filters["limit"]
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY updated_at DESC"
        
        if limit is not None:
            query += " LIMIT %(limit)s"
            params["limit"] = limit
        
        result = msf_db.execute_query(query, params)
        
        if result["status"] == "success":
            for row in result["data"]:
                row["host"] = row.pop("address", row.get("host"))
                row["last_seen"] = row.pop("updated_at", row.get("last_seen"))
        
        return result
    
    def get_host_details(self, host_id: int) -> Dict:
        """获取主机详细信息"""
        host_result = msf_db.execute_query(
            """
            SELECT id, host, os_name, os_flavor, os_sp, os_lang, 
                   state, last_seen, info, mac
            FROM hosts WHERE id = %s;
            """,
            (host_id,)
        )
        
        if host_result["status"] != "success" or not host_result["data"]:
            return {"status": "error", "message": "Host not found"}
        
        host = host_result["data"][0]
        
        services_result = msf_db.execute_query(
            """
            SELECT id, port, proto, name, state, info
            FROM services WHERE host_id = %s
            ORDER BY port;
            """,
            (host_id,)
        )
        
        vulns_result = msf_db.execute_query(
            """
            SELECT id, name, severity, confidence, description
            FROM vulns WHERE host_id = %s;
            """,
            (host_id,)
        )
        
        return {
            "status": "success",
            "host": host,
            "services": services_result.get("data", []),
            "vulnerabilities": vulns_result.get("data", [])
        }
    
    def add_host(self, host_data: Dict) -> Dict:
        """添加主机"""
        required_fields = ["host"]
        
        for field in required_fields:
            if field not in host_data:
                return {"status": "error", "message": f"Missing required field: {field}"}
        
        query = """
            INSERT INTO hosts (address, os_name, os_flavor, os_sp, os_lang, 
                              state, info, mac, workspace_id, created_at)
            VALUES (%(address)s, %(os_name)s, %(os_flavor)s, %(os_sp)s, %(os_lang)s,
                    %(state)s, %(info)s, %(mac)s, %(workspace_id)s, NOW())
            RETURNING id;
        """
        
        params = {
            "address": host_data.get("host"),
            "os_name": host_data.get("os_name", ""),
            "os_flavor": host_data.get("os_flavor", ""),
            "os_sp": host_data.get("os_sp", ""),
            "os_lang": host_data.get("os_lang", ""),
            "state": host_data.get("state", "alive"),
            "info": host_data.get("info", ""),
            "mac": host_data.get("mac", ""),
            "workspace_id": host_data.get("workspace_id", 1)
        }
        
        return msf_db.execute_command(query, params)
    
    def update_host(self, host_id: int, host_data: Dict) -> Dict:
        """更新主机信息"""
        if not host_data:
            return {"status": "error", "message": "No data to update"}
        
        set_clauses = []
        params = {"id": host_id}
        
        if "os_name" in host_data:
            set_clauses.append("os_name = %(os_name)s")
            params["os_name"] = host_data["os_name"]
        if "os_flavor" in host_data:
            set_clauses.append("os_flavor = %(os_flavor)s")
            params["os_flavor"] = host_data["os_flavor"]
        if "os_sp" in host_data:
            set_clauses.append("os_sp = %(os_sp)s")
            params["os_sp"] = host_data["os_sp"]
        if "state" in host_data:
            set_clauses.append("state = %(state)s")
            params["state"] = host_data["state"]
        if "info" in host_data:
            set_clauses.append("info = %(info)s")
            params["info"] = host_data["info"]
        if "mac" in host_data:
            set_clauses.append("mac = %(mac)s")
            params["mac"] = host_data["mac"]
        
        if not set_clauses:
            return {"status": "error", "message": "No valid fields to update"}
        
        query = "UPDATE hosts SET " + ", ".join(set_clauses) + " WHERE id = %(id)s"
        
        return msf_db.execute_command(query, params)
    
    def delete_host(self, host_id: int) -> Dict:
        """删除主机"""
        return msf_db.execute_command(
            "DELETE FROM hosts WHERE id = %s;",
            (host_id,)
        )
    
    def get_services(self, filters: Optional[Dict] = None) -> Dict:
        """获取服务列表"""
        query = """
            SELECT s.id, s.host_id, h.host, s.port, s.proto, s.name, 
                   s.state, s.info, s.created_at
            FROM services s
            JOIN hosts h ON s.host_id = h.id
        """
        
        conditions = []
        params = {}
        limit = None
        
        if filters:
            if "host_id" in filters:
                conditions.append("s.host_id = %(host_id)s")
                params["host_id"] = filters["host_id"]
            if "port" in filters:
                conditions.append("s.port = %(port)s")
                params["port"] = filters["port"]
            if "name" in filters:
                conditions.append("s.name LIKE %(name)s")
                params["name"] = f"%{filters['name']}%"
            if "state" in filters:
                conditions.append("s.state = %(state)s")
                params["state"] = filters["state"]
            if "limit" in filters:
                limit = filters["limit"]
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY s.host_id, s.port"
        
        if limit is not None:
            query += " LIMIT %s"
            params["limit"] = limit
        
        return msf_db.execute_query(query, params)
    
    def add_service(self, service_data: Dict) -> Dict:
        """添加服务"""
        required_fields = ["host_id", "port", "proto"]
        
        for field in required_fields:
            if field not in service_data:
                return {"status": "error", "message": f"Missing required field: {field}"}
        
        query = """
            INSERT INTO services (host_id, port, proto, name, state, info, created_at)
            VALUES (%(host_id)s, %(port)s, %(proto)s, %(name)s, %(state)s, %(info)s, NOW())
            RETURNING id;
        """
        
        params = {
            "host_id": service_data["host_id"],
            "port": service_data["port"],
            "proto": service_data.get("proto", "tcp"),
            "name": service_data.get("name", ""),
            "state": service_data.get("state", "open"),
            "info": service_data.get("info", "")
        }
        
        return msf_db.execute_command(query, params)
    
    def get_vulnerabilities(self, filters: Optional[Dict] = None) -> Dict:
        """获取漏洞列表"""
        query = """
            SELECT v.id, v.host_id, h.host, v.name, v.severity, 
                   v.confidence, v.description, v.created_at
            FROM vulns v
            JOIN hosts h ON v.host_id = h.id
        """
        
        conditions = []
        params = {}
        limit = None
        
        if filters:
            if "host_id" in filters:
                conditions.append("v.host_id = %(host_id)s")
                params["host_id"] = filters["host_id"]
            if "severity" in filters:
                conditions.append("v.severity = %(severity)s")
                params["severity"] = filters["severity"]
            if "name" in filters:
                conditions.append("v.name LIKE %(name)s")
                params["name"] = f"%{filters['name']}%"
            if "limit" in filters:
                limit = filters["limit"]
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY v.severity DESC, v.created_at DESC"
        
        if limit is not None:
            query += " LIMIT %s"
            params["limit"] = limit
        
        return msf_db.execute_query(query, params)
    
    def add_vulnerability(self, vuln_data: Dict) -> Dict:
        """添加漏洞"""
        required_fields = ["host_id", "name"]
        
        for field in required_fields:
            if field not in vuln_data:
                return {"status": "error", "message": f"Missing required field: {field}"}
        
        query = """
            INSERT INTO vulns (host_id, name, severity, confidence, description, created_at)
            VALUES (%(host_id)s, %(name)s, %(severity)s, %(confidence)s, %(description)s, NOW())
            RETURNING id;
        """
        
        params = {
            "host_id": vuln_data["host_id"],
            "name": vuln_data["name"],
            "severity": vuln_data.get("severity", "medium"),
            "confidence": vuln_data.get("confidence", 50),
            "description": vuln_data.get("description", "")
        }
        
        return msf_db.execute_command(query, params)
    
    def get_credentials(self, filters: Optional[Dict] = None) -> Dict:
        """获取凭据信息"""
        query = """
            SELECT c.id, c.host_id, h.host, c.service, c.username, 
                   c.password, c.type, c.created_at
            FROM creds c
            JOIN hosts h ON c.host_id = h.id
        """
        
        conditions = []
        params = {}
        limit = None
        
        if filters:
            if "host_id" in filters:
                conditions.append("c.host_id = %(host_id)s")
                params["host_id"] = filters["host_id"]
            if "service" in filters:
                conditions.append("c.service LIKE %(service)s")
                params["service"] = f"%{filters['service']}%"
            if "username" in filters:
                conditions.append("c.username LIKE %(username)s")
                params["username"] = f"%{filters['username']}%"
            if "limit" in filters:
                limit = filters["limit"]
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY c.created_at DESC"
        
        if limit is not None:
            query += " LIMIT %s"
            params["limit"] = limit
        
        return msf_db.execute_query(query, params)
    
    def add_credential(self, cred_data: Dict) -> Dict:
        """添加凭据"""
        required_fields = ["host_id", "username", "password"]
        
        for field in required_fields:
            if field not in cred_data:
                return {"status": "error", "message": f"Missing required field: {field}"}
        
        query = """
            INSERT INTO creds (host_id, service, username, password, type, created_at)
            VALUES (%(host_id)s, %(service)s, %(username)s, %(password)s, %(type)s, NOW())
            RETURNING id;
        """
        
        params = {
            "host_id": cred_data["host_id"],
            "service": cred_data.get("service", ""),
            "username": cred_data["username"],
            "password": cred_data["password"],
            "type": cred_data.get("type", "password")
        }
        
        return msf_db.execute_command(query, params)
    
    def get_sessions(self, filters: Optional[Dict] = None) -> Dict:
        """获取会话列表"""
        query = """
            SELECT id, host_id, type, session_port, via_exploit, 
                   via_payload, desc, opened_at, closed_at, is_dead
            FROM sessions
        """
        
        conditions = []
        params = {}
        limit = None
        
        if filters:
            if "host_id" in filters:
                conditions.append("host_id = %(host_id)s")
                params["host_id"] = filters["host_id"]
            if "type" in filters:
                conditions.append("type = %(type)s")
                params["type"] = filters["type"]
            if "is_dead" in filters:
                conditions.append("is_dead = %(is_dead)s")
                params["is_dead"] = filters["is_dead"]
            if "limit" in filters:
                limit = filters["limit"]
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY opened_at DESC"
        
        if limit is not None:
            query += " LIMIT %s"
            params["limit"] = limit
        
        return msf_db.execute_query(query, params)
    
    def get_workspaces(self) -> Dict:
        """获取工作空间列表"""
        query = "SELECT id, name, created_at FROM workspaces ORDER BY name;"
        return msf_db.execute_query(query)
    
    def get_notes(self, filters: Optional[Dict] = None) -> Dict:
        """获取笔记列表"""
        query = """
            SELECT n.id, n.host_id, h.host, n.type, n.data, n.created_at
            FROM notes n
            LEFT JOIN hosts h ON n.host_id = h.id
        """
        
        conditions = []
        params = {}
        limit = None
        
        if filters:
            if "host_id" in filters:
                conditions.append("n.host_id = %(host_id)s")
                params["host_id"] = filters["host_id"]
            if "type" in filters:
                conditions.append("n.type = %(type)s")
                params["type"] = filters["type"]
            if "limit" in filters:
                limit = filters["limit"]
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY n.created_at DESC"
        
        if limit is not None:
            query += " LIMIT %s"
            params["limit"] = limit
        
        return msf_db.execute_query(query, params)
    
    def get_loots(self, filters: Optional[Dict] = None) -> Dict:
        """获取战利品列表"""
        query = """
            SELECT l.id, l.host_id, h.host, l.type, l.name, l.data, l.created_at
            FROM loots l
            LEFT JOIN hosts h ON l.host_id = h.id
        """
        
        conditions = []
        params = {}
        limit = None
        
        if filters:
            if "host_id" in filters:
                conditions.append("l.host_id = %(host_id)s")
                params["host_id"] = filters["host_id"]
            if "type" in filters:
                conditions.append("l.type = %(type)s")
                params["type"] = filters["type"]
            if "limit" in filters:
                limit = filters["limit"]
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY l.created_at DESC"
        
        if limit is not None:
            query += " LIMIT %s"
            params["limit"] = limit
        
        return msf_db.execute_query(query, params)
    
    def execute_raw_query(self, query: str, params: Optional[Dict] = None) -> Dict:
        """执行原始SQL查询（只读）"""
        original_query = query.strip()
        query_upper = original_query.upper()
        
        if not query_upper.startswith("SELECT") and not query_upper.startswith("SHOW"):
            return {"status": "error", "message": "Only SELECT and SHOW queries are allowed"}
        
        if self._contains_dangerous_pattern(query_upper):
            return {"status": "error", "message": "Query contains potentially dangerous patterns"}
        
        return msf_db.execute_query(original_query, params)
    
    def execute_raw_command(self, query: str, params: Optional[Dict] = None) -> Dict:
        """执行原始SQL命令（谨慎使用）"""
        original_query = query.strip()
        query_upper = original_query.upper()
        
        allowed_actions = ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]
        
        action = query_upper.split()[0] if query_upper else ""
        if action not in allowed_actions:
            return {"status": "error", "message": f"Unsupported command type: {action}"}
        
        if self._contains_dangerous_pattern(query_upper):
            return {"status": "error", "message": "Query contains potentially dangerous patterns"}
        
        return msf_db.execute_command(original_query, params)
    
    def _contains_dangerous_pattern(self, query: str) -> bool:
        """检查查询是否包含危险模式"""
        dangerous_patterns = [
            r"--.*DROP",
            r";\s*DROP",
            r";\s*DELETE",
            r";\s*UPDATE",
            r"\bUNION\b.*\bSELECT\b",
            r"\bEXEC\b",
            r"\bEXECUTE\b",
            r"\bXP_\w+\b",
            r"\bsp_\w+\b",
            r"\bSHUTDOWN\b",
            r"\bTRUNCATE\b"
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        
        return False
    
    def get_summary(self) -> Dict:
        """获取数据库摘要信息"""
        queries = [
            ("hosts", "SELECT COUNT(*) AS count FROM hosts;"),
            ("services", "SELECT COUNT(*) AS count FROM services;"),
            ("vulns", "SELECT COUNT(*) AS count FROM vulns;"),
            ("creds", "SELECT COUNT(*) AS count FROM creds;"),
            ("sessions", "SELECT COUNT(*) AS count FROM sessions;"),
            ("workspaces", "SELECT COUNT(*) AS count FROM workspaces;"),
            ("notes", "SELECT COUNT(*) AS count FROM notes;"),
            ("loots", "SELECT COUNT(*) AS count FROM loots;")
        ]
        
        summary = {}
        for name, query in queries:
            result = msf_db.execute_query(query)
            if result.get("status") != "success":
                return {"status": "error", "message": f"Failed to get {name} count: {result.get('message', 'unknown error')}"}
            
            count = result.get("data", [{"count": 0}])[0].get("count", 0)
            if name == "vulns":
                summary["vulnerabilities"] = count
            elif name == "creds":
                summary["credentials"] = count
            else:
                summary[name] = count
        
        return {
            "status": "success",
            "summary": summary
        }


msf_ops = MSFOperations()