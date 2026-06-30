# -*- coding: utf-8 -*-
"""
Humanaize Skill Installer - Skill安装管理器

功能：
1. 解压用户提供的Skill压缩包
2. 将代码文件安装到 skills/<name>/ 目录
3. 将提示词文件安装到 prompt/ 目录
4. 支持多种压缩格式：zip, tar.gz, tar
"""

import os
import sys
import shutil
import zipfile
import tarfile
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class SkillInstaller:
    """Skill安装管理器"""
    
    def __init__(self, skills_dir: str = None, prompts_dir: str = None):
        """初始化安装器
        
        Args:
            skills_dir: skills目录路径，默认为项目根目录下的skills/
            prompts_dir: prompts目录路径，默认为项目根目录下的prompt/
        """
        if skills_dir:
            self.skills_dir = skills_dir
        else:
            self.skills_dir = os.path.join(PROJECT_ROOT, "skills")
        
        if prompts_dir:
            self.prompts_dir = prompts_dir
        else:
            self.prompts_dir = os.path.join(PROJECT_ROOT, "prompt")
        
        # 确保目录存在
        os.makedirs(self.skills_dir, exist_ok=True)
        os.makedirs(self.prompts_dir, exist_ok=True)
    
    def install_from_archive(self, archive_path: str, skill_name: str = None) -> Dict:
        """从压缩包安装Skill
        
        Args:
            archive_path: 压缩包文件路径
            skill_name: 指定Skill名称（可选，默认从压缩包结构推断）
        
        Returns:
            Dict with installation result
        """
        if not os.path.exists(archive_path):
            return {
                "success": False,
                "error": f"压缩包文件不存在: {archive_path}"
            }
        
        # 创建临时解压目录
        temp_dir = os.path.join(PROJECT_ROOT, "temp_skill_install")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # 解压文件
            extract_result = self._extract_archive(archive_path, temp_dir)
            if not extract_result["success"]:
                return extract_result
            
            extracted_dir = extract_result["extracted_dir"]
            
            # 分析解压后的目录结构
            structure = self._analyze_structure(extracted_dir)
            
            # 确定Skill名称
            if not skill_name:
                skill_name = structure.get("skill_name", os.path.basename(extracted_dir))
            
            # 安装代码文件
            code_result = self._install_code_files(structure.get("code_files", []), skill_name)
            
            # 安装提示词文件
            prompt_result = self._install_prompt_files(structure.get("prompt_files", []))
            
            # 安装其他资源文件
            resource_result = self._install_resources(structure.get("resources", []), skill_name)
            
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # 生成安装报告
            installed_files = []
            if code_result.get("success"):
                installed_files.extend(code_result.get("installed_files", []))
            if prompt_result.get("success"):
                installed_files.extend(prompt_result.get("installed_files", []))
            if resource_result.get("success"):
                installed_files.extend(resource_result.get("installed_files", []))
            
            return {
                "success": True,
                "skill_name": skill_name,
                "installed_files": installed_files,
                "code_installed": code_result.get("success", False),
                "prompts_installed": prompt_result.get("success", False),
                "resources_installed": resource_result.get("success", False),
                "message": f"Skill '{skill_name}' 安装成功"
            }
        
        except Exception as e:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {
                "success": False,
                "error": f"安装过程中发生错误: {str(e)}"
            }
    
    def _extract_archive(self, archive_path: str, target_dir: str) -> Dict:
        """解压压缩包
        
        Args:
            archive_path: 压缩包路径
            target_dir: 目标解压目录
        
        Returns:
            Dict with extraction result
        """
        archive_lower = archive_path.lower()
        
        try:
            if archive_lower.endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(target_dir)
                    extracted_dir = target_dir
            
            elif archive_lower.endswith('.tar.gz') or archive_lower.endswith('.tgz'):
                with tarfile.open(archive_path, 'r:gz') as tf:
                    tf.extractall(target_dir)
                    extracted_dir = target_dir
            
            elif archive_lower.endswith('.tar'):
                with tarfile.open(archive_path, 'r') as tf:
                    tf.extractall(target_dir)
                    extracted_dir = target_dir
            
            else:
                return {
                    "success": False,
                    "error": f"不支持的压缩包格式: {archive_path}"
                }
            
            # 检查解压后的内容，找到实际的内容目录
            extracted_items = os.listdir(target_dir)
            
            # 如果只有一个目录，进入该目录
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(target_dir, extracted_items[0])):
                extracted_dir = os.path.join(target_dir, extracted_items[0])
            
            return {
                "success": True,
                "extracted_dir": extracted_dir,
                "files": os.listdir(extracted_dir)
            }
        
        except zipfile.BadZipFile:
            return {
                "success": False,
                "error": "无效的ZIP文件"
            }
        except tarfile.TarError:
            return {
                "success": False,
                "error": "无效的TAR文件"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"解压失败: {str(e)}"
            }
    
    def _analyze_structure(self, extracted_dir: str) -> Dict:
        """分析解压后的目录结构
        
        识别：
        - 代码文件（.py文件）
        - 提示词文件（.txt, .md文件，特别是包含prompt、skill等关键词的文件）
        - 资源文件（配置、数据等）
        - Skill名称（从SKILL.md或目录名推断）
        
        Args:
            extracted_dir: 解压后的目录
        
        Returns:
            Dict with structure analysis
        """
        structure = {
            "skill_name": None,
            "code_files": [],
            "prompt_files": [],
            "resources": [],
            "skill_md": None
        }
        
        # 遍历解压目录
        for root, dirs, files in os.walk(extracted_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, extracted_dir)
                
                # 检查是否是SKILL.md文件
                if file.lower() == "skill.md":
                    structure["skill_md"] = file_path
                    # 从SKILL.md解析Skill名称
                    skill_name = self._parse_skill_name(file_path)
                    if skill_name:
                        structure["skill_name"] = skill_name
                
                # 分类文件
                file_lower = file.lower()
                
                # Python代码文件
                if file.endswith('.py'):
                    structure["code_files"].append(file_path)
                
                # 提示词文件
                elif file.endswith('.txt') or (file.endswith('.md') and file.lower() != 'skill.md'):
                    # 检查是否包含提示词关键词
                    prompt_keywords = ['prompt', 'skill', 'instruction', 'template', 'guide']
                    is_prompt = any(kw in file_lower for kw in prompt_keywords)
                    
                    # 或者检查文件内容是否包含提示词特征
                    if not is_prompt and file.endswith('.txt'):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read(200)
                                prompt_indicators = ['你', 'please', '指令', '系统', '角色', 'role', 'assistant', 'response']
                                is_prompt = any(ind in content.lower() for ind in prompt_indicators)
                        except:
                            pass
                    
                    if is_prompt:
                        structure["prompt_files"].append(file_path)
                    else:
                        structure["resources"].append(file_path)
                
                # 配置文件
                elif file.endswith('.json') or file.endswith('.yaml') or file.endswith('.yml'):
                    structure["resources"].append(file_path)
                
                # 其他文件
                else:
                    structure["resources"].append(file_path)
        
        # 如果没有从SKILL.md获取名称，使用目录名
        if not structure["skill_name"]:
            structure["skill_name"] = os.path.basename(extracted_dir)
        
        return structure
    
    def _parse_skill_name(self, skill_md_path: str) -> Optional[str]:
        """从SKILL.md解析Skill名称
        
        Args:
            skill_md_path: SKILL.md文件路径
        
        Returns:
            Skill名称或None
        """
        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析YAML frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    import yaml
                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        if frontmatter and 'name' in frontmatter:
                            return frontmatter['name']
                    except:
                        pass
            
            return None
        
        except Exception as e:
            logger.warning(f"解析SKILL.md失败: {e}")
            return None
    
    def _install_code_files(self, code_files: List[str], skill_name: str) -> Dict:
        """安装代码文件到 skills/<name>/ 目录
        
        Args:
            code_files: 代码文件列表
            skill_name: Skill名称
        
        Returns:
            Dict with installation result
        """
        if not code_files:
            return {
                "success": True,
                "installed_files": [],
                "message": "没有代码文件需要安装"
            }
        
        # 创建Skill目录
        skill_dir = os.path.join(self.skills_dir, skill_name)
        os.makedirs(skill_dir, exist_ok=True)
        
        installed_files = []
        
        try:
            for code_file in code_files:
                file_name = os.path.basename(code_file)
                target_path = os.path.join(skill_dir, file_name)
                
                shutil.copy2(code_file, target_path)
                installed_files.append(target_path)
            
            return {
                "success": True,
                "installed_files": installed_files,
                "skill_dir": skill_dir,
                "message": f"已安装 {len(installed_files)} 个代码文件"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"代码文件安装失败: {str(e)}",
                "installed_files": installed_files
            }
    
    def _install_prompt_files(self, prompt_files: List[str]) -> Dict:
        """安装提示词文件到 prompt/ 目录
        
        Args:
            prompt_files: 提示词文件列表
        
        Returns:
            Dict with installation result
        """
        if not prompt_files:
            return {
                "success": True,
                "installed_files": [],
                "message": "没有提示词文件需要安装"
            }
        
        installed_files = []
        
        try:
            for prompt_file in prompt_files:
                file_name = os.path.basename(prompt_file)
                target_path = os.path.join(self.prompts_dir, file_name)
                
                # 如果文件已存在，添加后缀避免覆盖
                if os.path.exists(target_path):
                    base, ext = os.path.splitext(file_name)
                    counter = 1
                    while os.path.exists(target_path):
                        target_path = os.path.join(self.prompts_dir, f"{base}_{counter}{ext}")
                        counter += 1
                
                shutil.copy2(prompt_file, target_path)
                installed_files.append(target_path)
            
            return {
                "success": True,
                "installed_files": installed_files,
                "prompts_dir": self.prompts_dir,
                "message": f"已安装 {len(installed_files)} 个提示词文件"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"提示词文件安装失败: {str(e)}",
                "installed_files": installed_files
            }
    
    def _install_resources(self, resources: List[str], skill_name: str) -> Dict:
        """安装资源文件
        
        Args:
            resources: 资源文件列表
            skill_name: Skill名称
        
        Returns:
            Dict with installation result
        """
        if not resources:
            return {
                "success": True,
                "installed_files": [],
                "message": "没有资源文件需要安装"
            }
        
        # 在Skill目录下创建resources子目录
        resources_dir = os.path.join(self.skills_dir, skill_name, "resources")
        os.makedirs(resources_dir, exist_ok=True)
        
        installed_files = []
        
        try:
            for resource in resources:
                file_name = os.path.basename(resource)
                target_path = os.path.join(resources_dir, file_name)
                
                shutil.copy2(resource, target_path)
                installed_files.append(target_path)
            
            return {
                "success": True,
                "installed_files": installed_files,
                "resources_dir": resources_dir,
                "message": f"已安装 {len(installed_files)} 个资源文件"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"资源文件安装失败: {str(e)}",
                "installed_files": installed_files
            }
    
    def uninstall_skill(self, skill_name: str) -> Dict:
        """卸载Skill
        
        Args:
            skill_name: Skill名称
        
        Returns:
            Dict with uninstallation result
        """
        skill_dir = os.path.join(self.skills_dir, skill_name)
        
        if not os.path.exists(skill_dir):
            return {
                "success": False,
                "error": f"Skill '{skill_name}' 不存在"
            }
        
        try:
            # 删除Skill目录
            shutil.rmtree(skill_dir)
            
            # 尝试删除相关的提示词文件（可选）
            # 注意：不自动删除prompt/下的文件，避免误删
            
            return {
                "success": True,
                "message": f"Skill '{skill_name}' 已卸载"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"卸载失败: {str(e)}"
            }
    
    def list_installed_skills(self) -> Dict:
        """列出已安装的Skills
        
        Returns:
            Dict with list of installed skills
        """
        skills = []
        
        try:
            if os.path.exists(self.skills_dir):
                for skill_name in os.listdir(self.skills_dir):
                    skill_path = os.path.join(self.skills_dir, skill_name)
                    if os.path.isdir(skill_path):
                        skill_md = os.path.join(skill_path, "SKILL.md")
                        
                        skill_info = {
                            "name": skill_name,
                            "path": skill_path,
                            "has_skill_md": os.path.exists(skill_md)
                        }
                        
                        if os.path.exists(skill_md):
                            parsed_name = self._parse_skill_name(skill_md)
                            if parsed_name:
                                skill_info["name"] = parsed_name
                        
                        # 检查是否有__init__.py（可执行）
                        skill_info["executable"] = os.path.exists(
                            os.path.join(skill_path, "__init__.py")
                        )
                        
                        skills.append(skill_info)
            
            return {
                "success": True,
                "skills": skills,
                "count": len(skills)
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"列出Skills失败: {str(e)}"
            }


