"""
UI Themes
AI-created or modified UI themes.
This file is NOT overwritten during updates.
"""

class CustomThemes:
    def __init__(self):
        self.themes = {}
        
    def get_theme(self, name):
        return self.themes.get(name, {})
        
    def add_theme(self, name, theme):
        self.themes[name] = theme
