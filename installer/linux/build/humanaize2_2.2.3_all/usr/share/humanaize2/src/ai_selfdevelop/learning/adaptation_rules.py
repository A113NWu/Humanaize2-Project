"""
Adaptation Rules
AI-generated rules for adapting to user behavior.
This file is NOT overwritten during updates.
"""

import json
import os
from datetime import datetime

class AdaptationRules:
    def __init__(self):
        self.rules = []
        self._load_rules()
        self._initialize_default_rules()
        
    def _load_rules(self):
        """Load saved rules from file"""
        rules_path = os.path.join(os.path.dirname(__file__), 'adaptation_rules.json')
        if os.path.exists(rules_path):
            try:
                with open(rules_path, 'r') as f:
                    data = json.load(f)
                    self.rules = data.get('rules', [])
            except:
                pass
                
    def _save_rules(self):
        """Save rules to file"""
        rules_path = os.path.join(os.path.dirname(__file__), 'adaptation_rules.json')
        try:
            with open(rules_path, 'w') as f:
                json.dump({
                    'rules': self.rules,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except:
            pass
            
    def _initialize_default_rules(self):
        """Initialize default adaptation rules if none exist"""
        if len(self.rules) > 0:
            return
            
        # Default rules based on common user patterns
        default_rules = [
            {
                "name": "short_response_when_busy",
                "condition": lambda ctx: ctx.get('user_message_length', 0) < 20 and ctx.get('time_of_day', '') in ['morning', 'evening'],
                "action": "RESPONSE_CONCISE",
                "priority": 3,
                "description": "Use short responses when user sends brief messages during busy times"
            },
            {
                "name": "detailed_response_for_complex",
                "condition": lambda ctx: ctx.get('user_message_length', 0) > 100 or ctx.get('is_question', False),
                "action": "RESPONSE_DETAILED",
                "priority": 3,
                "description": "Provide detailed responses for long messages or questions"
            },
            {
                "name": "friendly_greeting_morning",
                "condition": lambda ctx: ctx.get('time_of_day', '') == 'morning' and ctx.get('interaction_count', 0) == 0,
                "action": "GREETING_MORNING",
                "priority": 2,
                "description": "Use morning greeting for first interaction of the day"
            },
            {
                "name": "friendly_greeting_evening",
                "condition": lambda ctx: ctx.get('time_of_day', '') == 'evening' and ctx.get('interaction_count', 0) == 0,
                "action": "GREETING_EVENING",
                "priority": 2,
                "description": "Use evening greeting for first interaction of the evening"
            },
            {
                "name": "use_search_for_unknown",
                "condition": lambda ctx: ctx.get('confidence', 1.0) < 0.5 or ctx.get('needs_search', False),
                "action": "USE_WEB_SEARCH",
                "priority": 4,
                "description": "Perform web search when confidence is low or topic requires up-to-date information"
            },
            {
                "name": "follow_up_on_feedback",
                "condition": lambda ctx: ctx.get('user_feedback', '') in ['positive', 'negative'],
                "action": "FOLLOW_UP_FEEDBACK",
                "priority": 3,
                "description": "Follow up on user feedback"
            },
            {
                "name": "avoid_interrupting_long_task",
                "condition": lambda ctx: ctx.get('user_is_busy', False) or ctx.get('task_duration', 0) > 300,
                "action": "DO_NOT_INTERRUPT",
                "priority": 5,
                "description": "Avoid interrupting user during long tasks"
            },
            {
                "name": "summarize_long_conversation",
                "condition": lambda ctx: ctx.get('conversation_length', 0) > 10,
                "action": "SUMMARIZE_CONVERSATION",
                "priority": 2,
                "description": "Offer to summarize long conversations"
            }
        ]
        
        for rule in default_rules:
            self.add_rule(rule['condition'], rule['action'], rule['priority'], rule.get('description', ''), rule.get('name', ''))
            
        self._save_rules()
        
    def add_rule(self, condition, action, priority=1, description='', name=''):
        """Add a new adaptation rule"""
        rule = {
            "condition": condition,
            "action": action,
            "priority": priority,
            "description": description,
            "name": name,
            "added_at": datetime.now().isoformat(),
            "enabled": True
        }
        self.rules.append(rule)
        self._save_rules()
        
    def remove_rule(self, rule_name):
        """Remove a rule by name"""
        self.rules = [r for r in self.rules if r.get('name') != rule_name]
        self._save_rules()
        
    def enable_rule(self, rule_name):
        """Enable a rule"""
        for rule in self.rules:
            if rule.get('name') == rule_name:
                rule['enabled'] = True
        self._save_rules()
        
    def disable_rule(self, rule_name):
        """Disable a rule"""
        for rule in self.rules:
            if rule.get('name') == rule_name:
                rule['enabled'] = False
        self._save_rules()
        
    def evaluate_rules(self, context):
        """Evaluate all rules against context and return actions"""
        actions = []
        enabled_rules = [r for r in self.rules if r.get('enabled', True)]
        
        for rule in sorted(enabled_rules, key=lambda x: -x['priority']):
            try:
                if rule["condition"](context):
                    actions.append({
                        'action': rule['action'],
                        'priority': rule['priority'],
                        'description': rule.get('description', ''),
                        'name': rule.get('name', '')
                    })
            except Exception as e:
                # Skip rules that fail to evaluate
                continue
                
        return actions
        
    def learn_from_interaction(self, user_input, response, success, context):
        """Learn from user interaction and potentially create new rules"""
        # Analyze what worked well
        if success:
            # If response was well-received, reinforce related rules
            response_length = len(response)
            input_length = len(user_input)
            
            # Create adaptive rules based on successful interactions
            if response_length < 50 and input_length < 30:
                # Short response worked for short input
                self._reinforce_rule('short_response_when_busy')
            elif response_length > 200 and input_length > 50:
                # Detailed response worked for long input
                self._reinforce_rule('detailed_response_for_complex')
                
    def _reinforce_rule(self, rule_name):
        """Increase priority of a rule"""
        for rule in self.rules:
            if rule.get('name') == rule_name:
                rule['priority'] = min(rule['priority'] + 1, 10)
        self._save_rules()
        
    def get_rules_summary(self):
        """Get summary of all rules"""
        summary = []
        for rule in self.rules:
            summary.append({
                'name': rule.get('name', 'Unnamed'),
                'priority': rule['priority'],
                'enabled': rule.get('enabled', True),
                'description': rule.get('description', '')
            })
        return summary
