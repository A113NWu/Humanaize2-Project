#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IoT 算力网络模块 - 分布式设备算力共享

允许用户将其他设备（手机、其他计算机）接入系统，
并将它们的算力用于分布式任务处理。

支持功能：
- 设备注册/认证/心跳
- 任务分发和结果聚合
- 设备与 Aize 的对话功能
- 通过 WebSocket 进行实时通信
- 支持 Android/iOS/PC 多平台设备
"""

import os
import sys
import json
import time
import uuid
import threading
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """设备类型"""
    ANDROID_PHONE = "android_phone"
    ANDROID_TABLET = "android_tablet"
    PC_WINDOWS = "pc_windows"
    PC_LINUX = "pc_linux"
    PC_MAC = "pc_mac"
    IOT_DEVICE = "iot_device"
    UNKNOWN = "unknown"


class DeviceStatus(Enum):
    """设备状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    IDLE = "idle"
    DISCONNECTED = "disconnected"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DeviceCapabilities:
    """设备能力描述"""
    can_compute: bool = True
    max_concurrent_tasks: int = 1
    avg_tasks_per_second: float = 0.0
    supported_task_types: List[str] = field(default_factory=list)
    gpu_available: bool = False
    memory_gb: float = 0.0
    cpu_cores: int = 0
    can_shell_exec: bool = False  # 是否支持远程 Shell 命令执行（Shizuku 授权）


@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str = ""
    device_name: str = ""
    device_type: DeviceType = DeviceType.UNKNOWN
    status: DeviceStatus = DeviceStatus.OFFLINE
    ip_address: str = ""
    port: int = 0
    capabilities: DeviceCapabilities = field(default_factory=DeviceCapabilities)
    registered_at: float = 0.0
    last_heartbeat: float = 0.0
    total_tasks_completed: int = 0
    total_compute_time: float = 0.0
    _ws = None  # WebSocket 连接引用
    _loop = None  # asyncio 事件循环
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['device_type'] = self.device_type.value
        data['status'] = self.status.value
        # 移除不可序列化的字段
        data.pop('_ws', None)
        data.pop('_loop', None)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DeviceInfo':
        data['device_type'] = DeviceType(data.get('device_type', 'unknown'))
        data['status'] = DeviceStatus(data.get('status', 'offline'))
        data['capabilities'] = DeviceCapabilities(**data.get('capabilities', {}))
        return cls(**data)


@dataclass
class ComputeTask:
    """计算任务"""
    task_id: str = ""
    task_type: str = "general"
    payload: Dict[str, Any] = field(default_factory=dict)
    assigned_device_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    result: Optional[Dict] = None
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['status'] = self.status.value
        return data


