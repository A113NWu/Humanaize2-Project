"""
Response Templates
AI-created response templates for common scenarios.
This file is NOT overwritten during updates.
"""

class ResponseTemplates:
    def __init__(self):
        self.templates = {}
        
    def get_template(self, scenario):
        return self.templates.get(scenario, "")
        
    def add_template(self, scenario, template):
        self.templates[scenario] = template
