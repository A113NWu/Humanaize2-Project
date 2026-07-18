"""
Humanaize 技能系統
OpenClaw 相容的技能管理，支援完整執行功能
"""

import os
import re
import json
import yaml
import importlib
import inspect
from typing import Dict, List, Optional, Any, Callable

# 导入日志模块
try:
    from logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class Skill:
    """代表單一技能"""
    
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
        
        # Try multiple possible skills directories
        if skills_dir:
            self.skills_dir = skills_dir
        else:
            # Check for skills in common locations (priority: system -> user -> dev)
            possible_dirs = [
                "/usr/share/humanaize2/skills",
                os.path.join(os.path.expanduser("~"), ".humanaize", "skills"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "skills"),
                os.path.join(os.path.dirname(__file__), "skills")
            ]
            for dir_path in possible_dirs:
                if os.path.isdir(dir_path) and len(os.listdir(dir_path)) > 0:
                    self.skills_dir = dir_path
                    break
            else:
                self.skills_dir = "/usr/share/humanaize2/skills"
        
        # Try multiple possible config paths
        self.skills_config_path = os.path.join(os.path.dirname(__file__), "data", "skills_config.json")
        if not os.path.exists(self.skills_config_path):
            # Check system-wide config path
            system_config = "/var/lib/humanaize/skills_config.json"
            if os.path.exists(system_config):
                self.skills_config_path = system_config
            else:
                # Create in user home directory
                os.makedirs(os.path.join(os.path.expanduser("~"), ".humanaize"), exist_ok=True)
                self.skills_config_path = os.path.join(os.path.expanduser("~"), ".humanaize", "skills_config.json")
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
            "firewall": self._execute_firewall,
            "msf": self._execute_msf,
            "mode-manager": self._execute_mode_manager,
            "network": self._execute_network,
            "message-bus": self._execute_message_bus,
            "multisensory": self._execute_multisensory,
            "platform": self._execute_platform,
        }
    
    def load_skills(self):
        """Load all skills from skills directory"""
        self.skills = {}

        # Load skills from main skills directory (Core)
        if os.path.exists(self.skills_dir):
            for skill_name in os.listdir(self.skills_dir):
                skill_path = os.path.join(self.skills_dir, skill_name)
                if os.path.isdir(skill_path):
                    skill_file = os.path.join(skill_path, "SKILL.md")
                    if os.path.exists(skill_file):
                        self._load_skill_from_path(skill_path, skill_file)
    
    def _setup_skill_executor(self, skill: Skill):
        """Setup executor for a skill - try loading from module first, then use default executors"""
        if not self._try_load_skill_module(skill):
            if skill.name in self._skill_executors:
                skill.executor = self._skill_executors[skill.name]
    
    def _load_skill_from_path(self, skill_path: str, skill_file: str):
        """Load a single skill from a directory path"""
        skill = self._parse_skill_file(skill_file)
        if skill:
            skill.skill_dir = skill_path

            all_enabled = self.skills_config.get('all_enabled', True)
            
            # HSN skill should be disabled by default
            hsn_skill_names = ["humanaizesocietynetwork", "hsn"]
            is_hsn_skill = any(name in skill.name.lower() for name in hsn_skill_names)
            
            if is_hsn_skill:
                skill.enabled = False
            else:
                skill.enabled = all_enabled

            skills_config = self.skills_config.get('skills', {})
            for config_name, config_data in skills_config.items():
                if config_name.lower() == skill.name.lower():
                    skill.enabled = config_data.get('enabled', False) or all_enabled
                    break

            self.skills[skill.name] = skill

            # Setup executor for the skill
            self._setup_skill_executor(skill)
    
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
            module_name = f"skills.{folder_name}".replace('-', '_')

            importlib.invalidate_caches()
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                spec = importlib.util.spec_from_file_location(f"skills_{folder_name}", init_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

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
        """Get a skill by name (case-insensitive)"""
        # 首先尝试精确匹配
        if name in self.skills:
            return self.skills[name]
        
        # 如果精确匹配失败，尝试大小写不敏感匹配
        name_lower = name.lower()
        for skill_name in self.skills:
            if skill_name.lower() == name_lower:
                return self.skills[skill_name]
        
        return None
    
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
        
        # 如果技能不存在，检查是否有默认执行器
        if not skill:
            # 检查是否有默认执行器（即使技能未加载）
            if skill_name in self._skill_executors:
                try:
                    result = self._skill_executors[skill_name](input_data)
                    return self._adapt_response_language(result, language)
                except Exception as e:
                    error_messages = {
                        "en": f"Execution error: {str(e)}",
                        "zh": f"执行错误：{str(e)}",
                        "zh-TW": f"執行錯誤：{str(e)}",
                    }
                    return {"error": error_messages.get(language, error_messages["en"])}
            
            # 没有找到技能或执行器
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
            try:
                from deepface import DeepFace
            except ImportError:
                return {"error": "deepface not installed. Please install with: pip install deepface", 
                       "dominant": "unknown", "confidence": 0.0}

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

    def _execute_firewall(self, input_data: Any) -> Dict:
        """Execute firewall skill"""
        try:
            from .ai_firewall import ai_firewall
            
            if isinstance(input_data, dict):
                action = input_data.get('action', '')
                params = input_data.get('params', {})
            else:
                return {"error": "firewall requires action and params"}
            
            if action == 'start':
                return ai_firewall.firewall_api.start_firewall()
            elif action == 'stop':
                return ai_firewall.firewall_api.stop_firewall()
            elif action == 'status':
                return ai_firewall.get_status()
            elif action == 'block_ip':
                ip = params.get('ip', '')
                duration = params.get('duration', 3600)
                return ai_firewall.firewall_api.block_ip(ip, duration)
            elif action == 'unblock_ip':
                ip = params.get('ip', '')
                return ai_firewall.firewall_api.unblock_ip(ip)
            elif action == 'block_port':
                port = params.get('port', 0)
                return ai_firewall.firewall_api.block_port(port)
            elif action == 'unblock_port':
                port = params.get('port', 0)
                return ai_firewall.firewall_api.unblock_port(port)
            elif action == 'detect_attack':
                data = params.get('data', '')
                source_ip = params.get('source_ip', '')
                return ai_firewall.firewall_api.detect_attack(data, source_ip)
            elif action == 'scan_packet':
                return ai_firewall.firewall_api.scan_packet(params)
            elif action == 'get_attack_history':
                limit = params.get('limit', 20)
                return ai_firewall.firewall_api.get_attack_history(limit)
            elif action == 'analyze_attack':
                return ai_firewall.ai_analyze_attack(params)
            elif action == 'execute_command':
                command = params.get('command', '')
                return ai_firewall.execute_ai_command(command)
            else:
                return {"error": f"Unknown firewall action: {action}"}
        except Exception as e:
            return {"error": str(e)}

    def _execute_msf(self, input_data: Any) -> Dict:
        """Execute MSF database skill"""
        try:
            from .msf_db import msf_db
            from .msf_operations import msf_ops
            
            if isinstance(input_data, dict):
                action = input_data.get('action', '')
                params = input_data.get('params', {})
            else:
                return {"error": "msf requires action and params"}
            
            if action == 'connect':
                return msf_db.connect()
            elif action == 'disconnect':
                return msf_db.disconnect()
            elif action == 'test_connection':
                return msf_db.test_connection()
            elif action == 'get_status':
                return msf_db.get_status()
            elif action == 'get_hosts':
                filters = params.get('filters', {})
                return msf_ops.get_hosts(filters)
            elif action == 'get_host_details':
                host_id = params.get('host_id', 0)
                return msf_ops.get_host_details(host_id)
            elif action == 'add_host':
                return msf_ops.add_host(params)
            elif action == 'update_host':
                host_id = params.get('host_id', 0)
                host_data = {k: v for k, v in params.items() if k != 'host_id'}
                return msf_ops.update_host(host_id, host_data)
            elif action == 'delete_host':
                host_id = params.get('host_id', 0)
                return msf_ops.delete_host(host_id)
            elif action == 'get_services':
                filters = params.get('filters', {})
                return msf_ops.get_services(filters)
            elif action == 'add_service':
                return msf_ops.add_service(params)
            elif action == 'get_vulnerabilities':
                filters = params.get('filters', {})
                return msf_ops.get_vulnerabilities(filters)
            elif action == 'add_vulnerability':
                return msf_ops.add_vulnerability(params)
            elif action == 'get_credentials':
                filters = params.get('filters', {})
                return msf_ops.get_credentials(filters)
            elif action == 'add_credential':
                return msf_ops.add_credential(params)
            elif action == 'get_sessions':
                filters = params.get('filters', {})
                return msf_ops.get_sessions(filters)
            elif action == 'get_workspaces':
                return msf_ops.get_workspaces()
            elif action == 'get_notes':
                filters = params.get('filters', {})
                return msf_ops.get_notes(filters)
            elif action == 'get_loots':
                filters = params.get('filters', {})
                return msf_ops.get_loots(filters)
            elif action == 'execute_query':
                query = params.get('query', '')
                query_params = params.get('params', {})
                return msf_ops.execute_raw_query(query, query_params)
            elif action == 'execute_command':
                query = params.get('query', '')
                query_params = params.get('params', {})
                return msf_ops.execute_raw_command(query, query_params)
            elif action == 'get_summary':
                return msf_ops.get_summary()
            else:
                return {"error": f"Unknown MSF action: {action}"}
        except Exception as e:
            return {"error": str(e)}

    def _execute_mode_manager(self, input_data: Any) -> Dict:
        """Execute mode manager skill"""
        try:
            from .mode_manager import mode_manager
            
            if isinstance(input_data, dict):
                action = input_data.get('action', '')
                params = input_data.get('params', {})
            else:
                return {"error": "mode-manager requires action and params"}
            
            if action == 'analyze':
                context = params.get('context', '')
                return mode_manager.analyze_context(context)
            elif action == 'suggest':
                context = params.get('context', '')
                return mode_manager.suggest_mode(context)
            elif action == 'start':
                mode = params.get('mode', '')
                mode_params = params.get('mode_params', {})
                return mode_manager.start_mode(mode, mode_params)
            elif action == 'stop':
                mode = params.get('mode', '')
                return mode_manager.stop_mode(mode)
            elif action == 'status':
                return mode_manager.get_status()
            else:
                return {"error": f"Unknown mode-manager action: {action}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_network(self, input_data: Any) -> Dict:
        """Execute network layer skill"""
        try:
            from .network_layer import NetworkLayerAPI
            
            if isinstance(input_data, dict):
                action = input_data.get('action', '')
                params = input_data.get('params', {})
            else:
                return {"error": "network requires action and params"}
            
            if action == 'connect':
                return NetworkLayerAPI.connect(params)
            elif action == 'disconnect':
                return NetworkLayerAPI.disconnect()
            elif action == 'get':
                return NetworkLayerAPI.get(params.get('url', ''), params.get('params'), params.get('headers'))
            elif action == 'post':
                return NetworkLayerAPI.post(params.get('url', ''), params.get('data'), params.get('headers'))
            elif action == 'status':
                return NetworkLayerAPI.get_status()
            elif action == 'is_connected':
                return {"connected": NetworkLayerAPI.is_connected()}
            else:
                return {"error": f"Unknown network action: {action}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_message_bus(self, input_data: Any) -> Dict:
        """Execute message bus skill"""
        try:
            from .message_bus import MessageBusAPI
            
            if isinstance(input_data, dict):
                action = input_data.get('action', '')
                params = input_data.get('params', {})
            else:
                return {"error": "message-bus requires action and params"}
            
            if action == 'publish':
                MessageBusAPI.publish(params.get('topic', ''), params.get('message', {}))
                return {"status": "success", "message": "Message published"}
            elif action == 'send':
                return MessageBusAPI.send_message(
                    params.get('platform', 'local'),
                    params.get('content', ''),
                    metadata=params.get('metadata'),
                    attachments=params.get('attachments')
                )
            elif action == 'start':
                MessageBusAPI.start()
                return {"status": "success", "message": "Message bus started"}
            elif action == 'stop':
                MessageBusAPI.stop()
                return {"status": "success", "message": "Message bus stopped"}
            elif action == 'status':
                return MessageBusAPI.get_status()
            elif action == 'history':
                return {"history": MessageBusAPI.get_history(params.get('limit', 100))}
            else:
                return {"error": f"Unknown message-bus action: {action}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_multisensory(self, input_data: Any) -> Dict:
        """Execute multisensory system skill"""
        try:
            from .multisensory_system import MultisensoryAPI
            
            if isinstance(input_data, dict):
                action = input_data.get('action', '')
                params = input_data.get('params', {})
            else:
                return {"error": "multisensory requires action and params"}
            
            if action == 'perceive':
                return MultisensoryAPI.perceive(
                    params.get('type', 'text'),
                    params.get('data', ''),
                    params.get('source', 'unknown')
                )
            elif action == 'vision':
                image_path = params.get('image_path')
                if image_path:
                    return MultisensoryAPI.vision_analyze(image_path)
                base64_data = params.get('base64')
                if base64_data:
                    return MultisensoryAPI.vision_analyze_base64(base64_data)
                return {"error": "image_path or base64 required"}
            elif action == 'hearing':
                audio_path = params.get('audio_path')
                if audio_path:
                    return MultisensoryAPI.hearing_process(audio_path)
                return MultisensoryAPI.hearing_listen(params.get('duration', 5))
            elif action == 'speech':
                return MultisensoryAPI.speech_speak(params.get('text', ''))
            elif action == 'environment':
                return MultisensoryAPI.environment_info()
            elif action == 'network_status':
                return MultisensoryAPI.network_status()
            elif action == 'status':
                return MultisensoryAPI.get_status()
            elif action == 'history':
                return {"history": MultisensoryAPI.get_history(params.get('limit', 20))}
            elif action == 'start':
                MultisensoryAPI.start()
                return {"status": "success", "message": "Multisensory system started"}
            elif action == 'stop':
                MultisensoryAPI.stop()
                return {"status": "success", "message": "Multisensory system stopped"}
            else:
                return {"error": f"Unknown multisensory action: {action}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_platform(self, input_data: Any) -> Dict:
        """Execute platform adapters skill"""
        try:
            from .platform_adapters import PlatformAdaptersAPI
            
            if isinstance(input_data, dict):
                action = input_data.get('action', '')
                params = input_data.get('params', {})
            else:
                return {"error": "platform requires action and params"}
            
            if action == 'configure':
                return PlatformAdaptersAPI.configure(params.get('platform', ''), **params.get('config', {}))
            elif action == 'connect':
                return PlatformAdaptersAPI.connect(params.get('platform', ''))
            elif action == 'disconnect':
                return PlatformAdaptersAPI.disconnect(params.get('platform', ''))
            elif action == 'send':
                return PlatformAdaptersAPI.send_message(
                    params.get('platform', ''),
                    params.get('content', ''),
                    metadata=params.get('metadata'),
                    attachments=params.get('attachments')
                )
            elif action == 'start_all':
                return PlatformAdaptersAPI.start_all()
            elif action == 'stop_all':
                return PlatformAdaptersAPI.stop_all()
            elif action == 'status':
                return PlatformAdaptersAPI.get_status()
            else:
                return {"error": f"Unknown platform action: {action}"}
        except Exception as e:
            return {"error": str(e)}

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