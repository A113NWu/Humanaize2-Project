import asyncio
import json
import time
import uuid
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from enum import Enum

try:
    from .message_bus import message_bus, Message, MessageType, PlatformType
except ImportError:
    from message_bus import message_bus, Message, MessageType, PlatformType

class AdapterStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class AdapterConfig:
    enabled: bool = False
    token: str = ""
    api_url: str = ""
    webhook_url: str = ""
    polling_interval: int = 5
    timeout: int = 30

class BaseAdapter:
    def __init__(self, platform: PlatformType, config: AdapterConfig):
        self.platform = platform
        self.config = config
        self.status = AdapterStatus.DISCONNECTED
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def connect(self) -> Dict:
        self.status = AdapterStatus.CONNECTING
        try:
            await self._connect()
            self.status = AdapterStatus.CONNECTED
            message_bus.register_platform(self.platform, self)
            return {"status": "success", "message": f"{self.platform.value} adapter connected"}
        except Exception as e:
            self.status = AdapterStatus.ERROR
            return {"status": "error", "message": str(e)}
    
    async def disconnect(self) -> Dict:
        self._running = False
        if self._task:
            self._task.cancel()
        try:
            await self._disconnect()
            self.status = AdapterStatus.DISCONNECTED
            return {"status": "success", "message": f"{self.platform.value} adapter disconnected"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def _connect(self):
        pass
    
    async def _disconnect(self):
        pass
    
    async def _poll(self):
        pass
    
    def send_message(self, message: Message):
        pass
    
    def get_status(self) -> Dict:
        return {
            "platform": self.platform.value,
            "status": self.status.value,
            "enabled": self.config.enabled
        }
    
    def start(self):
        if not self.config.enabled:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll())

class DiscordAdapter(BaseAdapter):
    def __init__(self, config: AdapterConfig):
        super().__init__(PlatformType.DISCORD, config)
        self._client = None
        self._intents = None
    
    async def _connect(self):
        try:
            import discord
            from discord.ext import commands
            
            intents = discord.Intents.default()
            intents.message_content = True
            
            self._bot = commands.Bot(command_prefix='!', intents=intents)
            
            @self._bot.event
            async def on_ready():
                print(f"Discord bot connected as {self._bot.user}")
            
            @self._bot.event
            async def on_message(message):
                if message.author == self._bot.user:
                    return
                
                msg = Message(
                    id=str(message.id),
                    type=MessageType.TEXT,
                    platform=PlatformType.DISCORD,
                    sender=str(message.author),
                    content=message.content,
                    timestamp=message.created_at.timestamp(),
                    metadata={
                        "channel": str(message.channel),
                        "guild": str(message.guild) if message.guild else None
                    }
                )
                message_bus.publish("incoming", msg)
            
            await self._bot.start(self.config.token)
        except ImportError:
            raise Exception("discord.py not installed")
        except Exception as e:
            raise Exception(f"Discord connection failed: {e}")
    
    async def _disconnect(self):
        if self._bot:
            await self._bot.close()
    
    def send_message(self, message: Message):
        if self.status != AdapterStatus.CONNECTED or not self._bot:
            return
        
        asyncio.create_task(self._send_message_async(message))
    
    async def _send_message_async(self, message: Message):
        try:
            channel_id = message.metadata.get("channel_id")
            if channel_id:
                channel = self._bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(message.content)
        except Exception:
            pass

class TelegramAdapter(BaseAdapter):
    def __init__(self, config: AdapterConfig):
        super().__init__(PlatformType.TELEGRAM, config)
        self._last_update_id = 0
    
    async def _connect(self):
        pass
    
    async def _poll(self):
        if not self.config.token:
            return
        
        try:
            import requests
            
            while self._running:
                url = f"https://api.telegram.org/bot{self.config.token}/getUpdates"
                params = {"offset": self._last_update_id + 1, "timeout": self.config.timeout}
                
                response = requests.get(url, params=params)
                data = response.json()
                
                if data.get("ok"):
                    for update in data.get("result", []):
                        self._last_update_id = update.get("update_id", self._last_update_id)
                        
                        message_data = update.get("message")
                        if message_data:
                            msg = Message(
                                id=str(message_data.get("message_id")),
                                type=MessageType.TEXT,
                                platform=PlatformType.TELEGRAM,
                                sender=str(message_data.get("from", {}).get("id", "unknown")),
                                content=message_data.get("text", ""),
                                timestamp=message_data.get("date", time.time()),
                                metadata={
                                    "chat_id": message_data.get("chat", {}).get("id")
                                }
                            )
                            message_bus.publish("incoming", msg)
                
                await asyncio.sleep(self.config.polling_interval)
        except Exception:
            await asyncio.sleep(self.config.polling_interval)
    
    def send_message(self, message: Message):
        if not self.config.token:
            return
        
        try:
            import requests
            
            chat_id = message.metadata.get("chat_id")
            if chat_id:
                url = f"https://api.telegram.org/bot{self.config.token}/sendMessage"
                params = {
                    "chat_id": chat_id,
                    "text": message.content
                }
                requests.get(url, params=params)
        except Exception:
            pass

