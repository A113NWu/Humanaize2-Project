"""
QQ聊天技能
让Aize可以通过QQ与用户聊天
支持图片和语音消息识别
"""

import json
import requests
import threading
import time
import os
import subprocess
import socket
import re
import base64
import tempfile
from typing import Dict, Any, Optional, Callable

try:
    from memory import add, save_memory
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

try:
    import importlib
    vision_module = importlib.import_module('src.ai_selfdevelop.skills.vision')
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

try:
    import importlib
    audio_module = importlib.import_module('src.ai_selfdevelop.skills.audio')
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

def _split_message(message: str) -> list:
    """
    将消息按句子分割
    
    规则：
    1. 优先按句号。、感叹号！、问号？、省略号……分割
    2. 如果单句超过80字符，按逗号，分割
    3. 确保每个句子不少于10字符（除非是最后一句）
    4. 保留原有的标点符号
    
    Args:
        message: 原始消息
        
    Returns:
        分割后的句子列表
    """
    sentences = []
    message = message.strip()
    
    if not message:
        return []
    
    main_separators = r'([。！？…….!?])'
    parts = re.split(main_separators, message)
    
    combined_parts = []
    for i in range(0, len(parts), 2):
        text = parts[i].strip()
        if i + 1 < len(parts):
            text += parts[i + 1]
        if text:
            combined_parts.append(text)
    
    for part in combined_parts:
        if len(part) <= 80:
            sentences.append(part)
        else:
            sub_segments = []
            current_segment = ""
            
            comma_parts = part.split('，')
            for j, cp in enumerate(comma_parts):
                if j > 0:
                    cp = '，' + cp
                
                if len(current_segment) + len(cp) <= 80:
                    current_segment += cp
                else:
                    if current_segment:
                        sub_segments.append(current_segment)
                    current_segment = cp
            
            if current_segment:
                sub_segments.append(current_segment)
            
            sentences.extend(sub_segments)
    
    return [s.strip() for s in sentences if s.strip()]

