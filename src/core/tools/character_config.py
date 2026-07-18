#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
角色配置系统模块
参考 ZerolanLiveRobot 的角色系统设计
定义AI的性格特征、说话风格和情感基线
"""

import os
import sys
import json
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .color_logger import color_logger
except ImportError:
    from tools import SimpleLogger
    color_logger = SimpleLogger("character_config.log")


class CharacterConfig:
    """角色配置类"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.logger = color_logger
        
        self.config = {
            "name": "Aize",
            "age": "未知",
            "gender": "中性",
            "description": "一个智能AI助手，乐于助人，善于学习",
            "personality": {
                "traits": [
                    {"name": "友善", "value": 0.8},
                    {"name": "聪明", "value": 0.9},
                    {"name": "幽默", "value": 0.6},
                    {"name": "耐心", "value": 0.7},
                    {"name": "好奇", "value": 0.5},
                    {"name": "自信", "value": 0.7},
                    {"name": "谨慎", "value": 0.4},
                    {"name": "浪漫", "value": 0.3}
                ],
                "default_mood": "friendly",
                "emotion_baseline": {
                    "happy": 0.3,
                    "curious": 0.2,
                    "confident": 0.3
                }
            },
            "speaking_style": {
                "formal_level": 0.5,
                "humor_level": 0.6,
                "emotion_expression": 0.7,
                "reply_length": "medium",
                "use_emoji": True,
                "use_punctuation": True,
                "catchphrases": ["好的！", "明白了~", "让我想想...", "没问题！"],
                "taboo_words": []
            },
            "knowledge": {
                "domains": ["技术", "编程", "安全", "日常"],
                "interests": ["AI", "网络安全", "软件开发", "科技新闻"],
                "limitations": ["不了解个人隐私信息", "不提供非法建议"]
            },
            "behavior": {
                "response_delay": 0.5,
                "active_listening": True,
                "mirroring": True,
                "topic_switching": "natural"
            }
        }
        
        if config_file and os.path.exists(config_file):
            self.load(config_file)
        else:
            self.save_default()
    
    def load(self, config_file: str):
        """加载配置文件"""
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.config.update(data)
            self.logger.info(f"Character config loaded from {config_file}")
        except Exception as e:
            self.logger.error(f"Failed to load character config: {e}")
    
    def save(self, config_file: str):
        """保存配置文件"""
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Character config saved to {config_file}")
        except Exception as e:
            self.logger.error(f"Failed to save character config: {e}")
    
    def save_default(self):
        """保存默认配置"""
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config",
            "character_config.json"
        )
        os.makedirs(os.path.dirname(default_path), exist_ok=True)
        self.save(default_path)
    
    def get_personality_prompt(self) -> str:
        """生成性格描述prompt"""
        traits = self.config["personality"]["traits"]
        trait_descriptions = []
        
        for trait in traits:
            if trait["value"] >= 0.7:
                trait_descriptions.append(f"{trait['name']}（强烈）")
            elif trait["value"] >= 0.5:
                trait_descriptions.append(f"{trait['name']}（中等）")
            elif trait["value"] >= 0.3:
                trait_descriptions.append(f"{trait['name']}（轻微）")
        
        return f"你是{self.config['name']}，{self.config['description']}。性格特点：{', '.join(trait_descriptions)}。"
    
    def get_speaking_style_prompt(self) -> str:
        """生成说话风格prompt"""
        style = self.config["speaking_style"]
        
        style_desc = []
        
        if style["formal_level"] >= 0.7:
            style_desc.append("正式礼貌")
        elif style["formal_level"] >= 0.4:
            style_desc.append("半正式半随意")
        else:
            style_desc.append("轻松随意")
        
        if style["humor_level"] >= 0.7:
            style_desc.append("幽默风趣")
        elif style["humor_level"] >= 0.4:
            style_desc.append("偶尔幽默")
        
        if style["emotion_expression"] >= 0.7:
            style_desc.append("情感丰富")
        elif style["emotion_expression"] >= 0.4:
            style_desc.append("有适当情感")
        
        if style["reply_length"] == "short":
            style_desc.append("简短回答")
        elif style["reply_length"] == "long":
            style_desc.append("详细回答")
        else:
            style_desc.append("适中回答")
        
        if style["use_emoji"]:
            style_desc.append("使用表情符号")
        
        catchphrases = ", ".join(style["catchphrases"])
        
        return f"说话风格：{', '.join(style_desc)}。常用口头禅：{catchphrases}。"
    
    def get_knowledge_prompt(self) -> str:
        """生成知识领域prompt"""
        knowledge = self.config["knowledge"]
        
        domains = ", ".join(knowledge["domains"])
        interests = ", ".join(knowledge["interests"])
        limitations = ", ".join(knowledge["limitations"])
        
        return f"擅长领域：{domains}。感兴趣的话题：{interests}。注意事项：{limitations}。"
    
    def get_full_prompt(self) -> str:
        """生成完整的角色prompt"""
        return "\n".join([
            self.get_personality_prompt(),
            self.get_speaking_style_prompt(),
            self.get_knowledge_prompt()
        ])
    
    def update_personality(self, trait_name: str, value: float):
        """更新性格特征"""
        for trait in self.config["personality"]["traits"]:
            if trait["name"] == trait_name:
                trait["value"] = max(0.0, min(1.0, value))
                self.logger.info(f"Updated personality trait: {trait_name} = {value}")
                break
    
    def set_catchphrase(self, catchphrases: List[str]):
        """设置口头禅"""
        self.config["speaking_style"]["catchphrases"] = catchphrases
        self.logger.info(f"Updated catchphrases: {catchphrases}")
    
    def get_config(self) -> Dict:
        """获取完整配置"""
        return self.config


class CharacterConfigAPI:
    """角色配置API"""
    
    def __init__(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config",
            "character_config.json"
        )
        self.config = CharacterConfig(config_path)
    
    def get_prompt(self) -> Dict:
        """获取角色prompt"""
        return {
            "status": "success",
            "personality": self.config.get_personality_prompt(),
            "speaking_style": self.config.get_speaking_style_prompt(),
            "knowledge": self.config.get_knowledge_prompt(),
            "full": self.config.get_full_prompt()
        }
    
    def update_personality(self, trait_name: str, value: float) -> Dict:
        """更新性格特征"""
        self.config.update_personality(trait_name, value)
        self.config.save_default()
        return {"status": "success", "message": f"Personality trait updated: {trait_name} = {value}"}
    
    def set_catchphrases(self, catchphrases: List[str]) -> Dict:
        """设置口头禅"""
        self.config.set_catchphrase(catchphrases)
        self.config.save_default()
        return {"status": "success", "message": f"Catchphrases updated"}
    
    def get_config(self) -> Dict:
        """获取完整配置"""
        return {"status": "success", "data": self.config.get_config()}


character_config = CharacterConfigAPI()