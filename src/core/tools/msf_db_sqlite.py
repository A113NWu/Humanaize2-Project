#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSF数据库连接管理器 - SQLite版本
用于没有安装PostgreSQL的环境，提供相同的API接口
"""

import os
import sys
import time
import logging
import sqlite3
import re
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .msf_config import msf_config

logger = logging.getLogger(__name__)


class MSFDBError(Exception):
    """MSF数据库异常"""
    pass


class MSFDB:
    """MSF数据库核心类 - SQLite版本"""
    
    def __init__(self):
        self._conn = None
        self._connected = False
        self._db_path = self._get_db_path()
    
    def _get_db_path(self) -> str:
        """获取数据库文件路径"""
        db_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data"
        )
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, "msf.db")
    
    def _init_tables(self):
        """初始化MSF数据库表结构"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS hosts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host TEXT NOT NULL,
                os_name TEXT DEFAULT '',
                os_flavor TEXT DEFAULT '',
                os_sp TEXT DEFAULT '',
                os_lang TEXT DEFAULT '',
                state TEXT DEFAULT 'alive',
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                info TEXT DEFAULT '',
                mac TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER NOT NULL,
                port INTEGER NOT NULL,
                proto TEXT DEFAULT 'tcp',
                name TEXT DEFAULT '',
                state TEXT DEFAULT 'open',
                info TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (host_id) REFERENCES hosts(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS vulns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                confidence INTEGER DEFAULT 50,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (host_id) REFERENCES hosts(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS creds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER NOT NULL,
                service TEXT DEFAULT '',
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                type TEXT DEFAULT 'password',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (host_id) REFERENCES hosts(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER NOT NULL,
                type TEXT DEFAULT '',
                session_port INTEGER DEFAULT 0,
                via_exploit TEXT DEFAULT '',
                via_payload TEXT DEFAULT '',
                desc TEXT DEFAULT '',
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                is_dead INTEGER DEFAULT 0,
                FOREIGN KEY (host_id) REFERENCES hosts(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER,
                type TEXT DEFAULT '',
                data TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (host_id) REFERENCES hosts(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS loots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER,
                type TEXT DEFAULT '',
                name TEXT DEFAULT '',
                data TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (host_id) REFERENCES hosts(id)
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_hosts_host ON hosts(host);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_hosts_state ON hosts(state);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_services_host_id ON services(host_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_vulns_host_id ON vulns(host_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_creds_host_id ON creds(host_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_host_id ON sessions(host_id);
            """
        ]
        
        for query in tables:
            try:
                self._conn.execute(query)
            except Exception as e:
                logger.warning(f"Failed to create table: {e}")
        
        self._conn.commit()
        logger.info("MSF SQLite database tables initialized")
    
    def connect(self) -> Dict:
        """建立数据库连接"""
        try:
            self._conn = sqlite3.connect(self._db_path, timeout=msf_config.connect_timeout)
            self._conn.row_factory = sqlite3.Row
            self._connected = True
            
            self._init_tables()
            
            cursor = self._conn.cursor()
            cursor.execute("SELECT sqlite_version();")
            version = cursor.fetchone()[0]
            
            return {
                "status": "success",
                "message": f"Connected to MSF SQLite database at {self._db_path}",
                "version": f"SQLite {version}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {e}"}
    
    def disconnect(self) -> Dict:
        """断开数据库连接"""
        try:
            if self._conn:
                self._conn.close()
                self._conn = None
            self._connected = False
            return {"status": "success", "message": "Disconnected from MSF database"}
        except Exception as e:
            return {"status": "error", "message": f"Disconnect failed: {e}"}
    
    def _convert_query_params(self, query: str, params: Optional[Any]) -> tuple:
        """将PostgreSQL风格的参数转换为SQLite风格"""
        if params is None:
            params = {}
        
        query = query.replace("NOW()", "datetime('now')")
        
        query = re.sub(r'\bRETURNING\s+\w+\b', '', query)
        
        if isinstance(params, dict):
            converted_params = []
            
            percent_s_count = query.count("%s")
            
            dict_keys = list(params.keys())
            processed_keys = set()
            
            for key in dict_keys:
                placeholder = f"%({key})s"
                if placeholder in query:
                    query = query.replace(placeholder, "?")
                    converted_params.append(params[key])
                    processed_keys.add(key)
            
            remaining_keys = [k for k in dict_keys if k not in processed_keys]
            
            for _ in range(percent_s_count):
                query = query.replace("%s", "?", 1)
                if remaining_keys:
                    converted_params.append(params[remaining_keys.pop(0)])
                else:
                    converted_params.append(None)
            
            return query, converted_params if converted_params else None
        
        if isinstance(params, (tuple, list)):
            converted_query = query.replace("%s", "?")
            return converted_query, params
        
        return query, None
    
    def execute_query(self, query: str, params: Optional[Any] = None) -> Dict:
        """执行查询"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        try:
            cursor = self._conn.cursor()
            
            query, params = self._convert_query_params(query, params)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows = cursor.fetchall()
            
            if rows:
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in rows]
            else:
                results = []
            
            return {
                "status": "success",
                "data": results,
                "count": len(results)
            }
        except sqlite3.Error as e:
            logger.error(f"Query execution failed: {e}")
            return {"status": "error", "message": f"Database error: {e}"}
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return {"status": "error", "message": str(e)}
    
    def execute_command(self, query: str, params: Optional[Any] = None) -> Dict:
        """执行命令（INSERT/UPDATE/DELETE）"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        try:
            cursor = self._conn.cursor()
            
            query, params = self._convert_query_params(query, params)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            self._conn.commit()
            
            rowcount = cursor.rowcount
            lastrowid = cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
            
            return {
                "status": "success",
                "rowcount": rowcount,
                "lastrowid": lastrowid
            }
        except sqlite3.Error as e:
            self._conn.rollback()
            logger.error(f"Command execution failed: {e}")
            return {"status": "error", "message": f"Database error: {e}"}
        except Exception as e:
            self._conn.rollback()
            logger.error(f"Command execution error: {e}")
            return {"status": "error", "message": str(e)}
    
    def execute_batch(self, queries: List[Dict]) -> Dict:
        """批量执行命令"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        results = []
        
        try:
            cursor = self._conn.cursor()
            
            for i, query_data in enumerate(queries):
                query = query_data.get("query", "")
                params = query_data.get("params", {})
                
                try:
                    query, params = self._convert_query_params(query, params)
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                    results.append({
                        "index": i,
                        "status": "success",
                        "rowcount": cursor.rowcount
                    })
                except Exception as e:
                    results.append({
                        "index": i,
                        "status": "error",
                        "message": str(e)
                    })
                    self._conn.rollback()
                    return {
                        "status": "error",
                        "message": f"Batch failed at query {i}",
                        "results": results
                    }
            
            self._conn.commit()
            
            return {
                "status": "success",
                "results": results,
                "total": len(results)
            }
        except Exception as e:
            self._conn.rollback()
            logger.error(f"Batch execution failed: {e}")
            return {"status": "error", "message": str(e), "results": results}
    
    def execute_transaction(self, queries: List[Dict]) -> Dict:
        """执行事务"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        try:
            cursor = self._conn.cursor()
            
            for i, query_data in enumerate(queries):
                query = query_data.get("query", "")
                params = query_data.get("params", {})
                query, params = self._convert_query_params(query, params)
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
            
            self._conn.commit()
            
            return {
                "status": "success",
                "message": "Transaction completed successfully",
                "query_count": len(queries)
            }
        except Exception as e:
            self._conn.rollback()
            logger.error(f"Transaction failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def test_connection(self) -> Dict:
        """测试数据库连接"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            
            if result and result[0] == 1:
                return {"status": "success", "message": "Connection test successful"}
            else:
                return {"status": "error", "message": "Connection test failed"}
        except Exception as e:
            return {"status": "error", "message": f"Connection test failed: {e}"}
    
    def get_table_names(self) -> Dict:
        """获取所有表名"""
        query = """
            SELECT name 
            FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name;
        """
        return self.execute_query(query)
    
    def get_table_columns(self, table_name: str) -> Dict:
        """获取表结构"""
        query = f"PRAGMA table_info({table_name});"
        result = self.execute_query(query)
        
        if result["status"] == "success":
            columns = []
            for row in result["data"]:
                columns.append({
                    "column_name": row["name"],
                    "data_type": row["type"],
                    "is_nullable": "YES" if row["notnull"] == 0 else "NO",
                    "column_default": row["dflt_value"]
                })
            return {"status": "success", "data": columns, "count": len(columns)}
        
        return result
    
    def get_status(self) -> Dict:
        """获取数据库状态"""
        return {
            "connected": self._connected,
            "connection_count": 1 if self._connected else 0,
            "config": msf_config.to_dict(),
            "db_path": self._db_path
        }


msf_db = MSFDB()