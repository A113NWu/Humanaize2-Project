#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IoT 設備掃描工具

掃描局域網內運行 Aize Companion 的設備（Android 手機、平板等），
並管理已連接設備的發現和狀態。

使用方法：
    from tools.iot_device_scanner import IoTDeviceScanner
    
    scanner = IoTDeviceScanner()
    scanner.start_scanning()
    devices = scanner.get_discovered_devices()
    scanner.stop_scanning()
"""

import socket
import threading
import time
import json
import os
import sys
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredDevice:
    """已發現的設備"""
    ip: str
    port: int
    device_name: str = ""
    device_type: str = "unknown"
    last_seen: float = 0.0
    is_connected: bool = False
    device_id: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


class IoTDeviceScanner:
    """
    IoT 設備掃描器
    
    在局域網內掃描運行 Aize Companion 的設備。
    使用 TCP 連接檢測 WebSocket 端口是否開放。
    """
    
    def __init__(self, port: int = 8765, scan_interval: int = 30):
        self.port = port
        self.scan_interval = scan_interval
        self._devices: Dict[str, DiscoveredDevice] = {}
        self._scanning = False
        self._scan_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._on_device_found_callbacks: List[Callable] = []
        self._on_device_lost_callbacks: List[Callable] = []
    
    def start_scanning(self):
        """開始後台掃描"""
        if self._scanning:
            return
        
        self._scanning = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        logger.info("IoT device scanning started")
        print("[IoT] 設備掃描已啟動")
    
    def stop_scanning(self):
        """停止掃描"""
        self._scanning = False
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=2)
        logger.info("IoT device scanning stopped")
        print("[IoT] 設備掃描已停止")
    
    def _scan_loop(self):
        """掃描循環"""
        while self._scanning:
            try:
                self._do_scan()
                self._cleanup_stale_devices()
            except Exception as e:
                logger.error(f"Scan error: {e}")
            
            # 分段等待，每5秒檢查一次是否停止
            for _ in range(self.scan_interval):
                if not self._scanning:
                    break
                time.sleep(1)
    
    def _do_scan(self):
        """執行一次掃描"""
        local_ip = self._get_local_ip()
        if not local_ip:
            return
        
        subnet = local_ip.rsplit('.', 1)[0]
        found_ips = set()
        
        # 掃描 1-254 範圍
        for i in range(1, 255):
            if not self._scanning:
                break
            
            target_ip = f"{subnet}.{i}"
            
            # 跳過自己
            if target_ip == local_ip:
                continue
            
            # 並發檢測（使用線程池避免卡頓）
            if self._check_port_open(target_ip, self.port):
                found_ips.add(target_ip)
                self._add_or_update_device(target_ip)
        
        # 清理未找到的設備
        with self._lock:
            stale_ips = set(self._devices.keys()) - found_ips
            for ip in stale_ips:
                if time.time() - self._devices[ip].last_seen > self.scan_interval * 2:
                    self._remove_device(ip)
    
    def _check_port_open(self, ip: str, port: int, timeout: float = 0.5) -> bool:
        """檢查端口是否開放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _get_local_ip(self) -> Optional[str]:
        """獲取本機局域網 IP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except Exception:
            # 回退方案
            try:
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except Exception:
                return None
    
    def _add_or_update_device(self, ip: str):
        """添加或更新設備"""
        with self._lock:
            existing = self._devices.get(ip)
            now = time.time()
            
            if existing:
                existing.last_seen = now
                if not existing.is_connected:
                    self._fire_device_found(existing)
            else:
                device = DiscoveredDevice(
                    ip=ip,
                    port=self.port,
                    device_name=f"Unknown Device ({ip})",
                    last_seen=now
                )
                self._devices[ip] = device
                logger.info(f"Discovered IoT device at {ip}:{self.port}")
                print(f"[IoT] 發現設備: {ip}:{self.port}")
                self._fire_device_found(device)
    
    def _remove_device(self, ip: str):
        """移除設備"""
        with self._lock:
            if ip in self._devices:
                device = self._devices.pop(ip)
                logger.info(f"Device lost: {ip}")
                self._fire_device_lost(device)
    
    def _cleanup_stale_devices(self):
        """清理過期設備"""
        now = time.time()
        with self._lock:
            stale = [ip for ip, d in self._devices.items() 
                     if now - d.last_seen > self.scan_interval * 3]
            for ip in stale:
                del self._devices[ip]
    
    def _fire_device_found(self, device: DiscoveredDevice):
        """觸發設備發現回調"""
        for callback in self._on_device_found_callbacks:
            try:
                callback(device.to_dict())
            except Exception as e:
                logger.error(f"Device found callback error: {e}")
    
    def _fire_device_lost(self, device: DiscoveredDevice):
        """觸發設備丟失回調"""
        for callback in self._on_device_lost_callbacks:
            try:
                callback(device.to_dict())
            except Exception as e:
                logger.error(f"Device lost callback error: {e}")
    
    def on_device_found(self, callback: Callable):
        """註冊設備發現回調"""
        self._on_device_found_callbacks.append(callback)
    
    def on_device_lost(self, callback: Callable):
        """註冊設備丟失回調"""
        self._on_device_lost_callbacks.append(callback)
    
    def get_discovered_devices(self) -> List[Dict]:
        """獲取所有已發現設備"""
        with self._lock:
            return [d.to_dict() for d in self._devices.values()]
    
    def get_device_count(self) -> int:
        """獲取設備數量"""
        with self._lock:
            return len(self._devices)
    
    def is_scanning(self) -> bool:
        """是否正在掃描"""
        return self._scanning
    
    def set_scan_interval(self, seconds: int):
        """設置掃描間隔"""
        self.scan_interval = max(5, min(300, seconds))


def save_discovered_devices_to_settings(devices: List[Dict], settings_path: str):
    """保存已發現設備到設置文件"""
    try:
        settings = {}
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        
        settings['iot_discovered_devices'] = devices
        
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save discovered devices: {e}")


def load_discovered_devices_from_settings(settings_path: str) -> List[Dict]:
    """從設置文件加載已發現設備"""
    try:
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            return settings.get('iot_discovered_devices', [])
    except Exception:
        pass
    return []
