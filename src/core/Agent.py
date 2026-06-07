import os
import subprocess
import re
import json
from typing import Dict, Any, Optional

try:
    from skills_manager import SkillsManager, LanguageAdapter
    from language_adapter import LanguageAdapter as StandaloneLanguageAdapter
    SKILLS_AVAILABLE = True
except ImportError:
    SKILLS_AVAILABLE = False


class Agent:
    def __init__(self, special):
        self.special = special
        self.skills_manager = None
        self.language_adapter = None
        self.current_language = "en"
        
        if SKILLS_AVAILABLE:
            skills_dir = os.path.join(os.path.dirname(__file__), "skills")
            self.skills_manager = SkillsManager(skills_dir)
            self.language_adapter = StandaloneLanguageAdapter()
    
    def set_language(self, language: str):
        """Set the current language for the agent"""
        self.current_language = language
        if self.language_adapter:
            self.language_adapter.set_language(language)
    
    def detect_user_language(self, text: str) -> str:
        """Detect the user's language from input text"""
        if self.language_adapter:
            return self.language_adapter.detect_language(text)
        
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return "en"
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return "zh"
        
        return "en"
    
    def get_message(self, key: str, **kwargs) -> str:
        """Get a translated message in the current language"""
        if self.language_adapter:
            return self.language_adapter.get_message(key, **kwargs)
        return key
    
    def _find_json_object(self, text):
        start = None
        depth = 0
        for i, ch in enumerate(text):
            if ch == '{':
                if start is None:
                    start = i
                depth += 1
            elif ch == '}' and start is not None:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    def _extract_actions(self, response):
        actions = []
        if not response:
            return actions

        text = str(response).strip()
        text = re.sub(r'```(?:json)?\s*|```', '', text)

        for cmd in re.findall(r'!(.+?)!', text, flags=re.DOTALL):
            cmd = cmd.strip()
            if cmd:
                actions.append({"type": "shell", "command": cmd})

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
            candidate = self._find_json_object(text)
            if candidate:
                try:
                    payload = json.loads(candidate)
                except json.JSONDecodeError:
                    payload = None

        if isinstance(payload, dict):
            skill_name = payload.get('skill')
            if skill_name:
                actions.append({
                    "type": "skill",
                    "name": skill_name,
                    "input": payload.get('input')
                })
            else:
                cmd = payload.get('input') or payload.get('command')
                if isinstance(cmd, dict):
                    nested = cmd.get('command') or cmd.get('input')
                    if nested:
                        actions.append({"type": "shell", "command": str(nested).strip()})
                    else:
                        actions.append({"type": "shell", "command": json.dumps(cmd, ensure_ascii=False)})
                elif cmd:
                    actions.append({"type": "shell", "command": str(cmd).strip()})

        return actions

    def has_actions(self, response):
        return len(self._extract_actions(response)) > 0

    def _run_shell(self, cmd):
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            out = (proc.stdout or "") + (proc.stderr or "")
            return out.strip()
        except Exception as e:
            return f"Command execution error: {e}"

    def _execute_skill(self, skill_name: str, input_data: Any, language: str = "en") -> Dict:
        """Execute a skill with language support"""
        if not self.skills_manager:
            return self._get_error_response("skills_not_available", language)

        skill = self.skills_manager.get_skill(skill_name)
        if not skill:
            return self._get_error_response("skill_not_found", language, skill_name=skill_name)

        if not skill.enabled:
            return self._get_error_response("skill_disabled", language, skill_name=skill_name)

        if skill.executor:
            try:
                result = skill.executor(input_data)
                if isinstance(result, dict):
                    result['language'] = language
                    return result
                return {"result": result, "status": "success", "language": language}
            except Exception as e:
                return {"error": str(e), "status": "error", "language": language}

        result = self._run_skill_action(skill_name, input_data, language)
        return result
    
    def _get_error_response(self, error_type: str, language: str, **kwargs) -> Dict:
        """Get an error response in the appropriate language"""
        error_messages = {
            "skills_not_available": {
                "en": "Skills system not available",
                "zh": "技能系统不可用",
                "zh-TW": "技能系統不可用"
            },
            "skill_not_found": {
                "en": "Skill '{skill_name}' not found",
                "zh": "未找到技能 '{skill_name}'",
                "zh-TW": "未找到技能 '{skill_name}'"
            },
            "skill_disabled": {
                "en": "Skill '{skill_name}' is disabled",
                "zh": "技能 '{skill_name}' 已禁用",
                "zh-TW": "技能 '{skill_name}' 已停用"
            }
        }
        
        msg_template = error_messages.get(error_type, {}).get(language, error_messages.get(error_type, {}).get("en", "Unknown error"))
        
        if kwargs:
            try:
                message = msg_template.format(**kwargs)
            except (KeyError, ValueError):
                message = msg_template
        else:
            message = msg_template
        
        return {"error": message, "status": "error", "language": language}

    def _run_skill_action(self, skill_name: str, input_data: Any, language: str = "en") -> Dict:
        """Run a specific skill action with language support"""
        
        if skill_name == "shell":
            if isinstance(input_data, dict):
                cmd = input_data.get('command', '')
            else:
                cmd = str(input_data)
            output = self._run_shell(cmd)
            return {"output": output, "status": "success", "language": language}
        
        elif skill_name == "file-read":
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
                    content = ''.join(lines[offset:offset+limit])
                return {"content": content, "status": "success", "path": path, "language": language}
            except Exception as e:
                return {"error": str(e), "status": "error", "language": language}
        
        elif skill_name == "file-write":
            if isinstance(input_data, dict):
                path = input_data.get('path', '')
                content = input_data.get('content', '')
                mode = input_data.get('mode', 'write')
            else:
                return {"error": self.get_message("invalid_input"), "status": "error", "language": language}
            
            try:
                write_mode = 'w' if mode == 'write' else 'a'
                with open(path, write_mode, encoding='utf-8') as f:
                    f.write(content)
                return {"status": "success", "path": path, "language": language}
            except Exception as e:
                return {"error": str(e), "status": "error", "language": language}
        
        elif skill_name == "memory":
            from memory import load_memory
            memory = load_memory()
            
            if isinstance(input_data, dict):
                action = input_data.get('action', 'status')
                limit = input_data.get('limit', 10)
            else:
                action = 'status'
                limit = 10
            
            if action == 'recall':
                msgs = memory.get('messages', [])[-limit:]
                return {"messages": msgs, "status": "success", "language": language}
            elif action == 'status':
                return {
                    "messages": len(memory.get('messages', [])),
                    "thoughts": len(memory.get('thoughts', [])),
                    "decisions": len(memory.get('decisions', [])),
                    "status": "success",
                    "language": language
                }
            elif action == 'thoughts':
                thoughts = memory.get('thoughts', [])[-limit:]
                return {"thoughts": thoughts, "status": "success", "language": language}
            else:
                return {"error": f"Unknown memory action: {action}", "status": "error", "language": language}
        
        elif skill_name == "reminder":
            if isinstance(input_data, dict):
                message = input_data.get('message', '')
                delay_minutes = input_data.get('delay_minutes', 0)
                repeat = input_data.get('repeat', False)
            else:
                return {"error": self.get_message("invalid_input"), "status": "error", "language": language}
            
            from datetime import datetime, timedelta
            scheduled_time = datetime.now() + timedelta(minutes=delay_minutes)
            
            return {
                "status": "scheduled",
                "message": message,
                "delay_minutes": delay_minutes,
                "scheduled_at": scheduled_time.isoformat(),
                "repeat": repeat,
                "language": language
            }
        
        elif skill_name == "web-search":
            try:
                from web_tool import search_web
                if isinstance(input_data, dict):
                    query = input_data.get('query', '')
                    num_results = input_data.get('num_results', 5)
                else:
                    query = str(input_data)
                    num_results = 5
                
                results = search_web(query, num_results)
                return {"results": results, "status": "success", "language": language}
            except ImportError:
                return {"error": "web-search tool not available", "status": "error", "language": language}
        
        elif skill_name == "web-fetch":
            try:
                from web_tool import fetch_url
                if isinstance(input_data, dict):
                    url = input_data.get('url', '')
                else:
                    url = str(input_data)
                
                content = fetch_url(url)
                return {"content": content, "status": "success", "language": language}
            except ImportError:
                return {"error": "web-fetch tool not available", "status": "error", "language": language}
        
        elif skill_name == "humanaize-society-network":
            return self._execute_society_network(input_data, language)
        
        else:
            if self.skills_manager and self.skills_manager.get_skill(skill_name):
                skill = self.skills_manager.get_skill(skill_name)
                if hasattr(skill, 'executor') and skill.executor:
                    try:
                        result = skill.executor(input_data)
                        if isinstance(result, dict):
                            result['language'] = language
                            return result
                        return {"result": result, "status": "success", "language": language}
                    except Exception as e:
                        return {"error": str(e), "status": "error", "language": language}
            
            return {
                "status": "ready",
                "skill": skill_name,
                "input": input_data,
                "instructions": self.skills_manager.get_skill(skill_name).instructions if self.skills_manager and self.skills_manager.get_skill(skill_name) else "",
                "language": language
            }
    
    def _execute_society_network(self, input_data: Any, language: str = "en") -> Dict:
        """Execute Humanaize Society Network skill"""
        try:
            from skills.HumanaizeSocietyNetwork.skill_handler import execute_skill as society_execute
            result = society_execute(input_data)
            if isinstance(result, dict):
                result['language'] = language
            return result
        except ImportError:
            return {"error": "Humanaize Society Network not available", "status": "error", "language": language}
        except Exception as e:
            return {"error": f"Society Network error: {str(e)}", "status": "error", "language": language}

    def agent(self, special, response, user_input: str = ""):
        """Main agent function with language detection"""
        language = self.detect_user_language(user_input)
        
        if self.language_adapter:
            self.language_adapter.set_language(language)
        
        actions = self._extract_actions(response)
        if not actions:
            return ""

        outputs = []
        for action in actions:
            action_type = action.get("type", "shell")
            
            if action_type == "shell":
                cmd = action.get("command", "")
                output = self._run_shell(cmd)
                outputs.append(output)
            elif action_type == "skill":
                skill_name = action.get("name", "")
                input_data = action.get("input")
                result = self._execute_skill(skill_name, input_data, language)
                outputs.append(json.dumps(result, ensure_ascii=False, indent=2))
        
        return "\n---\n".join(outputs).strip()
    
    def get_skills_prompt(self, language: str = None) -> str:
        """Get skills prompt in the specified language"""
        if language is None and self.language_adapter:
            language = self.language_adapter.current_language
        
        if self.skills_manager:
            return self.skills_manager.get_skills_prompt(language or "en")
        return ""