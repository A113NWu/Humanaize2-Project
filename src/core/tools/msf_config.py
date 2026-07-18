#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSF数据库配置模块
负责管理MSF数据库连接配置和安全设置
"""

import os
import json
import ssl
from typing import Dict, Optional


class MSFConfig:
    """MSF数据库配置类"""
    
    def __init__(self):
        self._config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        config_path = self._get_config_path()
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load MSF config: {e}, using defaults")
        
        return self._get_default_config()
    
    def _get_config_path(self) -> str:
        """获取配置文件路径"""
        config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config"
        )
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "msf_config.json")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "host": "127.0.0.1",
            "port": 5432,
            "database": "msf",
            "username": "msf",
            "password": "",
            "ssl_mode": "disable",
            "connect_timeout": 10,
            "pool_size": 5,
            "max_overflow": 10,
            "retry_attempts": 3,
            "retry_delay": 2,
            "query_timeout": 30,
            "encoding": "utf-8"
        }
    
    def save_config(self):
        """保存配置到文件"""
        config_path = self._get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save MSF config: {e}")
            return False
    
    def get(self, key: str, default=None):
        """获取配置项"""
        return self._config.get(key, default)
    
    def set(self, key: str, value):
        """设置配置项"""
        self._config[key] = value
    
    @property
    def host(self) -> str:
        return self._config.get("host", "127.0.0.1")
    
    @host.setter
    def host(self, value: str):
        self._config["host"] = value
    
    @property
    def port(self) -> int:
        return self._config.get("port", 5432)
    
    @port.setter
    def port(self, value: int):
        self._config["port"] = value
    
    @property
    def database(self) -> str:
        return self._config.get("database", "msf")
    
    @database.setter
    def database(self, value: str):
        self._config["database"] = value
    
    @property
    def username(self) -> str:
        return self._config.get("username", "msf")
    
    @username.setter
    def username(self, value: str):
        self._config["username"] = value
    
    @property
    def password(self) -> str:
        return self._config.get("password", "")
    
    @password.setter
    def password(self, value: str):
        self._config["password"] = value
    
    @property
    def ssl_mode(self) -> str:
        return self._config.get("ssl_mode", "disable")
    
    @ssl_mode.setter
    def ssl_mode(self, value: str):
        self._config["ssl_mode"] = value
    
    @property
    def connect_timeout(self) -> int:
        return self._config.get("connect_timeout", 10)
    
    @property
    def pool_size(self) -> int:
        return self._config.get("pool_size", 5)
    
    @property
    def max_overflow(self) -> int:
        return self._config.get("max_overflow", 10)
    
    @property
    def retry_attempts(self) -> int:
        return self._config.get("retry_attempts", 3)
    
    @property
    def retry_delay(self) -> int:
        return self._config.get("retry_delay", 2)
    
    @property
    def query_timeout(self) -> int:
        return self._config.get("query_timeout", 30)
    
    @property
    def encoding(self) -> str:
        return self._config.get("encoding", "utf-8")
    
    def get_connection_string(self) -> str:
        """获取数据库连接字符串"""
        ssl_part = ""
        if self.ssl_mode == "require":
            ssl_part = " sslmode=require"
        elif self.ssl_mode == "verify-full":
            ssl_part = " sslmode=verify-full"
        
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}{ssl_part}"
    
    def validate_config(self) -> Dict:
        """验证配置是否有效"""
        errors = []
        
        if not self.host:
            errors.append("host cannot be empty")
        if not isinstance(self.port, int) or self.port <= 0 or self.port > 65535:
            errors.append("port must be a valid integer between 1 and 65535")
        if not self.database:
            errors.append("database cannot be empty")
        if not self.username:
            errors.append("username cannot be empty")
        if self.connect_timeout <= 0:
            errors.append("connect_timeout must be positive")
        if self.pool_size <= 0:
            errors.append("pool_size must be positive")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def to_dict(self) -> Dict:
        """转换为字典（不包含密码）"""
        config = self._config.copy()
        if "password" in config:
            config["password"] = "***"
        return config
    
    def reload(self):
        """重新加载配置"""
        self._config = self._load_config()


msf_config = MSFConfig()