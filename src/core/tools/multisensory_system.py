import asyncio
import time
import base64
import json
from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

class SensoryType(Enum):
    VISION = "vision"
    HEARING = "hearing"
    SPEECH = "speech"
    TOUCH = "touch"
    ENVIRONMENT = "environment"
    EMOTION = "emotion"

class SensoryStatus(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

@dataclass
class SensoryData:
    type: SensoryType
    data: Any
    confidence: float
    timestamp: float
    source: str
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "data": self.data,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "source": self.source,
            "metadata": self.metadata or {}
        }

@dataclass
class Perception:
    id: str
    sensory_data: List[SensoryData]
    interpretation: str
    timestamp: float
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "sensory_data": [sd.to_dict() for sd in self.sensory_data],
            "interpretation": self.interpretation,
            "timestamp": self.timestamp
        }

class VisionProcessor:
    def __init__(self):
        self.status = SensoryStatus.IDLE
        self._available = False
        
        try:
            self._check_vision_available()
        except Exception:
            pass
    
    def _check_vision_available(self):
        try:
            from .vision import Vision
            self._vision = Vision()
            self._available = True
            self.status = SensoryStatus.READY
        except ImportError:
            self._available = False
    
    def is_available(self) -> bool:
        return self._available
    
    def process_image(self, image_path: str) -> Dict:
        if not self._available:
            return {
                "status": "error",
                "message": "Vision module not available"
            }
        
        self.status = SensoryStatus.PROCESSING
        
        try:
            result = self._vision.analyze_image(image_path)
            self.status = SensoryStatus.READY
            
            return {
                "status": "success",
                "description": result.get("description", ""),
                "objects": result.get("objects", []),
                "confidence": result.get("confidence", 0.5)
            }
        except Exception as e:
            self.status = SensoryStatus.ERROR
            return {
                "status": "error",
                "message": str(e)
            }
    
    def process_image_base64(self, base64_data: str) -> Dict:
        if not self._available:
            return {
                "status": "error",
                "message": "Vision module not available"
            }
        
        self.status = SensoryStatus.PROCESSING
        
        try:
            result = self._vision.analyze_base64(base64_data)
            self.status = SensoryStatus.READY
            
            return {
                "status": "success",
                "description": result.get("description", ""),
                "objects": result.get("objects", []),
                "confidence": result.get("confidence", 0.5)
            }
        except Exception as e:
            self.status = SensoryStatus.ERROR
            return {
                "status": "error",
                "message": str(e)
            }

class HearingProcessor:
    def __init__(self):
        self.status = SensoryStatus.IDLE
        self._available = False
        
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._available = True
            self.status = SensoryStatus.READY
        except ImportError:
            self._available = False
    
    def is_available(self) -> bool:
        return self._available
    
    def listen(self, duration: int = 5) -> Dict:
        if not self._available:
            return {
                "status": "error",
                "message": "Speech recognition not available"
            }
        
        self.status = SensoryStatus.PROCESSING
        
        try:
            import speech_recognition as sr
            
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source)
                audio = self._recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
            
            try:
                text = self._recognizer.recognize_google(audio, language='zh-CN')
                self.status = SensoryStatus.READY
                return {
                    "status": "success",
                    "text": text,
                    "confidence": 0.9
                }
            except sr.UnknownValueError:
                self.status = SensoryStatus.READY
                return {
                    "status": "success",
                    "text": "",
                    "confidence": 0.0,
                    "message": "Could not understand audio"
                }
            except sr.RequestError as e:
                self.status = SensoryStatus.ERROR
                return {
                    "status": "error",
                    "message": f"Speech recognition service error: {e}"
                }
        except Exception as e:
            self.status = SensoryStatus.ERROR
            return {
                "status": "error",
                "message": str(e)
            }
    
    def process_audio_file(self, audio_path: str) -> Dict:
        if not self._available:
            return {
                "status": "error",
                "message": "Speech recognition not available"
            }
        
        self.status = SensoryStatus.PROCESSING
        
        try:
            import speech_recognition as sr
            
            with sr.AudioFile(audio_path) as source:
                audio = self._recognizer.record(source)
            
            try:
                text = self._recognizer.recognize_google(audio, language='zh-CN')
                self.status = SensoryStatus.READY
                return {
                    "status": "success",
                    "text": text,
                    "confidence": 0.9
                }
            except sr.UnknownValueError:
                self.status = SensoryStatus.READY
                return {
                    "status": "success",
                    "text": "",
                    "confidence": 0.0,
                    "message": "Could not understand audio"
                }
            except sr.RequestError as e:
                self.status = SensoryStatus.ERROR
                return {
                    "status": "error",
                    "message": f"Speech recognition service error: {e}"
                }
        except Exception as e:
            self.status = SensoryStatus.ERROR
            return {
                "status": "error",
                "message": str(e)
            }

