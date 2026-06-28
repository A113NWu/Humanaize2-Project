import os
import subprocess
import re
import json
from typing import Dict, Any, Optional

# Add tools directory to path for skill imports
tools_dir = os.path.join(os.path.dirname(__file__), "tools")
import sys
sys.path.insert(0, tools_dir)

# 导入日志模块
try:
    from logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from skills_manager import SkillsManager, LanguageAdapter
    from language_adapter import LanguageAdapter as StandaloneLanguageAdapter
    SKILLS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Skills system not available: {e}")
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
        
        # 移除markdown代码块标记（包括 ```json 和 ```）
        text = re.sub(r'```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\s*```\s*$', '', text)
        
        # 移除多余的空白字符
        text = text.strip()

        # 使用JSON格式提取命令，不再支持!command!格式
        existing_commands = set()

        # 1. 查找RESPONSE:标签后的内容
        response_match = re.search(r'RESPONSE:\s*(.+)$', text, flags=re.MULTILINE | re.DOTALL)
        if response_match:
            response_content = response_match.group(1).strip()
            self._parse_response_content(response_content, actions, existing_commands)
        else:
            # 如果没有找到RESPONSE:标签，尝试在整个文本中查找JSON
            self._parse_response_content(text, actions, existing_commands)
        
        # 2. 尝试从文本中提取纯命令（如"执行命令：ls -la"或"运行：ls -la"）
        self._extract_plain_commands(text, actions, existing_commands)

        return actions
    
    def _parse_response_content(self, content, actions, existing_commands):
        """Parse response content and extract actions"""
        # 尝试解析JSON
        payload = None
        
        # 首先尝试直接解析
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 如果失败，尝试查找JSON对象
        if payload is None:
            candidate = self._find_json_object(content)
            if candidate:
                try:
                    payload = json.loads(candidate)
                except json.JSONDecodeError:
                    # 尝试修复常见的JSON错误
                    fixed_candidate = self._fix_json_format(candidate)
                    if fixed_candidate:
                        try:
                            payload = json.loads(fixed_candidate)
                        except json.JSONDecodeError:
                            pass
        
        # 如果仍然失败，尝试解析简化格式（如 skill: shell, input: command: echo）
        if payload is None:
            payload = self._parse_simplified_format(content)
        
        if isinstance(payload, dict):
            self._process_payload(payload, actions, existing_commands)
    
    def _parse_simplified_format(self, content):
        """解析简化格式的命令（如 skill: shell, input: command: echo）"""
        # 移除可能的大括号
        content = content.replace('{', '').replace('}', '').strip()
        
        # 按逗号分割键值对
        pairs = re.split(r',\s*(?![^{}]*\})', content)
        
        result = {}
        current_key = None
        
        for pair in pairs:
            pair = pair.strip()
            if ':' in pair:
                parts = pair.split(':', 1)
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ''
                
                # 如果值看起来像嵌套的键值对，递归解析
                if ':' in value and not value.startswith('"'):
                    nested = self._parse_simplified_format(value)
                    if nested:
                        result[key] = nested
                    else:
                        result[key] = value
                else:
                    result[key] = value
            elif current_key:
                # 继续前一个键的值
                result[current_key] = result.get(current_key, '') + ' ' + pair
        
        return result if result else None
    
    def _fix_json_format(self, json_str):
        """尝试修复常见的JSON格式错误"""
        if not json_str:
            return None
        
        fixed = json_str
        
        # 修复缺少引号的键名：{skill: shell} -> {"skill": shell}
        fixed = re.sub(r'(\{|\s)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)
        
        # 修复缺少引号的字符串值（简单情况，不包含空格和特殊字符）
        fixed = re.sub(r':\s*([a-zA-Z_][a-zA-Z0-9_]*)([,}])', r': "\1"\2', fixed)
        
        # 修复嵌套的缺少引号的键名
        fixed = re.sub(r'(\{|\s)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)
        
        # 移除多余的逗号
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
        
        # 尝试修复更复杂的情况：处理空格分隔的多个键值对
        # 例如：{skill: shell, input: {command: echo hello}}
        # 尝试添加引号到值中（处理包含空格的值）
        # 匹配 pattern: value, pattern
        fixed = re.sub(r':\s*([^{}\[\],:\s]+(?:\s+[^{}\[\],:\s]+)*?)(\s*[,}])', r': "\1"\2', fixed)
        
        return fixed
    
    def _process_payload(self, payload, actions, existing_commands):
        """处理JSON payload并添加操作"""
        skill_name = payload.get('skill')
        if skill_name:
            input_data = payload.get('input', {})
            # 检查input是否为字符串（可能是错误格式）
            if isinstance(input_data, str):
                input_data = {"command": input_data}
            actions.append({
                "type": "skill",
                "name": skill_name,
                "input": input_data
            })
        else:
            cmd = payload.get('input') or payload.get('command')
            if isinstance(cmd, dict):
                nested = cmd.get('command') or cmd.get('input')
                if nested:
                    cmd_str = str(nested).strip()
                    if cmd_str and cmd_str not in existing_commands:
                        actions.append({"type": "shell", "command": cmd_str})
                        existing_commands.add(cmd_str)
                else:
                    cmd_str = json.dumps(cmd, ensure_ascii=False)
                    if cmd_str not in existing_commands:
                        actions.append({"type": "shell", "command": cmd_str})
                        existing_commands.add(cmd_str)
            elif cmd:
                cmd_str = str(cmd).strip()
                if cmd_str and cmd_str not in existing_commands:
                    actions.append({"type": "shell", "command": cmd_str})
                    existing_commands.add(cmd_str)
    
    def _extract_plain_commands(self, text, actions, existing_commands):
        """从文本中提取纯命令（不需要特殊标记）"""
        # 查找"执行命令：xxx"或"运行：xxx"格式
        patterns = [
            r'[执行运行命令]\s*[：:]\s*([^\n]+)',
            r'execute\s+command\s*[：:]\s*([^\n]+)',
            r'run\s*[：:]\s*([^\n]+)',
        ]
        
        for pattern in patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                cmd = match.strip()
                
                # 检查命令是否已经是!command!格式的一部分
                # 如果命令以!开头或包含!，可能是已经被提取过的
                if cmd.startswith('!') or cmd.endswith('!'):
                    # 提取实际的命令内容（去掉!）
                    actual_cmd = cmd.replace('!', '').strip()
                    if actual_cmd and actual_cmd not in existing_commands:
                        actions.append({"type": "shell", "command": actual_cmd})
                        existing_commands.add(actual_cmd)
                    continue
                
                if cmd and cmd not in existing_commands:
                    actions.append({"type": "shell", "command": cmd})
                    existing_commands.add(cmd)

    def has_actions(self, response):
        return len(self._extract_actions(response)) > 0

    def _run_shell(self, cmd):
        """执行Shell命令"""
        logger.info(f"Executing shell command: {cmd}")
        
        try:
            # 使用subprocess执行命令
            proc = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30,
                executable='/bin/bash' if os.name != 'nt' else None
            )
            
            # 合并stdout和stderr
            out = (proc.stdout or "") + (proc.stderr or "")
            result = out.strip()
            
            logger.info(f"Command output: {result[:500] if result else 'Empty'}")
            
            if proc.returncode != 0:
                logger.warning(f"Command returned non-zero exit code: {proc.returncode}")
            
            return result
            
        except subprocess.TimeoutExpired:
            logger.error(f"Command timeout: {cmd}")
            return f"Command timeout after 30 seconds"
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return f"Command execution error: {e}"

    def _execute_skill(self, skill_name: str, input_data: Any, language: str = "en") -> Dict:
        """Execute a skill with language support"""
        if not self.skills_manager:
            return self._get_error_response("skills_not_available", language)

        # 直接使用skills_manager的execute_skill方法
        # 这样可以利用默认执行器（即使技能未加载）
        return self.skills_manager.execute_skill(skill_name, input_data, language)
    
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
            # 如果技能管理器中有该技能，尝试使用技能管理器执行
            if self.skills_manager:
                skill = self.skills_manager.get_skill(skill_name)
                if skill:
                    # 调用技能管理器的execute_skill方法，避免重复代码
                    return self.skills_manager.execute_skill(skill_name, input_data, language)
            
            # 如果没有找到技能或技能管理器不可用，返回准备状态
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
        logger.info(f"Agent called with response: {response[:200] if response else 'Empty'}...")
        
        language = self.detect_user_language(user_input)
        
        if self.language_adapter:
            self.language_adapter.set_language(language)
        
        actions = self._extract_actions(response)
        logger.info(f"Extracted actions: {actions}")
        
        if not actions:
            logger.info("No actions found")
            return ""

        outputs = []
        for action in actions:
            action_type = action.get("type", "shell")
            logger.info(f"Processing action: type={action_type}, action={action}")
            
            if action_type == "shell":
                cmd = action.get("command", "")
                if not cmd:
                    logger.warning("Empty shell command")
                    continue
                output = self._run_shell(cmd)
                outputs.append(output)
            elif action_type == "skill":
                skill_name = action.get("name", "")
                input_data = action.get("input")
                logger.info(f"Executing skill: {skill_name} with input: {input_data}")
                result = self._execute_skill(skill_name, input_data, language)
                logger.info(f"Skill result: {result}")
                
                # 如果是shell技能，提取output字段
                if skill_name == "shell" and isinstance(result, dict):
                    if result.get("status") == "success":
                        outputs.append(result.get("output", ""))
                    else:
                        outputs.append(f"Error: {result.get('error', 'Unknown error')}")
                else:
                    # 其他技能返回JSON格式
                    outputs.append(json.dumps(result, ensure_ascii=False, indent=2))
        
        final_output = "\n---\n".join(outputs).strip()
        logger.info(f"Agent final output: {final_output[:500] if final_output else 'Empty'}")
        return final_output
    
    def get_skills_prompt(self, language: str = None) -> str:
        """Get skills prompt in the specified language"""
        if language is None and self.language_adapter:
            language = self.language_adapter.current_language
        
        if self.skills_manager:
            return self.skills_manager.get_skills_prompt(language or "en")
        return ""