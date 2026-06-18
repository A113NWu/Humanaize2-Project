"""
AI Selfdevelop Module
This module contains files that AI can modify to adapt to user preferences.
These files are NOT overwritten during updates.

Features:
- Behavior Learning: AI learns from user interactions
- Adaptive Rules: AI creates rules to adapt behavior
- Web Search Integration: AI can search the internet when unsure
- Continuous Improvement: AI gets better over time
"""

__all__ = ['skills', 'preferences', 'learning', 'customizations']

# Version info
__version__ = '2.2.3'

# Initialize learning modules
from .learning import BehaviorModel, AdaptationRules

# Create singleton instances
behavior_model = BehaviorModel()
adaptation_rules = AdaptationRules()

def get_behavior_model():
    """Get the behavior model singleton"""
    return behavior_model

def get_adaptation_rules():
    """Get the adaptation rules singleton"""
    return adaptation_rules

def learn_from_interaction(user_input, response, success=True, feedback=None):
    """Learn from user interaction"""
    behavior_model.record_interaction(user_input, response, success, feedback)
    
def suggest_improvements():
    """Get improvement suggestions based on learning"""
    return behavior_model.suggest_improvement()
