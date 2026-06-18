"""
Humanaize v2.0 - Skills CLI Interface
Skills management through command line interface
"""

import os
import sys
import json
import shutil
import zipfile
from typing import Dict, List, Optional


class SkillsCLI:
    """Skills command line interface manager"""
    
    def __init__(self):
        # Try multiple possible skills directories
        # Priority: system-wide -> user home -> local dev
        possible_dirs = [
            "/usr/share/humanaize2/skills",
            os.path.join(os.path.expanduser("~"), ".humanaize", "skills"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills"),
            os.path.join(os.path.dirname(__file__), "skills")
        ]
        
        self.skills_dir = "/usr/share/humanaize2/skills"
        for dir_path in possible_dirs:
            if os.path.isdir(dir_path) and len(os.listdir(dir_path)) > 0:
                self.skills_dir = dir_path
                break
        
        # Try multiple possible config paths
        self.skills_config_path = os.path.join(os.path.dirname(__file__), "data", "skills_config.json")
        if not os.path.exists(self.skills_config_path):
            system_config = "/var/lib/humanaize/skills_config.json"
            if os.path.exists(system_config):
                self.skills_config_path = system_config
            else:
                os.makedirs(os.path.join(os.path.expanduser("~"), ".humanaize"), exist_ok=True)
                self.skills_config_path = os.path.join(os.path.expanduser("~"), ".humanaize", "skills_config.json")
        
        self.skills_config = self._load_skills_config()
        
        os.makedirs(self.skills_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.skills_config_path), exist_ok=True)
    
    def _load_skills_config(self) -> Dict:
        """Load skills configuration from file"""
        try:
            if os.path.exists(self.skills_config_path):
                with open(self.skills_config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[SkillsCLI] Error loading config: {e}")
        
        return {
            'skills': {},
            'all_enabled': False
        }
    
    def _save_skills_config(self):
        """Save skills configuration to file"""
        try:
            with open(self.skills_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.skills_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[SkillsCLI] Error saving config: {e}")
    
    def _get_installed_skills(self) -> List[str]:
        """Get list of installed skills"""
        installed = []
        
        if os.path.exists(self.skills_dir):
            for skill_name in os.listdir(self.skills_dir):
                skill_path = os.path.join(self.skills_dir, skill_name)
                if os.path.isdir(skill_path):
                    skill_file = os.path.join(skill_path, "SKILL.md")
                    if os.path.exists(skill_file):
                        installed.append(skill_name)
        
        return installed
    
    def _get_skill_info(self, skill_name: str) -> Optional[Dict]:
        """Get information about a specific skill"""
        skill_path = os.path.join(self.skills_dir, skill_name)
        skill_file = os.path.join(skill_path, "SKILL.md")
        
        if not os.path.exists(skill_file):
            return None
        
        try:
            import yaml
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
            match = re.match(pattern, content, re.DOTALL)
            
            if match:
                frontmatter = yaml.safe_load(match.group(1))
                return {
                    'name': frontmatter.get('name', skill_name),
                    'description': frontmatter.get('description', ''),
                    'metadata': frontmatter.get('metadata', {}),
                    'enabled': self.skills_config.get('skills', {}).get(skill_name, {}).get('enabled', False)
                }
        except Exception as e:
            print(f"[SkillsCLI] Error reading skill info: {e}")
        
        return None
    
    def _resolve_skill_name(self, skill_name: str, installed_skills: List[str]) -> Optional[str]:
        """Resolve skill name with alias support"""
        skill_name_lower = skill_name.lower()
        
        for s in installed_skills:
            if s.lower() == skill_name_lower:
                return s
        
        aliases = {
            'hsn': 'humanaizesocietynetwork',
        }
        
        if skill_name_lower in aliases:
            target = aliases[skill_name_lower]
            for s in installed_skills:
                if s.lower() == target:
                    return s
        
        return None
    
    def enable_skill(self, skill_name: str) -> bool:
        """Enable a specific skill"""
        installed_skills = self._get_installed_skills()
        
        actual_skill_name = self._resolve_skill_name(skill_name, installed_skills)
        
        if actual_skill_name is None:
            print(f"[SkillsCLI] Error: Skill '{skill_name}' is not installed")
            print(f"[SkillsCLI] Installed skills: {', '.join(installed_skills) if installed_skills else 'None'}")
            return False
        
        is_hsn = actual_skill_name.lower() in ['hsn', 'humanizesocietynetwork', 'humanaizesocietynetwork']
        
        if is_hsn:
            if not self._show_hsn_license():
                return False
        
        if 'skills' not in self.skills_config:
            self.skills_config['skills'] = {}
        
        self.skills_config['skills'][actual_skill_name] = {
            'enabled': True,
            'enabled_at': self._get_timestamp()
        }
        
        self._save_skills_config()
        
        skill_info = self._get_skill_info(skill_name)
        if skill_info:
            print(f"[SkillsCLI] Skill '{skill_info.get('name', skill_name)}' enabled successfully")
            print(f"[SkillsCLI] Description: {skill_info.get('description', 'No description')}")
        else:
            print(f"[SkillsCLI] Skill '{skill_name}' enabled successfully")
        
        return True
    
    def _show_hsn_license(self) -> bool:
        """Show HSN license and ask for user agreement"""
        license_path = os.path.join(self.skills_dir, "HumanaizeSocietyNetwork", "License.md")
        
        if not os.path.exists(license_path):
            print(f"[SkillsCLI] Warning: License file not found at {license_path}")
            return True
        
        print("\n" + "=" * 70)
        print("  HUMANAIZE SOCIETY NETWORK - LICENSE AGREEMENT")
        print("=" * 70)
        print()
        
        try:
            with open(license_path, 'r', encoding='utf-8') as f:
                license_content = f.read()
            import sys
            sys.stdout.reconfigure(encoding='utf-8')
            print(license_content)
        except Exception as e:
            print(f"[SkillsCLI] Error reading license file: {e}")
            return False
        
        print()
        print("=" * 70)
        print()
        print("  Please read the license agreement above carefully.")
        print()
        
        while True:
            try:
                response = input("  Do you agree to the license terms? (yes/no): ").strip().lower()
                
                if response in ['yes', 'y', '是', '同意', 'agree']:
                    print("\n  [SkillsCLI] Thank you for agreeing to the license terms.")
                    return True
                elif response in ['no', 'n', '否', '不同意', 'disagree', 'reject']:
                    print("\n  [SkillsCLI] License not accepted. HSN skill will not be enabled.")
                    return False
                else:
                    print("  Please enter 'yes' or 'no' (or '是'/'否' in Chinese)")
            except (KeyboardInterrupt, EOFError):
                print("\n\n  [SkillsCLI] Operation cancelled by user.")
                return False
    
    def enable_all_skills(self) -> bool:
        """Enable all installed skills"""
        installed_skills = self._get_installed_skills()
        
        if not installed_skills:
            print("[SkillsCLI] No skills installed")
            return False
        
        if 'skills' not in self.skills_config:
            self.skills_config['skills'] = {}
        
        for skill_name in installed_skills:
            self.skills_config['skills'][skill_name] = {
                'enabled': True,
                'enabled_at': self._get_timestamp()
            }
        
        self.skills_config['all_enabled'] = True
        
        self._save_skills_config()
        
        print(f"[SkillsCLI] All skills enabled successfully ({len(installed_skills)} skills)")
        for skill_name in installed_skills:
            print(f"  - {skill_name}")
        
        return True
    
    def disable_skill(self, skill_name: str) -> bool:
        """Disable a specific skill"""
        installed_skills = self._get_installed_skills()
        
        actual_skill_name = self._resolve_skill_name(skill_name, installed_skills)
        
        if actual_skill_name is None:
            print(f"[SkillsCLI] Error: Skill '{skill_name}' is not installed")
            return False
        
        if 'skills' not in self.skills_config:
            self.skills_config['skills'] = {}
        
        self.skills_config['skills'][actual_skill_name] = {
            'enabled': False,
            'disabled_at': self._get_timestamp()
        }
        
        self.skills_config['all_enabled'] = False
        
        self._save_skills_config()
        
        print(f"[SkillsCLI] Skill '{skill_name}' disabled successfully")
        return True
    
    def disable_all_skills(self) -> bool:
        """Disable all skills"""
        installed_skills = self._get_installed_skills()
        
        if 'skills' not in self.skills_config:
            self.skills_config['skills'] = {}
        
        for skill_name in installed_skills:
            self.skills_config['skills'][skill_name] = {
                'enabled': False,
                'disabled_at': self._get_timestamp()
            }
        
        self.skills_config['all_enabled'] = False
        
        self._save_skills_config()
        
        print(f"[SkillsCLI] All skills disabled successfully")
        return True
    
    def install_skill(self, skill_source: str) -> bool:
        """Install a skill from zip file or directory"""
        
        if not os.path.exists(skill_source):
            print(f"[SkillsCLI] Error: Skill source '{skill_source}' not found")
            return False
        
        if skill_source.endswith('.zip'):
            return self._install_from_zip(skill_source)
        elif os.path.isdir(skill_source):
            return self._install_from_directory(skill_source)
        else:
            print(f"[SkillsCLI] Error: Invalid skill source format (must be .zip file or directory)")
            return False
    
    def _install_from_zip(self, zip_path: str) -> bool:
        """Install skill from zip file"""
        try:
            temp_dir = os.path.join(os.path.dirname(__file__), "temp_skill_install")
            os.makedirs(temp_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            extracted_items = os.listdir(temp_dir)
            
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_dir, extracted_items[0])):
                skill_dir_name = extracted_items[0]
                skill_temp_path = os.path.join(temp_dir, skill_dir_name)
            else:
                skill_dir_name = os.path.splitext(os.path.basename(zip_path))[0]
                skill_temp_path = temp_dir
            
            skill_file = os.path.join(skill_temp_path, "SKILL.md")
            if not os.path.exists(skill_file):
                print(f"[SkillsCLI] Error: No SKILL.md found in the zip file")
                shutil.rmtree(temp_dir)
                return False
            
            skill_dest_path = os.path.join(self.skills_dir, skill_dir_name)
            
            if os.path.exists(skill_dest_path):
                print(f"[SkillsCLI] Warning: Skill '{skill_dir_name}' already exists, overwriting...")
                shutil.rmtree(skill_dest_path)
            
            shutil.copytree(skill_temp_path, skill_dest_path)
            
            shutil.rmtree(temp_dir)
            
            skill_info = self._get_skill_info(skill_dir_name)
            if skill_info:
                print(f"[SkillsCLI] Skill '{skill_info.get('name', skill_dir_name)}' installed successfully")
                print(f"[SkillsCLI] Description: {skill_info.get('description', 'No description')}")
            else:
                print(f"[SkillsCLI] Skill '{skill_dir_name}' installed successfully")
            
            print(f"[SkillsCLI] Note: Skill is disabled by default. Use 'humanaize2 skills -enable {skill_dir_name}' to enable it.")
            
            return True
            
        except Exception as e:
            print(f"[SkillsCLI] Error installing skill from zip: {e}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False
    
    def _install_from_directory(self, dir_path: str) -> bool:
        """Install skill from directory"""
        try:
            skill_file = os.path.join(dir_path, "SKILL.md")
            if not os.path.exists(skill_file):
                print(f"[SkillsCLI] Error: No SKILL.md found in the directory")
                return False
            
            skill_dir_name = os.path.basename(dir_path)
            skill_dest_path = os.path.join(self.skills_dir, skill_dir_name)
            
            if os.path.exists(skill_dest_path):
                print(f"[SkillsCLI] Warning: Skill '{skill_dir_name}' already exists, overwriting...")
                shutil.rmtree(skill_dest_path)
            
            shutil.copytree(dir_path, skill_dest_path)
            
            skill_info = self._get_skill_info(skill_dir_name)
            if skill_info:
                print(f"[SkillsCLI] Skill '{skill_info.get('name', skill_dir_name)}' installed successfully")
                print(f"[SkillsCLI] Description: {skill_info.get('description', 'No description')}")
            else:
                print(f"[SkillsCLI] Skill '{skill_dir_name}' installed successfully")
            
            print(f"[SkillsCLI] Note: Skill is disabled by default. Use 'humanaize2 skills -enable {skill_dir_name}' to enable it.")
            
            return True
            
        except Exception as e:
            print(f"[SkillsCLI] Error installing skill from directory: {e}")
            return False
    
    def uninstall_skill(self, skill_name: str) -> bool:
        """Uninstall a skill"""
        skill_path = os.path.join(self.skills_dir, skill_name)
        
        if not os.path.exists(skill_path):
            print(f"[SkillsCLI] Error: Skill '{skill_name}' is not installed")
            return False
        
        try:
            shutil.rmtree(skill_path)
            
            if 'skills' in self.skills_config and skill_name in self.skills_config['skills']:
                del self.skills_config['skills'][skill_name]
            
            self._save_skills_config()
            
            print(f"[SkillsCLI] Skill '{skill_name}' uninstalled successfully")
            return True
            
        except Exception as e:
            print(f"[SkillsCLI] Error uninstalling skill: {e}")
            return False
    
    def list_skills(self):
        """List all installed skills with their status"""
        installed_skills = self._get_installed_skills()
        
        if not installed_skills:
            print("[SkillsCLI] No skills installed")
            print("[SkillsCLI] Use 'humanaize2 skills -install [skill_file.zip]' to install a skill")
            return
        
        print("\n" + "=" * 60)
        print("  Installed Skills")
        print("=" * 60)
        
        for skill_name in installed_skills:
            skill_info = self._get_skill_info(skill_name)
            if skill_info:
                status = "[+]" if skill_info.get('enabled', False) else "[-]"
                print(f"\n  {status} {skill_info.get('name', skill_name)}")
                print(f"    Description: {skill_info.get('description', 'No description')[:50]}...")
                
                metadata = skill_info.get('metadata', {})
                if metadata:
                    category = metadata.get('category', 'general')
                    risk_level = metadata.get('risk_level', 'low')
                    print(f"    Category: {category}, Risk: {risk_level}")
            else:
                status = "[-]"
                print(f"\n  {status} {skill_name}")
        
        print("\n" + "=" * 60)
        print(f"  Total: {len(installed_skills)} skills installed")
        print("=" * 60)
    
    def show_skill_details(self, skill_name: str):
        """Show detailed information about a skill"""
        skill_info = self._get_skill_info(skill_name)
        
        if not skill_info:
            print(f"[SkillsCLI] Error: Skill '{skill_name}' not found")
            return
        
        print("\n" + "=" * 60)
        print(f"  Skill: {skill_info.get('name', skill_name)}")
        print("=" * 60)
        
        print(f"\n  Status: {'Enabled' if skill_info.get('enabled', False) else 'Disabled'}")
        print(f"  Description: {skill_info.get('description', 'No description')}")
        
        metadata = skill_info.get('metadata', {})
        if metadata:
            print("\n  Metadata:")
            for key, value in metadata.items():
                print(f"    {key}: {value}")
        
        skill_path = os.path.join(self.skills_dir, skill_name)
        print(f"\n  Path: {skill_path}")
        
        skill_file = os.path.join(skill_path, "SKILL.md")
        if os.path.exists(skill_file):
            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                import re
                pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
                match = re.match(pattern, content, re.DOTALL)
                
                if match:
                    instructions = match.group(2).strip()
                    if instructions:
                        print("\n  Instructions:")
                        print("  " + "-" * 56)
                        for line in instructions.split('\n')[:20]:
                            print(f"    {line}")
                        if len(instructions.split('\n')) > 20:
                            print("    ... (more instructions available)")
            except Exception as e:
                print(f"\n  Error reading instructions: {e}")
        
        print("\n" + "=" * 60)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def process_command(self, args: List[str]) -> bool:
        """Process skills command from CLI"""
        
        if len(args) < 2:
            self._print_usage()
            return False
        
        command = args[1].lower()
        
        if command == '-enable':
            if len(args) < 3:
                print("[SkillsCLI] Error: Missing skill name")
                print("[SkillsCLI] Usage: humanaize2 skills -enable [skill_name]")
                print("[SkillsCLI]        humanaize2 skills -enable all")
                return False
            
            target = args[2].lower()
            
            if target == 'all':
                return self.enable_all_skills()
            else:
                return self.enable_skill(target)
        
        elif command == '-disable':
            if len(args) < 3:
                print("[SkillsCLI] Error: Missing skill name")
                print("[SkillsCLI] Usage: humanaize2 skills -disable [skill_name]")
                print("[SkillsCLI]        humanaize2 skills -disable all")
                return False
            
            target = args[2].lower()
            
            if target == 'all':
                return self.disable_all_skills()
            else:
                return self.disable_skill(target)
        
        elif command == '-install':
            if len(args) < 3:
                print("[SkillsCLI] Error: Missing skill source")
                print("[SkillsCLI] Usage: humanaize2 skills -install [skill_file.zip]")
                print("[SkillsCLI]        humanaize2 skills -install [skill_directory]")
                return False
            
            skill_source = args[2]
            return self.install_skill(skill_source)
        
        elif command == '-uninstall':
            if len(args) < 3:
                print("[SkillsCLI] Error: Missing skill name")
                print("[SkillsCLI] Usage: humanaize2 skills -uninstall [skill_name]")
                return False
            
            skill_name = args[2]
            return self.uninstall_skill(skill_name)
        
        elif command == '-list':
            self.list_skills()
            return True
        
        elif command == '-info':
            if len(args) < 3:
                print("[SkillsCLI] Error: Missing skill name")
                print("[SkillsCLI] Usage: humanaize2 skills -info [skill_name]")
                return False
            
            skill_name = args[2]
            self.show_skill_details(skill_name)
            return True
        
        elif command == '-help':
            self._print_usage()
            return True
        
        else:
            print(f"[SkillsCLI] Error: Unknown command '{command}'")
            self._print_usage()
            return False
    
    def _print_usage(self):
        """Print usage information"""
        print("\n" + "=" * 60)
        print("  Humanaize v2.0 - Skills Management")
        print("=" * 60)
        
        print("\n  Commands:")
        print("    humanaize2 skills -enable [skill_name]    Enable a specific skill")
        print("    humanaize2 skills -enable all             Enable all installed skills")
        print("    humanaize2 skills -disable [skill_name]   Disable a specific skill")
        print("    humanaize2 skills -disable all            Disable all skills")
        print("    humanaize2 skills -install [source]       Install a skill (zip or directory)")
        print("    humanaize2 skills -uninstall [skill_name] Uninstall a skill")
        print("    humanaize2 skills -list                   List all installed skills")
        print("    humanaize2 skills -info [skill_name]      Show skill details")
        print("    humanaize2 skills -help                   Show this help message")
        
        print("\n  Notes:")
        print("    - All skills are disabled by default after installation")
        print("    - Use '-enable' commands to activate skills")
        print("    - Skills can be installed from .zip files or directories")
        print("    - Manual installation: extract zip to './skills' folder")
        
        print("\n" + "=" * 60)


def main():
    """Main entry point for Skills CLI"""
    if len(sys.argv) < 2:
        print("[SkillsCLI] Error: No command provided")
        print("[SkillsCLI] Usage: humanaize2 skills [command]")
        return
    
    skills_cli = SkillsCLI()
    skills_cli.process_command(sys.argv)


if __name__ == "__main__":
    main()