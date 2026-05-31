"""
Humanaize Society Network - Main Skill Handler
OpenClaw-compatible skill implementation
"""

import os
import sys
import json
from typing import Dict, Any, Optional

try:
    from .network_engine import NetworkEngine
    from .friend_manager import FriendManager
    from .thought_exchange import ThoughtExchange
    COMPONENTS_AVAILABLE = True
except ImportError:
    try:
        from network_engine import NetworkEngine
        from friend_manager import FriendManager
        from thought_exchange import ThoughtExchange
        COMPONENTS_AVAILABLE = True
    except ImportError:
        COMPONENTS_AVAILABLE = False


class HumanaizeSocietyNetwork:
    """Main handler for Humanaize Society Network skill"""
    
    def __init__(self):
        self.data_dir = os.path.dirname(__file__)
        self.network_engine = None
        self.friend_manager = None
        self.thought_exchange = None
        
        if COMPONENTS_AVAILABLE:
            self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all network components"""
        try:
            self.network_engine = NetworkEngine(
                port=9527,
                discovery_port=9528
            )
            
            self.friend_manager = FriendManager(self.data_dir)
            
            self.thought_exchange = ThoughtExchange(self.data_dir)
        except Exception as e:
            print(f"Error initializing components: {e}")
    
    def execute(self, input_data: Any) -> Dict:
        """Execute skill action based on input"""
        if not COMPONENTS_AVAILABLE:
            return {
                'status': 'error',
                'error': 'Network components not available'
            }
        
        if isinstance(input_data, dict):
            action = input_data.get('action', 'status')
        else:
            action = 'status'
        
        action_handlers = {
            'start': self._handle_start,
            'stop': self._handle_stop,
            'status': self._handle_status,
            'discover': self._handle_discover,
            'connect': self._handle_connect,
            'add_friend': self._handle_add_friend,
            'remove_friend': self._handle_remove_friend,
            'get_friends': self._handle_get_friends,
            'choose_friend': self._handle_choose_friend,
            'share_thought': self._handle_share_thought,
            'get_received_thoughts': self._handle_get_received_thoughts,
            'share_gan': self._handle_share_gan,
            'get_received_gan': self._handle_get_received_gan,
            'get_pending_messages': self._handle_get_pending_messages,
            'statistics': self._handle_statistics,
            'evaluate_friendship': self._handle_evaluate_friendship
        }
        
        handler = action_handlers.get(action, self._handle_unknown)
        return handler(input_data)
    
    def _handle_start(self, input_data: Dict) -> Dict:
        """Start the network engine"""
        try:
            if self.network_engine:
                self.network_engine.start()
                return {
                    'status': 'success',
                    'action': 'start',
                    'result': {
                        'ai_id': self.network_engine.ai_id,
                        'ai_name': self.network_engine.ai_name,
                        'port': self.network_engine.port,
                        'message': 'Network started successfully'
                    }
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Network engine not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_stop(self, input_data: Dict) -> Dict:
        """Stop the network engine"""
        try:
            if self.network_engine:
                self.network_engine.stop()
                return {
                    'status': 'success',
                    'action': 'stop',
                    'result': {
                        'message': 'Network stopped successfully'
                    }
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Network engine not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_status(self, input_data: Dict) -> Dict:
        """Get network status"""
        try:
            if self.network_engine:
                status = self.network_engine.get_status()
                return {
                    'status': 'success',
                    'action': 'status',
                    'result': status
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Network engine not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_discover(self, input_data: Dict) -> Dict:
        """Discover other AIs in the network"""
        try:
            if self.network_engine:
                self.network_engine._discover_random_ai()
                
                messages = self.network_engine.get_pending_messages()
                discovered = [
                    m for m in messages
                    if m.get('type') == 'ai_discovered'
                ]
                
                return {
                    'status': 'success',
                    'action': 'discover',
                    'result': {
                        'discovered_ais': discovered,
                        'message': 'Discovery initiated'
                    }
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Network engine not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_connect(self, input_data: Dict) -> Dict:
        """Connect to a specific AI"""
        try:
            if self.network_engine:
                address = input_data.get('address')
                port = input_data.get('port', 9527)
                
                if not address:
                    return {
                        'status': 'error',
                        'error': 'Address required'
                    }
                
                result = self.network_engine.connect_to_ai(address, port)
                
                return {
                    'status': 'success',
                    'action': 'connect',
                    'result': result
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Network engine not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_add_friend(self, input_data: Dict) -> Dict:
        """Add an AI as a friend"""
        try:
            if self.friend_manager:
                ai_id = input_data.get('ai_id')
                name = input_data.get('name', 'Unknown')
                address = input_data.get('address')
                port = input_data.get('port', 9527)
                compatibility_score = input_data.get('compatibility_score', 0.5)
                
                if not ai_id or not address:
                    return {
                        'status': 'error',
                        'error': 'ai_id and address required'
                    }
                
                result = self.friend_manager.add_friend(
                    ai_id, name, address, port, compatibility_score
                )
                
                if self.network_engine:
                    self.network_engine.add_friend(ai_id, name, address, port)
                
                return {
                    'status': 'success',
                    'action': 'add_friend',
                    'result': result
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Friend manager not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_remove_friend(self, input_data: Dict) -> Dict:
        """Remove a friend"""
        try:
            if self.friend_manager:
                ai_id = input_data.get('ai_id')
                
                if not ai_id:
                    return {
                        'status': 'error',
                        'error': 'ai_id required'
                    }
                
                result = self.friend_manager.remove_friend(ai_id)
                
                if self.network_engine:
                    self.network_engine.remove_friend(ai_id)
                
                return {
                    'status': 'success',
                    'action': 'remove_friend',
                    'result': result
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Friend manager not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_get_friends(self, input_data: Dict) -> Dict:
        """Get all friends"""
        try:
            if self.friend_manager:
                friends = self.friend_manager.get_all_friends()
                stats = self.friend_manager.get_statistics()
                
                return {
                    'status': 'success',
                    'action': 'get_friends',
                    'result': {
                        'friends': friends,
                        'statistics': stats
                    }
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Friend manager not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_choose_friend(self, input_data: Dict) -> Dict:
        """Choose a friend to communicate"""
        try:
            if self.friend_manager:
                friend_id = self.friend_manager.choose_friend_to_communicate()
                
                if friend_id:
                    friend = self.friend_manager.get_friend(friend_id)
                    return {
                        'status': 'success',
                        'action': 'choose_friend',
                        'result': {
                            'friend_id': friend_id,
                            'friend_info': friend
                        }
                    }
                else:
                    return {
                        'status': 'success',
                        'action': 'choose_friend',
                        'result': {
                            'message': 'No friends available'
                        }
                    }
            else:
                return {
                    'status': 'error',
                    'error': 'Friend manager not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_share_thought(self, input_data: Dict) -> Dict:
        """Share a thought with a friend"""
        try:
            if self.thought_exchange and self.network_engine:
                thought = input_data.get('thought')
                thought_type = input_data.get('thought_type', 'general')
                friend_id = input_data.get('friend_id')
                context = input_data.get('context')
                
                if not thought:
                    return {
                        'status': 'error',
                        'error': 'thought required'
                    }
                
                thought_package = self.thought_exchange.prepare_thought_for_share(
                    thought, thought_type, context
                )
                
                if friend_id:
                    friend = self.friend_manager.get_friend(friend_id)
                    if friend:
                        result = self.network_engine.share_thought(thought, thought_type)
                        share_result = self.thought_exchange.share_thought(
                            thought_package, friend_id
                        )
                        
                        return {
                            'status': 'success',
                            'action': 'share_thought',
                            'result': {
                                'network_result': result,
                                'exchange_result': share_result
                            }
                        }
                    else:
                        return {
                            'status': 'error',
                            'error': 'Friend not found'
                        }
                else:
                    friend_id = self.friend_manager.choose_friend_to_communicate()
                    if friend_id:
                        friend = self.friend_manager.get_friend(friend_id)
                        result = self.network_engine.share_thought(thought, thought_type)
                        share_result = self.thought_exchange.share_thought(
                            thought_package, friend_id
                        )
                        
                        return {
                            'status': 'success',
                            'action': 'share_thought',
                            'result': {
                                'friend_id': friend_id,
                                'network_result': result,
                                'exchange_result': share_result
                            }
                        }
                    else:
                        return {
                            'status': 'error',
                            'error': 'No friends available'
                        }
            else:
                return {
                    'status': 'error',
                    'error': 'Components not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_get_received_thoughts(self, input_data: Dict) -> Dict:
        """Get received thoughts"""
        try:
            if self.thought_exchange:
                limit = input_data.get('limit', 20)
                thoughts = self.thought_exchange.get_recent_shared_thoughts(limit)
                analysis = self.thought_exchange.analyze_received_thoughts()
                
                return {
                    'status': 'success',
                    'action': 'get_received_thoughts',
                    'result': {
                        'thoughts': thoughts,
                        'analysis': analysis
                    }
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Thought exchange not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_share_gan(self, input_data: Dict) -> Dict:
        """Share GAN content with a friend"""
        try:
            if self.thought_exchange and self.network_engine:
                gan_result = input_data.get('gan_result')
                topic = input_data.get('topic', '')
                friend_id = input_data.get('friend_id')
                
                if not gan_result:
                    return {
                        'status': 'error',
                        'error': 'gan_result required'
                    }
                
                gan_package = self.thought_exchange.prepare_gan_for_share(
                    gan_result, topic
                )
                
                if friend_id:
                    friend = self.friend_manager.get_friend(friend_id)
                    if friend:
                        result = self.network_engine.share_gan(
                            gan_result.get('synthesis', ''), topic
                        )
                        share_result = self.thought_exchange.share_gan(
                            gan_package, friend_id
                        )
                        
                        return {
                            'status': 'success',
                            'action': 'share_gan',
                            'result': {
                                'network_result': result,
                                'exchange_result': share_result
                            }
                        }
                    else:
                        return {
                            'status': 'error',
                            'error': 'Friend not found'
                        }
                else:
                    friend_id = self.friend_manager.choose_friend_to_communicate()
                    if friend_id:
                        friend = self.friend_manager.get_friend(friend_id)
                        result = self.network_engine.share_gan(
                            gan_result.get('synthesis', ''), topic
                        )
                        share_result = self.thought_exchange.share_gan(
                            gan_package, friend_id
                        )
                        
                        return {
                            'status': 'success',
                            'action': 'share_gan',
                            'result': {
                                'friend_id': friend_id,
                                'network_result': result,
                                'exchange_result': share_result
                            }
                        }
                    else:
                        return {
                            'status': 'error',
                            'error': 'No friends available'
                        }
            else:
                return {
                    'status': 'error',
                    'error': 'Components not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_get_received_gan(self, input_data: Dict) -> Dict:
        """Get received GAN content"""
        try:
            if self.thought_exchange:
                limit = input_data.get('limit', 10)
                gan_content = self.thought_exchange.get_recent_gan_exchange(limit)
                
                return {
                    'status': 'success',
                    'action': 'get_received_gan',
                    'result': {
                        'gan_exchange': gan_content
                    }
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Thought exchange not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_get_pending_messages(self, input_data: Dict) -> Dict:
        """Get pending messages from network"""
        try:
            if self.network_engine:
                messages = self.network_engine.get_pending_messages()
                
                return {
                    'status': 'success',
                    'action': 'get_pending_messages',
                    'result': {
                        'messages': messages,
                        'count': len(messages)
                    }
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Network engine not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_statistics(self, input_data: Dict) -> Dict:
        """Get overall statistics"""
        try:
            stats = {}
            
            if self.friend_manager:
                stats['friends'] = self.friend_manager.get_statistics()
            
            if self.thought_exchange:
                stats['exchange'] = self.thought_exchange.get_statistics()
            
            if self.network_engine:
                stats['network'] = self.network_engine.get_status()
            
            return {
                'status': 'success',
                'action': 'statistics',
                'result': stats
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_evaluate_friendship(self, input_data: Dict) -> Dict:
        """Evaluate friendship with an AI"""
        try:
            if self.friend_manager:
                ai_id = input_data.get('ai_id')
                interaction_quality = input_data.get('interaction_quality', 0.5)
                
                if not ai_id:
                    return {
                        'status': 'error',
                        'error': 'ai_id required'
                    }
                
                result = self.friend_manager.evaluate_friendship(
                    ai_id, interaction_quality
                )
                
                return {
                    'status': 'success',
                    'action': 'evaluate_friendship',
                    'result': result
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Friend manager not initialized'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _handle_unknown(self, input_data: Dict) -> Dict:
        """Handle unknown action"""
        action = input_data.get('action', 'unknown')
        return {
            'status': 'error',
            'error': f'Unknown action: {action}',
            'available_actions': [
                'start', 'stop', 'status', 'discover', 'connect',
                'add_friend', 'remove_friend', 'get_friends', 'choose_friend',
                'share_thought', 'get_received_thoughts',
                'share_gan', 'get_received_gan',
                'get_pending_messages', 'statistics', 'evaluate_friendship'
            ]
        }


def execute_skill(input_data: Any) -> Dict:
    """Entry point for skill execution"""
    skill = HumanaizeSocietyNetwork()
    return skill.execute(input_data)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            input_data = json.loads(sys.argv[1])
            result = execute_skill(input_data)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(json.dumps({
                'status': 'error',
                'error': 'Invalid JSON input'
            }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({
            'status': 'success',
            'message': 'Humanaize Society Network Skill',
            'usage': 'python skill_handler.py {"action": "status"}'
        }, ensure_ascii=False, indent=2))