class IoTComputeNetwork:
    """
    IoT 算力网络管理器
    
    负责管理分布式设备的连接、认证、任务分发和结果聚合。
    
    使用方法:
        from iot_compute_network import init_network, get_network
        
        # 启动服务
        network = init_network(host='0.0.0.0', port=8765)
        
        # 提交任务
        task_id = network.submit_task('compute', {'data': '...'})
        
        # 获取结果
        result = network.wait_for_result(task_id)
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.devices: Dict[str, DeviceInfo] = {}
        self.tasks: Dict[str, ComputeTask] = {}
        self.is_running = False
        self._server_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.RLock()  # 使用 RLock 防止嵌套死锁
        self._event_handlers: Dict[str, List[Callable]] = {
            'device_connected': [],
            'device_disconnected': [],
            'task_completed': [],
            'task_failed': [],
            'task_assigned': [],
            'chat_message': [],
            'chat_response': [],
        }
        self._config = {
            'heartbeat_interval': 30,
            'device_timeout': 90,
            'max_pending_tasks': 100,
            'task_timeout': 300,
            'auto_assign': True,
            'prefer_gpu': False,
            'max_retries': 3,
        }
        # 存储待发送的消息队列
        self._pending_messages: Dict[str, List[Dict]] = {}
        # Shell 执行：shell_id -> asyncio Future（保存結果）
        self._shell_pending: Dict[str, 'asyncio.Future[Dict]'] = {}
        self._shell_pending_lock = threading.RLock()
    
    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)
    
    def _emit(self, event: str, *args, **kwargs):
        """触发事件"""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    if callable(handler):
                        handler(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
    
    def start(self):
        """启动 IoT 算力网络服务"""
        if self.is_running:
            logger.warning("IoT Compute Network is already running")
            return
        
        self.is_running = True
        
        # 启动 asyncio 事件循环线程
        self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._loop_thread.start()
        
        # 等待事件循环就绪
        time.sleep(0.5)
        
        # 启动心跳检测
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        
        logger.info(f"IoT Compute Network started on {self.host}:{self.port}")
        print(f"[IoT] 算力网络已启动: ws://{self.host}:{self.port}")
    
    def stop(self):
        """停止 IoT 算力网络服务"""
        self.is_running = False
        self._disconnect_all_devices()
        
        # 停止事件循环
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except:
                pass
        
        logger.info("IoT Compute Network stopped")
        print("[IoT] 算力网络已停止")
    
    def _run_event_loop(self):
        """运行 asyncio 事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            # 启动 WebSocket 服务器
            start_server = self._loop.create_task(self._start_ws_server())
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Event loop error: {e}")
        finally:
            self._loop.close()
    
    async def _start_ws_server(self):
        """启动 WebSocket 服务器"""
        try:
            import websockets
            
            async def handler(websocket, path):
                await self._handle_connection(websocket, path)
            
            async with websockets.serve(handler, self.host, self.port):
                logger.info(f"WebSocket server listening on {self.host}:{self.port}")
                # 保持服务器运行
                while self.is_running:
                    await asyncio.sleep(1)
        except ImportError:
            logger.error("websockets library not installed. Install with: pip install websockets")
            self.is_running = False
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
            self.is_running = False
    
    async def _handle_connection(self, websocket, path):
        """处理新的 WebSocket 连接"""
        device_id = None
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    action = data.get('action', '')
                    
                    if action == 'register':
                        device_id = await self._handle_register_async(data, websocket)
                    elif action == 'heartbeat':
                        self._handle_heartbeat(device_id, data)
                        # 发送心跳确认
                        await self._send_ws_async(websocket, {
                            'action': 'heartbeat_ack',
                            'device_id': device_id,
                            'timestamp': time.time()
                        })
                    elif action == 'task_result':
                        await self._handle_task_result_async(device_id, data, websocket)
                    elif action == 'chat_message':
                        await self._handle_chat_message_async(device_id, data, websocket)
                    elif action == 'chat_stream':
                        await self._handle_chat_stream_async(device_id, data, websocket)
                    elif action == 'shell_result':
                        await self._handle_shell_result_async(device_id, data, websocket)
                    elif action == 'disconnect':
                        self._handle_disconnect(device_id)
                        break
                    elif action == 'ping':
                        await self._send_ws_async(websocket, {
                            'action': 'pong',
                            'device_id': device_id
                        })
                    else:
                        logger.warning(f"Unknown action: {action}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from device")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        except Exception as e:
            logger.info(f"WebSocket connection closed: {e}")
        finally:
            if device_id:
                self._handle_disconnect(device_id)
    
    async def _handle_register_async(self, data: Dict, websocket) -> str:
        """异步处理设备注册"""
        device_id = str(uuid.uuid4())
        device_type = DeviceType(data.get('device_type', 'unknown'))
        device_name = data.get('device_name', f'Unknown-{device_id[:8]}')
        
        capabilities = DeviceCapabilities(
            can_compute=data.get('can_compute', True),
            max_concurrent_tasks=data.get('max_concurrent_tasks', 1),
            gpu_available=data.get('gpu_available', False),
            memory_gb=data.get('memory_gb', 0),
            cpu_cores=data.get('cpu_cores', 0),
            supported_task_types=data.get('supported_task_types', []),
            can_shell_exec=data.get('can_shell_exec', False)
        )
        
        device = DeviceInfo(
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            status=DeviceStatus.ONLINE,
            ip_address=data.get('ip', ''),
            port=data.get('port', 0),
            capabilities=capabilities,
            registered_at=time.time(),
            last_heartbeat=time.time(),
            _ws=websocket,
            _loop=self._loop
        )
        
        with self._lock:
            self.devices[device_id] = device
            self._pending_messages[device_id] = []
        
        # 发送注册确认
        response = {
            'action': 'register_ack',
            'device_id': device_id,
            'status': 'success',
            'config': {
                'heartbeat_interval': self._config['heartbeat_interval'],
                'task_timeout': self._config['task_timeout'],
                'server_version': '2.0.0'
            }
        }
        await self._send_ws_async(websocket, response)
        
        self._emit('device_connected', device.to_dict())
        logger.info(f"Device registered: {device_name} ({device_id[:8]})")
        print(f"[IoT] 设备已连接: {device_name} ({device_type.value})")
        
        # 发送队列中待处理的任务
        await self._flush_pending_messages(device_id, websocket)
        
        return device_id
    
    async def _handle_task_result_async(self, device_id: str, data: Dict, websocket):
        """异步处理任务结果"""
        task_id = data.get('task_id', '')
        result = data.get('result', {})
        success = data.get('success', True)
        
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if success:
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task.completed_at = time.time()
                    self._emit('task_completed', task.to_dict())
                else:
                    task.status = TaskStatus.FAILED
                    task.error_message = data.get('error', 'Unknown error')
                    self._emit('task_failed', task.to_dict())
                
                if device_id in self.devices:
                    self.devices[device_id].status = DeviceStatus.IDLE
                    self.devices[device_id].total_tasks_completed += 1
                    self.devices[device_id].total_compute_time += data.get('compute_time', 0)
        
        # 发送结果确认
        await self._send_ws_async(websocket, {
            'action': 'result_ack',
            'task_id': task_id,
            'status': 'received'
        })
    
    async def _handle_chat_message_async(self, device_id: str, data: Dict, websocket):
        """异步处理来自设备的聊天消息"""
        message = data.get('message', '')
        user_id = data.get('user_id', device_id)
        conversation_id = data.get('conversation_id', str(uuid.uuid4()))
        
        # 触发事件，让外部（如 ThinkingEngineAPI）处理
        self._emit('chat_message', {
            'device_id': device_id,
            'user_id': user_id,
            'message': message,
            'conversation_id': conversation_id,
            'timestamp': time.time()
        })
        
        # 如果有注册的聊天处理器，使用它
        response_msg = f"[已收到] {message}"
        
        # 发送响应
        response = {
            'action': 'chat_response',
            'message': response_msg,
            'conversation_id': conversation_id,
            'device_id': device_id,
            'timestamp': time.time()
        }
        await self._send_ws_async(websocket, response)
        
        self._emit('chat_response', {
            'device_id': device_id,
            'message': response_msg,
            'conversation_id': conversation_id
        })
    
    async def _handle_chat_stream_async(self, device_id: str, data: Dict, websocket):
        """异步处理流式聊天请求"""
        message = data.get('message', '')
        user_id = data.get('user_id', device_id)
        conversation_id = data.get('conversation_id', str(uuid.uuid4()))
        
        # 发送开始标记
        await self._send_ws_async(websocket, {
            'action': 'chat_stream_start',
            'conversation_id': conversation_id,
            'device_id': device_id
        })
        
        # 触发事件处理
        self._emit('chat_message', {
            'device_id': device_id,
            'user_id': user_id,
            'message': message,
            'conversation_id': conversation_id,
            'stream': True,
            'timestamp': time.time()
        })
        
        # 发送模拟响应（实际应通过 ThinkingEngine 处理）
        response_text = f"收到你的消息: {message[:100]}"
        for char in response_text:
            await self._send_ws_async(websocket, {
                'action': 'chat_stream_chunk',
                'conversation_id': conversation_id,
                'content': char,
                'device_id': device_id
            })
            await asyncio.sleep(0.02)
        
        # 发送结束标记
        await self._send_ws_async(websocket, {
            'action': 'chat_stream_end',
            'conversation_id': conversation_id,
            'device_id': device_id
        })

    async def _handle_shell_result_async(self, device_id: str, data: Dict, websocket):
        """异步处理来自设备端的 Shell 执行结果"""
        shell_id = data.get('shell_id')
        success = data.get('success', False)
        exit_code = data.get('exit_code', -1)
        stdout = data.get('stdout', '')
        stderr = data.get('stderr', '')
        error = data.get('error')
        compute_time = data.get('compute_time', 0.0)

        result = {
            'shell_id': shell_id,
            'device_id': device_id,
            'success': bool(success),
            'exit_code': int(exit_code),
            'stdout': stdout,
            'stderr': stderr,
            'error': error,
            'compute_time_ms': compute_time,
            'timestamp': time.time()
        }

        # 若有等待中的 Future，完成它
        future = None
        with self._shell_pending_lock:
            if shell_id and shell_id in self._shell_pending:
                future = self._shell_pending.pop(shell_id)

        if future is not None:
            try:
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                logger.error(f"Set shell result future failed: {e}")

        # 触发事件，方便非协程代码订阅
        self._emit('shell_result', result)
        logger.debug(f"Shell result: id={shell_id}, exit={exit_code}, success={success}")
    
    async def _send_ws_async(self, websocket, data: Dict):
        """异步发送 WebSocket 消息"""
        try:
            msg = json.dumps(data, ensure_ascii=False)
            await websocket.send(msg)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    async def _flush_pending_messages(self, device_id: str, websocket):
        """发送待处理的消息到设备"""
        with self._lock:
            messages = self._pending_messages.pop(device_id, [])
        
        for msg in messages:
            await self._send_ws_async(websocket, msg)
    
    def send_to_device(self, device_id: str, data: Dict) -> bool:
        """向指定设备发送消息（线程安全）"""
        with self._lock:
            if device_id not in self.devices:
                return False
            
            device = self.devices[device_id]
            if not device._ws or not device._loop:
                # 设备未连接，保存到待发送队列
                if device_id not in self._pending_messages:
                    self._pending_messages[device_id] = []
                self._pending_messages[device_id].append(data)
                return False
            
            ws = device._ws
            loop = device._loop
        
        # 在事件循环中发送
        asyncio.run_coroutine_threadsafe(
            self._send_ws_async(ws, data),
            loop
        )
        return True

    def get_shell_capable_devices(self) -> List[Dict]:
        """返回支持远程 Shell 执行（Shizuku 授權）的設備列表"""
        with self._lock:
            return [
                d.to_dict()
                for d in self.devices.values()
                if d.status in [DeviceStatus.ONLINE, DeviceStatus.IDLE, DeviceStatus.BUSY]
                and d.capabilities.can_shell_exec
            ]

    def send_shell_command(self, device_id: str, command: str,
                           timeout: int = 30, work_dir: Optional[str] = None,
                           env_vars: Optional[Dict[str, str]] = None,
                           wait_timeout: float = 120.0) -> Dict:
        """
        向指定設備發送 Shell 命令並阻塞等待結果。
        權限依賴：設備需已開啟 Shizuku 並授予 Aize Shell 級別權限。

        Args:
            device_id: 目標設備 ID
            command: Shell 命令（支持管道/重定向，將由 sh -c 執行）
            timeout: 設備端超時（秒）
            work_dir: 工作目錄；可為 None
            env_vars: 額外環境變數；可為 None
            wait_timeout: 本機等待響應最長秒數；0 表示只發送不等待

        Returns:
            {'success': bool, 'exit_code': int, 'stdout': str, 'stderr': str,
             'error': Optional[str], 'shell_id': str, 'device_id': str}
            若 wait_timeout=0，則僅返回 {'success': True, 'sent': True, 'shell_id': str}
        """
        if not command or not command.strip():
            return {
                'success': False, 'exit_code': -1, 'stdout': '',
                'stderr': '', 'error': 'Empty command'
            }

        # 校驗設備連線與能力
        with self._lock:
            device = self.devices.get(device_id)
            if device is None:
                return {
                    'success': False, 'exit_code': -1, 'stdout': '',
                    'stderr': '', 'error': f'Device not found: {device_id}'
                }
            if not device.capabilities.can_shell_exec:
                return {
                    'success': False, 'exit_code': -1, 'stdout': '',
                    'stderr': '',
                    'error': 'Device does not support remote shell. '
                             'Please enable Shizuku and grant permission on the device.'
                }
            if device.status not in [DeviceStatus.ONLINE, DeviceStatus.IDLE, DeviceStatus.BUSY] \
                    or device._ws is None or device._loop is None:
                return {
                    'success': False, 'exit_code': -1, 'stdout': '',
                    'stderr': '', 'error': f'Device {device_id} is offline'
                }
            device_loop = device._loop

        shell_id = 'sh_' + uuid.uuid4().hex[:16]
        msg = {
            'action': 'shell_exec',
            'shell_id': shell_id,
            'command': command,
            'timeout': int(timeout) if timeout and timeout > 0 else 30,
            'work_dir': work_dir,
            'env_vars': env_vars or {},
        }

        # 如果不需要等待結果，直接發送返回
        if wait_timeout == 0:
            ok = self.send_to_device(device_id, msg)
            return {'success': ok, 'sent': ok, 'shell_id': shell_id}

        # 建立 Future 並註冊到 shell_pending
        loop = device_loop if device_loop else asyncio.get_event_loop()
        future: 'asyncio.Future[Dict]' = loop.create_future()

        with self._shell_pending_lock:
            self._shell_pending[shell_id] = future

        # 設備斷線時的清理
        def _cleanup_pending():
            with self._shell_pending_lock:
                self._shell_pending.pop(shell_id, None)

        # 發送消息
        sent = self.send_to_device(device_id, msg)
        if not sent:
            _cleanup_pending()
            try:
                future.cancel()
            except Exception:
                pass
            return {
                'success': False, 'exit_code': -1, 'stdout': '',
                'stderr': '', 'error': 'Failed to send shell command to device'
            }

        # 阻塞等待結果（跨線程安全地等待 asyncio Future）
        result_holder: Dict = {}

        def _waiter():
            async def _wait():
                try:
                    return await asyncio.wait_for(future, timeout=max(0.1, wait_timeout))
                except asyncio.TimeoutError:
                    return {
                        'success': False, 'exit_code': -99,
                        'stdout': '', 'stderr': '',
                        'error': f'Timeout waiting for shell result ({wait_timeout}s)'
                    }
                except Exception as e:
                    return {
                        'success': False, 'exit_code': -1,
                        'stdout': '', 'stderr': '',
                        'error': f'Wait error: {e}'
                    }
                finally:
                    _cleanup_pending()

            try:
                result_holder['r'] = asyncio.run_coroutine_threadsafe(_wait(), loop).result()
            except Exception as e:
                result_holder['r'] = {
                    'success': False, 'exit_code': -1,
                    'stdout': '', 'stderr': '',
                    'error': f'Wait error: {e}'
                }
                _cleanup_pending()

        waiter_thread = threading.Thread(target=_waiter, daemon=True)
        waiter_thread.start()
        waiter_thread.join(timeout=max(1.0, wait_timeout + 5.0))

        if 'r' in result_holder:
            return result_holder['r']

        # 極端情況：線程未能完成
        _cleanup_pending()
        return {
            'success': False, 'exit_code': -1, 'stdout': '', 'stderr': '',
            'error': 'Unexpected timeout waiting for shell result'
        }
    
    def broadcast_to_all(self, data: Dict):
        """向所有在线设备广播消息"""
        with self._lock:
            online_devices = [
                (d.device_id, d._ws, d._loop)
                for d in self.devices.values()
                if d.status in [DeviceStatus.ONLINE, DeviceStatus.IDLE, DeviceStatus.BUSY]
                and d._ws is not None and d._loop is not None
            ]
        
        for device_id, ws, loop in online_devices:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._send_ws_async(ws, data),
                    loop
                )
            except Exception as e:
                logger.error(f"Broadcast error for {device_id}: {e}")
    
    def _handle_heartbeat(self, device_id: str, data: Dict):
        """处理设备心跳"""
        with self._lock:
            if device_id in self.devices:
                device = self.devices[device_id]
                device.last_heartbeat = time.time()
                if device.status == DeviceStatus.OFFLINE:
                    device.status = DeviceStatus.ONLINE
    
    def _handle_disconnect(self, device_id: str):
        """处理设备断开"""
        with self._lock:
            if device_id in self.devices:
                self.devices[device_id].status = DeviceStatus.OFFLINE
                self.devices[device_id]._ws = None
                self._emit('device_disconnected', self.devices[device_id].to_dict())
                logger.info(f"Device disconnected: {self.devices[device_id].device_name}")
                print(f"[IoT] 设备已断开: {self.devices[device_id].device_name}")
    
    def _heartbeat_loop(self):
        """心跳检测循环"""
        while self.is_running:
            time.sleep(self._config['heartbeat_interval'])
            self._check_device_health()
    
    def _check_device_health(self):
        """检查设备健康状态"""
        now = time.time()
        timeout = self._config['device_timeout']
        
        with self._lock:
            for device_id, device in self.devices.items():
                if device.status in [DeviceStatus.ONLINE, DeviceStatus.BUSY, DeviceStatus.IDLE]:
                    if now - device.last_heartbeat > timeout:
                        logger.warning(f"Device timeout: {device.device_name}")
                        device.status = DeviceStatus.DISCONNECTED
                        self._emit('device_disconnected', device.to_dict())
    
    def _disconnect_all_devices(self):
        """断开所有设备"""
        with self._lock:
            for device in self.devices.values():
                device.status = DeviceStatus.OFFLINE
                device._ws = None
        logger.info("All devices disconnected")
    
    def submit_task(self, task_type: str, payload: Dict, 
                   preferred_device_id: Optional[str] = None,
                   timeout: int = None) -> str:
        """提交计算任务"""
        task_id = str(uuid.uuid4())
        task = ComputeTask(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            status=TaskStatus.PENDING,
            created_at=time.time(),
            max_retries=self._config['max_retries']
        )
        
        with self._lock:
            self.tasks[task_id] = task
        
        # 尝试分配到设备
        if self._config['auto_assign']:
            device = self._find_best_device(task_type, preferred_device_id)
            if device:
                self._assign_task(task, device)
            else:
                logger.warning("No available device for task assignment")
        
        return task_id
    
    def _find_best_device(self, task_type: str, 
                          preferred_id: Optional[str] = None) -> Optional[DeviceInfo]:
        """查找最适合的设备"""
        candidates = []
        
        with self._lock:
            if preferred_id and preferred_id in self.devices:
                device = self.devices[preferred_id]
                if device.status in [DeviceStatus.ONLINE, DeviceStatus.IDLE]:
                    return device
            
            for device in self.devices.values():
                if device.status in [DeviceStatus.ONLINE, DeviceStatus.IDLE]:
                    caps = device.capabilities
                    if caps.can_compute:
                        if (not caps.supported_task_types or 
                            task_type in caps.supported_task_types):
                            candidates.append(device)
        
        if not candidates:
            return None
        
        # 优先选择 GPU 设备（如果配置允许）
        if self._config['prefer_gpu']:
            gpu_devices = [d for d in candidates if d.capabilities.gpu_available]
            if gpu_devices:
                candidates = gpu_devices
        
        # 选择最空闲的设备
        candidates.sort(key=lambda d: (
            d.status == DeviceStatus.IDLE,
            d.last_heartbeat
        ))
        
        return candidates[0] if candidates else None
    
    def _assign_task(self, task: ComputeTask, device: DeviceInfo):
        """分配任务到设备"""
        task.status = TaskStatus.ASSIGNED
        task.assigned_device_id = device.device_id
        task.started_at = time.time()
        device.status = DeviceStatus.BUSY
        
        # 发送任务到设备
        task_message = {
            'action': 'assign_task',
            'task_id': task.task_id,
            'task_type': task.task_type,
            'payload': task.payload,
            'timeout': self._config['task_timeout']
        }
        
        self.send_to_device(device.device_id, task_message)
        self._emit('task_assigned', task.to_dict(), device.to_dict())
        
        logger.info(f"Task {task.task_id[:8]} assigned to {device.device_name}")
        print(f"[IoT] 任务 {task.task_id[:8]} 已分配给 {device.device_name}")
    
    def send_chat_to_device(self, device_id: str, message: str, 
                           conversation_id: str = None) -> str:
        """向设备发送聊天消息"""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        data = {
            'action': 'chat_message',
            'message': message,
            'conversation_id': conversation_id,
            'timestamp': time.time()
        }
        
        self.send_to_device(device_id, data)
        return conversation_id
    
    def broadcast_chat(self, message: str, exclude_device_id: str = None):
        """向所有设备广播聊天消息"""
        data = {
            'action': 'chat_broadcast',
            'message': message,
            'timestamp': time.time()
        }
        
        with self._lock:
            targets = [
                d.device_id for d in self.devices.values()
                if d.status in [DeviceStatus.ONLINE, DeviceStatus.IDLE]
                and d.device_id != exclude_device_id
            ]
        
        for device_id in targets:
            self.send_to_device(device_id, data)
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """查询任务状态"""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                return task.to_dict()
        return None
    
    def get_result(self, task_id: str) -> Optional[Dict]:
        """获取任务结果"""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status == TaskStatus.COMPLETED:
                    return task.result
        return None
    
    def wait_for_result(self, task_id: str, timeout: float = 60) -> Optional[Dict]:
        """等待任务完成并获取结果"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_task_status(task_id)
            if status:
                task_status = status.get('status', '')
                if task_status == TaskStatus.COMPLETED.value:
                    return self.get_result(task_id)
                elif task_status == TaskStatus.FAILED.value:
                    logger.error(f"Task failed: {status.get('error_message')}")
                    return None
            time.sleep(0.5)
        
        logger.warning(f"Timeout waiting for task {task_id[:8]}")
        return None
    
    def get_device_list(self) -> List[Dict]:
        """获取所有设备列表"""
        with self._lock:
            return [device.to_dict() for device in self.devices.values()]
    
    def get_online_devices(self) -> List[Dict]:
        """获取在线设备列表"""
        with self._lock:
            return [
                device.to_dict() 
                for device in self.devices.values()
                if device.status in [DeviceStatus.ONLINE, DeviceStatus.IDLE, DeviceStatus.BUSY]
            ]
    
    def get_network_stats(self) -> Dict:
        """获取网络统计信息"""
        with self._lock:
            total_devices = len(self.devices)
            online_devices = len([
                d for d in self.devices.values()
                if d.status in [DeviceStatus.ONLINE, DeviceStatus.IDLE, DeviceStatus.BUSY]
            ])
            total_tasks = len(self.tasks)
            completed_tasks = len([
                t for t in self.tasks.values()
                if t.status == TaskStatus.COMPLETED
            ])
            failed_tasks = len([
                t for t in self.tasks.values()
                if t.status == TaskStatus.FAILED
            ])
            
            return {
                'total_devices': total_devices,
                'online_devices': online_devices,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'failed_tasks': failed_tasks,
                'is_running': self.is_running,
                'host': self.host,
                'port': self.port
            }
    
    def configure(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if key in self._config:
                self._config[key] = value
                logger.info(f"Config updated: {key} = {value}")


# 全局实例
_network_instance: Optional[IoTComputeNetwork] = None


def get_network(host: str = "0.0.0.0", port: int = 8765) -> IoTComputeNetwork:
    """获取全局 IoT 算力网络实例"""
    global _network_instance
    if _network_instance is None:
        _network_instance = IoTComputeNetwork(host, port)
    return _network_instance


def init_network(host: str = "0.0.0.0", port: int = 8765) -> IoTComputeNetwork:
    """初始化并启动 IoT 算力网络"""
    network = get_network(host, port)
    if not network.is_running:
        network.start()
    return network


def stop_network():
    """停止 IoT 算力网络"""
    global _network_instance
    if _network_instance and _network_instance.is_running:
        _network_instance.stop()
