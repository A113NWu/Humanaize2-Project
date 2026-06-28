"""
Humanaize v2.0 - UI 主程序

核心原则:
- UI线程永不卡顿
- 所有UI更新通过 root.after() 进行
- 所有耗时操作在后台线程执行
- 线程安全的回调机制

UI布局:
- 聊天区域 (中央)
- 情绪日志 (右侧上)
- AI思考日志 (右侧中)
- 系统状态 (下方)
"""

import glob
import json
import os
import threading
import tkinter as tk
from tkinter import filedialog
import queue
import time
import customtkinter as ctk

# 导入日志模块
try:
    from tools.logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from core.Agent import Agent
from core.thinking_engine import ThinkingEngine
from memory.memory import load_memory, save_memory, add
from core.personality import load_personality, save_personality
from core.autonomous import check_silence_and_decide
from ui.idle import IdleEngine
from tools.tools import SimpleLogger, check_llm_server
import config


class HumanaizeUI:
    """Humanaize 主 UI - 现代化设计"""

    def __init__(self, root):
        self.root = root
        title = getattr(config, "UI_TITLE", "Humanaize v2.0")
        width = getattr(config, "UI_WIDTH", 1200)
        height = getattr(config, "UI_HEIGHT", 800)
        self.root.title(title)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(1000, 600)
        
        # Add close protocol handler to ensure proper shutdown
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.memory = load_memory()
        self.personality = load_personality()
        self.logger = SimpleLogger()
        self.focused_textbox = None

        self.settings = self._load_settings()
        self.language = self.settings.get("language", "English")
        self.theme = self.settings.get("theme", "Dark")
        self.model_name = self.settings.get("model_name", config.MODEL_NAME)
        self.custom_model_path = self.settings.get("model_path", "")
        self.skills_prompt = self.settings.get("skills_prompt", "")
        self.auto_break_silence = self.settings.get("auto_break_silence", True)
        self.gan_enabled = self.settings.get("gan_enabled", True)
        
        # 检查自定义模型路径是否存在，如果不存在则回退
        if self.custom_model_path and not os.path.exists(self.custom_model_path):
            print(f"[WARN] Custom model path not found: {self.custom_model_path}")
            print("[INFO] Falling back to default model path")
            self.custom_model_path = ""
        
        self._language_code_map = {
            "English": "en",
            "中文": "zh",
            "中文(繁體)": "zh-TW",
            "en": "en",
            "zh": "zh",
            "zh-TW": "zh-TW"
        }

        self.thinking_engine = ThinkingEngine(on_response_callback=self.on_engine_response)
        self.thinking_engine.set_language(self.get_language_code())

        # 从外部文件加载翻译
        self.translations = self._load_translations()

        self.autonomous_engine = self._AutonomousAdapter(
            self.memory,
            on_auto_speak=self.on_autonomous_speak,
            on_decision_callback=self.on_engine_response,
            thinking_engine=self.thinking_engine,
            auto_break_silence=self.auto_break_silence,
        )
        self.autonomous_engine.start()

        self.idle_engine = IdleEngine(self.memory, self.on_engine_response, gan_enabled=self.gan_enabled)

        self.emotion_callback = None
        self._emotion_result = None

        self._create_ui()
        self._auto_save()
        self._update_status()

        self._event_queue = queue.Queue()
        self._ui_update_queue = queue.Queue()  # 用于UI更新的队列
        self._event_processor_running = True
        
        # 创建专门的事件处理线程
        self._event_processor_thread = threading.Thread(
            target=self._event_processor_loop, 
            daemon=True,
            name="EventProcessor"
        )
        self._event_processor_thread.start()
        
        # UI更新循环（在主线程中）
        self.root.after(50, self._ui_update_loop)
        
        # 添加性能优化：定期清理UI缓存
        self._performance_cleanup_interval = 30000  # 30秒清理一次
        self.root.after(self._performance_cleanup_interval, self._performance_cleanup)
        
        self.logger.info("Humanaize v2.0 started successfully")
    
    def _load_translations(self):
        """从 languages 文件夹加载翻译文件"""
        translations = {}
        # 获取项目根目录 (src/core/ui/ui.py -> src/core/ui -> src/core -> src -> project_root)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        languages_dir = os.path.join(project_root, "languages")
        
        # 语言文件映射
        lang_file_map = {
            "English": "en_US.txt",
            "中文": "zh_CN.txt",
            "中文(繁體)": "zh_CN_TW.txt"
        }
        
        for lang_name, filename in lang_file_map.items():
            filepath = os.path.join(languages_dir, filename)
            translations[lang_name] = self._parse_lang_file(filepath)
        
        return translations
    
    def _parse_lang_file(self, filepath):
        """解析语言文件"""
        lang_dict = {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释和空行
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        lang_dict[key.strip()] = value.strip()
        except Exception as e:
            print(f"Error loading language file {filepath}: {e}")
        
        return lang_dict

    def _t(self, key: str) -> str:
        return self.translations.get(self.language, self.translations["English"]).get(key, key)
    
    def get_language_code(self) -> str:
        """Get standardized language code (en/zh) for language_adapter compatibility"""
        return self._language_code_map.get(self.language, "en")

    def _load_settings(self) -> dict:
        settings_path = os.path.join(os.path.dirname(__file__), "data", "ui_settings.json")
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self, settings: dict):
        settings_path = os.path.join(os.path.dirname(__file__), "data", "ui_settings.json")
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        self.settings = settings
        
        old_language = self.language
        old_theme = self.theme
        old_model_path = self.custom_model_path
        self.language = settings.get("language", self.language)
        self.theme = settings.get("theme", self.theme)
        self.model_name = settings.get("model_name", self.model_name)
        self.custom_model_path = settings.get("model_path", self.custom_model_path)
        self.skills_prompt = settings.get("skills_prompt", self.skills_prompt)
        self.auto_break_silence = settings.get("auto_break_silence", self.auto_break_silence)
        self.gan_enabled = settings.get("gan_enabled", self.gan_enabled)
        if hasattr(self, "idle_engine"):
            self.idle_engine.gan_enabled = self.gan_enabled
        if hasattr(self, "autonomous_engine"):
            self.autonomous_engine.auto_break_silence = self.auto_break_silence
        
        if old_language != self.language:
            self._update_language()
        
        if old_theme != self.theme:
            self._update_theme()
        
        # 检查模型路径变化
        new_model_path = self.custom_model_path
        if old_model_path != new_model_path and new_model_path:
            self._restart_llm_server()
    
    def _restart_llm_server(self):
        """重启LLM服务器以加载新模型"""
        from tools.tools import restart_llm_server
        
        def do_restart():
            model_path = self.custom_model_path
            if not model_path:
                print("[ERROR] Model path is empty")
                return
            if not os.path.exists(model_path):
                print(f"[ERROR] Model file does not exist: {model_path}")
                return
            print(f"[INFO] Restarting LLM server with model: {model_path}")
            result = restart_llm_server(model_path)
            if result:
                print("[INFO] LLM server restarted successfully!")
            else:
                print("[ERROR] Failed to restart LLM server")
        
        # 在后台线程中执行，避免阻塞UI
        threading.Thread(target=do_restart, daemon=True).start()

    def _update_theme(self):
        mode = "Dark" if self.theme.lower() == "dark" else "Light"
        ctk.set_appearance_mode(mode)
        
        # Update root background with gradient-like effect
        bg_color = "#0f0f1a" if mode == "Dark" else "#f8f9fc"
        self.root.configure(bg=bg_color)
        
        # Update main frame if exists
        if hasattr(self, 'main_frame'):
            frame_bg = "#1a1a2e" if mode == "Dark" else "#ffffff"
            self.main_frame.configure(fg_color=frame_bg)
        
        # Update colors
        textbox_bg = "#0a0a15" if mode == "Dark" else "#f0f0f5"
        textbox_text_color = "#ffffff" if mode == "Dark" else "#1a1a2e"
        accent_color = "#6366f1"  # Indigo accent color
        
        if hasattr(self, 'chat_box'):
            self.chat_box.configure(fg_color=textbox_bg, text_color=textbox_text_color)
        if hasattr(self, 'thought_text'):
            self.thought_text.configure(fg_color=textbox_bg, text_color=textbox_text_color)
        if hasattr(self, 'status_text'):
            self.status_text.configure(fg_color=textbox_bg, text_color=textbox_text_color)
        if hasattr(self, 'command_text'):
            self.command_text.configure(fg_color=textbox_bg, text_color=textbox_text_color)
        
        self.root.update()
    
    def _update_language(self):
        """Update UI text when language changes"""
        if hasattr(self, 'entry'):
            self.entry.configure(placeholder_text=self._t("input_placeholder"))
        
        if hasattr(self, 'send_btn'):
            self.send_btn.configure(text=self._t("send"))
        
        if hasattr(self, 'clear_btn'):
            self.clear_btn.configure(text=self._t("clear"))
        
        if hasattr(self, 'chat_label'):
            self.chat_label.configure(text=f"💬 {self._t('chat')}")
        
        if hasattr(self, 'thought_label'):
            self.thought_label.configure(text=f"🤔 {self._t('thoughts')}")
        
        if hasattr(self, 'cmd_label'):
            self.cmd_label.configure(text=f"🔧 {self._t('command_output')}")
        
        if hasattr(self, 'status_label'):
            self.status_label.configure(text=f"⚙️ {self._t('system')}")
        
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.title(self._t("settings"))
        
        if hasattr(self, 'thinking_engine'):
            self.thinking_engine.set_language(self.get_language_code())
            
        self.root.update()
    
    def _theme_changed_prompt(self):
        if hasattr(self, '_theme_changed_label'):
            self._theme_changed_label.destroy()
        self._theme_changed_label = ctk.CTkLabel(self.root, text="Theme changed! Restarting...", text_color="#fbbf24", font=("Segoe UI", 12, "bold"))
        # Use grid instead of pack to avoid conflicts
        self._theme_changed_label.grid(row=2, column=0, columnspan=2, pady=10)
        self.root.after(1500, self._restart_app)
    
    def _restart_app(self):
        import sys
        import os
        self.root.destroy()
        os.execv(sys.executable, [sys.executable, os.path.join(os.path.dirname(__file__), "main.py"), "boot", "-m", "gui"])

    def _browse_model_path(self, path_var, name_var=None):
        # 使用 initialdir 设置默认目录，避免每次都从根目录开始
        initial_dir = os.path.dirname(path_var.get()) if path_var.get() else os.path.expanduser("~")
        if not os.path.exists(initial_dir):
            initial_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "model")
        
        # 使用 askopenfilenames 的 callback 版本，避免阻塞主线程
        def on_file_selected():
            file_path = self._pending_file_path
            if file_path:
                path_var.set(file_path)
                # 自动刷新模型名称为新模型文件名称
                if name_var is not None:
                    model_name = os.path.splitext(os.path.basename(file_path))[0]
                    name_var.set(model_name)
                self._pending_file_path = None
        
        # 存储待处理的路径
        self._pending_file_path = None
        
        # 使用线程打开文件对话框
        import threading
        def open_dialog():
            self._pending_file_path = filedialog.askopenfilename(
                title=self._t("custom_model"),
                initialdir=initial_dir,
                filetypes=[("GGUF Model", "*.gguf"), ("All Files", "*.*")]
            )
            # 回到主线程更新UI
            self.root.after(0, on_file_selected)
        
        threading.Thread(target=open_dialog, daemon=True).start()

    def _open_settings_window(self):
        if getattr(self, "settings_window", None) and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        # Create settings window with proper theme support
        self.settings_window = ctk.CTkToplevel(self.root)
        self.settings_window.title(self._t("settings"))
        self.settings_window.geometry("800x720")
        self.settings_window.minsize(640, 560)
        self.settings_window.resizable(True, True)
        self.settings_window.transient(self.root)
        self.settings_window.grid_columnconfigure(0, weight=1)
        
        # Apply theme settings to the toplevel window
        if self.theme == "Dark":
            self.settings_window._apply_appearance_mode("dark")
        else:
            self.settings_window._apply_appearance_mode("light")
        
        # Update and make window visible before grab_set
        self.settings_window.update_idletasks()
        self.settings_window.grab_set()

        # Create scrollable frame
        scroll_frame = ctk.CTkScrollableFrame(
            self.settings_window, 
            width=760,
            corner_radius=16,
            fg_color="#1a1a2e" if self.theme == "Dark" else "#f8f9fc"
        )
        scroll_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        scroll_frame.grid_columnconfigure(0, weight=1)
        self.settings_window.grid_rowconfigure(0, weight=1)

        language_var = tk.StringVar(value=self.language)
        theme_var = tk.StringVar(value=self.theme)
        model_name_var = tk.StringVar(value=self.model_name)
        model_path_var = tk.StringVar(value=self.custom_model_path)
        auto_break_var = tk.BooleanVar(value=self.auto_break_silence)
        gan_enabled_var = tk.BooleanVar(value=self.gan_enabled)

        row = 0
        title_label = ctk.CTkLabel(scroll_frame, text=self._t("settings"), font=("Segoe UI", 20, "bold"), text_color="#6366f1")
        title_label.grid(row=row, column=0, sticky="w", padx=0, pady=(0, 20))
        row += 1

        # Language Section
        lang_frame = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color="#252540" if self.theme == "Dark" else "#e8e8f0")
        lang_frame.grid(row=row, column=0, sticky="ew", padx=0, pady=(0, 15))
        lang_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(lang_frame, text=self._t("language"), anchor="w", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))
        ctk.CTkOptionMenu(lang_frame, values=["English", "中文", "中文(繁體)"], variable=language_var, corner_radius=8).grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 12))
        row += 1

        # Theme Section
        theme_frame = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color="#252540" if self.theme == "Dark" else "#e8e8f0")
        theme_frame.grid(row=row, column=0, sticky="ew", padx=0, pady=(0, 15))
        theme_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(theme_frame, text=self._t("theme"), anchor="w", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))
        ctk.CTkOptionMenu(theme_frame, values=["Dark", "Light"], variable=theme_var, corner_radius=8).grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 12))
        row += 1

        # Model Section
        model_frame = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color="#252540" if self.theme == "Dark" else "#e8e8f0")
        model_frame.grid(row=row, column=0, sticky="ew", padx=0, pady=(0, 15))
        model_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(model_frame, text=self._t("model"), anchor="w", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))
        ctk.CTkEntry(model_frame, textvariable=model_name_var, placeholder_text=config.MODEL_NAME, corner_radius=8).grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 8))
        
        ctk.CTkLabel(model_frame, text=self._t("custom_model"), anchor="w").grid(row=2, column=0, sticky="w", padx=15, pady=(8, 4))
        model_path_frame = ctk.CTkFrame(model_frame, fg_color="transparent")
        model_path_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 12))
        model_path_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(model_path_frame, textvariable=model_path_var, placeholder_text="model/tinyllama.gguf", corner_radius=8).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(model_path_frame, text="Browse", width=96, corner_radius=8, fg_color="#6366f1", hover_color="#4f46e5", command=lambda: self._browse_model_path(model_path_var, model_name_var)).grid(row=0, column=1)
        row += 1
        
        from core.llm.model_downloader import ModelDownloader
        downloader = ModelDownloader()
        is_installed = downloader.is_model_installed()
        
        download_frame = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color="#252540" if self.theme == "Dark" else "#e8e8f0")
        download_frame.grid(row=row, column=0, sticky="ew", padx=0, pady=(0, 15))
        download_frame.grid_columnconfigure(0, weight=1)
        
        download_status_label = ctk.CTkLabel(download_frame, text="", anchor="w")
        
        def download_tinyllama():
            if downloader.downloading:
                return
            
            download_status_label.configure(text="Initializing...")
            scroll_frame.update()
            
            def progress_callback(message):
                download_status_label.configure(text=message)
                scroll_frame.update()
                return False
            
            result = downloader.download_model(callback=progress_callback)
            
            if result.get("success"):
                download_status_label.configure(text=result["message"], text_color="#10b981")
                model_path_var.set("model/tinyllama.gguf")
            else:
                download_status_label.configure(text=f"Error: {result.get('error', 'Unknown error')}", text_color="#ef4444")
        
        download_btn = ctk.CTkButton(
            download_frame, 
            text="Download TinyLlama Model (173MB)" if not is_installed else "Model Already Installed", 
            command=download_tinyllama,
            state="normal" if not is_installed else "disabled",
            corner_radius=8,
            fg_color="#6366f1" if not is_installed else "#374151",
            hover_color="#4f46e5" if not is_installed else "#4b5563"
        )
        download_btn.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        download_status_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 10))
        
        row += 1

        # Skills Section
        skills_frame_main = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color="#252540" if self.theme == "Dark" else "#e8e8f0")
        skills_frame_main.grid(row=row, column=0, sticky="nsew", padx=0, pady=(0, 15))
        skills_frame_main.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(skills_frame_main, text=self._t("skills"), anchor="w", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))
        
        skills_frame = ctk.CTkFrame(skills_frame_main, fg_color="transparent")
        skills_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 8))
        skills_frame.grid_columnconfigure(0, weight=1)
        
        from core.tools.skills_manager import SkillsManager
        skills_manager = SkillsManager()
        installed_skills = skills_manager.get_all_skills()
        skill_vars = {}
        
        if not installed_skills:
            ctk.CTkLabel(skills_frame, text="No skills installed", anchor="w").grid(row=0, column=0, sticky="w", padx=0, pady=5)
        else:
            for idx, skill in enumerate(installed_skills):
                skill_vars[skill.name] = tk.BooleanVar(value=skill.enabled)
                cb = ctk.CTkCheckBox(skills_frame, text=f"{skill.name}", variable=skill_vars[skill.name], corner_radius=6)
                cb.grid(row=idx, column=0, sticky="w", padx=0, pady=3)
        
        skills_prompt_label = ctk.CTkLabel(skills_frame_main, text="Skills Prompt", anchor="w").grid(row=2, column=0, sticky="w", padx=15, pady=(8, 4))
        skills_box = ctk.CTkTextbox(skills_frame_main, width=500, height=100, wrap=tk.WORD, corner_radius=8)
        skills_box.grid(row=3, column=0, sticky="nsew", padx=15, pady=(0, 12))
        skills_box.insert(tk.END, self.skills_prompt)
        row += 1

        # Options Section
        options_frame = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color="#252540" if self.theme == "Dark" else "#e8e8f0")
        options_frame.grid(row=row, column=0, sticky="ew", padx=0, pady=(0, 15))
        options_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkCheckBox(options_frame, text=self._t("auto_break_silence"), variable=auto_break_var, corner_radius=6).grid(row=0, column=0, sticky="w", padx=15, pady=10)
        ctk.CTkCheckBox(options_frame, text=self._t("enable_gan"), variable=gan_enabled_var, corner_radius=6).grid(row=1, column=0, sticky="w", padx=15, pady=(0, 10))
        row += 1
        
        # Update Section
        update_frame = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color="#252540" if self.theme == "Dark" else "#e8e8f0")
        update_frame.grid(row=row, column=0, sticky="ew", padx=0, pady=(0, 15))
        update_frame.grid_columnconfigure(0, weight=1)
        
        update_title = ctk.CTkLabel(update_frame, text="Software Updates", font=("Segoe UI", 12, "bold"), anchor="w")
        update_title.grid(row=0, column=0, sticky="w", padx=15, pady=(12, 5))
        
        from core.utils.auto_updater import AutoUpdater
        updater = AutoUpdater("https://github.com/A113NWu/Humanaize2-Project.git")
        version_label = ctk.CTkLabel(update_frame, text=f"Current version: {updater.get_local_version()}", anchor="w")
        version_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 5))
        
        status_label = ctk.CTkLabel(update_frame, text="", anchor="w")
        status_label.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 5))
        
        update_progress_label = ctk.CTkLabel(update_frame, text="", anchor="w")
        update_progress_label.grid(row=3, column=0, sticky="w", padx=15, pady=(0, 5))
        
        def check_for_updates():
            status_label.configure(text="Checking for updates...")
            self.settings_window.update()
            
            result = updater.check_for_updates()
            
            if result.get("error"):
                status_label.configure(text=f"Error: {result['error']}", text_color="#ef4444")
            elif result.get("has_update"):
                status_label.configure(text=f"Update available: v{result['latest_version']} (you have v{result['current_version']})", text_color="#10b981")
            else:
                status_label.configure(text=f"You are up to date (v{result['current_version']})", text_color="#9ca3af")
        
        def download_update():
            def progress_callback(message):
                update_progress_label.configure(text=message)
                self.settings_window.update()
            
            update_progress_label.configure(text="Starting update...", text_color="#f59e0b")
            self.settings_window.update()
            
            result = updater.download_and_install_update(progress_callback)
            
            if result.get("success"):
                update_progress_label.configure(text="", text_color="#10b981")
                status_label.configure(text=result["message"], text_color="#10b981")
            else:
                update_progress_label.configure(text="", text_color="#ef4444")
                status_label.configure(text=result.get("message", "Update failed"), text_color="#ef4444")
        
        button_frame_update = ctk.CTkFrame(update_frame, fg_color="transparent")
        button_frame_update.grid(row=4, column=0, sticky="ew", padx=15, pady=(5, 12))
        button_frame_update.grid_columnconfigure(0, weight=1)
        button_frame_update.grid_columnconfigure(1, weight=1)
        
        check_btn = ctk.CTkButton(button_frame_update, text="Check for Updates", command=check_for_updates, corner_radius=8, fg_color="#6366f1", hover_color="#4f46e5")
        check_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        update_btn = ctk.CTkButton(button_frame_update, text="Download & Install Update", command=download_update, corner_radius=8, fg_color="#6366f1", hover_color="#4f46e5")
        update_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        
        check_for_updates()
        
        # Add some bottom padding
        padding_label = ctk.CTkLabel(scroll_frame, text="", height=20)
        padding_label.grid(row=row, column=0)
        
        # Button frame outside scrollable area
        button_frame = ctk.CTkFrame(self.settings_window, fg_color="transparent")
        button_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        def save_settings():
            old_theme = self.theme
            
            for skill_name, var in skill_vars.items():
                if var.get():
                    skills_manager.enable_skill(skill_name)
                else:
                    skills_manager.disable_skill(skill_name)
            
            settings = {
                "language": language_var.get(),
                "theme": theme_var.get(),
                "model_name": model_name_var.get().strip() or config.MODEL_NAME,
                "model_path": model_path_var.get().strip(),
                "skills_prompt": skills_box.get("1.0", tk.END).strip(),
                "auto_break_silence": auto_break_var.get(),
                "gan_enabled": gan_enabled_var.get(),
            }
            self._save_settings(settings)
            
            if old_theme.lower() != theme_var.get().lower():
                self._theme_changed_prompt()
            
            self.settings_window.destroy()

        ctk.CTkButton(button_frame, text=self._t("save"), command=save_settings, corner_radius=8, fg_color="#6366f1", hover_color="#4f46e5").grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(button_frame, text=self._t("cancel"), command=self.settings_window.destroy, corner_radius=8, fg_color="#374151", hover_color="#4b5563").grid(row=0, column=1, sticky="ew")

    def _create_ui(self):
        # Configure appearance
        ctk.set_appearance_mode("Dark" if self.theme.lower() == "dark" else "Light")
        ctk.set_default_color_theme("blue")
        
        # Main window background with modern color
        main_bg = "#0f0f1a" if self.theme.lower() == "dark" else "#f8f9fc"
        self.root.configure(bg=main_bg)
        
        # 配置主窗口的行和列权重，使子组件能够自适应缩放
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)  # 底部输入区域固定高度
        self.root.grid_rowconfigure(2, weight=0)  # 主题提示区域
        self.root.grid_columnconfigure(0, weight=0)  # 侧边栏固定宽度
        self.root.grid_columnconfigure(1, weight=1)  # 主内容区域自适应

        # 当前活动面板
        self.active_panel = "chat"

        # 左侧导航栏（侧拉栏入口）
        self._create_sidebar()

        # 主内容区域容器
        self.content_container = ctk.CTkFrame(
            self.root, 
            corner_radius=24, 
            fg_color="#1a1a2e",
            border_width=0
        )
        self.content_container.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        # 聊天面板
        self._create_chat_panel()
        
        # 思考面板
        self._create_thoughts_panel()
        
        # 命令输出面板
        self._create_command_panel()
        
        # 系统状态面板
        self._create_status_panel()
        
        # 默认显示聊天面板
        self._switch_panel("chat")

    def _create_sidebar(self):
        """创建侧边导航栏"""
        sidebar = ctk.CTkFrame(
            self.root,
            corner_radius=20,
            fg_color="#252540",
            border_width=0,
            width=80
        )
        sidebar.grid(row=0, column=0, sticky="ns", padx=16, pady=16)
        sidebar.grid_rowconfigure(0, weight=0)
        sidebar.grid_rowconfigure(1, weight=0)
        sidebar.grid_rowconfigure(2, weight=0)
        sidebar.grid_rowconfigure(3, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)
        
        # 导航按钮样式
        btn_style = {
            "width": 60,
            "height": 60,
            "corner_radius": 16,
            "font": ("Segoe UI", 20),
            "fg_color": "#353560",
            "hover_color": "#454580",
            "text_color": "#e0e0e0"
        }
        
        # 聊天按钮
        self.chat_btn = ctk.CTkButton(
            sidebar,
            text="💬",
            command=lambda: self._switch_panel("chat"),
            **btn_style
        )
        self.chat_btn.grid(row=0, column=0, padx=10, pady=16)
        
        # 思考按钮
        self.thought_btn = ctk.CTkButton(
            sidebar,
            text="💭",
            command=lambda: self._switch_panel("thoughts"),
            **btn_style
        )
        self.thought_btn.grid(row=1, column=0, padx=10, pady=8)
        
        # 命令按钮
        self.command_btn = ctk.CTkButton(
            sidebar,
            text="⚙",
            command=lambda: self._switch_panel("command"),
            **btn_style
        )
        self.command_btn.grid(row=2, column=0, padx=10, pady=8)
        
        # 状态按钮
        self.status_btn = ctk.CTkButton(
            sidebar,
            text="📊",
            command=lambda: self._switch_panel("status"),
            **btn_style
        )
        self.status_btn.grid(row=3, column=0, padx=10, pady=(0, 16), sticky="s")
        
        # 更新按钮状态
        self._update_sidebar_buttons()

    def _update_sidebar_buttons(self):
        """更新侧边栏按钮状态"""
        buttons = {
            "chat": self.chat_btn,
            "thoughts": self.thought_btn,
            "command": self.command_btn,
            "status": self.status_btn
        }
        
        for panel, btn in buttons.items():
            if panel == self.active_panel:
                btn.configure(
                    fg_color="#6366f1",
                    text_color="white",
                    hover_color="#4f46e5"
                )
            else:
                btn.configure(
                    fg_color="#353560",
                    text_color="#e0e0e0",
                    hover_color="#454580"
                )

    def _switch_panel(self, panel_name):
        """切换显示的面板"""
        self.active_panel = panel_name
        
        # 隐藏所有面板
        self.chat_frame.grid_remove()
        self.thoughts_frame.grid_remove()
        self.command_frame.grid_remove()
        self.status_frame.grid_remove()
        
        # 显示选中的面板
        if panel_name == "chat":
            self.chat_frame.grid(row=0, column=0, sticky="nsew")
        elif panel_name == "thoughts":
            self.thoughts_frame.grid(row=0, column=0, sticky="nsew")
        elif panel_name == "command":
            self.command_frame.grid(row=0, column=0, sticky="nsew")
        elif panel_name == "status":
            self.status_frame.grid(row=0, column=0, sticky="nsew")
        
        # 更新按钮状态
        self._update_sidebar_buttons()

    def _create_chat_panel(self):
        """创建聊天面板"""
        self.chat_frame = ctk.CTkFrame(
            self.content_container,
            corner_radius=20,
            fg_color="#252540",
            border_width=0
        )
        self.chat_frame.grid_rowconfigure(1, weight=1)  # 内容区域占满剩余空间
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # Chat Header
        header_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header_frame.grid_columnconfigure(0, weight=1)
        
        self.chat_label = ctk.CTkLabel(
            header_frame, 
            text="💬 Chat", 
            anchor="w", 
            font=("Segoe UI", 18, "bold"),
            text_color="#e0e0e0"
        )
        self.chat_label.grid(row=0, column=0, sticky="w")
        
        # Settings Button
        self.settings_btn = ctk.CTkButton(
            header_frame, 
            text="⚙", 
            width=44, 
            height=40, 
            fg_color="#353560", 
            hover_color="#454580",
            corner_radius=12,
            font=("Segoe UI", 16),
            command=self._open_settings_window
        )
        self.settings_btn.grid(row=0, column=1)

        # Chat Textbox - Adaptive styling (no fixed width/height)
        self.chat_box = ctk.CTkTextbox(
            self.chat_frame, 
            wrap=tk.WORD, 
            fg_color="#0a0a15",
            text_color="#e0e0e0",
            border_width=0,
            corner_radius=16,
            font=("Segoe UI", 14)
        )
        self.chat_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.chat_box.configure(state="disabled")
        self.chat_box.tag_config("thinking", foreground="#6b7280")
        self.chat_box.tag_config("autonomous", foreground="#a78bfa")
        self.chat_box.tag_config("command", foreground="#60a5fa")
        self.chat_box.tag_config("error", foreground="#f87171")
        self.chat_box.bind("<MouseWheel>", self._on_chat_scroll)
        self.chat_box.bind("<Enter>", lambda e: self._set_focused_textbox(self.chat_box))
        self.chat_box.bind("<Leave>", lambda e: self._set_focused_textbox(None))

    def _create_thoughts_panel(self):
        """创建思考面板"""
        self.thoughts_frame = ctk.CTkFrame(
            self.content_container,
            corner_radius=20,
            fg_color="#252540",
            border_width=0
        )
        self.thoughts_frame.grid_rowconfigure(1, weight=1)  # 内容区域占满剩余空间
        self.thoughts_frame.grid_columnconfigure(0, weight=1)

        # 头部
        header_frame = ctk.CTkFrame(self.thoughts_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        self.thought_label = ctk.CTkLabel(
            header_frame, 
            text="🤔 Thoughts", 
            anchor="w", 
            font=("Segoe UI", 18, "bold"),
            text_color="#e0e0e0"
        )
        self.thought_label.grid(row=0, column=0, sticky="w")

        # 思考内容区域
        self.thought_text = ctk.CTkTextbox(
            self.thoughts_frame,
            wrap=tk.WORD,
            fg_color="#0a0a15",
            text_color="#e0e0e0",
            border_width=0,
            corner_radius=16,
            font=("Segoe UI", 14)
        )
        self.thought_text.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.thought_text.configure(state="disabled")
        
        # 为不同类型的思考配置不同的颜色标签
        self.thought_text.tag_config("gan_decision", foreground="#a78bfa")  # 紫色 - GAN决策
        self.thought_text.tag_config("gan_topic", foreground="#fbbf24")  # 金色 - GAN主题
        self.thought_text.tag_config("gan_argument", foreground="#60a5fa")  # 蓝色 - GAN论点A
        self.thought_text.tag_config("gan_counter_argument", foreground="#f472b6")  # 粉色 - GAN论点B
        self.thought_text.tag_config("gan_synthesis", foreground="#34d399")  # 绿色 - GAN综合
        self.thought_text.tag_config("web_search", foreground="#38bdf8")  # 天蓝色 - 网络搜索
        self.thought_text.tag_config("break_silence", foreground="#fb923c")  # 橙色 - 打破沉默
        self.thought_text.tag_config("reflection", foreground="#c084fc")  # 浅紫色 - 反思
        self.thought_text.tag_config("internal", foreground="#9ca3af")  # 灰色 - 内部思考
        self.thought_text.tag_config("thinking", foreground="#6b7280")  # 默认灰色

    def _create_command_panel(self):
        """创建命令输出面板"""
        self.command_frame = ctk.CTkFrame(
            self.content_container,
            corner_radius=20,
            fg_color="#252540",
            border_width=0
        )
        self.command_frame.grid_rowconfigure(1, weight=1)  # 内容区域占满剩余空间
        self.command_frame.grid_columnconfigure(0, weight=1)

        # 头部
        header_frame = ctk.CTkFrame(self.command_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        self.cmd_label = ctk.CTkLabel(
            header_frame, 
            text="⚙️ Command Output", 
            anchor="w", 
            font=("Segoe UI", 18, "bold"),
            text_color="#e0e0e0"
        )
        self.cmd_label.grid(row=0, column=0, sticky="w")

        # 创建滚动条
        self.command_scrollbar = ctk.CTkScrollbar(self.command_frame, orientation="vertical")
        self.command_scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 16), pady=(0, 16))
        
        # 命令输出内容区域
        self.command_text = ctk.CTkTextbox(
            self.command_frame,
            wrap=tk.NONE,
            fg_color="#0a0a15",
            text_color="#e0e0e0",
            border_width=0,
            corner_radius=16,
            font=("Consolas", 12),
            yscrollcommand=self.command_scrollbar.set
        )
        self.command_text.grid(row=1, column=0, sticky="nsew", padx=(16, 0), pady=(0, 16))
        self.command_scrollbar.configure(command=self.command_text.yview)
        self.command_text.configure(state="disabled")

    def _create_status_panel(self):
        """创建系统状态面板"""
        self.status_frame = ctk.CTkFrame(
            self.content_container,
            corner_radius=20,
            fg_color="#252540",
            border_width=0
        )
        self.status_frame.grid_rowconfigure(1, weight=1)  # 内容区域占满剩余空间
        self.status_frame.grid_columnconfigure(0, weight=1)

        # 头部
        header_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            header_frame, 
            text="📊 System Status", 
            anchor="w", 
            font=("Segoe UI", 18, "bold"),
            text_color="#e0e0e0"
        )
        self.status_label.grid(row=0, column=0, sticky="w")

        # 状态内容区域
        self.status_text = ctk.CTkTextbox(
            self.status_frame,
            wrap=tk.WORD,
            fg_color="#0a0a15",
            text_color="#e0e0e0",
            border_width=0,
            corner_radius=16,
            font=("Segoe UI", 14)
        )
        self.status_text.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.status_text.configure(state="disabled")

        # Bottom Input Area - 使用 grid 布局而不是 pack
        bottom_frame = ctk.CTkFrame(
            self.root, 
            corner_radius=0, 
            fg_color="#1a1a2e",
            border_width=0
        )
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        bottom_frame.grid_columnconfigure(1, weight=1)  # 输入框占主要空间
        bottom_frame.grid_rowconfigure(0, weight=1)     # 允许垂直方向自适应

        # Input label
        input_label = ctk.CTkLabel(
            bottom_frame, 
            text="📝", 
            font=("Segoe UI", 14)
        )
        input_label.grid(row=0, column=0, sticky="w", padx=(16, 8), pady=14)

        # Input Entry - Adaptive styling (no fixed width)
        self.entry = ctk.CTkEntry(
            bottom_frame, 
            placeholder_text=self._t("input_placeholder"), 
            fg_color="#0a0a15",
            text_color="#e0e0e0",
            placeholder_text_color="#6b7280",
            border_width=0,
            corner_radius=14,
            font=("Segoe UI", 14),
            height=48
        )
        self.entry.grid(row=0, column=1, sticky="ew", padx=8, pady=14)
        self.entry.bind("<Return>", lambda e: self.send())

        # Send Button - Modern styling
        self.send_btn = ctk.CTkButton(
            bottom_frame, 
            text="Send", 
            command=self.send, 
            width=100,
            height=48,
            corner_radius=14,
            fg_color="#6366f1",
            hover_color="#4f46e5",
            font=("Segoe UI", 14, "bold"),
            text_color="#ffffff"
        )
        self.send_btn.grid(row=0, column=2, padx=8, pady=14)
        
        # Clear Button - Modern styling
        self.clear_btn = ctk.CTkButton(
            bottom_frame, 
            text="Clear", 
            command=self.clear_chat, 
            width=100,
            height=48,
            corner_radius=14,
            fg_color="#374151",
            hover_color="#4b5563",
            font=("Segoe UI", 14),
            text_color="#e0e0e0"
        )
        self.clear_btn.grid(row=0, column=3, padx=(8, 16), pady=14)

    def send(self):
        text = self.entry.get().strip()
        if not text:
            return
        
        logger.info(f"User input: {text}")

        # 确保在主线程执行UI更新
        def disable_ui():
            self.entry.delete(0, tk.END)
            self.send_btn.configure(state="disabled")
            self.entry.configure(state="disabled")
            self._add_chat_message("AI: Thinking...", "thinking_placeholder")
        
        self.root.after(0, disable_ui)

        self._add_chat_message(f"You: {text}")

        add(self.memory, "user", text)
        save_memory(self.memory)

        if hasattr(self, "idle_engine"):
            self.idle_engine.pause()
        self.autonomous_engine.on_user_message()

        # 设置超时机制，防止UI永久卡住（60秒超时）
        def timeout_handler():
            logger.warning("UI timeout triggered")
            self.root.after(0, self._restore_ui_state)
        
        self._ui_timeout_id = self.root.after(60000, timeout_handler)

        def on_answer_decision(result):
            
            # 取消超时定时器
            if hasattr(self, '_ui_timeout_id'):
                self.root.after_cancel(self._ui_timeout_id)
            
            should_answer, answer_reason = result
            
            # 使用 root.after() 确保在主线程执行UI更新
            def update_ui_answer():
                if not should_answer:
                    self._add_chat_message(f"System: AI chose not to respond to your input.", "autonomous")
                    self._add_chat_message(f"System: Reason: {answer_reason}", "autonomous")
                    self._resume_idle_engine()
                    self.send_btn.configure(state="normal")
                    self.entry.configure(state="normal")
                    self.entry.focus()
                    return
                
                context = self._build_context()
                
                def on_gan_decision(gan_result):
                    should_use_gan, gan_decision_reason = gan_result
                    
                    # 使用 root.after() 确保在主线程执行UI更新
                    def update_ui_gan():
                        if should_use_gan:
                            self._add_chat_message(self._t("gan_chosen"), "autonomous")
                            self._add_chat_message(f"System: AI decided to use GAN thinking before answering.", "autonomous")
                        else:
                            self._add_chat_message(self._t("gan_skipped"), "autonomous")
                        
                        prompt = f"""{context}\n\nUser: {text}\nAssistant:"""
                        
                        try:
                            if self.gan_enabled:
                                self.thinking_engine.queue_chat_task(prompt, memory=self.memory, use_gan_decision=True, user_text=text)
                            else:
                                self.thinking_engine.queue_chat_task(prompt, memory=self.memory)
                        except TypeError:
                            self.thinking_engine.queue_chat_task(prompt)
                    
                    # 使用 root.after() 确保在主线程执行
                    self.root.after(0, update_ui_gan)
                
                if self.gan_enabled:
                    self.thinking_engine.should_use_gan_async(text, context, on_gan_decision)
                else:
                    on_gan_decision((False, "GAN disabled"))
            
            # 使用 root.after() 确保在主线程执行
            self.root.after(0, update_ui_answer)
        
        self.thinking_engine.should_answer_user_async(text, on_answer_decision)

    def clear_chat(self):
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", tk.END)
        self.chat_box.configure(state="disabled")

    def _build_context(self) -> str:
        messages = self.memory.get("messages", [])[-8:]
        context = "Recent conversation:"
        for msg in messages:
            role = msg.get("role", "").capitalize()
            content = msg.get("content", "")[:100]
            context += f"\n{role}: {content}"
        return context

    def _add_chat_message(self, text: str, message_type: str = "normal"):
        # Chat区域只显示：1) 用户消息 2) AI回复 3) AI打破沉默的消息
        # 过滤掉系统消息、错误信息、命令执行消息等
        
        # 只允许以下类型的消息显示在Chat区域
        allowed_types = ["normal", "thinking_placeholder"]  # normal包含用户消息和AI回复
        
        # 检查消息内容是否为允许的类型
        if message_type not in allowed_types:
            # 检查是否是AI打破沉默的消息（以"📢 AI decided to speak proactively"开头）
            if not text.startswith("📢 AI decided to speak proactively"):
                # 其他系统消息、错误消息等不在Chat区域显示
                logger.info(f"Filtered message from Chat area: type={message_type}, text={text[:50]}...")
                return
        
        # Direct call for faster UI update (avoid after(0) delay)
        try:
            self._unsafe_add_chat_message(text, message_type)
        except Exception as e:
            # Fallback to after(0) if direct call fails
            self.root.after(0, lambda: self._unsafe_add_chat_message(text, message_type))

    def _add_thought_message(self, text: str, thought_type: str = "internal"):
        try:
            self._unsafe_add_thought_message(text, thought_type)
        except Exception:
            self.root.after(0, lambda: self._unsafe_add_thought_message(text, thought_type))

    def _unsafe_add_thought_message(self, text: str, thought_type: str = "internal"):
        """Add thought message with type-specific formatting"""
        self.thought_text.configure(state="normal")
        
        # 为不同类型的思考添加标识和颜色
        type_prefixes = {
            "gan_decision": "🧠 [GAN Decision]",
            "gan_topic": "🎯 [GAN Topic]",
            "gan_argument": "💬 [GAN Argument A]",
            "gan_counter_argument": "💭 [GAN Argument B]",
            "gan_synthesis": "✨ [GAN Synthesis]",
            "web_search": "🔍 [Web Search]",
            "break_silence": "📢 [Break Silence]",
            "reflection": "🤔 [Reflection]",
            "internal": "💭 [Internal Thought]"
        }
        
        # 获取对应的前缀
        prefix = type_prefixes.get(thought_type, "💭 [Thought]")
        
        # 添加带前缀的消息
        formatted_text = f"{prefix} {text}\n"
        self.thought_text.insert(tk.END, formatted_text, thought_type)
        self.thought_text.see(tk.END)
        self.thought_text.configure(state="disabled")
        # 不强制更新UI，让Tkinter自然处理

    def _unsafe_add_chat_message(self, text: str, message_type: str):
        try:
            self.chat_box.configure(state="normal")
            if message_type == "thinking":
                self.chat_box.insert(tk.END, text + "\n", "thinking")
            elif message_type == "thinking_placeholder":
                self.chat_box.insert(tk.END, text + "\n", "thinking")
            elif message_type == "autonomous":
                self.chat_box.insert(tk.END, text + "\n", "autonomous")
            elif message_type == "command":
                self.chat_box.insert(tk.END, text + "\n", "command")
            elif message_type == "error":
                self.chat_box.insert(tk.END, text + "\n", "error")
            else:
                self.chat_box.insert(tk.END, text + "\n")
            self.chat_box.see(tk.END)
            self.chat_box.configure(state="disabled")
            # 不强制更新UI，让Tkinter自然处理
        except Exception as e:
            pass

    def on_engine_response(self, response: dict):
        """接收来自引擎的响应 - 线程安全"""
        try:
            self._event_queue.put(response)
        except Exception as e:
            pass

    def _event_processor_loop(self):
        """在后台线程中处理事件 - 永不阻塞UI主线程"""
        while self._event_processor_running:
            try:
                # 使用较长的超时时间，减少CPU轮询
                event = self._event_queue.get(timeout=0.1)
                if event is None:
                    break
                
                # 处理事件并生成UI更新任务
                ui_updates = self._process_event_to_ui_updates(event)
                
                # 将UI更新任务放入UI队列
                for update in ui_updates:
                    self._ui_update_queue.put(update)
                    
            except queue.Empty:
                continue
            except Exception as e:
                pass

    def _process_event_to_ui_updates(self, event):
        """处理事件并返回UI更新任务列表"""
        updates = []
        response_type = event.get("type")
        
        if response_type == "chat_response":
            reply = event.get("reply", "")
            updates.append({
                "type": "chat_response",
                "reply": reply
            })
        
        elif response_type == "error":
            error = event.get("error", "Unknown error")
            updates.append({
                "type": "error",
                "error": error
            })
        
        elif response_type == "internal_thought":
            thought = event.get("thought", "")
            thought_type = event.get("thought_type", "internal")
            if thought:
                updates.append({
                    "type": "internal_thought",
                    "thought": thought,
                    "thought_type": thought_type
                })
        
        elif response_type == "command_start":
            msg = event.get("message", "AI is executing a command...\n")
            if not msg.endswith("\n"):
                msg += "\n"
            updates.append({
                "type": "command_start",
                "message": msg
            })
        
        elif response_type == "command_result":
            output = event.get("output", "")
            updates.append({
                "type": "command_result",
                "output": output
            })
        
        elif response_type == "pending_chat_ready":
            prompt = event.get("prompt")
            memory = event.get("memory")
            updates.append({
                "type": "pending_chat_ready",
                "prompt": prompt,
                "memory": memory
            })
        
        elif response_type == "autonomous_message":
            message = event.get("message", "The conversation is paused, AI is reviewing the context and preparing a reply.")
            updates.append({
                "type": "autonomous_message",
                "message": message
            })
        
        return updates

    def _ui_update_loop(self):
        """在主线程中执行UI更新 - 每50ms检查一次"""
        try:
            # 一次处理最多5个更新，避免阻塞
            for _ in range(5):
                try:
                    update = self._ui_update_queue.get_nowait()
                    self._apply_ui_update(update)
                except queue.Empty:
                    break
        except Exception as e:
            pass
        
        # 继续下一个循环
        self.root.after(50, self._ui_update_loop)

    def _apply_ui_update(self, update):
        """应用UI更新 - 在主线程中调用"""
        update_type = update.get("type")
        
        if update_type == "chat_response":
            self._handle_chat_response_update(update)
        elif update_type == "error":
            self._handle_error_update(update)
        elif update_type == "internal_thought":
            self._handle_internal_thought_update(update)
        elif update_type == "command_start":
            self._handle_command_start_update(update)
        elif update_type == "command_result":
            self._handle_command_result_update(update)
        elif update_type == "pending_chat_ready":
            self._handle_pending_chat_ready_update(update)
        elif update_type == "autonomous_message":
            self._handle_autonomous_message_update(update)

    def _handle_chat_response_update(self, update):
        """处理聊天响应更新"""
        # 取消超时定时器（任何响应都表示流程正常进行）
        if hasattr(self, '_ui_timeout_id'):
            try:
                self.root.after_cancel(self._ui_timeout_id)
            except Exception:
                pass
        
        reply = update.get("reply", "")
        logger.info(f"AI response to display: {reply[:200] if reply else 'Empty'}")
        
        # 优化的删除Thinking消息逻辑 - 只检查最后几行
        self.chat_box.configure(state="normal")
        content = self.chat_box.get("1.0", tk.END)
        
        # 检查最后几行是否包含Thinking消息
        if "AI: Thinking..." in content or "System: AI is thinking..." in content:
            lines = content.split('\n')
            for i in range(len(lines) - 1, max(0, len(lines) - 5), -1):
                if "Thinking..." in lines[i]:
                    line_num = i + 1
                    self.chat_box.delete(f"{line_num}.0", f"{line_num}.end")
                    break
        
        self.chat_box.configure(state="disabled")
        
        r = reply.strip()
        r = "\n".join([ln.rstrip() for ln in r.splitlines() if ln.strip() != ""]) or ""
        display = f"AI: {r}" if r else "AI:"
        logger.info(f"Final display text: {display}")
        self._add_chat_message(display)
        self.send_btn.configure(state="normal")
        self.entry.configure(state="normal")
        self.entry.focus()
        self._resume_idle_engine()

    def _handle_error_update(self, update):
        """处理错误更新"""
        error = update.get("error", "Unknown error")
        self._add_chat_message(f"[ERROR] {error}", "error")
        self.send_btn.configure(state="normal")
        self.entry.configure(state="normal")
        self._resume_idle_engine()

    def _handle_internal_thought_update(self, update):
        """处理内部思考更新"""
        thought = update.get("thought", "")
        thought_type = update.get("thought_type", "internal")
        if thought:
            self._add_thought_message(thought, thought_type)

    def _handle_command_start_update(self, update):
        """处理命令开始更新"""
        msg = update.get("message", "AI is executing a command...\n")
        self._add_chat_message(msg, "command")
        self.command_text.configure(state="normal")
        self.command_text.delete("1.0", tk.END)
        self.command_text.insert(tk.END, "Executing...\n")
        self.command_text.configure(state="disabled")

    def _handle_command_result_update(self, update):
        """处理命令结果更新"""
        output = update.get("output", "")
        if output:
            if not output.endswith("\n"):
                output += "\n"
            self.command_text.configure(state="normal")
            self.command_text.delete("1.0", tk.END)
            self.command_text.insert(tk.END, output)
            self.command_text.see(tk.END)
            self.command_text.configure(state="disabled")

    def _handle_pending_chat_ready_update(self, update):
        """处理待处理聊天就绪更新"""
        prompt = update.get("prompt")
        memory = update.get("memory")
        if prompt:
            try:
                self.thinking_engine.queue_chat_task(prompt, memory=memory)
            except TypeError:
                self.thinking_engine.queue_chat_task(prompt)
            self._add_chat_message("System: Current internal GAN finished. Answering your question now.", "autonomous")

    def _handle_autonomous_message_update(self, update):
        """处理自主消息更新"""
        message = update.get("message", "The conversation is paused, AI is reviewing the context and preparing a reply.")
        self._add_chat_message(f"📢 AI decided to speak proactively: {message}", "autonomous")

    def on_autonomous_speak(self):
        self._add_chat_message("📢 AI decided to speak proactively (thinking...)", "autonomous")

    def detect_emotion(self) -> dict:
        """Detect user emotion using camera. Call this when AI wants to know user's emotional state."""
        result = {"dominant": "neutral", "confidence": 0.0}
        
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
            
            result = {"dominant": dominant, "confidence": float(confidence)}
            
        except Exception as e:
            result = {"error": str(e), "dominant": "unknown", "confidence": 0.0}
        
        return result

    def _resume_idle_engine(self):
        if hasattr(self, "idle_engine") and getattr(self.idle_engine, "paused", False):
            self.idle_engine.resume()

    def _restore_ui_state(self):
        """恢复UI状态 - 用于超时或异常情况下的UI恢复"""
        try:
            self.send_btn.configure(state="normal")
            self.entry.configure(state="normal")
            self.entry.focus()
            self._resume_idle_engine()
            self._add_chat_message("System: UI timeout occurred, please try again.", "error")
        except Exception as e:
            pass

    def _performance_cleanup(self):
        """定期清理UI缓存，优化性能"""
        try:
            # 清理聊天框缓存（限制最大行数）
            chat_content = self.chat_box.get("1.0", tk.END)
            chat_lines = chat_content.split('\n')
            max_chat_lines = 500  # 最多保留500行
            
            if len(chat_lines) > max_chat_lines:
                # 删除多余的行
                self.chat_box.configure(state="normal")
                self.chat_box.delete("1.0", f"{len(chat_lines) - max_chat_lines + 1}.0")
                self.chat_box.configure(state="disabled")
            
            # 清理思考框缓存
            thought_content = self.thought_text.get("1.0", tk.END)
            thought_lines = thought_content.split('\n')
            max_thought_lines = 300  # 最多保留300行
            
            if len(thought_lines) > max_thought_lines:
                self.thought_text.configure(state="normal")
                self.thought_text.delete("1.0", f"{len(thought_lines) - max_thought_lines + 1}.0")
                self.thought_text.configure(state="disabled")
            
            # 清理命令输出框缓存
            command_content = self.command_text.get("1.0", tk.END)
            command_lines = command_content.split('\n')
            max_command_lines = 200
            
            if len(command_lines) > max_command_lines:
                self.command_text.configure(state="normal")
                self.command_text.delete("1.0", f"{len(command_lines) - max_command_lines + 1}.0")
                self.command_text.configure(state="disabled")
            
        except Exception as e:
            pass
        
        # 继续定期清理
        self.root.after(self._performance_cleanup_interval, self._performance_cleanup)

    def _update_status(self):
        def update():
            status = ""
            if check_llm_server():
                status += "✓ LLM: Ready\n"
            else:
                status += "✗ LLM: Offline\n"
            msgs = self.memory.get("messages", [])
            thoughts = self.memory.get("thoughts", []) if isinstance(self.memory.get("thoughts", None), list) else []
            decisions = self.memory.get("decisions", []) if isinstance(self.memory.get("decisions", None), list) else []
            status += f"💾 Messages: {len(msgs)}\n"
            status += f"💭 Thoughts: {len(thoughts)}\n"
            status += f"📊 Decisions: {len(decisions)}"
            self.status_text.configure(state="normal")
            self.status_text.delete("1.0", tk.END)
            self.status_text.insert(tk.END, status)
            self.status_text.configure(state="disabled")
            self.root.after(5000, update)
        update()

    def _set_focused_textbox(self, textbox):
        self.focused_textbox = textbox

    def _on_chat_scroll(self, event):
        textbox = self.chat_box
        scroll_pos = textbox.yview()
        current_top = scroll_pos[0]
        current_bottom = scroll_pos[1]
        
        if event.delta < 0 and current_bottom >= 1.0:
            return "break"
        if event.delta > 0 and current_top <= 0.0:
            return "break"
        
        textbox.configure(state="normal")
        textbox.yview_scroll(int(-1 * (event.delta / 120)), "units")
        textbox.configure(state="disabled")
        return "break"

    def _on_textbox_scroll(self, event):
        if not self.focused_textbox:
            return "break"
        
        textbox = self.focused_textbox
        scroll_pos = textbox.yview()
        current_top = scroll_pos[0]
        current_bottom = scroll_pos[1]
        
        if event.delta < 0 and current_bottom >= 1.0:
            return "break"
        if event.delta > 0 and current_top <= 0.0:
            return "break"
        
        textbox.configure(state="normal")
        textbox.yview_scroll(int(-1 * (event.delta / 120)), "units")
        textbox.configure(state="disabled")
        return "break"

    def _auto_save(self):
        def save():
            try:
                save_memory(self.memory)
                save_personality(self.personality)
            except Exception as e:
                self.logger.error(f"保存失败: {e}")
            interval = getattr(config, "MEMORY_AUTO_SAVE_INTERVAL", 60)
            self.root.after(int(interval * 1000), save)
        save()

    def on_closing(self):
        self.logger.info("关闭Humanaize...")
        self.thinking_engine.stop()
        try:
            self.autonomous_engine.stop()
        except:
            pass
        try:
            if hasattr(self.idle_engine, "running"):
                self.idle_engine.running = False
        except:
            pass
        save_memory(self.memory)
        save_personality(self.personality)
        self.root.destroy()

    class _AutonomousAdapter:
        """在 UI 内部实现的轻量适配器，兼容旧的 AutonomousEngine 接口"""
        def __init__(self, memory, on_auto_speak=None, on_decision_callback=None, thinking_engine=None, check_interval=30, auto_break_silence=True):
            self.memory = memory
            self.on_auto_speak = on_auto_speak
            self.on_decision_callback = on_decision_callback
            self.thinking_engine = thinking_engine
            self.check_interval = check_interval
            self.running = False
            self._thread = None
            self._last_user_time = None
            self.auto_break_silence = auto_break_silence

        def start(self):
            import threading
            self.running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

        def stop(self):
            self.running = False

        def on_user_message(self):
            from datetime import datetime
            self._last_user_time = datetime.now()

        def _run(self):
            import time
            while self.running:
                try:
                    decision = check_silence_and_decide(self.memory)
                    if decision:
                        if not getattr(self, "auto_break_silence", True):
                            time.sleep(self.check_interval)
                            continue
                        
                        if self.thinking_engine:
                            try:
                                self.thinking_engine.queue_gan_task(is_user_topic=False, memory=self.memory)
                            except:
                                pass
                        
                        if self.thinking_engine:
                            try:
                                msgs = self.memory.get("messages", [])[-4:]
                                context = "Recent conversation:\n"
                                for msg in msgs:
                                    role = msg.get("role", "").capitalize()
                                    content = msg.get("content", "")[:100]
                                    context += f"{role}: {content}\n"
                                prompt = f"{context}\nAssistant: I notice the conversation has paused. Let me share a brief thought:"
                                self.thinking_engine.queue_break_silence_task(prompt, memory=self.memory)
                            except:
                                pass
                except:
                    pass
                time.sleep(self.check_interval)