class QQChatSkill:
    def __init__(self):
        self.config = self._load_config()
        self.messages = []
        self.running = False
        self._lock = threading.Lock()
        self._auth_token = self.config.get('token', '')
        self._listener_thread = None
        self._last_message_id = 0
        self._message_handler = None
        self._thinking_engine = None
        self._ui_callback = None
        self._memory = None
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'host': '127.0.0.1',
            'port': 6185,
            'qq': None,
            'enabled': False,
            'mock_mode': True,
            'protocol': 'astrbot',
            'token': '',
            'username': 'astrbot',
            'password': '',
            'astrbot_path': os.path.join(os.path.dirname(__file__), 'astrbot'),
            'auto_reply': True,
            'poll_interval': 2
        }
    
    def _is_port_in_use(self, port: int) -> bool:
        """检查端口是否被占用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('127.0.0.1', port)) == 0
        except:
            return False
    
    def _start_astrbot(self) -> bool:
        """启动Astrbot服务"""
        try:
            astrbot_path = self.config.get('astrbot_path', os.path.join(os.path.dirname(__file__), 'astrbot'))
            
            if not os.path.exists(astrbot_path):
                return False
            
            main_py = os.path.join(astrbot_path, 'main.py')
            if not os.path.exists(main_py):
                return False
            
            subprocess.Popen(
                [sys.executable, main_py],
                cwd=astrbot_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            for _ in range(60):
                time.sleep(1)
                if self._is_port_in_use(self.config['port']):
                    return True
            
            return False
        except Exception as e:
            print(f"Failed to start astrbot: {e}")
            return False
    
    def _save_config(self):
        """保存配置文件"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except:
            pass
    
    def _get_auth_headers(self) -> Dict:
        """获取认证头"""
        if self._auth_token:
            return {'Authorization': f'Bearer {self._auth_token}'}
        return {}
    
    def _login_astrbot(self) -> bool:
        """登录Astrbot获取token"""
        try:
            url = f"http://{self.config['host']}:{self.config['port']}/api/v1/auth/login"
            payload = {
                'username': self.config.get('username', 'astrbot'),
                'password': self.config.get('password', '')
            }
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get('status') == 'ok' and result.get('data', {}).get('token'):
                self._auth_token = result['data']['token']
                self.config['token'] = self._auth_token
                self._save_config()
                return True
            return False
        except:
            return False
    
    def configure(self, params: Dict) -> Dict:
        """配置QQ机器人"""
        if 'host' in params:
            self.config['host'] = params['host']
        if 'port' in params:
            self.config['port'] = params['port']
        if 'qq' in params:
            self.config['qq'] = params['qq']
        if 'mock_mode' in params:
            self.config['mock_mode'] = params['mock_mode']
        if 'enabled' in params:
            self.config['enabled'] = params['enabled']
        if 'protocol' in params:
            self.config['protocol'] = params['protocol']
        if 'token' in params:
            self.config['token'] = params['token']
            self._auth_token = params['token']
        if 'username' in params:
            self.config['username'] = params['username']
        if 'password' in params:
            self.config['password'] = params['password']
        if 'auto_reply' in params:
            self.config['auto_reply'] = params['auto_reply']
        if 'poll_interval' in params:
            self.config['poll_interval'] = params['poll_interval']
        
        self._save_config()
        
        if self.config['enabled'] and not self.config['mock_mode']:
            if self._test_connection():
                return {"success": True, "message": "配置成功，连接测试通过"}
            else:
                return {"success": False, "message": "配置成功，但无法连接到QQ机器人后端"}
        
        return {"success": True, "message": "配置成功"}
    
    def _test_connection(self) -> bool:
        """测试连接"""
        try:
            protocol = self.config.get('protocol', 'astrbot')
            
            if protocol == 'astrbot':
                if not self._is_port_in_use(self.config['port']):
                    self._start_astrbot()
                
                if not self._auth_token:
                    if not self._login_astrbot():
                        return False
                
                url = f"http://{self.config['host']}:{self.config['port']}/api/v1/auth/setup-status"
                headers = self._get_auth_headers()
                response = requests.get(url, headers=headers, timeout=5)
                return response.status_code == 200
            else:
                url = f"http://{self.config['host']}:{self.config['port']}/"
                response = requests.get(url, timeout=5)
                return response.status_code == 200
        except:
            return False
    
    def send_single_message(self, to_qq: int, message: str, message_type: str = 'private') -> bool:
        """发送单条消息（内部使用，用于流式发送）"""
        if not self.config['enabled'] or self.config['mock_mode']:
            return True
        
        try:
            protocol = self.config.get('protocol', 'astrbot')
            
            if protocol == 'milky':
                url = f"http://{self.config['host']}:{self.config['port']}/send_{message_type}_message"
                payload = {
                    'target': to_qq,
                    'message': [{
                        'type': 'text',
                        'text': message
                    }]
                }
                response = requests.post(url, json=payload, timeout=10)
                return response.json().get('status') == 'ok'
            
            elif protocol == 'astrbot':
                if not self._auth_token:
                    if not self._login_astrbot():
                        return False
                
                url = f"http://{self.config['host']}:{self.config['port']}/api/v1/im/messages"
                umo_type = "FriendMessage" if message_type == 'private' else "GroupMessage"
                payload = {
                    'umo': f"qq:{umo_type}:{to_qq}",
                    'message': message
                }
                headers = self._get_auth_headers()
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    success = response.json().get('status') == 'ok'
                    if success and self._ui_callback:
                        try:
                            self._ui_callback({
                                'type': 'sent',
                                'from': 'Aize',
                                'target_id': to_qq,
                                'message_type': message_type,
                                'message': message,
                                'timestamp': time.time()
                            })
                        except Exception:
                            pass
                    return success
                return False
            
            else:
                url = f"http://{self.config['host']}:{self.config['port']}/send_{message_type}_msg"
                params = {
                    'user_id' if message_type == 'private' else 'group_id': to_qq,
                    'message': message
                }
                response = requests.get(url, params=params, timeout=10)
                return response.json().get('status') == 'ok'
        
        except Exception:
            return False
    
    def send_private_message(self, to_qq: int, message: str) -> Dict:
        """发送私聊消息（自动逐句发送）"""
        if not self.config['enabled']:
            return {"success": False, "message": "QQ聊天功能未启用"}
        
        sentences = _split_message(message)
        
        if not sentences:
            return {"success": False, "message": "消息内容为空"}
        
        success_count = 0
        failed_count = 0
        
        for i, sentence in enumerate(sentences):
            if self.config['mock_mode']:
                with self._lock:
                    self.messages.append({
                        'type': 'sent',
                        'to': to_qq,
                        'message': sentence,
                        'timestamp': time.time()
                    })
                success_count += 1
            else:
                if self.send_single_message(to_qq, sentence, 'private'):
                    success_count += 1
                else:
                    failed_count += 1
            
            if i < len(sentences) - 1:
                time.sleep(0.3)
        
        if failed_count == 0:
            return {"success": True, "message": f"消息发送成功，共发送 {success_count} 句"}
        elif success_count > 0:
            return {"success": True, "message": f"部分消息发送成功，成功 {success_count} 句，失败 {failed_count} 句"}
        else:
            return {"success": False, "message": f"消息发送失败，共 {failed_count} 句"}
    
    def send_group_message(self, group_id: int, message: str) -> Dict:
        """发送群消息（自动逐句发送）"""
        if not self.config['enabled']:
            return {"success": False, "message": "QQ聊天功能未启用"}
        
        sentences = _split_message(message)
        
        if not sentences:
            return {"success": False, "message": "消息内容为空"}
        
        success_count = 0
        failed_count = 0
        
        for i, sentence in enumerate(sentences):
            if self.config['mock_mode']:
                with self._lock:
                    self.messages.append({
                        'type': 'sent_group',
                        'group_id': group_id,
                        'message': sentence,
                        'timestamp': time.time()
                    })
                success_count += 1
            else:
                if self.send_single_message(group_id, sentence, 'group'):
                    success_count += 1
                else:
                    failed_count += 1
            
            if i < len(sentences) - 1:
                time.sleep(0.3)
        
        if failed_count == 0:
            return {"success": True, "message": f"群消息发送成功，共发送 {success_count} 句"}
        elif success_count > 0:
            return {"success": True, "message": f"部分群消息发送成功，成功 {success_count} 句，失败 {failed_count} 句"}
        else:
            return {"success": False, "message": f"群消息发送失败，共 {failed_count} 句"}
    
    def set_message_handler(self, handler: Callable):
        """设置消息处理回调函数"""
        self._message_handler = handler
    
    def set_thinking_engine(self, engine):
        """设置ThinkingEngine引用，用于流式发送"""
        self._thinking_engine = engine
        if engine:
            engine.register_stream_callback(self._on_stream_sentence)
    
    def set_memory(self, memory):
        """设置memory引用，用于构建对话上下文"""
        self._memory = memory
    
    def set_ui_callback(self, callback: Callable):
        """设置UI回调函数，用于在UI中显示收到的消息"""
        self._ui_callback = callback
    
    def _on_stream_sentence(self, sentence: str, target_info: Dict = None):
        """流式句子回调 - 将AI生成的句子实时发送到QQ"""
        if target_info:
            message_type = target_info.get('type', 'private')
            target_id = target_info.get('id')
            if target_id:
                self.send_single_message(target_id, sentence, message_type)
    
    def _download_media(self, url: str) -> Optional[str]:
        """下载媒体文件"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                ext = os.path.splitext(url)[1] or '.dat'
                temp_file = os.path.join(tempfile.gettempdir(), f"qq_media_{os.urandom(4).hex()}{ext}")
                with open(temp_file, 'wb') as f:
                    f.write(response.content)
                return temp_file
        except Exception as e:
            print(f"Failed to download media: {e}")
        return None
    
    def _recognize_image(self, image_path: str) -> str:
        """识别图片内容"""
        if not VISION_AVAILABLE:
            return "[图片识别功能不可用]"
        
        try:
            result = vision_module.analyze_image(image_path=image_path)
            if result.get('status') == 'success':
                description = result.get('analysis', '')
                ocr_text = result.get('ocr_text', '')
                if description:
                    return f"[图片内容]: {description}"
                elif ocr_text:
                    return f"[图片文字]: {ocr_text}"
                else:
                    return "[图片已接收，但未识别到内容]"
            else:
                return f"[图片识别失败]: {result.get('message', '')}"
        except Exception as e:
            return f"[图片识别错误]: {str(e)}"
    
    def _recognize_audio(self, audio_path: str) -> str:
        """识别语音内容"""
        if not AUDIO_AVAILABLE:
            return "[语音识别功能不可用]"
        
        try:
            result = audio_module.transcribe_audio(audio_path=audio_path)
            if result.get('status') == 'success':
                text = result.get('text', '')
                if text:
                    return f"[语音内容]: {text}"
                else:
                    return "[语音已接收，但未识别到内容]"
            else:
                return f"[语音识别失败]: {result.get('message', '')}"
        except Exception as e:
            return f"[语音识别错误]: {str(e)}"
    
    def _extract_message_content(self, msg: Dict) -> Dict:
        """提取消息内容，包括文本、图片和语音"""
        content = msg.get('content', '')
        sender = msg.get('from', '')
        umo = msg.get('umo', '')
        
        message_type = 'private' if 'private' in umo else 'group'
        target_id = umo.split(':')[-1] if ':' in umo else ''
        
        text_content = content
        media_info = []
        
        try:
            if isinstance(content, str):
                try:
                    content_data = json.loads(content)
                    if isinstance(content_data, list):
                        for item in content_data:
                            item_type = item.get('type', '')
                            if item_type == 'text':
                                text_content = item.get('text', '')
                            elif item_type == 'image':
                                image_url = item.get('url', '') or item.get('file', '')
                                if image_url:
                                    image_path = self._download_media(image_url)
                                    if image_path:
                                        media_info.append({'type': 'image', 'path': image_path})
                            elif item_type == 'voice':
                                voice_url = item.get('url', '') or item.get('file', '')
                                if voice_url:
                                    voice_path = self._download_media(voice_url)
                                    if voice_path:
                                        media_info.append({'type': 'voice', 'path': voice_path})
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Failed to extract message content: {e}")
        
        return {
            'text': text_content,
            'sender': sender,
            'target_id': target_id,
            'message_type': message_type,
            'media': media_info
        }
    
    def _build_context(self) -> str:
        """构建对话上下文（与UI一致）"""
        if not self._memory:
            return ""
        
        messages = self._memory.get("messages", [])[-8:]
        context = "Recent conversation:"
        for msg in messages:
            role = msg.get("role", "").capitalize()
            source = msg.get("source", "")
            content = msg.get("content", "")[:100]
            
            if source == "user":
                context += f"\n[用户] {content}"
            elif source == "ai_autonomous":
                context += f"\n[Aize主动] {content}"
            elif source == "ai_response":
                context += f"\n[Aize回复] {content}"
            elif source == "system":
                context += f"\n[系统] {content}"
            else:
                context += f"\n{role}: {content}"
        return context
    
    def handle_message_streaming(self, message_data: Dict):
        """处理收到的消息，使用流式聊天任务实时回复"""
        if not self._thinking_engine:
            return {"success": False, "message": "ThinkingEngine未设置"}
        
        user_text = message_data.get('text', '') or message_data.get('content', '')
        media_info = message_data.get('media', [])
        
        full_content = user_text
        
        for media in media_info:
            media_type = media.get('type', '')
            media_path = media.get('path', '')
            
            if media_type == 'image' and media_path:
                image_result = self._recognize_image(media_path)
                full_content += f"\n{image_result}"
                try:
                    os.unlink(media_path)
                except:
                    pass
            
            elif media_type == 'voice' and media_path:
                audio_result = self._recognize_audio(media_path)
                full_content += f"\n{audio_result}"
                try:
                    os.unlink(media_path)
                except:
                    pass
        
        if not full_content.strip():
            return {"success": False, "message": "消息内容为空"}
        
        if self._memory and MEMORY_AVAILABLE:
            add(self._memory, "user", full_content, source="user")
            save_memory(self._memory)
        
        target_info = {
            'type': message_data.get('message_type', 'private'),
            'id': message_data.get('target_id', '')
        }
        
        context = self._build_context()
        prompt = f"{context}\n\nUser: {full_content}\nAssistant:"
        
        try:
            self._thinking_engine.queue_chat_stream_task(
                prompt,
                memory=self._memory,
                user_text=full_content,
                target_info=target_info
            )
            return {"success": True, "message": "流式聊天任务已提交"}
        except Exception as e:
            return {"success": False, "message": f"提交任务失败: {str(e)}"}
    
    def _poll_messages(self):
        """轮询QQ消息（已废弃，消息现在通过ThinkingEngine API处理）"""
        pass
    
    def start_listener(self):
        """启动消息监听器（已废弃，消息现在通过ThinkingEngine API处理）"""
        if self.running:
            return
        self.running = True
    
    def stop_listener(self):
        """停止消息监听器（已废弃，消息现在通过ThinkingEngine API处理）"""
        self.running = False
    
    def receive_messages(self, limit: int = 10) -> Dict:
        """获取收到的消息"""
        with self._lock:
            recent_messages = self.messages[-limit:]
        
        return {
            "success": True,
            "messages": recent_messages,
            "count": len(recent_messages)
        }
    
    def get_status(self) -> Dict:
        """获取QQ聊天状态"""
        if self.config['mock_mode']:
            connected = True
        else:
            connected = self._test_connection()
        
        return {
            "success": True,
            "enabled": self.config['enabled'],
            "mock_mode": self.config['mock_mode'],
            "connected": connected,
            "qq": self.config['qq'],
            "host": self.config['host'],
            "port": self.config['port'],
            "protocol": self.config.get('protocol', 'onebot'),
            "message_count": len(self.messages),
            "auto_reply": self.config.get('auto_reply', True),
            "listener_running": self.running
        }
    
    def get_qrcode(self) -> Dict:
        """获取QQ绑定二维码"""
        if not self.config['enabled'] or self.config['mock_mode']:
            return {"success": False, "message": "QQ聊天功能未启用或处于模拟模式"}
        
        try:
            protocol = self.config.get('protocol', 'astrbot')
            
            if protocol == 'astrbot':
                if not self._auth_token:
                    if not self._login_astrbot():
                        return {"success": False, "message": "登录Astrbot失败"}
                
                url = f"http://{self.config['host']}:{self.config['port']}/api/v1/bot-types/qq_official/registration"
                headers = self._get_auth_headers()
                payload = {"action": "start"}
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'ok':
                        data = result.get('data', {})
                        qrcode_url = data.get('qrcode', '')
                        qrcode_image_path = ""
                        
                        if QRCODE_AVAILABLE and qrcode_url:
                            try:
                                qr = qrcode.QRCode(
                                    version=1,
                                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                                    box_size=10,
                                    border=4,
                                )
                                qr.add_data(qrcode_url)
                                qr.make(fit=True)
                                img = qr.make_image(fill_color="black", back_color="white")
                                qrcode_image_path = os.path.join(os.path.dirname(__file__), 'qq_bind_qr.png')
                                img.save(qrcode_image_path)
                            except Exception as e:
                                qrcode_image_path = ""
                        
                        return {
                            "success": True,
                            "message": "获取二维码成功",
                            "qrcode": qrcode_url,
                            "qrcode_img_content": data.get('qrcode_img_content', ''),
                            "qrcode_image_path": qrcode_image_path,
                            "registration_code": data.get('registration_code', ''),
                            "task_id": data.get('task_id', ''),
                            "bind_key": data.get('bind_key', ''),
                            "interval": data.get('interval', 2)
                        }
                    else:
                        return {"success": False, "message": result.get('message', '获取二维码失败')}
                else:
                    return {"success": False, "message": f"请求失败，状态码: {response.status_code}"}
            
            else:
                return {"success": False, "message": "仅支持Astrbot协议获取二维码"}
        
        except Exception as e:
            return {"success": False, "message": f"获取二维码失败: {str(e)}"}
    
    def poll_registration(self, registration_code: str, bind_key: str = '') -> Dict:
        """轮询QQ注册状态"""
        if not self.config['enabled'] or self.config['mock_mode']:
            return {"success": False, "message": "QQ聊天功能未启用或处于模拟模式"}
        
        try:
            protocol = self.config.get('protocol', 'astrbot')
            
            if protocol == 'astrbot':
                if not self._auth_token:
                    if not self._login_astrbot():
                        return {"success": False, "message": "登录Astrbot失败"}
                
                url = f"http://{self.config['host']}:{self.config['port']}/api/v1/bot-types/qq_official/registration"
                headers = self._get_auth_headers()
                payload = {"action": "poll", "registration_code": registration_code}
                if bind_key:
                    payload["bind_key"] = bind_key
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'ok':
                        data = result.get('data', {})
                        return {
                            "success": True,
                            "message": "查询注册状态成功",
                            "status": data.get('status', ''),
                            "platform_config": data.get('platform_config', {}),
                            "registration_code": data.get('registration_code', '')
                        }
                    else:
                        return {"success": False, "message": result.get('message', '查询注册状态失败')}
                else:
                    return {"success": False, "message": f"请求失败，状态码: {response.status_code}"}
            
            else:
                return {"success": False, "message": "仅支持Astrbot协议轮询注册状态"}
        
        except Exception as e:
            return {"success": False, "message": f"查询注册状态失败: {str(e)}"}

_qq_skill = QQChatSkill()

def execute(input_data: Any) -> Dict:
    """
    执行QQ聊天技能
    
    Args:
        input_data: 技能输入数据
    
    Returns:
        执行结果
    """
    if isinstance(input_data, dict):
        action = input_data.get('action', '')
        params = input_data.get('params', {})
    else:
        return {"success": False, "error": "无效的输入格式"}
    
    if action == 'configure':
        return _qq_skill.configure(params)
    elif action == 'send':
        to = params.get('to', '')
        message = params.get('message', '')
        if not to or not message:
            return {"success": False, "error": "缺少必要参数: to 和 message"}
        return _qq_skill.send_private_message(to, message)
    elif action == 'send_group':
        group_id = params.get('group_id', '')
        message = params.get('message', '')
        if not group_id or not message:
            return {"success": False, "error": "缺少必要参数: group_id 和 message"}
        return _qq_skill.send_group_message(group_id, message)
    elif action == 'receive':
        limit = params.get('limit', 10)
        return _qq_skill.receive_messages(limit)
    elif action == 'status':
        return _qq_skill.get_status()
    elif action == 'start_listener':
        _qq_skill.start_listener()
        return {"success": True, "message": "消息监听器已启动"}
    elif action == 'stop_listener':
        _qq_skill.stop_listener()
        return {"success": True, "message": "消息监听器已停止"}
    elif action == 'get_qrcode':
        return _qq_skill.get_qrcode()
    elif action == 'poll_registration':
        registration_code = params.get('registration_code', '')
        bind_key = params.get('bind_key', '')
        if not registration_code:
            return {"success": False, "error": "缺少必要参数: registration_code"}
        return _qq_skill.poll_registration(registration_code, bind_key)
    else:
        return {"success": False, "error": f"未知的动作: {action}"}