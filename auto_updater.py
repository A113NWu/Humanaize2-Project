import os
import json
import subprocess
import urllib.request
import zipfile
import shutil
from datetime import datetime
from typing import Optional, Dict

class AutoUpdater:
    def __init__(self, repo_url: str, current_version: str = "2.1.0"):
        self.repo_url = repo_url
        self.current_version = current_version
        self.update_info = None
        self.last_check_file = os.path.join(os.path.dirname(__file__), "data", "last_update_check.json")
        
    def get_local_version(self) -> str:
        version_file = os.path.join(os.path.dirname(__file__), "version.json")
        if os.path.exists(version_file):
            try:
                with open(version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("version", self.current_version)
            except Exception:
                pass
        return self.current_version
    
    def save_local_version(self, version: str):
        os.makedirs(os.path.dirname(__file__), exist_ok=True)
        version_file = os.path.join(os.path.dirname(__file__), "version.json")
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["version"] = version
        data["last_updated"] = datetime.now().isoformat()
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def check_for_updates(self) -> Dict:
        result = {
            "has_update": False,
            "latest_version": self.get_local_version(),
            "current_version": self.get_local_version(),
            "release_notes": "",
            "download_url": "",
            "error": None
        }
        
        try:
            api_url = self.repo_url.replace("github.com", "api.github.com/repos")
            if not api_url.endswith("/repos"):
                api_url = api_url.replace("https://api.github.com/repos", "")
            
            releases_url = f"https://api.github.com/repos/A113NWu/Humanaize2-Project/releases/latest"
            
            req = urllib.request.Request(
                releases_url,
                headers={"User-Agent": "Humanaize2-Update-Checker"}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                
                latest_version = data.get("tag_name", "").lstrip("v")
                
                result["latest_version"] = latest_version
                result["current_version"] = self.get_local_version()
                result["release_notes"] = data.get("body", "No release notes available.")
                result["download_url"] = data.get("zipball_url", "")
                
                if latest_version > result["current_version"]:
                    result["has_update"] = True
                
                self._save_last_check(latest_version)
                
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _save_last_check(self, version: str):
        os.makedirs(os.path.dirname(self.last_check_file), exist_ok=True)
        try:
            with open(self.last_check_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_checked": datetime.now().isoformat(),
                    "latest_version": version
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get_last_check_info(self) -> Optional[Dict]:
        if os.path.exists(self.last_check_file):
            try:
                with open(self.last_check_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None
    
    def download_and_install_update(self, progress_callback=None) -> Dict:
        result = {
            "success": False,
            "message": "",
            "error": None
        }
        
        try:
            update_info = self.check_for_updates()
            if not update_info.get("has_update"):
                result["message"] = "You are already on the latest version."
                return result
            
            download_url = update_info.get("download_url")
            if not download_url:
                result["error"] = "No download URL available"
                return result
            
            if progress_callback:
                progress_callback("Downloading update...")
            
            temp_dir = os.path.join(os.path.dirname(__file__), "temp_update")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            
            zip_path = os.path.join(temp_dir, "update.zip")
            
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Humanaize2-Update-Downloader"}
            )
            
            with urllib.request.urlopen(req, timeout=60) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192
                
                with open(zip_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(f"Downloading... {progress}%")
            
            if progress_callback:
                progress_callback("Extracting files...")
            
            extract_dir = os.path.join(temp_dir, "extracted")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            
            if progress_callback:
                progress_callback("Installing files...")
            
            extracted_items = os.listdir(extract_dir)
            if extracted_items:
                source_dir = os.path.join(extract_dir, extracted_items[0])
                
                for item in os.listdir(source_dir):
                    if item in [".git", "models", "llama", "temp_update", "data"]:
                        continue
                    
                    src = os.path.join(source_dir, item)
                    dst = os.path.join(os.path.dirname(__file__), item)
                    
                    if os.path.isdir(src):
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                    elif os.path.isfile(src):
                        shutil.copy2(src, dst)
            
            shutil.rmtree(temp_dir)
            
            self.save_local_version(update_info["latest_version"])
            
            result["success"] = True
            result["message"] = f"Successfully updated to version {update_info['latest_version']}. Please restart the application."
            
        except Exception as e:
            result["error"] = str(e)
            result["message"] = f"Update failed: {e}"
        
        return result
    
    def pull_latest_from_git(self, progress_callback=None) -> Dict:
        result = {
            "success": False,
            "message": "",
            "error": None
        }
        
        try:
            if progress_callback:
                progress_callback("Checking for updates...")
            
            update_info = self.check_for_updates()
            
            if not update_info.get("has_update"):
                result["message"] = "You are already on the latest version."
                return result
            
            if progress_callback:
                progress_callback("Pulling latest changes from Git...")
            
            git_dir = os.path.dirname(__file__)
            
            fetch_result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=git_dir,
                capture_output=True,
                text=True
            )
            
            if fetch_result.returncode != 0:
                result["error"] = f"Git fetch failed: {fetch_result.stderr}"
                return result
            
            if progress_callback:
                progress_callback("Resetting to latest commit...")
            
            reset_result = subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=git_dir,
                capture_output=True,
                text=True
            )
            
            if reset_result.returncode != 0:
                result["error"] = f"Git reset failed: {reset_result.stderr}"
                return result
            
            self.save_local_version(update_info["latest_version"])
            
            result["success"] = True
            result["message"] = f"Successfully updated to version {update_info['latest_version']}. Please restart the application."
            
        except Exception as e:
            result["error"] = str(e)
            result["message"] = f"Update failed: {e}"
        
        return result
    
    def get_update_status(self) -> str:
        info = self.get_last_check_info()
        if not info:
            return "Never checked for updates"
        
        last_checked = info.get("last_checked", "Unknown")
        latest = info.get("latest_version", "Unknown")
        current = self.get_local_version()
        
        if latest > current:
            return f"Update available: v{latest} (you have v{current})"
        elif latest < current:
            return f"You are on a newer version ({current}) than the latest release ({latest})"
        else:
            return f"You are up to date (v{current})"


def check_for_updates(repo_url: str = "https://github.com/A113NWu/Humanaize2-Project.git") -> Dict:
    updater = AutoUpdater(repo_url)
    return updater.check_for_updates()


def install_update(repo_url: str = "https://github.com/A113NWu/Humanaize2-Project.git", progress_callback=None) -> Dict:
    updater = AutoUpdater(repo_url)
    return updater.download_and_install_update(progress_callback)


def pull_latest(repo_url: str = "https://github.com/A113NWu/Humanaize2-Project.git", progress_callback=None) -> Dict:
    updater = AutoUpdater(repo_url)
    return updater.pull_latest_from_git(progress_callback)


if __name__ == "__main__":
    updater = AutoUpdater("https://github.com/A113NWu/Humanaize2-Project.git")
    
    print("Checking for updates...")
    info = updater.check_for_updates()
    print(f"Has update: {info['has_update']}")
    print(f"Current: {info['current_version']}, Latest: {info['latest_version']}")
    if info.get("release_notes"):
        print(f"Release notes: {info['release_notes']}")
    if info.get("error"):
        print(f"Error: {info['error']}")