#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IoT 算力管理器 - 獨立入口點

提供分布式算力利用功能，與 HSN（AI-to-AI 協作網絡）完全獨立。

使用場景：
- 用戶將手機、平板等設備接入系統
- 利用閒置設備的算力進行分布式計算
- 設備與 Aize 獨立對話

與 HSN 的區別：
- HSN: AI 與 AI 之間的溝通協作
- IoT Compute: 利用分佈式設備的 CPU/GPU 算力

使用方法：
    from tools.iot_compute_manager import IoTComputeManager
    
    manager = IoTComputeManager()
    manager.start()
    
    # 提交計算任務
    task_id = manager.submit_task('compute', {'data': '...'})
    
    # 獲取結果
    result = manager.wait_for_result(task_id)
    
    # 與設備對話
    manager.send_chat('device-id', '你好 Aize')
"""

import time
import uuid
import threading
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class IoTComputeManager:
    """
    IoT 算力管理器
    
    獨立的分布式算力利用系統，負責：
    - 啟動和管理 IoT 算力網絡
    - 設備管理（註冊、心跳、狀態監控）
    - 任務分發和結果聚合
    - 設備與 Aize 的對話中轉
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self._network = None
        self._initialized = False
        self._lock = threading.Lock()
        self._event_callbacks: Dict[str, List[Any]] = {
            'on_device_connected': [],
            'on_device_disconnected': [],
            'on_task_completed': [],
            'on_task_failed': [],
            'on_chat_message': [],
        }
    
    def initialize(self) -> bool:
        """初始化 IoT 算力管理器"""
        if self._initialized:
            return True
        
        try:
            from .iot_compute_network import IoTComputeNetwork
            self._network = IoTComputeNetwork(host=self.host, port=self.port)
            
            # 註冊事件監聽
            self._network.on('device_connected', self._on_device_connected)
            self._network.on('device_disconnected', self._on_device_disconnected)
            self._network.on('task_completed', self._on_task_completed)
            self._network.on('task_failed', self._on_task_failed)
            self._network.on('chat_message', self._on_chat_message)
            
            self._initialized = True
            logger.info("IoT Compute Manager initialized")
            return True
        except ImportError:
            logger.error("iot_compute_network module not available. Install websockets: pip install websockets>=12.0")
            return False
        except Exception as e:
            logger.error(f"IoT Compute Manager init failed: {e}")
            return False
    
    def start(self) -> bool:
        """啟動 IoT 算力網絡"""
        if not self._initialized:
            if not self.initialize():
                return False
        
        if self._network and not self._network.is_running:
            self._network.start()
            print(f"[IoT] 算力網絡已啟動: ws://{self.host}:{self.port}")
            return True
        return False
    
    def stop(self):
        """停止 IoT 算力網絡"""
        if self._network and self._network.is_running:
            self._network.stop()
            print("[IoT] 算力網絡已停止")
    
    def is_running(self) -> bool:
        """檢查是否正在運行"""
        return self._network is not None and self._network.is_running
    
    # ========== 設備管理 ==========
    
    def get_connected_devices(self) -> List[Dict]:
        """獲取所有已連接設備列表"""
        if not self._network:
            return []
        return self._network.get_device_list()
    
    def get_online_devices(self) -> List[Dict]:
        """獲取在線設備列表"""
        if not self._network:
            return []
        return self._network.get_online_devices()
    
    def get_device_count(self) -> int:
        """獲取設備數量"""
        if not self._network:
            return 0
        return len(self._network.devices)
    
    def get_online_count(self) -> int:
        """獲取在線設備數量"""
        if not self._network:
            return 0
        return len(self._network.get_online_devices())
    
    # ========== 任務管理 ==========
    
    def submit_task(self, task_type: str, payload: Dict,
                   preferred_device_id: Optional[str] = None,
                   timeout: int = None) -> Optional[str]:
        """
        提交計算任務
        
        Args:
            task_type: 任務類型 (compute, nlp, data_processing, general)
            payload: 任務數據
            preferred_device_id: 首選設備 ID
            timeout: 超時時間（秒）
            
        Returns:
            任務 ID，失敗返回 None
        """
        if not self._network:
            logger.error("IoT network not initialized")
            return None
        
        try:
            task_id = self._network.submit_task(
                task_type=task_type,
                payload=payload,
                preferred_device_id=preferred_device_id,
                timeout=timeout
            )
            logger.info(f"Task submitted: {task_id[:8]}...")
            return task_id
        except Exception as e:
            logger.error(f"Task submission failed: {e}")
            return None
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """查詢任務狀態"""
        if not self._network:
            return None
        return self._network.get_task_status(task_id)
    
    def get_task_result(self, task_id: str) -> Optional[Dict]:
        """獲取任務結果"""
        if not self._network:
            return None
        return self._network.get_result(task_id)
    
    def wait_for_result(self, task_id: str, timeout: float = 60) -> Optional[Dict]:
        """等待任務完成並獲取結果"""
        if not self._network:
            return None
        return self._network.wait_for_result(task_id, timeout)
    
    # ========== 聊天功能 ==========
    
    def send_chat(self, device_id: str, message: str,
                 conversation_id: str = None) -> Optional[str]:
        """
        向指定設備發送聊天消息
        
        Args:
            device_id: 目標設備 ID
            message: 聊天消息
            conversation_id: 對話 ID（可選，自動生成）
            
        Returns:
            對話 ID
        """
        if not self._network:
            return None
        
        conv_id = conversation_id or str(uuid.uuid4())
        self._network.send_chat_to_device(device_id, message, conv_id)
        return conv_id
    
    def broadcast_chat(self, message: str, exclude_device_id: str = None):
        """向所有設備廣播聊天消息"""
        if not self._network:
            return
        self._network.broadcast_chat(message, exclude_device_id)
    
    # ========== 統計和配置 ==========
    
    def get_stats(self) -> Dict:
        """獲取網絡統計信息"""
        if not self._network:
            return {
                'is_running': False,
                'total_devices': 0,
                'online_devices': 0,
                'total_tasks': 0
            }
        return self._network.get_network_stats()
    
    def configure(self, **kwargs):
        """更新配置"""
        if self._network:
            self._network.configure(**kwargs)
    
    # ========== 事件回調 ==========
    
    def on(self, event: str, callback):
        """註冊事件回調"""
        if event in self._event_callbacks:
            self._event_callbacks[event].append(callback)
    
    def _fire_event(self, event: str, *args):
        """觸發事件回調"""
        if event in self._event_callbacks:
            for callback in self._event_callbacks[event]:
                try:
                    callback(*args)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")
    
    def _on_device_connected(self, device_info: Dict):
        """設備連接回調"""
        device_name = device_info.get('device_name', 'Unknown')
        device_type = device_info.get('device_type', 'unknown')
        print(f"[IoT] 設備已連接: {device_name} ({device_type})")
        self._fire_event('on_device_connected', device_info)
    
    def _on_device_disconnected(self, device_info: Dict):
        """設備斷開回調"""
        device_name = device_info.get('device_name', 'Unknown')
        print(f"[IoT] 設備已斷開: {device_name}")
        self._fire_event('on_device_disconnected', device_info)
    
    def _on_task_completed(self, task_info: Dict):
        """任務完成回調"""
        task_id = task_info.get('task_id', 'Unknown')
        print(f"[IoT] 任務完成: {task_id[:8]}...")
        self._fire_event('on_task_completed', task_info)
    
    def _on_task_failed(self, task_info: Dict):
        """任務失敗回調"""
        task_id = task_info.get('task_id', 'Unknown')
        error = task_info.get('error_message', 'Unknown error')
        print(f"[IoT] 任務失敗: {task_id[:8]}... - {error}")
        self._fire_event('on_task_failed', task_info)
    
    def _on_chat_message(self, chat_data: Dict):
        """聊天消息回調"""
        device_id = chat_data.get('device_id', 'Unknown')
        message = chat_data.get('message', '')
        print(f"[IoT] 來自設備 {device_id[:8]} 的消息: {message[:50]}...")
        self._fire_event('on_chat_message', chat_data)


# 全局管理器實例
_manager_instance: Optional[IoTComputeManager] = None


def get_manager(host: str = "0.0.0.0", port: int = 8765) -> IoTComputeManager:
    """獲取全局 IoT 算力管理器實例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = IoTComputeManager(host, port)
    return _manager_instance


def start_iot_network(host: str = "0.0.0.0", port: int = 8765) -> IoTComputeManager:
    """初始化並啟動 IoT 算力網絡"""
    manager = get_manager(host, port)
    manager.initialize()
    manager.start()
    return manager


def stop_iot_network():
    """停止 IoT 算力網絡"""
    global _manager_instance
    if _manager_instance:
        _manager_instance.stop()
        _manager_instance = None
