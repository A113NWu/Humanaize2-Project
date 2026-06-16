"""
Interaction History
AI-tracked user interaction patterns.
This file is NOT overwritten during updates.
"""

class InteractionHistory:
    def __init__(self):
        self.conversations = []
        self.skill_usage = {}
        self.topic_frequency = {}
        self.response_ratings = []
        
    def record_conversation(self, user_input, ai_response, timestamp=None):
        import time
        self.conversations.append({
            "user_input": user_input,
            "ai_response": ai_response,
            "timestamp": timestamp or time.time()
        })
        
    def record_skill_usage(self, skill_name, success=True):
        if skill_name not in self.skill_usage:
            self.skill_usage[skill_name] = {"used": 0, "success": 0}
        self.skill_usage[skill_name]["used"] += 1
        if success:
            self.skill_usage[skill_name]["success"] += 1
