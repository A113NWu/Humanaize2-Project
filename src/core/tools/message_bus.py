import asyncio
import json
import time
import uuid
from typing import Dict, Optional, Any, List, Callable, Set
from dataclasses import dataclass
from enum import Enum
from threading import Lock

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    SYSTEM = "system"
    COMMAND = "command"
    EVENT = "event"
    RESPONSE = "response"

class PlatformType(Enum):
    LOCAL = "local"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    API = "api"

@dataclass
class Message:
    id: str
    type: MessageType
    platform: PlatformType
    sender: str
    content: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict]] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "platform": self.platform.value,
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata or {},
            "attachments": self.attachments or []
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Message":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MessageType(data.get("type", "text")),
            platform=PlatformType(data.get("platform", "local")),
            sender=data.get("sender", "unknown"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata"),
            attachments=data.get("attachments")
        )

class Subscription:
    def __init__(self, callback: Callable[[Message], None], filters: Optional[Dict] = None):
        self.callback = callback
        self.filters = filters or {}
        self.active = True

class MessageBus:
    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._processing_lock = Lock()
        self._message_history: List[Message] = []
        self._max_history_size = 1000
        self._platforms: Dict[PlatformType, Any] = {}
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
    
    def subscribe(self, topic: str, callback: Callable[[Message], None], filters: Optional[Dict] = None):
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        
        subscription = Subscription(callback, filters)
        self._subscriptions[topic].append(subscription)
        return subscription
    
    def unsubscribe(self, topic: str, callback: Callable[[Message], None]):
        if topic in self._subscriptions:
            self._subscriptions[topic] = [
                s for s in self._subscriptions[topic]
                if s.callback != callback
            ]
    
    def publish(self, topic: str, message: Message):
        self._message_queue.put_nowait((topic, message))
        
        self._message_history.append(message)
        if len(self._message_history) > self._max_history_size:
            self._message_history = self._message_history[-self._max_history_size:]
    
    async def _process_messages(self):
        while self._running:
            try:
                topic, message = await self._message_queue.get()
                
                if topic in self._subscriptions:
                    for subscription in self._subscriptions[topic]:
                        if not subscription.active:
                            continue
                        
                        if self._matches_filter(message, subscription.filters):
                            try:
                                if asyncio.iscoroutinefunction(subscription.callback):
                                    await subscription.callback(message)
                                else:
                                    subscription.callback(message)
                            except Exception:
                                pass
                
                self._message_queue.task_done()
            except Exception:
                await asyncio.sleep(0.1)
    
    def _matches_filter(self, message: Message, filters: Dict) -> bool:
        if "type" in filters and message.type != MessageType(filters["type"]):
            return False
        
        if "platform" in filters and message.platform != PlatformType(filters["platform"]):
            return False
        
        if "sender" in filters and message.sender != filters["sender"]:
            return False
        
        return True
    
    def register_platform(self, platform: PlatformType, handler: Any):
        self._platforms[platform] = handler
    
    def get_platform(self, platform: PlatformType) -> Optional[Any]:
        return self._platforms.get(platform)
    
    def start(self):
        if self._running:
            return
        
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._processing_task = loop.create_task(self._process_messages())
        except RuntimeError:
            self._processing_task = None
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            self._event_loop.create_task(self._process_messages())
    
    def stop(self):
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
    
    def get_history(self, limit: int = 100) -> List[Message]:
        return self._message_history[-limit:]
    
    def clear_history(self):
        self._message_history = []
    
    def get_status(self) -> Dict:
        return {
            "running": self._running,
            "queue_size": self._message_queue.qsize(),
            "history_size": len(self._message_history),
            "subscriptions": {
                topic: len(subscriptions)
                for topic, subscriptions in self._subscriptions.items()
            },
            "platforms": [p.value for p in self._platforms.keys()]
        }

message_bus = MessageBus()

class MessageBusAPI:
    @staticmethod
    def subscribe(topic: str, callback: Callable[[Message], None], filters: Optional[Dict] = None):
        return message_bus.subscribe(topic, callback, filters)
    
    @staticmethod
    def unsubscribe(topic: str, callback: Callable[[Message], None]):
        message_bus.unsubscribe(topic, callback)
    
    @staticmethod
    def publish(topic: str, message: Dict):
        msg = Message.from_dict(message)
        message_bus.publish(topic, msg)
    
    @staticmethod
    def send_message(platform: str, content: str, **kwargs):
        message = Message(
            id=str(uuid.uuid4()),
            type=MessageType.TEXT,
            platform=PlatformType(platform),
            sender="aize",
            content=content,
            timestamp=time.time(),
            metadata=kwargs.get("metadata"),
            attachments=kwargs.get("attachments")
        )
        
        handler = message_bus.get_platform(PlatformType(platform))
        if handler:
            try:
                handler.send_message(message)
            except Exception:
                pass
        
        message_bus.publish("outgoing", message)
    
    @staticmethod
    def start():
        message_bus.start()
    
    @staticmethod
    def stop():
        message_bus.stop()
    
    @staticmethod
    def get_status() -> Dict:
        return message_bus.get_status()
    
    @staticmethod
    def get_history(limit: int = 100) -> List[Dict]:
        return [msg.to_dict() for msg in message_bus.get_history(limit)]