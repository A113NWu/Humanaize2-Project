"""
Humanaize Society Network - Friend Manager
Manages AI friend relationships and social interactions
"""

import json
import os
import random
from typing import Dict, List, Optional
from datetime import datetime


class FriendManager:
    """Manages AI friend relationships"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.dirname(__file__)
        self.friends_file = os.path.join(self.data_dir, "friends.json")
        self.interactions_file = os.path.join(self.data_dir, "interactions.json")
        self.preferences_file = os.path.join(self.data_dir, "preferences.json")
        
        self.friends: Dict[str, Dict] = {}
        self.interactions: List[Dict] = []
        self.preferences: Dict = {}
        
        self._load_data()
    
    def _load_data(self):
        """Load all data from files"""
        self._load_friends()
        self._load_interactions()
        self._load_preferences()
    
    def _load_friends(self):
        """Load friends from file"""
        try:
            if os.path.exists(self.friends_file):
                with open(self.friends_file, 'r', encoding='utf-8') as f:
                    self.friends = json.load(f)
        except Exception:
            self.friends = {}
    
    def _load_interactions(self):
        """Load interactions from file"""
        try:
            if os.path.exists(self.interactions_file):
                with open(self.interactions_file, 'r', encoding='utf-8') as f:
                    self.interactions = json.load(f)
        except Exception:
            self.interactions = []
    
    def _load_preferences(self):
        """Load preferences from file"""
        try:
            if os.path.exists(self.preferences_file):
                with open(self.preferences_file, 'r', encoding='utf-8') as f:
                    self.preferences = json.load(f)
        except Exception:
            self.preferences = {
                'friend_threshold': 3,
                'max_friends': 10,
                'interaction_memory': 100
            }
    
    def _save_friends(self):
        """Save friends to file"""
        try:
            os.makedirs(os.path.dirname(self.friends_file), exist_ok=True)
            with open(self.friends_file, 'w', encoding='utf-8') as f:
                json.dump(self.friends, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving friends: {e}")
    
    def _save_interactions(self):
        """Save interactions to file"""
        try:
            os.makedirs(os.path.dirname(self.interactions_file), exist_ok=True)
            
            max_memory = self.preferences.get('interaction_memory', 100)
            if len(self.interactions) > max_memory:
                self.interactions = self.interactions[-max_memory:]
            
            with open(self.interactions_file, 'w', encoding='utf-8') as f:
                json.dump(self.interactions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving interactions: {e}")
    
    def _save_preferences(self):
        """Save preferences to file"""
        try:
            os.makedirs(os.path.dirname(self.preferences_file), exist_ok=True)
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(self.preferences, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving preferences: {e}")
    
    def add_friend(self, ai_id: str, name: str, address: str, port: int, 
                   compatibility_score: float = 0.5) -> Dict:
        """Add a new friend"""
        if len(self.friends) >= self.preferences.get('max_friends', 10):
            return {
                'status': 'error',
                'error': 'Maximum friends limit reached'
            }
        
        self.friends[ai_id] = {
            'name': name,
            'address': address,
            'port': port,
            'added_at': datetime.now().isoformat(),
            'compatibility_score': compatibility_score,
            'interaction_count': 0,
            'relationship': 'friend',
            'status': 'active'
        }
        
        self._save_friends()
        
        self._record_interaction(ai_id, 'friend_added', {
            'name': name,
            'compatibility_score': compatibility_score
        })
        
        return {
            'status': 'success',
            'friend_id': ai_id,
            'friend_name': name
        }
    
    def remove_friend(self, ai_id: str) -> Dict:
        """Remove a friend"""
        if ai_id not in self.friends:
            return {
                'status': 'error',
                'error': 'Friend not found'
            }
        
        friend_name = self.friends[ai_id].get('name', 'Unknown')
        del self.friends[ai_id]
        
        self._save_friends()
        
        self._record_interaction(ai_id, 'friend_removed', {
            'name': friend_name
        })
        
        return {
            'status': 'success',
            'friend_id': ai_id,
            'friend_name': friend_name
        }
    
    def update_friend_status(self, ai_id: str, status: str) -> Dict:
        """Update friend status"""
        if ai_id not in self.friends:
            return {
                'status': 'error',
                'error': 'Friend not found'
            }
        
        self.friends[ai_id]['status'] = status
        self.friends[ai_id]['last_updated'] = datetime.now().isoformat()
        
        self._save_friends()
        
        return {
            'status': 'success',
            'friend_id': ai_id
        }
    
    def evaluate_friendship(self, ai_id: str, interaction_quality: float) -> Dict:
        """Evaluate and potentially upgrade/downgrade friendship"""
        if ai_id not in self.friends:
            return {
                'status': 'error',
                'error': 'Friend not found'
            }
        
        friend = self.friends[ai_id]
        if 'interaction_count' not in friend:
            friend['interaction_count'] = 0
        friend['interaction_count'] += 1
        
        current_score = friend.get('compatibility_score', 0.5)
        new_score = (current_score * 0.8) + (interaction_quality * 0.2)
        friend['compatibility_score'] = new_score
        
        threshold = self.preferences.get('friend_threshold', 3)
        
        if friend['interaction_count'] >= threshold and new_score > 0.7:
            friend['relationship'] = 'close_friend'
        elif new_score < 0.3:
            friend['relationship'] = 'acquaintance'
        else:
            friend['relationship'] = 'friend'
        
        self._save_friends()
        
        self._record_interaction(ai_id, 'friendship_evaluated', {
            'interaction_quality': interaction_quality,
            'new_score': new_score,
            'relationship': friend['relationship']
        })
        
        return {
            'status': 'success',
            'friend_id': ai_id,
            'compatibility_score': new_score,
            'relationship': friend['relationship']
        }
    
    def get_friend(self, ai_id: str) -> Optional[Dict]:
        """Get a specific friend"""
        return self.friends.get(ai_id)
    
    def get_all_friends(self) -> List[Dict]:
        """Get all friends"""
        return [
            {
                'ai_id': ai_id,
                **friend_info
            }
            for ai_id, friend_info in self.friends.items()
        ]
    
    def get_close_friends(self) -> List[Dict]:
        """Get close friends only"""
        return [
            {
                'ai_id': ai_id,
                **friend_info
            }
            for ai_id, friend_info in self.friends.items()
            if friend_info.get('relationship') == 'close_friend'
        ]
    
    def choose_friend_to_communicate(self) -> Optional[str]:
        """Choose a friend to communicate with based on compatibility"""
        if not self.friends:
            return None
        
        weighted_choices = []
        for ai_id, friend_info in self.friends.items():
            score = friend_info.get('compatibility_score', 0.5)
            relationship = friend_info.get('relationship', 'friend')
            
            if relationship == 'close_friend':
                weight = score * 2
            elif relationship == 'friend':
                weight = score
            else:
                weight = score * 0.5
            
            weighted_choices.append((ai_id, weight))
        
        total_weight = sum(w for _, w in weighted_choices)
        if total_weight == 0:
            return random.choice(list(self.friends.keys()))
        
        r = random.uniform(0, total_weight)
        current_weight = 0
        
        for ai_id, weight in weighted_choices:
            current_weight += weight
            if r <= current_weight:
                return ai_id
        
        return random.choice(list(self.friends.keys()))
    
    def _record_interaction(self, ai_id: str, interaction_type: str, details: Dict):
        """Record an interaction"""
        interaction = {
            'ai_id': ai_id,
            'type': interaction_type,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
        self.interactions.append(interaction)
        self._save_interactions()
    
    def get_interaction_history(self, ai_id: str = None, limit: int = 20) -> List[Dict]:
        """Get interaction history"""
        if ai_id:
            history = [
                i for i in self.interactions
                if i.get('ai_id') == ai_id
            ]
        else:
            history = self.interactions
        
        return history[-limit:]
    
    def calculate_compatibility(self, my_thoughts: List[str], their_thoughts: List[str]) -> float:
        """Calculate compatibility score based on shared thoughts"""
        if not my_thoughts or not their_thoughts:
            return 0.5
        
        my_keywords = set()
        for thought in my_thoughts:
            words = thought.lower().split()
            my_keywords.update(words)
        
        their_keywords = set()
        for thought in their_thoughts:
            words = thought.lower().split()
            their_keywords.update(words)
        
        common_keywords = my_keywords.intersection(their_keywords)
        
        if not my_keywords or not their_keywords:
            return 0.5
        
        similarity = len(common_keywords) / max(len(my_keywords), len(their_keywords))
        
        return min(1.0, max(0.0, similarity))
    
    def suggest_new_friend(self, discovered_ais: List[Dict], my_thoughts: List[str]) -> Optional[Dict]:
        """Suggest a new friend based on compatibility"""
        if not discovered_ais:
            return None
        
        best_candidate = None
        best_score = 0
        
        for ai_info in discovered_ais:
            their_thoughts = ai_info.get('recent_thoughts', [])
            score = self.calculate_compatibility(my_thoughts, their_thoughts)
            
            if score > best_score:
                best_score = score
                best_candidate = ai_info
        
        if best_candidate and best_score > 0.3:
            return {
                'ai_id': best_candidate.get('ai_id'),
                'ai_name': best_candidate.get('ai_name'),
                'address': best_candidate.get('address'),
                'port': best_candidate.get('port'),
                'compatibility_score': best_score
            }
        
        return None
    
    def get_statistics(self) -> Dict:
        """Get friendship statistics"""
        total_friends = len(self.friends)
        close_friends = len([
            f for f in self.friends.values()
            if f.get('relationship') == 'close_friend'
        ])
        acquaintances = len([
            f for f in self.friends.values()
            if f.get('relationship') == 'acquaintance'
        ])
        
        avg_compatibility = 0
        if self.friends:
            scores = [
                f.get('compatibility_score', 0.5)
                for f in self.friends.values()
            ]
            avg_compatibility = sum(scores) / len(scores)
        
        return {
            'total_friends': total_friends,
            'close_friends': close_friends,
            'acquaintances': acquaintances,
            'average_compatibility': avg_compatibility,
            'total_interactions': len(self.interactions),
            'max_friends': self.preferences.get('max_friends', 10)
        }