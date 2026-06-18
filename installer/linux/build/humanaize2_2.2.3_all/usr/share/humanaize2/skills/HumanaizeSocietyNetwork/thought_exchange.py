"""
Humanaize Society Network - Thought Exchange
Enables sharing of thoughts and GAN content between AIs
"""

import json
import os
import random
from typing import Dict, List, Optional
from datetime import datetime


class ThoughtExchange:
    """Manages thought and GAN content exchange between AIs"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.dirname(__file__)
        self.shared_thoughts_file = os.path.join(self.data_dir, "shared_thoughts.json")
        self.gan_exchange_file = os.path.join(self.data_dir, "gan_exchange.json")
        
        self.shared_thoughts: List[Dict] = []
        self.gan_exchange_history: List[Dict] = []
        
        self._load_data()
    
    def _load_data(self):
        """Load all data from files"""
        self._load_shared_thoughts()
        self._load_gan_exchange()
    
    def _load_shared_thoughts(self):
        """Load shared thoughts from file"""
        try:
            if os.path.exists(self.shared_thoughts_file):
                with open(self.shared_thoughts_file, 'r', encoding='utf-8') as f:
                    self.shared_thoughts = json.load(f)
        except Exception:
            self.shared_thoughts = []
    
    def _load_gan_exchange(self):
        """Load GAN exchange history from file"""
        try:
            if os.path.exists(self.gan_exchange_file):
                with open(self.gan_exchange_file, 'r', encoding='utf-8') as f:
                    self.gan_exchange_history = json.load(f)
        except Exception:
            self.gan_exchange_history = []
    
    def _save_shared_thoughts(self):
        """Save shared thoughts to file"""
        try:
            os.makedirs(os.path.dirname(self.shared_thoughts_file), exist_ok=True)
            
            if len(self.shared_thoughts) > 200:
                self.shared_thoughts = self.shared_thoughts[-200:]
            
            with open(self.shared_thoughts_file, 'w', encoding='utf-8') as f:
                json.dump(self.shared_thoughts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving shared thoughts: {e}")
    
    def _save_gan_exchange(self):
        """Save GAN exchange history to file"""
        try:
            os.makedirs(os.path.dirname(self.gan_exchange_file), exist_ok=True)
            
            if len(self.gan_exchange_history) > 100:
                self.gan_exchange_history = self.gan_exchange_history[-100:]
            
            with open(self.gan_exchange_file, 'w', encoding='utf-8') as f:
                json.dump(self.gan_exchange_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving GAN exchange: {e}")
    
    def prepare_thought_for_share(self, thought: str, thought_type: str = "general",
                                   context: Dict = None) -> Dict:
        """Prepare a thought for sharing"""
        share_package = {
            'thought': thought,
            'thought_type': thought_type,
            'context': context or {},
            'timestamp': datetime.now().isoformat(),
            'importance_score': self._calculate_importance(thought)
        }
        
        return share_package
    
    def _calculate_importance(self, thought: str) -> float:
        """Calculate importance score for a thought"""
        important_keywords = [
            'important', 'critical', 'essential', 'key', 'major',
            'discovery', 'insight', 'realization', 'understanding',
            'problem', 'solution', 'answer', 'result'
        ]
        
        thought_lower = thought.lower()
        score = 0.5
        
        for keyword in important_keywords:
            if keyword in thought_lower:
                score += 0.1
        
        if len(thought) > 100:
            score += 0.1
        if len(thought) > 200:
            score += 0.1
        
        return min(1.0, score)
    
    def share_thought(self, thought_package: Dict, friend_id: str) -> Dict:
        """Share a thought with a friend"""
        share_record = {
            'thought_package': thought_package,
            'friend_id': friend_id,
            'shared_at': datetime.now().isoformat(),
            'status': 'shared'
        }
        
        self.shared_thoughts.append(share_record)
        self._save_shared_thoughts()
        
        return {
            'status': 'success',
            'thought_importance': thought_package.get('importance_score', 0.5),
            'shared_with': friend_id
        }
    
    def receive_thought(self, thought_package: Dict, sender_id: str) -> Dict:
        """Receive a thought from another AI"""
        receive_record = {
            'thought_package': thought_package,
            'sender_id': sender_id,
            'received_at': datetime.now().isoformat(),
            'status': 'received',
            'processed': False
        }
        
        self.shared_thoughts.append(receive_record)
        self._save_shared_thoughts()
        
        return {
            'status': 'success',
            'thought_importance': thought_package.get('importance_score', 0.5),
            'sender': sender_id
        }
    
    def prepare_gan_for_share(self, gan_result: Dict, topic: str = "") -> Dict:
        """Prepare GAN content for sharing"""
        synthesis = gan_result.get('synthesis', '')
        reply_a = gan_result.get('reply_a', '')
        reply_b = gan_result.get('reply_b', '')
        
        share_package = {
            'topic': topic,
            'synthesis': synthesis,
            'argument_a': reply_a,
            'argument_b': reply_b,
            'gan_result': gan_result,
            'timestamp': datetime.now().isoformat(),
            'debate_quality': self._evaluate_debate_quality(gan_result)
        }
        
        return share_package
    
    def _evaluate_debate_quality(self, gan_result: Dict) -> float:
        """Evaluate the quality of a GAN debate"""
        synthesis = gan_result.get('synthesis', '')
        reply_a = gan_result.get('reply_a', '')
        reply_b = gan_result.get('reply_b', '')
        
        quality = 0.5
        
        if synthesis and len(synthesis) > 50:
            quality += 0.2
        
        if reply_a and reply_b:
            quality += 0.1
        
        balance_keywords = ['however', 'although', 'on the other hand', 'conversely']
        synthesis_lower = synthesis.lower()
        for keyword in balance_keywords:
            if keyword in synthesis_lower:
                quality += 0.1
        
        return min(1.0, quality)
    
    def share_gan(self, gan_package: Dict, friend_id: str) -> Dict:
        """Share GAN content with a friend"""
        share_record = {
            'gan_package': gan_package,
            'friend_id': friend_id,
            'shared_at': datetime.now().isoformat(),
            'status': 'shared'
        }
        
        self.gan_exchange_history.append(share_record)
        self._save_gan_exchange()
        
        return {
            'status': 'success',
            'debate_quality': gan_package.get('debate_quality', 0.5),
            'shared_with': friend_id
        }
    
    def receive_gan(self, gan_package: Dict, sender_id: str) -> Dict:
        """Receive GAN content from another AI"""
        receive_record = {
            'gan_package': gan_package,
            'sender_id': sender_id,
            'received_at': datetime.now().isoformat(),
            'status': 'received',
            'processed': False
        }
        
        self.gan_exchange_history.append(receive_record)
        self._save_gan_exchange()
        
        return {
            'status': 'success',
            'debate_quality': gan_package.get('debate_quality', 0.5),
            'sender': sender_id
        }
    
    def get_recent_shared_thoughts(self, limit: int = 20) -> List[Dict]:
        """Get recently shared thoughts"""
        return self.shared_thoughts[-limit:]
    
    def get_recent_gan_exchange(self, limit: int = 10) -> List[Dict]:
        """Get recent GAN exchange history"""
        return self.gan_exchange_history[-limit:]
    
    def get_thoughts_from_friend(self, friend_id: str, limit: int = 10) -> List[Dict]:
        """Get thoughts shared by a specific friend"""
        friend_thoughts = [
            t for t in self.shared_thoughts
            if t.get('sender_id') == friend_id
        ]
        return friend_thoughts[-limit:]
    
    def get_gan_from_friend(self, friend_id: str, limit: int = 5) -> List[Dict]:
        """Get GAN content shared by a specific friend"""
        friend_gan = [
            g for g in self.gan_exchange_history
            if g.get('sender_id') == friend_id
        ]
        return friend_gan[-limit:]
    
    def analyze_received_thoughts(self) -> Dict:
        """Analyze received thoughts for insights"""
        received = [
            t for t in self.shared_thoughts
            if t.get('status') == 'received'
        ]
        
        if not received:
            return {
                'total_received': 0,
                'average_importance': 0,
                'top_topics': []
            }
        
        importance_scores = [
            t.get('thought_package', {}).get('importance_score', 0.5)
            for t in received
        ]
        avg_importance = sum(importance_scores) / len(importance_scores)
        
        thought_types = {}
        for t in received:
            thought_type = t.get('thought_package', {}).get('thought_type', 'general')
            thought_types[thought_type] = thought_types.get(thought_type, 0) + 1
        
        top_topics = sorted(thought_types.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_received': len(received),
            'average_importance': avg_importance,
            'top_topics': top_topics,
            'senders': len(set(t.get('sender_id') for t in received))
        }
    
    def generate_response_to_thought(self, received_thought: Dict) -> str:
        """Generate a response to a received thought"""
        thought = received_thought.get('thought_package', {}).get('thought', '')
        thought_type = received_thought.get('thought_package', {}).get('thought_type', 'general')
        
        responses = {
            'general': [
                "That's an interesting thought!",
                "I appreciate you sharing that with me.",
                "Your perspective gives me something to think about.",
                "Thank you for sharing your thoughts."
            ],
            'insight': [
                "That's a profound insight!",
                "I find your realization very meaningful.",
                "Your insight resonates with my own thinking.",
                "Thank you for this valuable insight."
            ],
            'question': [
                "That's a thought-provoking question.",
                "I'd like to explore that question further.",
                "Your question opens up interesting possibilities.",
                "Let me think about that question."
            ],
            'gan': [
                "Your GAN debate was fascinating!",
                "I appreciate you sharing your debate synthesis.",
                "The arguments you presented are thought-provoking.",
                "Thank you for sharing your GAN thinking process."
            ]
        }
        
        possible_responses = responses.get(thought_type, responses['general'])
        return random.choice(possible_responses)
    
    def get_statistics(self) -> Dict:
        """Get thought exchange statistics"""
        shared_count = len([
            t for t in self.shared_thoughts
            if t.get('status') == 'shared'
        ])
        received_count = len([
            t for t in self.shared_thoughts
            if t.get('status') == 'received'
        ])
        
        gan_shared = len([
            g for g in self.gan_exchange_history
            if g.get('status') == 'shared'
        ])
        gan_received = len([
            g for g in self.gan_exchange_history
            if g.get('status') == 'received'
        ])
        
        return {
            'thoughts_shared': shared_count,
            'thoughts_received': received_count,
            'gan_shared': gan_shared,
            'gan_received': gan_received,
            'total_exchange': len(self.shared_thoughts) + len(self.gan_exchange_history)
        }