class WebhookAdapter(BaseAdapter):
    def __init__(self, config: AdapterConfig):
        super().__init__(PlatformType.WEBHOOK, config)
        self._server = None
    
    async def _connect(self):
        pass
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8080):
        try:
            from aiohttp import web
            
            async def handle_webhook(request):
                try:
                    data = await request.json()
                    
                    msg = Message(
                        id=str(uuid.uuid4()),
                        type=MessageType(data.get("type", "text")),
                        platform=PlatformType.WEBHOOK,
                        sender=data.get("sender", "unknown"),
                        content=data.get("content", ""),
                        timestamp=time.time(),
                        metadata=data.get("metadata"),
                        attachments=data.get("attachments")
                    )
                    message_bus.publish("incoming", msg)
                    
                    return web.Response(text=json.dumps({"status": "success"}))
                except Exception:
                    return web.Response(text=json.dumps({"status": "error"}), status=400)
            
            app = web.Application()
            app.add_routes([web.post('/webhook', handle_webhook)])
            
            runner = web.AppRunner(app)
            await runner.setup()
            self._server = web.TCPSite(runner, host, port)
            await self._server.start()
            
            self.status = AdapterStatus.CONNECTED
            return {"status": "success", "message": f"Webhook server started on {host}:{port}"}
        except ImportError:
            return {"status": "error", "message": "aiohttp not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def stop_server(self):
        if self._server:
            await self._server.stop()
    
    def send_message(self, message: Message):
        if not self.config.webhook_url:
            return
        
        try:
            import requests
            
            data = {
                "id": message.id,
                "type": message.type.value,
                "platform": message.platform.value,
                "sender": message.sender,
                "content": message.content,
                "timestamp": message.timestamp,
                "metadata": message.metadata,
                "attachments": message.attachments
            }
            
            requests.post(self.config.webhook_url, json=data)
        except Exception:
            pass

class PlatformAdapters:
    def __init__(self):
        self._adapters: Dict[PlatformType, BaseAdapter] = {}
        self._configs: Dict[PlatformType, AdapterConfig] = {}
        
        self._configs[PlatformType.DISCORD] = AdapterConfig()
        self._configs[PlatformType.TELEGRAM] = AdapterConfig()
        self._configs[PlatformType.WEBHOOK] = AdapterConfig()
    
    def configure(self, platform: PlatformType, **kwargs):
        if platform in self._configs:
            for key, value in kwargs.items():
                setattr(self._configs[platform], key, value)
    
    def get_adapter(self, platform: PlatformType) -> BaseAdapter:
        if platform not in self._adapters:
            if platform == PlatformType.DISCORD:
                self._adapters[platform] = DiscordAdapter(self._configs[platform])
            elif platform == PlatformType.TELEGRAM:
                self._adapters[platform] = TelegramAdapter(self._configs[platform])
            elif platform == PlatformType.WEBHOOK:
                self._adapters[platform] = WebhookAdapter(self._configs[platform])
        
        return self._adapters.get(platform)
    
    async def connect(self, platform: PlatformType) -> Dict:
        adapter = self.get_adapter(platform)
        if adapter:
            return await adapter.connect()
        return {"status": "error", "message": "Adapter not found"}
    
    async def disconnect(self, platform: PlatformType) -> Dict:
        adapter = self.get_adapter(platform)
        if adapter:
            return await adapter.disconnect()
        return {"status": "error", "message": "Adapter not found"}
    
    def send_message(self, platform: PlatformType, content: str, **kwargs):
        adapter = self.get_adapter(platform)
        if adapter:
            msg = Message(
                id=str(uuid.uuid4()),
                type=MessageType.TEXT,
                platform=platform,
                sender="aize",
                content=content,
                timestamp=time.time(),
                metadata=kwargs.get("metadata"),
                attachments=kwargs.get("attachments")
            )
            adapter.send_message(msg)
    
    def start_all(self):
        for platform in self._configs:
            if self._configs[platform].enabled:
                adapter = self.get_adapter(platform)
                if adapter:
                    adapter.start()
    
    def stop_all(self):
        for adapter in self._adapters.values():
            asyncio.create_task(adapter.disconnect())
    
    def get_status(self) -> Dict:
        return {
            platform.value: adapter.get_status() if adapter else {"status": "not_init"}
            for platform, adapter in self._adapters.items()
        }

platform_adapters = PlatformAdapters()

class PlatformAdaptersAPI:
    @staticmethod
    def configure(platform: str, **kwargs) -> Dict:
        try:
            platform_type = PlatformType(platform)
            platform_adapters.configure(platform_type, **kwargs)
            return {"status": "success", "message": f"{platform} configured"}
        except ValueError:
            return {"status": "error", "message": f"Unknown platform: {platform}"}
    
    @staticmethod
    def connect(platform: str) -> Dict:
        try:
            platform_type = PlatformType(platform)
            return asyncio.run(platform_adapters.connect(platform_type))
        except ValueError:
            return {"status": "error", "message": f"Unknown platform: {platform}"}
    
    @staticmethod
    def disconnect(platform: str) -> Dict:
        try:
            platform_type = PlatformType(platform)
            return asyncio.run(platform_adapters.disconnect(platform_type))
        except ValueError:
            return {"status": "error", "message": f"Unknown platform: {platform}"}
    
    @staticmethod
    def send_message(platform: str, content: str, **kwargs) -> Dict:
        try:
            platform_type = PlatformType(platform)
            platform_adapters.send_message(platform_type, content, **kwargs)
            return {"status": "success", "message": "Message sent"}
        except ValueError:
            return {"status": "error", "message": f"Unknown platform: {platform}"}
    
    @staticmethod
    def start_all() -> Dict:
        platform_adapters.start_all()
        return {"status": "success", "message": "All enabled adapters started"}
    
    @staticmethod
    def stop_all() -> Dict:
        platform_adapters.stop_all()
        return {"status": "success", "message": "All adapters stopped"}
    
    @staticmethod
    def get_status() -> Dict:
        return platform_adapters.get_status()