def install_skill(archive_path: str, skill_name: str = None) -> Dict:
    """便捷函数：安装Skill
    
    Args:
        archive_path: 压缩包路径
        skill_name: Skill名称（可选）
    
    Returns:
        Dict with installation result
    """
    installer = SkillInstaller()
    return installer.install_from_archive(archive_path, skill_name)


def uninstall_skill(skill_name: str) -> Dict:
    """便捷函数：卸载Skill
    
    Args:
        skill_name: Skill名称
    
    Returns:
        Dict with uninstallation result
    """
    installer = SkillInstaller()
    return installer.uninstall_skill(skill_name)


def list_skills() -> Dict:
    """便捷函数：列出已安装的Skills
    
    Returns:
        Dict with list of skills
    """
    installer = SkillInstaller()
    return installer.list_installed_skills()


# CLI接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Humanaize Skill Installer")
    parser.add_argument("action", choices=["install", "uninstall", "list"], help="操作类型")
    parser.add_argument("--archive", help="压缩包路径（用于install）")
    parser.add_argument("--name", help="Skill名称")
    
    args = parser.parse_args()
    
    installer = SkillInstaller()
    
    if args.action == "install":
        if not args.archive:
            print("错误：需要指定压缩包路径 --archive")
            sys.exit(1)
        result = installer.install_from_archive(args.archive, args.name)
    
    elif args.action == "uninstall":
        if not args.name:
            print("错误：需要指定Skill名称 --name")
            sys.exit(1)
        result = installer.uninstall_skill(args.name)
    
    elif args.action == "list":
        result = installer.list_installed_skills()
    
    print(json.dumps(result, indent=2, ensure_ascii=False))