class SpeechProcessor:
    def __init__(self):
        self.status = SensoryStatus.IDLE
        self._available = False
        
        try:
            from ..voice.voice_service import VoiceService
            self._voice_service = VoiceService()
            self._available = True
            self.status = SensoryStatus.READY
        except ImportError:
            self._available = False
    
    def is_available(self) -> bool:
        return self._available
    
    def speak(self, text: str, **kwargs) -> Dict:
        if not self._available:
            return {
                "status": "error",
                "message": "Voice service not available"
            }
        
        self.status = SensoryStatus.PROCESSING
        
        try:
            result = self._voice_service.speak(text, **kwargs)
            self.status = SensoryStatus.READY
            return result
        except Exception as e:
            self.status = SensoryStatus.ERROR
            return {
                "status": "error",
                "message": str(e)
            }

class EnvironmentProcessor:
    def __init__(self):
        self.status = SensoryStatus.READY
        self._available = True
    
    def is_available(self) -> bool:
        return self._available
    
    def get_system_info(self) -> Dict:
        try:
            import psutil
            import os
            
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            return {
                "status": "success",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available": memory.available // (1024 * 1024),
                "disk_percent": disk.percent,
                "disk_available": disk.free // (1024 * 1024 * 1024),
                "network_sent": network.bytes_sent // (1024 * 1024),
                "network_recv": network.bytes_recv // (1024 * 1024),
                "process_count": len(psutil.pids()),
                "uptime": int(time.time() - psutil.boot_time())
            }
        except ImportError:
            return {
                "status": "success",
                "message": "psutil not available, basic info only",
                "uptime": int(time.time())
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_network_status(self) -> Dict:
        try:
            import socket
            
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            
            return {
                "status": "success",
                "hostname": hostname,
                "ip_address": ip_address,
                "connected": True
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "connected": False
            }

class MultisensorySystem:
    def __init__(self):
        self.vision = VisionProcessor()
        self.hearing = HearingProcessor()
        self.speech = SpeechProcessor()
        self.environment = EnvironmentProcessor()
        
        self._perception_history: List[Perception] = []
        self._max_history = 100
        self._callbacks: List[Callable[[Perception], None]] = []
        self._running = False
        
        try:
            from .emotion_engine import emotion_engine
            self._emotion_engine = emotion_engine
        except ImportError:
            self._emotion_engine = None
    
    def add_callback(self, callback: Callable[[Perception], None]):
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[Perception], None]):
        self._callbacks = [c for c in self._callbacks if c != callback]
    
    def perceive(self, sensory_type: SensoryType, data: Any, source: str = "unknown") -> Optional[Perception]:
        sensory_data = SensoryData(
            type=sensory_type,
            data=data,
            confidence=0.0,
            timestamp=time.time(),
            source=source
        )
        
        interpretation = self._interpret_sensory_data(sensory_data)
        
        if interpretation:
            sensory_data.confidence = self._calculate_confidence(sensory_data, interpretation)
            
            perception = Perception(
                id=str(time.time()),
                sensory_data=[sensory_data],
                interpretation=interpretation,
                timestamp=time.time()
            )
            
            self._perception_history.append(perception)
            if len(self._perception_history) > self._max_history:
                self._perception_history = self._perception_history[-self._max_history:]
            
            self._notify_callbacks(perception)
            
            if self._emotion_engine and sensory_type == SensoryType.HEARING:
                try:
                    from .sentiment_analyzer import sentiment_analyzer
                    result = sentiment_analyzer.analyze(data)
                    if result:
                        self._emotion_engine.add_emotion(
                            result["emotion"], 
                            result["intensity"],
                            source="user"
                        )
                except Exception:
                    pass
            
            return perception
        
        return None
    
    def _interpret_sensory_data(self, sensory_data: SensoryData) -> Optional[str]:
        if sensory_data.type == SensoryType.VISION:
            if isinstance(sensory_data.data, dict):
                return sensory_data.data.get("description", "")
            return str(sensory_data.data)
        
        elif sensory_data.type == SensoryType.HEARING:
            return str(sensory_data.data)
        
        elif sensory_data.type == SensoryType.ENVIRONMENT:
            if isinstance(sensory_data.data, dict):
                cpu = sensory_data.data.get("cpu_percent", 0)
                memory = sensory_data.data.get("memory_percent", 0)
                if cpu > 80 or memory > 80:
                    return f"系统负载较高，CPU: {cpu}%, 内存: {memory}%"
                return f"系统状态正常，CPU: {cpu}%, 内存: {memory}%"
            return str(sensory_data.data)
        
        elif sensory_data.type == SensoryType.EMOTION:
            if isinstance(sensory_data.data, dict):
                emotion = sensory_data.data.get("emotion", "unknown")
                intensity = sensory_data.data.get("intensity", 0)
                return f"检测到情绪: {emotion} (强度: {intensity})"
            return str(sensory_data.data)
        
        return None
    
    def _calculate_confidence(self, sensory_data: SensoryData, interpretation: str) -> float:
        if sensory_data.type == SensoryType.VISION:
            if isinstance(sensory_data.data, dict):
                return sensory_data.data.get("confidence", 0.7)
            return 0.6
        
        elif sensory_data.type == SensoryType.HEARING:
            if isinstance(sensory_data.data, dict):
                return sensory_data.data.get("confidence", 0.8)
            return 0.7
        
        elif sensory_data.type == SensoryType.ENVIRONMENT:
            return 0.95
        
        elif sensory_data.type == SensoryType.EMOTION:
            if isinstance(sensory_data.data, dict):
                return sensory_data.data.get("intensity", 0.5)
            return 0.5
        
        return 0.5
    
    def _notify_callbacks(self, perception: Perception):
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(perception))
                else:
                    callback(perception)
            except Exception:
                pass
    
    def get_status(self) -> Dict:
        return {
            "vision": {
                "available": self.vision.is_available(),
                "status": self.vision.status.value
            },
            "hearing": {
                "available": self.hearing.is_available(),
                "status": self.hearing.status.value
            },
            "speech": {
                "available": self.speech.is_available(),
                "status": self.speech.status.value
            },
            "environment": {
                "available": self.environment.is_available(),
                "status": self.environment.status.value
            },
            "perception_history_size": len(self._perception_history)
        }
    
    def get_perception_history(self, limit: int = 20) -> List[Dict]:
        return [p.to_dict() for p in self._perception_history[-limit:]]
    
    def start(self):
        self._running = True
    
    def stop(self):
        self._running = False

