"""
User Profile
AI-maintained user profile containing learned preferences.
This file is NOT overwritten during updates.
"""

class UserProfile:
    def __init__(self):
        self.name = ""
        self.preferred_language = "zh"
        self.interests = []
        self.avoid_topics = []
        self.response_style = "friendly"  # formal, friendly, concise, detailed
        self.preferred_time_of_day = None
        self.usage_patterns = {}
        
    def to_dict(self):
        return {
            "name": self.name,
            "preferred_language": self.preferred_language,
            "interests": self.interests,
            "avoid_topics": self.avoid_topics,
            "response_style": self.response_style,
            "preferred_time_of_day": self.preferred_time_of_day,
            "usage_patterns": self.usage_patterns
        }
        
    def from_dict(self, data):
        self.name = data.get("name", "")
        self.preferred_language = data.get("preferred_language", "zh")
        self.interests = data.get("interests", [])
        self.avoid_topics = data.get("avoid_topics", [])
        self.response_style = data.get("response_style", "friendly")
        self.preferred_time_of_day = data.get("preferred_time_of_day")
        self.usage_patterns = data.get("usage_patterns", {})
