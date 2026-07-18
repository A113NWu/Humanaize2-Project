"""
模型下載器 - 自動安裝 Tinyllama
"""

import os
import sys
import json
import threading
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# 导入统一版本管理模块
try:
    from ..utils.version import get_model_downloader_agent
except ImportError:
    # 如果从其他目录导入，提供备用方案
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
    from version import get_model_downloader_agent


class ModelDownloader:
    def __init__(self):
        self.downloading = False
        self.progress_callback = None
        self.cancel_event = threading.Event()
        
    def download_model(self, model_name="tinyllama", callback=None):
        """
        Download a model from Hugging Face
        """
        self.progress_callback = callback
        self.cancel_event.clear()
        self.downloading = True
        
        try:
            # TinyLlama-1.1B-Chat-v1.0-GGUF from Hugging Face
            model_info = {
                "tinyllama": {
                    "url": "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
                    "filename": "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
                    "size": 181299200  # Approx 173MB
                }
            }
            
            if model_name not in model_info:
                return {"success": False, "error": f"Unknown model: {model_name}"}
            
            info = model_info[model_name]
            # 下載到專案根目錄的 model 資料夾
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            model_dir = os.path.join(base_dir, "model")
            os.makedirs(model_dir, exist_ok=True)
            
            # 下載為 tinyllama.gguf（統一名稱）
            file_path = os.path.join(model_dir, "tinyllama.gguf")
            
            if self._callback(f"Downloading {model_name}..."):
                return {"success": False, "error": "Download cancelled"}
            
            try:
                # Use requests if available, otherwise urllib
                try:
                    import requests
                    session = requests.Session()
                    session.headers.update({"User-Agent": get_model_downloader_agent()})
                    
                    with session.get(info["url"], stream=True, timeout=30) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', info["size"]))
                        downloaded_size = 0
                        
                        with open(file_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if self.cancel_event.is_set():
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                    return {"success": False, "error": "Download cancelled"}
                                
                                if chunk:
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    progress = (downloaded_size / total_size) * 100
                                    
                                    if self._callback(f"Downloading... {progress:.1f}%"):
                                        if os.path.exists(file_path):
                                            os.remove(file_path)
                                        return {"success": False, "error": "Download cancelled"}
                    
                except ImportError:
                    # Fallback to urllib
                    req = Request(info["url"], headers={"User-Agent": get_model_downloader_agent()})
                    with urlopen(req, timeout=30) as response:
                        total_size = int(response.headers.get('Content-Length', info["size"]))
                        downloaded_size = 0
                        
                        with open(file_path, 'wb') as f:
                            while True:
                                if self.cancel_event.is_set():
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                    return {"success": False, "error": "Download cancelled"}
                                
                                chunk = response.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                progress = (downloaded_size / total_size) * 100
                                
                                if self._callback(f"Downloading... {progress:.1f}%"):
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                    return {"success": False, "error": "Download cancelled"}
            
            except (URLError, HTTPError) as e:
                return {"success": False, "error": f"Network error: {str(e)}"}
            except Exception as e:
                return {"success": False, "error": f"Download failed: {str(e)}"}
            
            # Verify download
            file_size = os.path.getsize(file_path)
            if file_size < info["size"] * 0.9:  # Allow 10% tolerance
                os.remove(file_path)
                return {"success": False, "error": "Download incomplete - file too small"}
            
            # Update config
            config_path = os.path.join(os.path.dirname(__file__), "config.py")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'MODEL_NAME' in content:
                        content = content.replace(
                            "MODEL_NAME = \"tinyllama\"",
                            "MODEL_NAME = \"tinyllama\""
                        )
                    if 'CUSTOM_MODEL_PATH' in content:
                        content = content.replace(
                            'CUSTOM_MODEL_PATH = ""',
                            f'CUSTOM_MODEL_PATH = "models/{info["filename"]}"'
                        )
                    with open(config_path, 'w', encoding='utf-8') as f:
                        f.write(content)
            
            # Update settings
            settings_path = os.path.join(os.path.dirname(__file__), "data", "settings.json")
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            else:
                settings = {}
            
            settings["model_path"] = f"models/{info['filename']}"
            
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            
            self._callback(f"Download completed!")
            return {"success": True, "message": f"Model downloaded successfully to {file_path}"}
            
        finally:
            self.downloading = False
    
    def cancel_download(self):
        """Cancel the ongoing download"""
        self.cancel_event.set()
    
    def _callback(self, message):
        """Helper method to call progress callback"""
        if self.progress_callback:
            try:
                return self.progress_callback(message)
            except:
                pass
        return False
    
    def is_model_installed(self, model_name="tinyllama"):
        """Check if the model is already installed"""
        model_info = {
            "tinyllama": {
                "filename": "tinyllama.gguf",
                "min_size": 170000000  # Minimum expected size in bytes
            }
        }
        
        if model_name not in model_info:
            return False
        
        info = model_info[model_name]
        # 檢查專案根目錄的 model 資料夾
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        file_path = os.path.join(base_dir, "model", info["filename"])
        
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            return file_size >= info["min_size"]
        
        return False
    
    def get_model_path(self, model_name="tinyllama"):
        """Get the path to the model file"""
        model_info = {
            "tinyllama": "tinyllama.gguf"
        }
        
        if model_name not in model_info:
            return None
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, "model", model_info[model_name])