multisensory_system = MultisensorySystem()

class MultisensoryAPI:
    @staticmethod
    def perceive(sensory_type: str, data: Any, source: str = "unknown") -> Dict:
        perception = multisensory_system.perceive(SensoryType(sensory_type), data, source)
        if perception:
            return perception.to_dict()
        return {"status": "error", "message": "Failed to process sensory data"}
    
    @staticmethod
    def vision_analyze(image_path: str) -> Dict:
        return multisensory_system.vision.process_image(image_path)
    
    @staticmethod
    def vision_analyze_base64(base64_data: str) -> Dict:
        return multisensory_system.vision.process_image_base64(base64_data)
    
    @staticmethod
    def hearing_listen(duration: int = 5) -> Dict:
        return multisensory_system.hearing.listen(duration)
    
    @staticmethod
    def hearing_process(audio_path: str) -> Dict:
        return multisensory_system.hearing.process_audio_file(audio_path)
    
    @staticmethod
    def speech_speak(text: str, **kwargs) -> Dict:
        return multisensory_system.speech.speak(text, **kwargs)
    
    @staticmethod
    def environment_info() -> Dict:
        return multisensory_system.environment.get_system_info()
    
    @staticmethod
    def network_status() -> Dict:
        return multisensory_system.environment.get_network_status()
    
    @staticmethod
    def get_status() -> Dict:
        return multisensory_system.get_status()
    
    @staticmethod
    def get_history(limit: int = 20) -> List[Dict]:
        return multisensory_system.get_perception_history(limit)
    
    @staticmethod
    def start():
        multisensory_system.start()
    
    @staticmethod
    def stop():
        multisensory_system.stop()