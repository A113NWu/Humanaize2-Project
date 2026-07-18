#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSF数据库连接管理器
负责管理数据库连接、连接池和事务处理
"""

import os
import sys
import time
import logging
import traceback
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .msf_config import msf_config

try:
    import psycopg2
    import psycopg2.pool
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger(__name__)


class MSFDBError(Exception):
    """MSF数据库异常"""
    pass


class _CursorContextManager:
    """游标上下文管理器"""
    
    def __init__(self, pool):
        self._pool = pool
        self._conn = None
        self._cursor = None
    
    def __enter__(self):
        self._conn = self._pool.get_connection()
        self._cursor = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return self._cursor
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._pool.put_connection(self._conn)


class ConnectionPool:
    """数据库连接池"""
    
    def __init__(self):
        self._pool = None
        self._connection_count = 0
    
    def init_pool(self):
        """初始化连接池"""
        if not PSYCOPG2_AVAILABLE:
            raise MSFDBError("psycopg2 not installed. Install with: pip install psycopg2-binary")
        
        try:
            ssl_params = {}
            if msf_config.ssl_mode == "require":
                ssl_params = {"sslmode": "require"}
            elif msf_config.ssl_mode == "verify-full":
                ssl_params = {"sslmode": "verify-full"}
            
            self._pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=msf_config.pool_size,
                host=msf_config.host,
                port=msf_config.port,
                database=msf_config.database,
                user=msf_config.username,
                password=msf_config.password,
                connect_timeout=msf_config.connect_timeout,
                **ssl_params
            )
            logger.info(f"MSF connection pool initialized: {msf_config.pool_size} connections")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise MSFDBError(f"Failed to initialize connection pool: {e}")
    
    def get_connection(self):
        """获取数据库连接"""
        if not self._pool:
            self.init_pool()
        
        for attempt in range(msf_config.retry_attempts):
            try:
                conn = self._pool.getconn()
                self._connection_count += 1
                return conn
            except Exception as e:
                logger.warning(f"Failed to get connection (attempt {attempt + 1}/{msf_config.retry_attempts}): {e}")
                if attempt < msf_config.retry_attempts - 1:
                    time.sleep(msf_config.retry_delay)
        
        raise MSFDBError("Failed to get database connection after retries")
    
    def put_connection(self, conn):
        """归还数据库连接"""
        if conn and self._pool:
            try:
                self._pool.putconn(conn)
                self._connection_count -= 1
            except Exception as e:
                logger.error(f"Failed to put connection back to pool: {e}")
    
    def close_all(self):
        """关闭所有连接"""
        if self._pool:
            try:
                self._pool.closeall()
                logger.info("MSF connection pool closed")
            except Exception as e:
                logger.error(f"Failed to close connection pool: {e}")
    
    @property
    def connection_count(self):
        """获取当前活跃连接数"""
        return self._connection_count


class MSFDB:
    """MSF数据库核心类"""
    
    def __init__(self):
        self._pool = ConnectionPool()
        self._connected = False
    
    def connect(self) -> Dict:
        """建立数据库连接"""
        try:
            self._pool.init_pool()
            self._connected = True
            
            with self._get_cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
            
            return {
                "status": "success",
                "message": "Connected to MSF database",
                "version": version
            }
        except MSFDBError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {e}"}
    
    def disconnect(self) -> Dict:
        """断开数据库连接"""
        try:
            self._pool.close_all()
            self._connected = False
            return {"status": "success", "message": "Disconnected from MSF database"}
        except Exception as e:
            return {"status": "error", "message": f"Disconnect failed: {e}"}
    
    def _get_cursor(self):
        """获取游标（上下文管理器）"""
        return _CursorContextManager(self._pool)
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Dict:
        """执行查询"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        try:
            with self._get_cursor() as cursor:
                cursor.execute(query, params or {})
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
        except psycopg2.Error as e:
            logger.error(f"Query execution failed: {e}")
            return {"status": "error", "message": f"Database error: {e}"}
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return {"status": "error", "message": str(e)}
    
    def execute_command(self, query: str, params: Optional[Dict] = None) -> Dict:
        """执行命令（INSERT/UPDATE/DELETE）"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        try:
            conn = self._pool.get_connection()
            try:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute(query, params or {})
                conn.commit()
                
                rowcount = cursor.rowcount
                lastrowid = cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
                
                return {
                    "status": "success",
                    "rowcount": rowcount,
                    "lastrowid": lastrowid
                }
            except Exception as e:
                conn.rollback()
                raise
            finally:
                self._pool.put_connection(conn)
        except psycopg2.Error as e:
            logger.error(f"Command execution failed: {e}")
            return {"status": "error", "message": f"Database error: {e}"}
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return {"status": "error", "message": str(e)}
    
    def execute_batch(self, queries: List[Dict]) -> Dict:
        """批量执行命令"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        conn = self._pool.get_connection()
        results = []
        
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            for i, query_data in enumerate(queries):
                query = query_data.get("query", "")
                params = query_data.get("params", {})
                
                try:
                    cursor.execute(query, params)
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
                    conn.rollback()
                    return {
                        "status": "error",
                        "message": f"Batch failed at query {i}",
                        "results": results
                    }
            
            conn.commit()
            
            return {
                "status": "success",
                "results": results,
                "total": len(results)
            }
        except Exception as e:
            conn.rollback()
            logger.error(f"Batch execution failed: {e}")
            return {"status": "error", "message": str(e), "results": results}
        finally:
            self._pool.put_connection(conn)
    
    def execute_transaction(self, queries: List[Dict]) -> Dict:
        """执行事务"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        conn = self._pool.get_connection()
        
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            for i, query_data in enumerate(queries):
                query = query_data.get("query", "")
                params = query_data.get("params", {})
                cursor.execute(query, params)
            
            conn.commit()
            
            return {
                "status": "success",
                "message": "Transaction completed successfully",
                "query_count": len(queries)
            }
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            self._pool.put_connection(conn)
    
    def test_connection(self) -> Dict:
        """测试数据库连接"""
        if not self._connected:
            return {"status": "error", "message": "Not connected to database"}
        
        try:
            with self._get_cursor() as cursor:
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
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """
        return self.execute_query(query)
    
    def get_table_columns(self, table_name: str) -> Dict:
        """获取表结构"""
        query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """
        return self.execute_query(query, (table_name,))
    
    def get_status(self) -> Dict:
        """获取数据库状态"""
        return {
            "connected": self._connected,
            "connection_count": self._pool.connection_count,
            "config": msf_config.to_dict()
        }


msf_db = MSFDB()