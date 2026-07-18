"""
Behavior Models
AI-learned behavior patterns and prediction models.
This file is NOT overwritten during updates.
"""

import json
import os
from datetime import datetime

class BehaviorModel:
    def __init__(self):
        self.predictions = {}
        self.adaptation_rules = []
        self.user_interactions = []
        self.learning_enabled = True
        self._load_model()
        
    def _load_model(self):
        """Load saved behavior model from file"""
        model_path = os.path.join(os.path.dirname(__file__), 'behavior_model.json')
        if os.path.exists(model_path):
            try:
                with open(model_path, 'r') as f:
                    data = json.load(f)
                    self.predictions = data.get('predictions', {})
                    self.adaptation_rules = data.get('adaptation_rules', [])
                    self.user_interactions = data.get('user_interactions', [])
            except:
                pass
                
    def _save_model(self):
        """Save behavior model to file"""
        model_path = os.path.join(os.path.dirname(__file__), 'behavior_model.json')
        try:
            with open(model_path, 'w') as f:
                json.dump({
                    'predictions': self.predictions,
                    'adaptation_rules': self.adaptation_rules,
                    'user_interactions': self.user_interactions,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except:
            pass
            
    def record_interaction(self, user_input, response, success=True, feedback=None):
        """Record user interaction for learning"""
        if not self.learning_enabled:
            return
            
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input[:500],
            'response_type': self._classify_response(response),
            'success': success,
            'feedback': feedback,
            'input_length': len(user_input),
            'response_length': len(response) if response else 0
        }
        self.user_interactions.append(interaction)
        
        # Keep only last 1000 interactions
        if len(self.user_interactions) > 1000:
            self.user_interactions = self.user_interactions[-1000:]
            
        self._update_models()
        self._save_model()
        
    def _classify_response(self, response):
        """Classify response type for learning"""
        if not response:
            return 'empty'
        response_lower = response.lower()
        if any(word in response_lower for word in ['sorry', 'apologize', 'can not', 'cannot', 'unable']):
            return 'apology'
        elif any(word in response_lower for word in ['question', 'what', 'how', 'why', 'when', 'where']):
            return 'question'
        elif any(word in response_lower for word in ['thank', 'thanks', 'great', 'good']):
            return 'positive'
        elif len(response) < 50:
            return 'short'
        elif len(response) > 500:
            return 'detailed'
        else:
            return 'normal'
            
    def _update_models(self):
        """Update prediction models based on interactions"""
        if len(self.user_interactions) < 10:
            return
            
        # Analyze response type distribution
        type_counts = {}
        for interaction in self.user_interactions:
            rtype = interaction['response_type']
            type_counts[rtype] = type_counts.get(rtype, 0) + 1
        
        self.predictions['response_type_distribution'] = type_counts
        
        # Calculate average response length
        avg_length = sum(i['response_length'] for i in self.user_interactions) / len(self.user_interactions)
        self.predictions['average_response_length'] = avg_length
        
        # Learn preferred response style
        self._learn_response_style()
        
    def _learn_response_style(self):
        """Learn user's preferred response style from interactions"""
        short_responses = [i for i in self.user_interactions if i['response_type'] == 'short']
        detailed_responses = [i for i in self.user_interactions if i['response_type'] == 'detailed']
        
        if len(short_responses) > len(detailed_responses) * 1.5:
            self.predictions['preferred_style'] = 'concise'
        elif len(detailed_responses) > len(short_responses) * 1.5:
            self.predictions['preferred_style'] = 'detailed'
        else:
            self.predictions['preferred_style'] = 'balanced'
            
    def predict_response_style(self, context):
        """Predict optimal response style based on context and learning"""
        return self.predictions.get('preferred_style', 'friendly')
        
    def should_interrupt(self, context):
        """Determine if AI should interrupt user"""
        # Only interrupt if user has been silent for a while and we have important info
        return False
        
    def get_preferred_topics(self):
        """Return list of topics user is likely interested in"""
        # Analyze past interactions to find common topics
        topics = []
        keyword_patterns = {
            'technology': ['tech', 'computer', 'programming', 'code', 'software', 'ai', 'machine learning'],
            'entertainment': ['movie', 'game', 'music', 'book', 'video'],
            'productivity': ['task', 'todo', 'work', 'project', 'deadline'],
            'learning': ['learn', 'study', 'education', 'course', 'knowledge'],
            'health': ['health', 'exercise', 'diet', 'sleep', 'mental']
        }
        
        for interaction in self.user_interactions[-50:]:
            input_text = interaction['user_input'].lower()
            for topic, keywords in keyword_patterns.items():
                if any(keyword in input_text for keyword in keywords):
                    if topic not in topics:
                        topics.append(topic)
        
        return topics[:5]
        
    def suggest_improvement(self):
        """Suggest improvements based on learning"""
        suggestions = []
        
        # Check if user often gets apologies (indicating failures)
        apology_count = sum(1 for i in self.user_interactions if i['response_type'] == 'apology')
        if apology_count > len(self.user_interactions) * 0.1:
            suggestions.append({
                'priority': 'high',
                'message': 'User is receiving many apology responses. Consider improving fallback mechanisms or expanding knowledge base.',
                'action': 'improve_fallback'
            })
        
        # Check interaction frequency
        if len(self.user_interactions) > 100:
            suggestions.append({
                'priority': 'medium',
                'message': 'User has interacted many times. Consider offering personalized features.',
                'action': 'personalize'
            })
        
        return suggestions
        
    def enable_learning(self):
        """Enable AI learning"""
        self.learning_enabled = True
        
    def disable_learning(self):
        """Disable AI learning"""
        self.learning_enabled = False
