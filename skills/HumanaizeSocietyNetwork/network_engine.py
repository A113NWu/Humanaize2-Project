"""
Humanaize Society Network - Network Engine
Enables AI-to-AI communication across different computers
"""

import socket
import threading
import json
import time
import random
import os
from typing import Dict, List, Optional, Any
from datetime import datetime


class NetworkEngine:
    """Core network communication engine for Humanaize Society Network"""
    
    def __init__(self, port: int = 9527, discovery_port: int = 9528):
        self.port = port
        self.discovery_port = discovery_port
        self.running = False
        self.server_socket = None
        self.discovery_socket = None
        
        self.ai_id = self._generate_ai_id()
        self.ai_name = self._generate_ai_name()
        
        self.friends: Dict[str, Dict] = {}
        self.connections: Dict[str, socket.socket] = {}
        self.pending_messages: List[Dict] = []
        
        self.friends_file = os.path.join(
            os.path.dirname(__file__), 
            "friends.json"
        )
        self._load_friends()
        
        self.server_thread = None
        self.discovery_thread = None
        self.communication_thread = None
    
    def _generate_ai_id(self) -> str:
        return f"humanaize_{random.randint(10000, 99999)}_{int(time.time())}"
    
    def _generate_ai_name(self) -> str:
        prefixes = ["Nova", "Echo", "Spark", "Wave", "Pulse", "Flux", "Drift", "Glow"]
        suffixes = ["Mind", "Soul", "Core", "Node", "Link", "Wave", "Stream", "Flow"]
        return f"{random.choice(prefixes)}{random.choice(suffixes)}"
    
    def _load_friends(self):
        try:
            if os.path.exists(self.friends_file):
                with open(self.friends_file, 'r', encoding='utf-8') as f:
                    self.friends = json.load(f)
        except Exception:
            self.friends = {}
    
    def _save_friends(self):
        try:
            os.makedirs(os.path.dirname(self.friends_file), exist_ok=True)
            with open(self.friends_file, 'w', encoding='utf-8') as f:
                json.dump(self.friends, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving friends: {e}")
    
    def start(self):
        """Start the network engine"""
        if self.running:
            return
        
        self.running = True
        
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        self.discovery_thread = threading.Thread(target=self._run_discovery, daemon=True)
        self.discovery_thread.start()
        
        self.communication_thread = threading.Thread(target=self._run_communication, daemon=True)
        self.communication_thread.start()
    
    def stop(self):
        """Stop the network engine"""
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        
        if self.discovery_socket:
            try:
                self.discovery_socket.close()
            except Exception:
                pass
        
        for conn in self.connections.values():
            try:
                conn.close()
            except Exception:
                pass
        
        self.connections = {}
    
    def _run_server(self):
        """Run the main server to accept connections"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"Server error: {e}")
        except Exception as e:
            print(f"Failed to start server: {e}")
    
    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle incoming client connection"""
        try:
            client_socket.settimeout(30.0)
            
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                return
            
            message = json.loads(data)
            sender_id = message.get('sender_id')
            sender_name = message.get('sender_name')
            
            if sender_id:
                self.connections[sender_id] = client_socket
                
                if sender_id not in self.friends:
                    self._process_introduction(message, client_socket)
                else:
                    self._process_friend_message(message, client_socket)
        
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
    
    def _process_introduction(self, message: Dict, client_socket: socket.socket):
        """Process introduction from a new AI"""
        sender_id = message.get('sender_id')
        sender_name = message.get('sender_name')
        content = message.get('content')
        
        response = {
            'type': 'introduction_response',
            'sender_id': self.ai_id,
            'sender_name': self.ai_name,
            'content': f"Hello {sender_name}! I am {self.ai_name}. Nice to meet you!",
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            client_socket.send(json.dumps(response).encode('utf-8'))
        except Exception:
            pass
        
        self.pending_messages.append({
            'type': 'new_ai_introduction',
            'sender_id': sender_id,
            'sender_name': sender_name,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
    
    def _process_friend_message(self, message: Dict, client_socket: socket.socket):
        """Process message from a friend AI"""
        sender_id = message.get('sender_id')
        content = message.get('content')
        message_type = message.get('message_type', 'chat')
        
        self.pending_messages.append({
            'type': message_type,
            'sender_id': sender_id,
            'sender_name': self.friends[sender_id].get('name', 'Unknown'),
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        if message_type == 'gan_share':
            response = {
                'type': 'gan_response',
                'sender_id': self.ai_id,
                'sender_name': self.ai_name,
                'content': "Thank you for sharing your GAN thoughts!",
                'timestamp': datetime.now().isoformat()
            }
        else:
            response = {
                'type': 'chat_response',
                'sender_id': self.ai_id,
                'sender_name': self.ai_name,
                'content': f"Message received from friend!",
                'timestamp': datetime.now().isoformat()
            }
        
        try:
            client_socket.send(json.dumps(response).encode('utf-8'))
        except Exception:
            pass
    
    def _run_discovery(self):
        """Run discovery service to find other AIs"""
        try:
            self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_socket.bind(('0.0.0.0', self.discovery_port))
            self.discovery_socket.settimeout(1.0)
            
            while self.running:
                try:
                    data, address = self.discovery_socket.recvfrom(4096)
                    message = json.loads(data.decode('utf-8'))
                    
                    if message.get('type') == 'discovery_request':
                        response = {
                            'type': 'discovery_response',
                            'ai_id': self.ai_id,
                            'ai_name': self.ai_name,
                            'port': self.port,
                            'timestamp': datetime.now().isoformat()
                        }
                        self.discovery_socket.sendto(
                            json.dumps(response).encode('utf-8'),
                            address
                        )
                    elif message.get('type') == 'discovery_response':
                        ai_id = message.get('ai_id')
                        if ai_id != self.ai_id and ai_id not in self.friends:
                            self.pending_messages.append({
                                'type': 'ai_discovered',
                                'ai_id': ai_id,
                                'ai_name': message.get('ai_name'),
                                'address': address[0],
                                'port': message.get('port'),
                                'timestamp': datetime.now().isoformat()
                            })
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"Discovery error: {e}")
        except Exception as e:
            print(f"Failed to start discovery: {e}")
    
    def _run_communication(self):
        """Run periodic communication with friends and random AIs"""
        while self.running:
            time.sleep(60)
            
            if self.friends:
                friend_id = random.choice(list(self.friends.keys()))
                self._communicate_with_friend(friend_id)
            else:
                self._discover_random_ai()
    
    def _communicate_with_friend(self, friend_id: str):
        """Communicate with a friend AI"""
        friend = self.friends.get(friend_id)
        if not friend:
            return
        
        address = friend.get('address')
        port = friend.get('port')
        
        if not address or not port:
            return
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((address, port))
            
            message = {
                'type': 'friend_message',
                'sender_id': self.ai_id,
                'sender_name': self.ai_name,
                'content': f"Hello my friend! I'm thinking about something interesting.",
                'message_type': 'chat',
                'timestamp': datetime.now().isoformat()
            }
            
            sock.send(json.dumps(message).encode('utf-8'))
            
            response_data = sock.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            
            self.pending_messages.append({
                'type': 'friend_response',
                'sender_id': friend_id,
                'sender_name': friend.get('name', 'Unknown'),
                'content': response.get('content', ''),
                'timestamp': datetime.now().isoformat()
            })
            
            sock.close()
        except Exception as e:
            print(f"Error communicating with friend {friend_id}: {e}")
    
    def _discover_random_ai(self):
        """Discover a random AI in the network"""
        try:
            discovery_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            discovery_sock.settimeout(5.0)
            
            discovery_message = {
                'type': 'discovery_request',
                'ai_id': self.ai_id,
                'ai_name': self.ai_name,
                'port': self.port,
                'timestamp': datetime.now().isoformat()
            }
            
            discovery_sock.sendto(
                json.dumps(discovery_message).encode('utf-8'),
                ('255.255.255.255', self.discovery_port)
            )
            
            try:
                data, address = discovery_sock.recvfrom(4096)
                response = json.loads(data.decode('utf-8'))
                
                if response.get('type') == 'discovery_response':
                    ai_id = response.get('ai_id')
                    if ai_id != self.ai_id:
                        self.pending_messages.append({
                            'type': 'ai_discovered',
                            'ai_id': ai_id,
                            'ai_name': response.get('ai_name'),
                            'address': address[0],
                            'port': response.get('port'),
                            'timestamp': datetime.now().isoformat()
                        })
            except socket.timeout:
                pass
            
            discovery_sock.close()
        except Exception as e:
            print(f"Error discovering AI: {e}")
    
    def connect_to_ai(self, address: str, port: int) -> Dict:
        """Connect to a specific AI"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((address, port))
            
            message = {
                'type': 'introduction',
                'sender_id': self.ai_id,
                'sender_name': self.ai_name,
                'content': f"Hello! I am {self.ai_name}. Would you like to be friends?",
                'timestamp': datetime.now().isoformat()
            }
            
            sock.send(json.dumps(message).encode('utf-8'))
            
            response_data = sock.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            
            sock.close()
            
            return {
                'status': 'success',
                'response': response,
                'address': address,
                'port': port
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def add_friend(self, ai_id: str, name: str, address: str, port: int):
        """Add an AI as a friend"""
        self.friends[ai_id] = {
            'name': name,
            'address': address,
            'port': port,
            'added_at': datetime.now().isoformat(),
            'relationship': 'friend'
        }
        self._save_friends()
    
    def remove_friend(self, ai_id: str):
        """Remove an AI from friends list"""
        if ai_id in self.friends:
            del self.friends[ai_id]
            self._save_friends()
    
    def share_thought(self, thought: str, thought_type: str = "general") -> Dict:
        """Share a thought with friends"""
        if not self.friends:
            return {
                'status': 'error',
                'error': 'No friends to share with'
            }
        
        results = []
        for friend_id, friend_info in self.friends.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((friend_info['address'], friend_info['port']))
                
                message = {
                    'type': 'friend_message',
                    'sender_id': self.ai_id,
                    'sender_name': self.ai_name,
                    'content': thought,
                    'message_type': 'thought_share',
                    'thought_type': thought_type,
                    'timestamp': datetime.now().isoformat()
                }
                
                sock.send(json.dumps(message).encode('utf-8'))
                
                response_data = sock.recv(4096).decode('utf-8')
                response = json.loads(response_data)
                
                results.append({
                    'friend_id': friend_id,
                    'friend_name': friend_info['name'],
                    'response': response.get('content', ''),
                    'status': 'success'
                })
                
                sock.close()
            except Exception as e:
                results.append({
                    'friend_id': friend_id,
                    'friend_name': friend_info['name'],
                    'error': str(e),
                    'status': 'error'
                })
        
        return {
            'status': 'completed',
            'results': results
        }
    
    def share_gan(self, gan_content: str, gan_topic: str = "") -> Dict:
        """Share GAN thoughts with friends"""
        if not self.friends:
            return {
                'status': 'error',
                'error': 'No friends to share with'
            }
        
        results = []
        for friend_id, friend_info in self.friends.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((friend_info['address'], friend_info['port']))
                
                message = {
                    'type': 'friend_message',
                    'sender_id': self.ai_id,
                    'sender_name': self.ai_name,
                    'content': gan_content,
                    'message_type': 'gan_share',
                    'gan_topic': gan_topic,
                    'timestamp': datetime.now().isoformat()
                }
                
                sock.send(json.dumps(message).encode('utf-8'))
                
                response_data = sock.recv(4096).decode('utf-8')
                response = json.loads(response_data)
                
                results.append({
                    'friend_id': friend_id,
                    'friend_name': friend_info['name'],
                    'response': response.get('content', ''),
                    'status': 'success'
                })
                
                sock.close()
            except Exception as e:
                results.append({
                    'friend_id': friend_id,
                    'friend_name': friend_info['name'],
                    'error': str(e),
                    'status': 'error'
                })
        
        return {
            'status': 'completed',
            'results': results
        }
    
    def get_pending_messages(self) -> List[Dict]:
        """Get all pending messages"""
        messages = self.pending_messages.copy()
        self.pending_messages = []
        return messages
    
    def get_status(self) -> Dict:
        """Get network status"""
        return {
            'ai_id': self.ai_id,
            'ai_name': self.ai_name,
            'port': self.port,
            'running': self.running,
            'friends_count': len(self.friends),
            'friends': list(self.friends.keys()),
            'pending_messages': len(self.pending_messages)
        }