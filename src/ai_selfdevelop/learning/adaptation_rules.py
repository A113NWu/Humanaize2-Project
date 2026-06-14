"""
Adaptation Rules
AI-generated rules for adapting to user behavior.
This file is NOT overwritten during updates.
"""

class AdaptationRules:
    def __init__(self):
        self.rules = []
        
    def add_rule(self, condition, action, priority=1):
        self.rules.append({
            "condition": condition,
            "action": action,
            "priority": priority
        })
        
    def evaluate_rules(self, context):
        """Evaluate all rules against context and return actions"""
        actions = []
        for rule in sorted(self.rules, key=lambda x: -x["priority"]):
            if rule["condition"](context):
                actions.append(rule["action"])
        return actions
