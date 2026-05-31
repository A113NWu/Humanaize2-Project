"""
Humanaize Skills System
OpenClaw-compatible skills management with full execution support
"""

import os
import re
import json
import yaml
import importlib
import inspect
from typing import Dict, List, Optional, Any, Callable


class Skill:
    """Represents a single skill"""
    
    def __init__(self, name: str, description: str, instructions: str, metadata: Dict = None):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.metadata = metadata or {}
        self.enabled = True
        self.executor: Optional[Callable] = None
        self.skill_dir: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "metadata": self.metadata,
            "enabled": self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Skill':
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            instructions=data.get("instructions", ""),
            metadata=data.get("metadata", {}),
            enabled=data.get("enabled", True)
        )
    
    def execute(self, input_data: Any) -> Dict:
        """Execute the skill with given input"""
        if not self.enabled:
            return {"error": f"Skill '{self.name}' is disabled"}
        
        if self.executor:
            try:
                return self.executor(input_data)
            except Exception as e:
                return {"error": f"Execution error: {str(e)}"}
        else:
            return {"error": f"No executor registered for skill '{self.name}'"}


class SkillsManager:
    """Manages all skills, OpenClaw-compatible with full execution support"""
    
    def __init__(self, skills_dir: str = None):
        self.skills: Dict[str, Skill] = {}
        self.skills_dir = skills_dir or os.path.join(os.path.dirname(__file__), "skills")
        self.skills_config_path = os.path.join(os.path.dirname(__file__), "data", "skills_config.json")
        self.skills_config: Dict = {}
        self._skill_executors: Dict[str, Callable] = {}
        self._language_adapter = None
        self._ensure_skills_dir()
        self._load_skills_config()
        self._register_default_executors()
        self.load_skills()
    
    def _ensure_skills_dir(self):
        os.makedirs(self.skills_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.skills_config_path), exist_ok=True)
    
    def _load_skills_config(self):
        """Load skills configuration from file"""
        try:
            if os.path.exists(self.skills_config_path):
                with open(self.skills_config_path, 'r', encoding='utf-8') as f:
                    self.skills_config = json.load(f)
        except Exception as e:
            print(f"Error loading skills config: {e}")
            self.skills_config = {
                'skills': {},
                'all_enabled': False
            }
    
    def _save_skills_config(self):
        """Save skills configuration to file"""
        try:
            with open(self.skills_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.skills_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving skills config: {e}")
    
    def _register_default_executors(self):
        """Register default skill executors"""
        self._skill_executors = {
            "shell": self._execute_shell,
            "file-read": self._execute_file_read,
            "file-write": self._execute_file_write,
            "memory": self._execute_memory,
            "reminder": self._execute_reminder,
            "web-search": self._execute_web_search,
            "web-fetch": self._execute_web_fetch,
            "humanaize-society-network": self._execute_society_network,
            "detect-emotion": self._execute_detect_emotion,
        }
    
    def load_skills(self):
        """Load all skills from skills directory"""
        self.skills = {}

        if not os.path.exists(self.skills_dir):
            return

        for skill_name in os.listdir(self.skills_dir):
            skill_path = os.path.join(self.skills_dir, skill_name)
            if os.path.isdir(skill_path):
                skill_file = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(skill_file):
                    skill = self._parse_skill_file(skill_file)
                    if skill:
                        skill.skill_dir = skill_path

                        all_enabled = self.skills_config.get('all_enabled', False)
                        skill.enabled = all_enabled

                        skills_config = self.skills_config.get('skills', {})
                        for config_name, config_data in skills_config.items():
                            if config_name.lower() == skill.name.lower():
                                skill.enabled = config_data.get('enabled', False) or all_enabled
                                break

                        self.skills[skill.name] = skill

                        if not self._try_load_skill_module(skill):
                            if skill.name in self._skill_executors:
                                skill.executor = self._skill_executors[skill.name]
    
    def _parse_skill_file(self, filepath: str) -> Optional[Skill]:
        """Parse a SKILL.md file (OpenClaw format)"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            frontmatter, instructions = self._extract_frontmatter(content)
            
            if not frontmatter:
                return None
            
            name = frontmatter.get("name", "")
            description = frontmatter.get("description", "")
            metadata = frontmatter.get("metadata", {})
            
            if not name:
                return None
            
            return Skill(name, description, instructions, metadata)
        except Exception as e:
            print(f"Error parsing skill file {filepath}: {e}")
            return None
    
    def _extract_frontmatter(self, content: str) -> tuple:
        """Extract YAML frontmatter from SKILL.md content"""
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return None, content

        try:
            frontmatter = yaml.safe_load(match.group(1))
            instructions = match.group(2).strip()
            return frontmatter, instructions
        except yaml.YAMLError:
            return None, content

    def _try_load_skill_module(self, skill: 'Skill'):
        """Try to load execute function from skill's __init__.py module"""
        try:
            if not skill.skill_dir:
                return False

            init_file = os.path.join(skill.skill_dir, "__init__.py")
            if not os.path.exists(init_file):
                return False

            folder_name = os.path.basename(skill.skill_dir)
            module_name = f"skills.{folder_name}"

            importlib.invalidate_caches()
            module = importlib.import_module(module_name)

            if hasattr(module, 'execute'):
                skill.executor = module.execute
                return True

            spec = importlib.util.spec_from_file_location(f"skills_{folder_name}", init_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'execute'):
                    skill.executor = module.execute
                    return True

        except Exception as e:
            pass

        return False
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name"""
        return self.skills.get(name)
    
    def get_all_skills(self) -> List[Skill]:
        """Get all skills"""
        return list(self.skills.values())
    
    def get_enabled_skills(self) -> List[Skill]:
        """Get all enabled skills"""
        return [s for s in self.skills.values() if s.enabled]
    
    def _find_skill_name(self, name: str) -> Optional[str]:
        """Find skill name by case-insensitive match or alias"""
        name_lower = name.lower()
        
        if name in self.skills:
            return name
        
        for skill_name in self.skills:
            if skill_name.lower() == name_lower:
                return skill_name
        
        aliases = {
            'hsn': 'humanaize-society-network',
        }
        
        if name_lower in aliases:
            target = aliases[name_lower]
            for skill_name in self.skills:
                if skill_name.lower() == target.lower():
                    return skill_name
        
        return None
    
    def enable_skill(self, name: str):
        """Enable a skill"""
        actual_name = self._find_skill_name(name)
        if actual_name and actual_name in self.skills:
            self.skills[actual_name].enabled = True
            
            if 'skills' not in self.skills_config:
                self.skills_config['skills'] = {}
            
            self.skills_config['skills'][actual_name] = {
                'enabled': True,
                'enabled_at': self._get_timestamp()
            }
            
            self._save_skills_config()
    
    def disable_skill(self, name: str):
        """Disable a skill"""
        actual_name = self._find_skill_name(name)
        if actual_name and actual_name in self.skills:
            self.skills[actual_name].enabled = False
            
            if 'skills' not in self.skills_config:
                self.skills_config['skills'] = {}
            
            self.skills_config['skills'][actual_name] = {
                'enabled': False,
                'disabled_at': self._get_timestamp()
            }
            
            self._save_skills_config()
    
    def enable_all_skills(self):
        """Enable all skills"""
        for name in self.skills:
            self.skills[name].enabled = True
        
        self.skills_config['all_enabled'] = True
        self._save_skills_config()
    
    def disable_all_skills(self):
        """Disable all skills"""
        for name in self.skills:
            self.skills[name].enabled = False
        
        self.skills_config['all_enabled'] = False
        self._save_skills_config()
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def register_executor(self, skill_name: str, executor: Callable):
        """Register a custom executor for a skill"""
        self._skill_executors[skill_name] = executor
        if skill_name in self.skills:
            self.skills[skill_name].executor = executor
    
    def create_skill(self, name: str, description: str, instructions: str, metadata: Dict = None):
        """Create a new skill"""
        skill = Skill(name, description, instructions, metadata)
        self.skills[name] = skill
        self._save_skill(skill)
    
    def _save_skill(self, skill: Skill):
        """Save a skill to SKILL.md file"""
        skill_dir = os.path.join(self.skills_dir, skill.name)
        os.makedirs(skill_dir, exist_ok=True)
        
        skill_file = os.path.join(skill_dir, "SKILL.md")
        
        frontmatter = {
            "name": skill.name,
            "description": skill.description
        }
        if skill.metadata:
            frontmatter["metadata"] = skill.metadata
        
        yaml_frontmatter = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        
        content = f"---\n{yaml_frontmatter}---\n\n{skill.instructions}"
        
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(content)
    
    def delete_skill(self, name: str):
        """Delete a skill"""
        if name in self.skills:
            del self.skills[name]
            skill_dir = os.path.join(self.skills_dir, name)
            if os.path.exists(skill_dir):
                import shutil
                shutil.rmtree(skill_dir)
    
    def get_skills_prompt(self, language: str = "en") -> str:
        """Generate a prompt containing all enabled skills"""
        enabled_skills = self.get_enabled_skills()

        if not enabled_skills:
            return ""

        prompts = {
            "en": "# Available Skills\n\nYou have access to the following skills. Use them when needed:\n\n",
            "zh": "# 可用技能\n\n你可以使用以下技能：\n\n",
            "zh-TW": "# 可用技能\n\n你可以使用以下技能：\n\n",
        }

        prompt = prompts.get(language, prompts["en"])

        for skill in enabled_skills:
            prompt += f"- **{skill.name}**: {skill.description}\n"

        prompt += "\n**To use a skill, output JSON like:** {\"skill\": \"skill-name\", \"input\": \"...\"}\n"

        return prompt
    
    def execute_skill(self, skill_name: str, input_data: Any, language: str = "en") -> Dict:
        """Execute a skill with given input"""
        skill = self.get_skill(skill_name)
        
        if not skill:
            error_messages = {
                "en": f"Skill '{skill_name}' not found",
                "zh": f"未找到技能 '{skill_name}'",
                "zh-TW": f"未找到技能 '{skill_name}'",
            }
            return {"error": error_messages.get(language, error_messages["en"])}
        
        if not skill.enabled:
            error_messages = {
                "en": f"Skill '{skill_name}' is disabled",
                "zh": f"技能 '{skill_name}' 已禁用",
                "zh-TW": f"技能 '{skill_name}' 已停用",
            }
            return {"error": error_messages.get(language, error_messages["en"])}
        
        try:
            result = skill.execute(input_data)
            return self._adapt_response_language(result, language)
        except Exception as e:
            error_messages = {
                "en": f"Execution error: {str(e)}",
                "zh": f"执行错误：{str(e)}",
                "zh-TW": f"執行錯誤：{str(e)}",
            }
            return {"error": error_messages.get(language, error_messages["en"])}
    
    def _adapt_response_language(self, response: Dict, language: str) -> Dict:
        """Adapt response to match the user's language"""
        if not isinstance(response, dict):
            return response
        
        if language == "en":
            return response
        
        translations = {
            "zh": {
                "success": "成功",
                "error": "错误",
                "status": "状态",
                "result": "结果",
                "message": "消息",
                "output": "输出",
                "content": "内容",
                "file": "文件",
                "path": "路径",
                "status": "状态",
            },
            "zh-TW": {
                "success": "成功",
                "error": "錯誤",
                "status": "狀態",
                "result": "結果",
                "message": "消息",
                "output": "輸出",
                "content": "內容",
                "file": "文件",
                "path": "路徑",
                "status": "狀態",
            }
        }
        
        if language not in translations:
            return response
        
        trans = translations[language]
        adapted = response.copy()
        
        for key, value in response.items():
            if key.lower() in ["error", "status"] and isinstance(value, str):
                continue
            
            if isinstance(value, dict):
                adapted[key] = self._adapt_response_language(value, language)
            elif isinstance(value, list):
                adapted[key] = [
                    self._adapt_response_language(item, language) if isinstance(item, dict) else item
                    for item in value
                ]
        
        return adapted
    
    def _execute_shell(self, input_data: Any) -> Dict:
        """Execute shell command"""
        if isinstance(input_data, dict):
            cmd = input_data.get('command', '')
            cwd = input_data.get('cwd')
        else:
            cmd = str(input_data)
            cwd = None
        
        try:
            import subprocess
            kwargs = {"shell": True, "capture_output": True, "text": True, "timeout": 30}
            if cwd:
                kwargs["cwd"] = cwd
            
            result = subprocess.run(cmd, **kwargs)
            output = (result.stdout or "") + (result.stderr or "")
            
            return {
                "status": "success",
                "output": output.strip(),
                "return_code": result.returncode
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_file_read(self, input_data: Any) -> Dict:
        """Execute file read"""
        if isinstance(input_data, dict):
            path = input_data.get('path', '')
            limit = input_data.get('limit', 2000)
            offset = input_data.get('offset', 0)
        else:
            path = str(input_data)
            limit = 2000
            offset = 0
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                start = max(0, offset)
                end = min(len(lines), offset + limit)
                content = ''.join(lines[start:end])
            
            return {
                "status": "success",
                "content": content,
                "path": path,
                "lines_read": end - start,
                "total_lines": len(lines)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_file_write(self, input_data: Any) -> Dict:
        """Execute file write"""
        if isinstance(input_data, dict):
            path = input_data.get('path', '')
            content = input_data.get('content', '')
            mode = input_data.get('mode', 'write')
        else:
            return {"error": "file-write requires path and content"}
        
        try:
            write_mode = 'w' if mode == 'write' else 'a'
            with open(path, write_mode, encoding='utf-8') as f:
                f.write(content)
            
            return {
                "status": "success",
                "path": path,
                "bytes_written": len(content.encode('utf-8'))
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_memory(self, input_data: Any) -> Dict:
        """Execute memory operation"""
        if isinstance(input_data, dict):
            action = input_data.get('action', 'status')
            limit = input_data.get('limit', 10)
        else:
            action = 'status'
            limit = 10
        
        try:
            from memory import load_memory
            memory = load_memory()
            
            if action == 'recall':
                msgs = memory.get('messages', [])[-limit:]
                return {"status": "success", "messages": msgs, "count": len(msgs)}
            elif action == 'status':
                return {
                    "status": "success",
                    "messages": len(memory.get('messages', [])),
                    "thoughts": len(memory.get('thoughts', [])),
                    "decisions": len(memory.get('decisions', []))
                }
            elif action == 'thoughts':
                thoughts = memory.get('thoughts', [])[-limit:]
                return {"status": "success", "thoughts": thoughts, "count": len(thoughts)}
            else:
                return {"error": f"Unknown memory action: {action}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_reminder(self, input_data: Any) -> Dict:
        """Execute reminder operation"""
        if isinstance(input_data, dict):
            message = input_data.get('message', '')
            delay_minutes = input_data.get('delay_minutes', 0)
            repeat = input_data.get('repeat', False)
        else:
            return {"error": "reminder requires message and delay_minutes"}
        
        try:
            from datetime import datetime, timedelta
            scheduled_time = datetime.now() + timedelta(minutes=delay_minutes)
            
            return {
                "status": "scheduled",
                "message": message,
                "delay_minutes": delay_minutes,
                "scheduled_at": scheduled_time.isoformat(),
                "repeat": repeat,
                "note": "Reminder has been scheduled"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_web_search(self, input_data: Any) -> Dict:
        """Execute web search"""
        try:
            from web_tool import search_web
        except ImportError:
            return {"error": "web-search tool not available (web_tool not found)"}
        
        if isinstance(input_data, dict):
            query = input_data.get('query', '')
            num_results = input_data.get('num_results', 5)
        else:
            query = str(input_data)
            num_results = 5
        
        try:
            results = search_web(query, num_results)
            return {"status": "success", "results": results, "query": query}
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_web_fetch(self, input_data: Any) -> Dict:
        """Execute web fetch"""
        try:
            from web_tool import fetch_url
        except ImportError:
            return {"error": "web-fetch tool not available (web_tool not found)"}
        
        if isinstance(input_data, dict):
            url = input_data.get('url', '')
        else:
            url = str(input_data)
        
        try:
            content = fetch_url(url)
            return {"status": "success", "url": url, "content": content[:1000], "truncated": len(content) > 1000}
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_society_network(self, input_data: Any) -> Dict:
        """Execute Humanaize Society Network skill"""
        try:
            from skills.HumanaizeSocietyNetwork.skill_handler import execute_skill as society_execute
            result = society_execute(input_data)
            return result
        except ImportError:
            return {"error": "Humanaize Society Network skill not available"}
        except Exception as e:
            return {"error": f"Society Network error: {str(e)}"}

    def _execute_detect_emotion(self, input_data: Any) -> Dict:
        """Execute emotion detection using camera"""
        try:
            import cv2
            from deepface import DeepFace

            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return {"error": "Camera not available", "dominant": "unknown", "confidence": 0.0}

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                return {"error": "Failed to capture frame", "dominant": "unknown", "confidence": 0.0}

            result_list = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            if isinstance(result_list, list) and result_list:
                r = result_list[0]
            else:
                r = result_list or {}

            dominant = r.get("dominant_emotion") or r.get("dominant", "neutral")
            emo = r.get("emotion", {})
            if isinstance(emo, dict):
                confidence = max(emo.values()) if emo else 0.0
            else:
                confidence = 0.0

            return {"dominant": dominant, "confidence": float(confidence), "status": "success"}
        except Exception as e:
            return {"error": str(e), "dominant": "unknown", "confidence": 0.0}

    def set_language_adapter(self, adapter):
        """Set custom language adapter"""
        self._language_adapter = adapter
    
    def detect_language(self, text: str) -> str:
        """Detect language from text"""
        if not text:
            return "en"
        
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return "en"
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            if any(ord(c) >= 0x4E00 and ord(c) <= 0x9FFF for c in text):
                if any('\u4e00' <= c <= '\u9fff' for c in text):
                    return "zh"
        
        return "en"


class LanguageAdapter:
    """Handles language detection and adaptation for AI responses"""
    
    def __init__(self):
        self.current_language = "en"
        self.supported_languages = ["en", "zh", "zh-TW"]
        
        self.translations = {
            "en": {
                "greeting": "Hello! How can I help you today?",
                "thinking": "Thinking...",
                "processing": "Processing your request...",
                "success": "Operation completed successfully",
                "error": "An error occurred",
                "not_understood": "I didn't understand that. Could you please rephrase?",
                "skill_invoked": "Invoking skill: {skill_name}",
                "skill_success": "Skill executed successfully",
                "skill_error": "Skill execution failed",
                "network_connected": "Connected to network",
                "network_disconnected": "Disconnected from network",
                "friend_added": "Friend added successfully",
                "friend_removed": "Friend removed successfully",
                "thought_shared": "Thought shared with friends",
                "gan_shared": "GAN content shared with friends",
            },
            "zh": {
                "greeting": "你好！有什么我可以帮助你的吗？",
                "thinking": "思考中...",
                "processing": "正在处理你的请求...",
                "success": "操作成功完成",
                "error": "发生了一个错误",
                "not_understood": "我没有理解。能请你重新表述一下吗？",
                "skill_invoked": "正在调用技能：{skill_name}",
                "skill_success": "技能执行成功",
                "skill_error": "技能执行失败",
                "network_connected": "已连接到网络",
                "network_disconnected": "已断开网络连接",
                "friend_added": "成功添加好友",
                "friend_removed": "成功删除好友",
                "thought_shared": "思考已与好友分享",
                "gan_shared": "GAN 内容已与好友分享",
            },
            "zh-TW": {
                "greeting": "你好！有什麼我可以幫助你的嗎？",
                "thinking": "思考中...",
                "processing": "正在處理你的請求...",
                "success": "操作成功完成",
                "error": "發生了一個錯誤",
                "not_understood": "我沒有理解。能請你重新表述一下嗎？",
                "skill_invoked": "正在調用技能：{skill_name}",
                "skill_success": "技能執行成功",
                "skill_error": "技能執行失敗",
                "network_connected": "已連接到網絡",
                "network_disconnected": "已斷開網絡連接",
                "friend_added": "成功添加好友",
                "friend_removed": "成功刪除好友",
                "thought_shared": "思考已與好友分享",
                "gan_shared": "GAN 內容已與好友分享",
            }
        }
    
    def detect_language(self, text: str) -> str:
        """Detect language from input text"""
        if not text:
            return self.current_language
        
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return self.current_language
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return "zh"
        
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        english_ratio = english_words / max(total_chars, 1)
        
        if english_ratio > 0.5:
            return "en"
        
        return self.current_language
    
    def set_language(self, language: str):
        """Set the current language"""
        if language in self.supported_languages:
            self.current_language = language
    
    def get_message(self, key: str, **kwargs) -> str:
        """Get translated message"""
        message = self.translations.get(self.current_language, {}).get(
            key,
            self.translations["en"].get(key, key)
        )
        
        if kwargs:
            try:
                return message.format(**kwargs)
            except (KeyError, ValueError):
                return message
        
        return message
    
    def adapt_response(self, response: str) -> str:
        """Adapt response to match current language"""
        if self.current_language == "en":
            return response
        
        return response
    
    def should_respond_in_chinese(self, text: str) -> bool:
        """Determine if response should be in Chinese"""
        detected = self.detect_language(text)
        return detected in ["zh", "zh-TW"]