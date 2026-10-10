"""
Humanaize Auto Updater
Handles software updates from GitHub
"""

import os
import sys
import json
import tempfile
import subprocess
import zipfile
import shutil
from datetime import datetime
from typing import Optional, Dict, Callable

# 导入统一版本管理模块
try:
    from .version import get_version, get_update_checker_agent, get_downloader_agent
except ImportError:
    # 如果从其他目录导入，提供备用方案
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from version import get_version, get_update_checker_agent, get_downloader_agent

# Try to use requests for better error handling
try:
    import requests
    USE_REQUESTS = True
except ImportError:
    import urllib.request
    USE_REQUESTS = False


class AutoUpdater:
    def __init__(self, repo_url: str, current_version: str = None):
        self.repo_url = repo_url
        self.current_version = self._normalize_version(current_version or get_version())
        self.update_info = None
        self.last_check_file = os.path.join(os.path.dirname(__file__), "data", "last_update_check.json")
        self._session = None
        if USE_REQUESTS:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": get_update_checker_agent()
            })

    @staticmethod
    def _normalize_version(v: str) -> str:
        """统一内部版本号格式：移除 v 前缀，用于存储与比较。内部始终使用 X.X.X 纯数字形式。"""
        if not v:
            return "0.0.0"
        return v.strip().lstrip("vV")

    @staticmethod
    def _format_release_tag(v: str) -> str:
        """将内部版本号格式化为 Release 标签：vX.X.X（GitHub 标签标准命名）。"""
        n = AutoUpdater._normalize_version(v)
        return f"v{n}"

    def _get_session(self):
        """Get or create a requests session"""
        if USE_REQUESTS and not self._session:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": get_update_checker_agent()
            })
        return self._session
    
    def get_local_version(self) -> str:
        # 使用统一的版本获取函数，并标准化为 X.X.X
        return self._normalize_version(get_version())

    def save_local_version(self, version: str):
        os.makedirs(os.path.dirname(__file__), exist_ok=True)
        version_file = os.path.join(os.path.dirname(__file__), "version.json")
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        # 统一以不带 v 前缀的形式存储，避免前缀重复
        data["version"] = self._normalize_version(version)
        data["last_updated"] = datetime.now().isoformat()
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _fetch_with_retry(self, url: str, max_retries: int = 3, timeout: int = 10) -> Optional[Dict]:
        """Fetch URL with retry logic"""
        for attempt in range(max_retries):
            try:
                if USE_REQUESTS:
                    session = self._get_session()
                    response = session.get(url, timeout=timeout)
                    response.raise_for_status()
                    return response.json()
                else:
                    req = urllib.request.Request(url, headers={"User-Agent": get_update_checker_agent()})
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        return json.loads(response.read().decode("utf-8"))
            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return None
    
    def check_for_updates(self) -> Dict:
        current_internal = self.get_local_version()
        result = {
            "has_update": False,
            "latest_version": current_internal,        # 内部版本号 X.X.X（无 v 前缀）
            "latest_tag": self._format_release_tag(current_internal),  # Release 标签 vX.X.X
            "current_version": current_internal,
            "current_tag": self._format_release_tag(current_internal),
            "release_notes": "",
            "download_url": "",
            "installer_url": "",
            "error": None
        }

        try:
            # Build the GitHub API URL for latest release
            releases_url = "https://api.github.com/repos/A113NWu/Humanaize2-Project/releases/latest"

            # Try multiple endpoints
            data = self._fetch_with_retry(releases_url)

            if data is None:
                # Try alternative method using tags
                tags_url = "https://api.github.com/repos/A113NWu/Humanaize2-Project/tags"
                data = self._fetch_with_retry(tags_url)
                if isinstance(data, list) and data:
                    # Get the first tag (usually the latest) - tag 名统一格式为 vX.X.X
                    latest_tag = data[0].get("name", "")
                    latest_ver = self._normalize_version(latest_tag)
                    result["latest_version"] = latest_ver
                    result["latest_tag"] = self._format_release_tag(latest_ver)
                    result["download_url"] = f"https://github.com/A113NWu/Humanaize2-Project/archive/refs/tags/{result['latest_tag']}.zip"

            if data and isinstance(data, dict):
                latest_tag_raw = data.get("tag_name", "")
                latest_ver = self._normalize_version(latest_tag_raw)
                result["latest_version"] = latest_ver
                result["latest_tag"] = self._format_release_tag(latest_ver)
                result["release_notes"] = data.get("body", "No release notes available.")
                # 優先選取 Windows x64 的 Inno 安裝包資產
                result["installer_url"] = self._select_installer_asset(data.get("assets") or [])
                # 向後兼容：下載鏈接直接指向安裝包；無安裝包時退回 zipball（僅開發態使用）
                result["download_url"] = result["installer_url"] or data.get("zipball_url", "") or (
                    f"https://github.com/A113NWu/Humanaize2-Project/archive/refs/tags/{result['latest_tag']}.zip"
                )

            result["current_version"] = current_internal
            result["current_tag"] = self._format_release_tag(current_internal)

            # Compare versions（使用内部标准的 X.X.X 做比较）
            if self._version_compare(result["latest_version"], result["current_version"]) > 0:
                result["has_update"] = True

            # 保存时使用内部标准版本号，避免 v 前缀重复
            self._save_last_check(result["latest_version"])

        except Exception as e:
            result["error"] = str(e)

        return result

    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare two version strings（统一先去掉 v 前缀，按数字段比较）"""
        vv1 = self._normalize_version(v1)
        vv2 = self._normalize_version(v2)
        parts1 = [int(p) for p in vv1.split(".") if p.isdigit()]
        parts2 = [int(p) for p in vv2.split(".") if p.isdigit()]

        # Pad with zeros to make lengths equal
        max_len = max(len(parts1), len(parts2), 3)
        parts1 += [0] * (max_len - len(parts1))
        parts2 += [0] * (max_len - len(parts2))

        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        return 0
    
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
    
    @staticmethod
    def _select_installer_asset(assets: list) -> str:
        """從 Release assets 中挑選 Windows x64 安裝包。

        優先級：Humanaize2-Setup-x86_64-v*.exe > 任意 Setup*.exe > 任意 .exe。
        """
        exes = []
        for a in assets or []:
            name = str(a.get("name") or "").lower()
            url = str(a.get("browser_download_url") or "")
            if name.endswith(".exe") and url:
                exes.append((name, url))
        for needle in ("setup-x86_64", "setup_x86_64", "setup-x64", "x86_64", "x64", "amd64"):
            for name, url in exes:
                if needle in name:
                    return url
        if exes:
            return exes[0][1]
        return ""

    def download_and_install_update(self, progress_callback=None, force=False) -> Dict:
        result = {
            "success": False,
            "message": "",
            "error": None
        }

        try:
            update_info = self.check_for_updates()
            if not update_info.get("has_update") and not force:
                result["message"] = "You are already on the latest version."
                return result

            # 打包後的 Windows 本體：下載 Inno 安裝包並靜默升級。
            # 舊邏輯（解壓源碼 zip 覆蓋文件）只適用於開發態，在 onefile 安裝版上
            # 只會覆蓋 PyInstaller 內部文件、無法更新 exe，已廢棄。
            if sys.platform == "win32" and getattr(sys, "frozen", False):
                return self._install_via_inno(update_info, progress_callback)

            return self._install_from_zip(update_info, progress_callback)

        except Exception as e:
            result["error"] = str(e)
            result["message"] = f"Update failed: {e}"

        return result

    def _download_file(self, url: str, dest_path: str, progress_callback, label: str):
        """流式下載文件，支持 requests / urllib 雙後端。"""
        if USE_REQUESTS:
            session = self._get_session()
            response = session.get(url, stream=True, timeout=60, allow_redirects=True)
            response.raise_for_status()
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(f"{label}... {progress}%")
        else:
            req = urllib.request.Request(url, headers={"User-Agent": get_downloader_agent()})
            with urllib.request.urlopen(req, timeout=60) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(f"{label}... {progress}%")

    def _install_via_inno(self, update_info: Dict, progress_callback) -> Dict:
        """下載 Inno 安裝包，交由獨立 PowerShell 引導進程靜默安裝並重啟。"""
        result = {"success": False, "message": "", "error": None}

        installer_url = update_info.get("installer_url") or ""
        if not installer_url:
            result["error"] = "該版本未提供 Windows 安裝包（Setup .exe），請到 Releases 頁面手動下載。"
            result["message"] = result["error"]
            return result

        version = update_info.get("latest_version", "new")
        setup_path = os.path.join(tempfile.gettempdir(), f"Humanaize2-Setup-v{version}.exe")

        if progress_callback:
            progress_callback("Downloading installer...")
        self._download_file(installer_url, setup_path, progress_callback, "Downloading installer")

        # 基本完整性校驗：MZ 頭 + 體積（安裝包通常 50MB+）
        if os.path.getsize(setup_path) < 1024 * 1024:
            result["error"] = "安裝包下載不完整（體積異常）"
            result["message"] = result["error"]
            return result
        with open(setup_path, "rb") as f:
            if f.read(2) != b"MZ":
                result["error"] = "下載文件不是有效的 Windows 可執行文件"
                result["message"] = result["error"]
                return result

        # 當前 exe 所在目錄（Inno 會記住上次安裝目錄，靜默升級裝到同一處）
        install_dir = os.path.dirname(os.path.abspath(sys.executable))
        exe_after_install = os.path.join(install_dir, "Humanaize2.exe")
        log_path = os.path.join(tempfile.gettempdir(), "humanaize2_update.log")

        # 引導腳本：等本體退出 → 管理員靜默安裝 → 重新啟動本體。
        # 必須是獨立進程（DETACHED_PROCESS），否則本體被關閉時腳本一併死亡。
        bootstrap = (
            "$ErrorActionPreference = 'Continue'\n"
            "Start-Sleep -Seconds 3\n"
            "Stop-Process -Name 'Humanaize2' -Force -ErrorAction SilentlyContinue\n"
            "Start-Sleep -Seconds 2\n"
            f"$setup = {json.dumps(setup_path)}\n"
            f"$exe = {json.dumps(exe_after_install)}\n"
            f"Start-Transcript -Path {json.dumps(log_path)} -Force | Out-Null\n"
            "$p = Start-Process -FilePath $setup -ArgumentList "
            "'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS','/NOCANCEL' "
            "-Verb RunAs -Wait -PassThru\n"
            "Write-Output ('InstallerExitCode=' + $p.ExitCode)\n"
            "Start-Sleep -Seconds 2\n"
            "if (Test-Path $exe) { Start-Process -FilePath $exe -ArgumentList '--tray' }\n"
            "Stop-Transcript | Out-Null\n"
        )
        bootstrap_path = os.path.join(tempfile.gettempdir(), "humanaize2_update_bootstrap.ps1")
        with open(bootstrap_path, "w", encoding="utf-8-sig") as f:
            f.write(bootstrap)

        # 0x00000008 DETACHED_PROCESS | 0x00000200 NEW_PROCESS_GROUP | 0x08000000 NO_WINDOW
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", bootstrap_path,
            ],
            creationflags=0x00000008 | 0x00000200 | 0x08000000,
            close_fds=True,
        )

        result["success"] = True
        result["message"] = (
            f"安裝包已下載完成。應用即將自動關閉，請在 UAC 彈窗中允許安裝 v{version}，"
            "安裝完成後會自動重啟。"
        )
        return result

    def _install_from_zip(self, update_info: Dict, progress_callback) -> Dict:
        """開發態/源碼部署：下載源碼 zip 覆蓋更新（打包版不再使用此路徑）。"""
        result = {"success": False, "message": "", "error": None}

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
        self._download_file(download_url, zip_path, progress_callback, "Downloading")

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

            # Directories to skip during update (preserve user data and AI self-developed content)
            skip_dirs = [
                ".git",
                "models",
                "llama",
                "temp_update",
                "data",
                "ai_selfdevelop"  # AI self-developed skills and customizations - NOT overwritten
            ]

            for item in os.listdir(source_dir):
                if item in skip_dirs:
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
        return result
    
    def pull_latest_from_git(self, progress_callback=None, force=False) -> Dict:
        result = {
            "success": False,
            "message": "",
            "error": None
        }
        
        try:
            if progress_callback:
                progress_callback("Checking for updates...")
            
            update_info = self.check_for_updates()
            
            if not update_info.get("has_update") and not force:
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
        current_internal = self.get_local_version()
        current_tag = self._format_release_tag(current_internal)
        if not info:
            return f"Never checked for updates (current: {current_tag})"

        latest_internal = self._normalize_version(info.get("latest_version", "0.0.0"))
        current_internal = self.get_local_version()
        latest_tag = self._format_release_tag(latest_internal)
        current_tag = self._format_release_tag(current_internal)

        cmp_result = self._version_compare(latest_internal, current_internal)
        if cmp_result > 0:
            return f"Update available: {latest_tag} (you have {current_tag})"
        elif cmp_result < 0:
            return f"You are on a newer version ({current_tag}) than the latest release ({latest_tag})"
        else:
            return f"You are up to date ({current_tag})"


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
        print(f"Release notes: {info['release_notes'][:100]}...")
    if info.get("error"):
        print(f"Error: {info['error']}")