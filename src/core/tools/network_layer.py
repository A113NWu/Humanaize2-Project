import asyncio
import aiohttp
import json
import ssl
import time
import hashlib
import hmac
from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

class NetworkProtocol(Enum):
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "websocket"
    WEBSOCKETS = "wss"

class NetworkStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"

@dataclass
class NetworkConfig:
    protocol: NetworkProtocol = NetworkProtocol.HTTPS
    host: str = "localhost"
    port: int = 443
    api_key: str = ""
    secret_key: str = ""
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 2.0
    verify_ssl: bool = True
    proxy_url: Optional[str] = None

@dataclass
class NetworkRequest:
    method: str
    url: str
    headers: Optional[Dict[str, str]] = None
    data: Optional[Any] = None
    params: Optional[Dict[str, str]] = None
    timeout: int = 30

@dataclass
class NetworkResponse:
    status_code: int
    data: Any
    headers: Optional[Dict[str, str]] = None
    error: Optional[str] = None
    latency: float = 0.0

class NetworkLayer:
    def __init__(self, config: Optional[NetworkConfig] = None):
        self.config = config or NetworkConfig()
        self.status = NetworkStatus.DISCONNECTED
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._reconnect_count = 0
        self._last_connect_time = 0
        self._callbacks: List[Callable[[NetworkStatus], None]] = []
        
        self._ssl_context = None
        if self.config.verify_ssl:
            self._ssl_context = ssl.create_default_context()
    
    def add_status_callback(self, callback: Callable[[NetworkStatus], None]):
        self._callbacks.append(callback)
    
    def _notify_status(self, new_status: NetworkStatus):
        self.status = new_status
        for callback in self._callbacks:
            try:
                callback(new_status)
            except Exception:
                pass
    
    async def connect(self):
        if self.status == NetworkStatus.CONNECTED:
            return {"status": "success", "message": "Already connected"}
        
        self._notify_status(NetworkStatus.CONNECTING)
        
        try:
            connector_args = {}
            if self.config.proxy_url:
                connector_args["proxy"] = self.config.proxy_url
            
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                connector=aiohttp.TCPConnector(ssl=self._ssl_context, **connector_args)
            )
            
            await self._test_connection()
            
            self._notify_status(NetworkStatus.CONNECTED)
            self._reconnect_count = 0
            self._last_connect_time = time.time()
            
            return {"status": "success", "message": "Network layer connected"}
        
        except Exception as e:
            self._notify_status(NetworkStatus.DISCONNECTED)
            return {"status": "error", "message": f"Failed to connect: {str(e)}"}
    
    async def disconnect(self):
        if self._session:
            await self._session.close()
            self._session = None
        
        self._notify_status(NetworkStatus.DISCONNECTED)
        return {"status": "success", "message": "Network layer disconnected"}
    
    async def _test_connection(self):
        test_url = f"{self.config.protocol.value}://{self.config.host}:{self.config.port}/"
        try:
            async with self._session.get(test_url, timeout=5):
                pass
        except Exception:
            pass
    
    def _sign_request(self, request: NetworkRequest) -> Dict[str, str]:
        headers = request.headers.copy() if request.headers else {}
        
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        
        if self.config.secret_key:
            timestamp = str(int(time.time()))
            signature_data = f"{timestamp}:{request.method}:{request.url}"
            if request.data:
                signature_data += f":{json.dumps(request.data)}"
            
            signature = hmac.new(
                self.config.secret_key.encode(),
                signature_data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            headers["X-Timestamp"] = timestamp
            headers["X-Signature"] = signature
        
        return headers
    
    async def request(self, request: NetworkRequest) -> NetworkResponse:
        if self.status != NetworkStatus.CONNECTED and self.status != NetworkStatus.CONNECTING:
            await self.connect()
        
        if self.status != NetworkStatus.CONNECTED:
            return NetworkResponse(
                status_code=0,
                data=None,
                error="Network layer not connected"
            )
        
        start_time = time.time()
        
        for attempt in range(self.config.retry_count):
            try:
                headers = self._sign_request(request)
                
                async with self._lock:
                    async with self._session.request(
                        method=request.method,
                        url=request.url,
                        headers=headers,
                        json=request.data,
                        params=request.params,
                        timeout=request.timeout
                    ) as response:
                        try:
                            data = await response.json()
                        except Exception:
                            data = await response.text()
                        
                        latency = time.time() - start_time
                        
                        return NetworkResponse(
                            status_code=response.status,
                            data=data,
                            headers=dict(response.headers),
                            latency=latency
                        )
            
            except Exception as e:
                if attempt < self.config.retry_count - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    latency = time.time() - start_time
                    return NetworkResponse(
                        status_code=0,
                        data=None,
                        error=str(e),
                        latency=latency
                    )
    
    async def get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> NetworkResponse:
        request = NetworkRequest(method="GET", url=url, params=params, headers=headers)
        return await self.request(request)
    
    async def post(self, url: str, data: Optional[Any] = None, headers: Optional[Dict] = None) -> NetworkResponse:
        request = NetworkRequest(method="POST", url=url, data=data, headers=headers)
        return await self.request(request)
    
    async def put(self, url: str, data: Optional[Any] = None, headers: Optional[Dict] = None) -> NetworkResponse:
        request = NetworkRequest(method="PUT", url=url, data=data, headers=headers)
        return await self.request(request)
    
    async def delete(self, url: str, headers: Optional[Dict] = None) -> NetworkResponse:
        request = NetworkRequest(method="DELETE", url=url, headers=headers)
        return await self.request(request)
    
    def is_connected(self) -> bool:
        return self.status == NetworkStatus.CONNECTED
    
    def get_status(self) -> Dict:
        return {
            "status": self.status.value,
            "reconnect_count": self._reconnect_count,
            "last_connect_time": self._last_connect_time,
            "config": {
                "protocol": self.config.protocol.value,
                "host": self.config.host,
                "port": self.config.port,
                "timeout": self.config.timeout,
                "verify_ssl": self.config.verify_ssl
            }
        }

network_layer = NetworkLayer()

class NetworkLayerAPI:
    @staticmethod
    def connect(config: Optional[Dict] = None) -> Dict:
        if config:
            network_layer.config = NetworkConfig(**config)
        return asyncio.run(network_layer.connect())
    
    @staticmethod
    def disconnect() -> Dict:
        return asyncio.run(network_layer.disconnect())
    
    @staticmethod
    def request(method: str, url: str, **kwargs) -> Dict:
        request = NetworkRequest(method=method, url=url, **kwargs)
        response = asyncio.run(network_layer.request(request))
        return {
            "status": "success" if response.error is None else "error",
            "status_code": response.status_code,
            "data": response.data,
            "error": response.error,
            "latency": response.latency
        }
    
    @staticmethod
    def get(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        return NetworkLayerAPI.request("GET", url, params=params, headers=headers)
    
    @staticmethod
    def post(url: str, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        return NetworkLayerAPI.request("POST", url, data=data, headers=headers)
    
    @staticmethod
    def get_status() -> Dict:
        return network_layer.get_status()
    
    @staticmethod
    def is_connected() -> bool:
        return network_layer.is_connected()