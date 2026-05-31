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

from Agent import Agent
from thinking_engine import ThinkingEngine
from memory import load_memory, save_memory, add
from personality import load_personality, save_personality
from autonomous import check_silence_and_decide
from idle import IdleEngine
from tools import SimpleLogger, check_llm_server
import config


class HumanaizeUI:
    """Humanaize 主 UI"""

    def __init__(self, root):
        self.root = root
        title = getattr(config, "UI_TITLE", "Humanaize v2.0")
        width = getattr(config, "UI_WIDTH", 1000)
        height = getattr(config, "UI_HEIGHT", 700)
        self.root.title(title)
        self.root.geometry(f"{width}x{height}")

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

        self._language_code_map = {
            "English": "en",
            "中文": "zh",
            "en": "en",
            "zh": "zh",
            "zh-TW": "zh"
        }

        self.thinking_engine = ThinkingEngine(on_response_callback=self.on_engine_response)
        self.thinking_engine.set_language(self.get_language_code())

        self.translations = {
            "English": {
                "chat": "Chat",
                "thoughts": "Thoughts",
                "system": "System",
                "command_output": "Command Output",
                "input": "Input:",
                "input_placeholder": "Enter your question. AI will pause background GAN while deciding.",
                "send": "Send",
                "clear": "Clear",
                "settings": "Settings",
                "language": "Language",
                "theme": "Theme",
                "model": "Local Model",
                "custom_model": "Custom Model Path",
                "skills": "Skills Configuration",
                "auto_break_silence": "Allow Auto Break Silence",
                "enable_gan": "Enable GAN",
                "save": "Save Settings",
                "cancel": "Cancel",
                "deciding_gan": "System: Pausing background GAN while AI decides whether to use it...",
                "gan_chosen": "System: AI decided to continue GAN thinking before answering.",
                "gan_skipped": "System: AI decided to answer directly without GAN thinking."
            },
            "中文": {
                "chat": "对话",
                "thoughts": "思考",
                "system": "系统",
                "command_output": "命令输出",
                "input": "输入:",
                "input_placeholder": "请输入问题，AI会在判断是否使用GAN时暂停后台思考。",
                "send": "发送",
                "clear": "清空",
                "settings": "设置",
                "language": "语言",
                "theme": "模式",
                "model": "本地模型",
                "custom_model": "自定义模型路径",
                "skills": "技能配置",
                "auto_break_silence": "允许自动打破沉默",
                "enable_gan": "启用 GAN",
                "save": "保存设置",
                "cancel": "取消",
                "deciding_gan": "系统：在AI决定是否继续使用GAN前，已暂停后台GAN。",
                "gan_chosen": "系统：AI决定在回答前继续GAN思考。",
                "gan_skipped": "系统：AI决定直接回答，不继续GAN思考。"
            }
        }
        
        try:
            import autonomous as _autonomous_mod
            _orig = getattr(_autonomous_mod, "check_silence_and_decide", None)
            def _safe_check(mem, threshold_seconds=60):
                try:
                    if _orig is None:
                        return None
                    return _orig(mem, threshold_seconds)
                except Exception:
                    msgs = mem.get("messages", [])
                    if not msgs:
                        return None
                    last = msgs[-1]
                    t = last.get("time")
                    try:
                        from datetime import datetime
                        if isinstance(t, str):
                            last_time = datetime.fromisoformat(t)
                        else:
                            return None
                        now = datetime.now()
                        from datetime import timedelta
                        if (now - last_time) > timedelta(seconds=threshold_seconds):
                            return {
                                "action": "AUTO_THINK",
                                "message": "对话已经暂停，AI正在回顾上下文并思考下一步行动。",
                                "confidence": 0.9
                            }
                        return None
                    except Exception:
                        return None
            if _orig is not None:
                _autonomous_mod.check_silence_and_decide = _safe_check
        except Exception:
            pass

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
        self.root.after(100, self._process_event_queue)

        self.logger.info("Humanaize v2.0 started successfully")

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
        
        self._update_theme()

    def _update_theme(self):
        mode = "Dark" if self.theme.lower() == "dark" else "Light"
        ctk.set_appearance_mode(mode)
        self.root.configure(bg="#101010" if mode == "Dark" else "#f0f0f0")
        self.root.update()
    
    def _update_language(self):
        """Update UI text when language changes"""
        if hasattr(self, 'input_entry'):
            self.input_entry.configure(placeholder_text=self._t("input_placeholder"))
        
        if hasattr(self, 'send_button'):
            self.send_button.configure(text=self._t("send"))
        
        if hasattr(self, 'clear_button'):
            self.clear_button.configure(text=self._t("clear"))
        
        if hasattr(self, 'settings_button'):
            self.settings_button.configure(text=self._t("settings"))
        
        if hasattr(self, 'chat_tab'):
            self.chat_tab.configure(text=self._t("chat"))
        
        if hasattr(self, 'thoughts_tab'):
            self.thoughts_tab.configure(text=self._t("thoughts"))
        
        if hasattr(self, 'system_tab'):
            self.system_tab.configure(text=self._t("system"))
        
        if hasattr(self, 'command_output_tab'):
            self.command_output_tab.configure(text=self._t("command_output"))
        
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.title(self._t("settings"))
        
        if hasattr(self, 'thinking_engine'):
            self.thinking_engine.set_language(self.get_language_code())
            
        self.root.update()
    
    def _theme_changed_prompt(self):
        if hasattr(self, '_theme_changed_label'):
            self._theme_changed_label.destroy()
        self._theme_changed_label = ctk.CTkLabel(self.root, text="Theme changed! Restarting...", text_color="#fbbf24", font=("Segoe UI", 12, "bold"))
        self._theme_changed_label.pack(side="bottom", pady=10)
        self.root.after(1500, self._restart_app)
    
    def _restart_app(self):
        import sys
        import os
        self.root.destroy()
        os.execv(sys.executable, [sys.executable, os.path.join(os.path.dirname(__file__), "main.py"), "boot", "-m", "gui"])

    def _browse_model_path(self, path_var):
        file_path = filedialog.askopenfilename(
            title=self._t("custom_model"),
            filetypes=[("GGUF Model", "*.gguf"), ("All Files", "*.*")]
        )
        if file_path:
            path_var.set(file_path)

    def _open_settings_window(self):
        if getattr(self, "settings_window", None) and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        self.settings_window = ctk.CTkToplevel(self.root)
        self.settings_window.title(self._t("settings"))
        self.settings_window.geometry("760x680")
        self.settings_window.minsize(640, 560)
        self.settings_window.resizable(True, True)
        self.settings_window.transient(self.root)
        self.settings_window.grab_set()
        self.settings_window.grid_columnconfigure(0, weight=1)

        language_var = tk.StringVar(value=self.language)
        theme_var = tk.StringVar(value=self.theme)
        model_name_var = tk.StringVar(value=self.model_name)
        model_path_var = tk.StringVar(value=self.custom_model_path)
        auto_break_var = tk.BooleanVar(value=self.auto_break_silence)
        gan_enabled_var = tk.BooleanVar(value=self.gan_enabled)

        row = 0
        title_label = ctk.CTkLabel(self.settings_window, text=self._t("settings"), font=("Segoe UI", 16, "bold"))
        title_label.grid(row=row, column=0, sticky="w", padx=20, pady=(20, 10))
        row += 1

        ctk.CTkLabel(self.settings_window, text=self._t("language"), anchor="w").grid(row=row, column=0, sticky="w", padx=20, pady=(10, 4))
        row += 1
        ctk.CTkOptionMenu(self.settings_window, values=["English", "中文"], variable=language_var).grid(row=row, column=0, sticky="ew", padx=20)
        row += 1

        ctk.CTkLabel(self.settings_window, text=self._t("theme"), anchor="w").grid(row=row, column=0, sticky="w", padx=20, pady=(10, 4))
        row += 1
        ctk.CTkOptionMenu(self.settings_window, values=["Dark", "Light"], variable=theme_var).grid(row=row, column=0, sticky="ew", padx=20)
        row += 1

        ctk.CTkLabel(self.settings_window, text=self._t("model"), anchor="w").grid(row=row, column=0, sticky="w", padx=20, pady=(10, 4))
        row += 1
        ctk.CTkEntry(self.settings_window, textvariable=model_name_var, placeholder_text=config.MODEL_NAME).grid(row=row, column=0, sticky="ew", padx=20)
        row += 1

        ctk.CTkLabel(self.settings_window, text=self._t("custom_model"), anchor="w").grid(row=row, column=0, sticky="w", padx=20, pady=(10, 4))
        row += 1
        model_path_frame = ctk.CTkFrame(self.settings_window, fg_color="transparent")
        model_path_frame.grid(row=row, column=0, sticky="ew", padx=20)
        model_path_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(model_path_frame, textvariable=model_path_var, placeholder_text="models/tinyllama.gguf").grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(model_path_frame, text="Browse", width=96, command=lambda: self._browse_model_path(model_path_var)).grid(row=0, column=1)
        row += 1

        ctk.CTkLabel(self.settings_window, text=self._t("skills"), anchor="w").grid(row=row, column=0, sticky="w", padx=20, pady=(10, 4))
        row += 1
        skills_frame = ctk.CTkFrame(self.settings_window)
        skills_frame.grid(row=row, column=0, sticky="nsew", padx=20)
        skills_frame.grid_columnconfigure(0, weight=1)
        row += 1
        
        from skills_manager import SkillsManager
        skills_manager = SkillsManager()
        installed_skills = skills_manager.get_all_skills()
        skill_vars = {}
        
        if not installed_skills:
            ctk.CTkLabel(skills_frame, text="No skills installed", anchor="w").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        else:
            for idx, skill in enumerate(installed_skills):
                skill_vars[skill.name] = tk.BooleanVar(value=skill.enabled)
                cb = ctk.CTkCheckBox(skills_frame, text=f"{skill.name}", variable=skill_vars[skill.name])
                cb.grid(row=idx, column=0, sticky="w", padx=10, pady=2)
        
        self.settings_window.grid_rowconfigure(row, weight=0)
        skills_prompt_label = ctk.CTkLabel(self.settings_window, text="Skills Prompt", anchor="w").grid(row=row, column=0, sticky="w", padx=20, pady=(10, 4))
        row += 1
        self.settings_window.grid_rowconfigure(row, weight=1)
        skills_box = ctk.CTkTextbox(self.settings_window, width=500, height=120, wrap=tk.WORD)
        skills_box.grid(row=row, column=0, sticky="nsew", padx=20)
        skills_box.insert(tk.END, self.skills_prompt)
        row += 1
        
        self.settings_window.grid_rowconfigure(row, weight=0)

        ctk.CTkCheckBox(self.settings_window, text=self._t("auto_break_silence"), variable=auto_break_var).grid(row=row, column=0, sticky="w", padx=20, pady=(10, 4))
        row += 1
        ctk.CTkCheckBox(self.settings_window, text=self._t("enable_gan"), variable=gan_enabled_var).grid(row=row, column=0, sticky="w", padx=20, pady=(4, 10))
        row += 1
        
        update_frame = ctk.CTkFrame(self.settings_window, fg_color=("#2a2a2a", "#1a1a1a"))
        update_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=(10, 10))
        update_frame.grid_columnconfigure(0, weight=1)
        row += 1
        
        update_title = ctk.CTkLabel(update_frame, text="Software Updates", font=("Segoe UI", 12, "bold"), anchor="w")
        update_title.grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))
        
        from auto_updater import AutoUpdater
        updater = AutoUpdater("https://github.com/A113NWu/Humanaize2-Project.git")
        version_label = ctk.CTkLabel(update_frame, text=f"Current version: {updater.get_local_version()}", anchor="w")
        version_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 5))
        
        status_label = ctk.CTkLabel(update_frame, text="", anchor="w", text_color="#888888")
        status_label.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 5))
        
        update_progress_label = ctk.CTkLabel(update_frame, text="", anchor="w", text_color="#888888")
        update_progress_label.grid(row=3, column=0, sticky="w", padx=15, pady=(0, 5))
        
        def check_for_updates():
            status_label.configure(text="Checking for updates...")
            self.settings_window.update()
            
            result = updater.check_for_updates()
            
            if result.get("error"):
                status_label.configure(text=f"Error: {result['error']}", text_color="#ff6666")
            elif result.get("has_update"):
                status_label.configure(text=f"Update available: v{result['latest_version']} (you have v{result['current_version']})", text_color="#66ff66")
            else:
                status_label.configure(text=f"You are up to date (v{result['current_version']})", text_color="#888888")
        
        def download_update():
            def progress_callback(message):
                update_progress_label.configure(text=message)
                self.settings_window.update()
            
            update_progress_label.configure(text="Starting update...", text_color="#fbbf24")
            self.settings_window.update()
            
            result = updater.download_and_install_update(progress_callback)
            
            if result.get("success"):
                update_progress_label.configure(text="", text_color="#66ff66")
                status_label.configure(text=result["message"], text_color="#66ff66")
            else:
                update_progress_label.configure(text="", text_color="#ff6666")
                status_label.configure(text=result.get("message", "Update failed"), text_color="#ff6666")
        
        button_frame_update = ctk.CTkFrame(update_frame, fg_color="transparent")
        button_frame_update.grid(row=4, column=0, sticky="ew", padx=10, pady=(5, 10))
        button_frame_update.grid_columnconfigure(0, weight=1)
        button_frame_update.grid_columnconfigure(1, weight=1)
        
        check_btn = ctk.CTkButton(button_frame_update, text="Check for Updates", command=check_for_updates, fg_color="#3d3d3d", text_color="#ffffff")
        check_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        update_btn = ctk.CTkButton(button_frame_update, text="Download & Install Update", command=download_update, fg_color="#2563eb", text_color="#ffffff")
        update_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        
        check_for_updates()
        
        button_frame = ctk.CTkFrame(self.settings_window, fg_color="transparent")
        button_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=20)
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

        ctk.CTkButton(button_frame, text=self._t("save"), command=save_settings).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(button_frame, text=self._t("cancel"), command=self.settings_window.destroy).grid(row=0, column=1, sticky="ew")

    def _create_ui(self):
        ctk.set_appearance_mode("Dark" if self.theme.lower() == "dark" else "Light")
        ctk.set_default_color_theme("dark-blue")
        self.root.configure(bg="#101010" if self.theme.lower() == "dark" else "#f0f0f0")

        main_frame = ctk.CTkFrame(self.root, corner_radius=20, fg_color="#141414")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)

        left_frame = ctk.CTkFrame(main_frame, corner_radius=18, fg_color="#1a1a1a")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=6)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        chat_label = ctk.CTkLabel(left_frame, text="💬 Chat", anchor="w", font=("Segoe UI", 14, "bold"))
        chat_label.grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))

        self.chat_box = ctk.CTkTextbox(left_frame, width=680, height=430, wrap=tk.WORD, fg_color="#1f1f1f", text_color="#f5f5f5")
        self.chat_box.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.chat_box.configure(state="disabled", corner_radius=16)
        self.chat_box.tag_config("thinking", foreground="#6b7280")
        self.chat_box.tag_config("autonomous", foreground="#7c3aed")
        self.chat_box.tag_config("command", foreground="#2563eb")
        self.chat_box.tag_config("error", foreground="#dc2626")
        self.chat_box.bind("<MouseWheel>", self._on_chat_scroll)
        self.chat_box.bind("<Enter>", lambda e: self._set_focused_textbox(self.chat_box))
        self.chat_box.bind("<Leave>", lambda e: self._set_focused_textbox(None))

        right_frame = ctk.CTkFrame(main_frame, corner_radius=18, fg_color="#1a1a1a")
        right_frame.grid(row=0, column=1, sticky="nsew", pady=6)
        right_frame.grid_rowconfigure(2, weight=1)
        right_frame.grid_rowconfigure(4, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_columnconfigure(1, weight=0)

        self.settings_btn = ctk.CTkButton(right_frame, text="⚙", width=40, height=36, fg_color="#262626", hover_color="#333333", command=self._open_settings_window)
        self.settings_btn.grid(row=0, column=1, sticky="ne", padx=(0, 14), pady=(14, 4))

        thought_label = ctk.CTkLabel(right_frame, text="🤔 Thoughts", anchor="w", font=("Segoe UI", 12, "bold"))
        thought_label.grid(row=1, column=0, sticky="w", padx=14, pady=(14, 4))
        self.thought_text = ctk.CTkTextbox(right_frame, width=340, height=200, wrap=tk.WORD, fg_color="#1f1f1f", text_color="#f5f5f5")
        self.thought_text.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 8))
        self.thought_text.configure(state="disabled", corner_radius=14)
        self.thought_text.tag_config("thinking", foreground="#6b7280")
        self.thought_text.tag_config("command", foreground="#2563eb")
        self.thought_text.bind("<MouseWheel>", self._on_textbox_scroll)
        self.thought_text.bind("<Enter>", lambda e: self._set_focused_textbox(self.thought_text))
        self.thought_text.bind("<Leave>", lambda e: self._set_focused_textbox(None))

        cmd_label = ctk.CTkLabel(right_frame, text="🔧 Command Output", anchor="w", font=("Segoe UI", 12, "bold"))
        cmd_label.grid(row=3, column=0, sticky="w", padx=14, pady=(4, 4))
        self.command_text = ctk.CTkTextbox(right_frame, width=340, height=180, wrap=tk.NONE, fg_color="#1f1f1f", text_color="#f5f5f5")
        self.command_text.grid(row=4, column=0, sticky="nsew", padx=14, pady=(0, 8))
        self.command_text.configure(state="disabled", corner_radius=14)
        self.command_text.bind("<MouseWheel>", self._on_textbox_scroll)
        self.command_text.bind("<Enter>", lambda e: self._set_focused_textbox(self.command_text))
        self.command_text.bind("<Leave>", lambda e: self._set_focused_textbox(None))

        status_label = ctk.CTkLabel(right_frame, text="⚙️ System", anchor="w", font=("Segoe UI", 12, "bold"))
        status_label.grid(row=5, column=0, sticky="w", padx=14, pady=(4, 4))
        self.status_text = ctk.CTkTextbox(right_frame, width=340, height=100, wrap=tk.WORD, fg_color="#1f1f1f", text_color="#f5f5f5")
        self.status_text.grid(row=7, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.status_text.configure(state="disabled", corner_radius=14)
        self.status_text.bind("<MouseWheel>", self._on_textbox_scroll)
        self.status_text.bind("<Enter>", lambda e: self._set_focused_textbox(self.status_text))
        self.status_text.bind("<Leave>", lambda e: self._set_focused_textbox(None))

        bottom_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="#141414")
        bottom_frame.pack(fill=tk.X, padx=12, pady=(0, 12))
        bottom_frame.grid_columnconfigure(1, weight=1)

        input_label = ctk.CTkLabel(bottom_frame, text="📝 Input:", font=("Segoe UI", 12))
        input_label.grid(row=0, column=0, sticky="w", padx=(14, 6), pady=12)

        self.entry = ctk.CTkEntry(bottom_frame, width=520, placeholder_text=self._t("input_placeholder"), fg_color="#252525", text_color="#f5f5f5")
        self.entry.grid(row=0, column=1, sticky="ew", padx=6, pady=12)
        self.entry.bind("<Return>", lambda e: self.send())

        self.send_btn = ctk.CTkButton(bottom_frame, text="Send", command=self.send, width=96)
        self.send_btn.grid(row=0, column=2, padx=6, pady=12)
        self.clear_btn = ctk.CTkButton(bottom_frame, text="Clear", command=self.clear_chat, width=96, fg_color="#2d2d2d", text_color="#f5f5f5")
        self.clear_btn.grid(row=0, column=3, padx=(6, 14), pady=12)

    def send(self):
        text = self.entry.get().strip()
        if not text:
            return

        self.entry.delete(0, tk.END)
        self.send_btn.configure(state="disabled")
        self.entry.configure(state="disabled")

        self._add_chat_message(f"You: {text}")

        add(self.memory, "user", text)
        save_memory(self.memory)

        if hasattr(self, "idle_engine"):
            self.idle_engine.pause()
        self.autonomous_engine.on_user_message()

        self._add_chat_message("System: AI is thinking...", "autonomous")

        def on_answer_decision(result):
            should_answer, answer_reason = result
            
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
                    
                    self.root.after(0, update_ui_gan)
                
                if self.gan_enabled:
                    self.thinking_engine.should_use_gan_async(text, context, on_gan_decision)
                else:
                    on_gan_decision((False, "GAN disabled"))
            
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
        self.root.after(0, lambda: self._unsafe_add_chat_message(text, message_type))

    def _add_thought_message(self, text: str):
        self.root.after(0, lambda: self._unsafe_add_thought_message(text))

    def _unsafe_add_thought_message(self, text: str):
        self.thought_text.configure(state="normal")
        self.thought_text.insert(tk.END, text + "\n", "thinking")
        self.thought_text.see(tk.END)
        self.thought_text.configure(state="disabled")

    def _unsafe_add_chat_message(self, text: str, message_type: str):
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

    def on_engine_response(self, response: dict):
        try:
            self._event_queue.put(response)
        except Exception:
            pass

    def _process_event_queue(self):
        try:
            while True:
                event = self._event_queue.get_nowait()
                try:
                    self._handle_engine_response(event)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self.root.after(100, self._process_event_queue)

    def _handle_engine_response(self, response: dict):
        response_type = response.get("type")
        if response_type == "chat_response":
            reply = response.get("reply", "")
            content = self.chat_box.get("1.0", tk.END)
            if content.rstrip().endswith("AI: Thinking..."):
                self.chat_box.configure(state="normal")
                self.chat_box.delete("end-2l", "end-1l")
                self.chat_box.configure(state="disabled")
            r = reply.strip()
            r = "\n".join([ln.rstrip() for ln in r.splitlines() if ln.strip() != ""]) or ""
            display = f"AI: {r}" if r else "AI:"
            self._add_chat_message(display)
            self.send_btn.configure(state="normal")
            self.entry.configure(state="normal")
            self.entry.focus()
            self._resume_idle_engine()
        elif response_type == "error":
            error = response.get("error", "Unknown error")
            self._add_chat_message(f"[ERROR] {error}", "error")
            self.send_btn.configure(state="normal")
            self.entry.configure(state="normal")
            self._resume_idle_engine()
        elif response_type == "internal_thought":
            thought = response.get("thought", "")
            if thought:
                self._add_thought_message(thought)
        elif response_type == "pending_chat_ready":
            prompt = response.get("prompt")
            memory = response.get("memory")
            if prompt:
                try:
                    self.thinking_engine.queue_chat_task(prompt, memory=memory)
                except TypeError:
                    self.thinking_engine.queue_chat_task(prompt)
                self._add_chat_message("System: Current internal GAN finished. Answering your question now.", "autonomous")
        elif response_type == "autonomous_message":
            message = response.get("message", "The conversation is paused, AI is reviewing the context and preparing a reply.")
            self._add_chat_message(f"📢 AI decided to speak proactively: {message}", "autonomous")
        elif response_type == "command_start":
            msg = response.get("message", "AI is executing a command...\n")
            if not msg.endswith("\n"):
                msg += "\n"
            self._add_chat_message(msg, "command")
            self.command_text.configure(state="normal")
            self.command_text.delete("1.0", tk.END)
            self.command_text.insert(tk.END, "Executing...\n")
            self.command_text.configure(state="disabled")
        elif response_type == "command_result":
            out = response.get("output", "")
            self._add_chat_message(f"Command output:\n{out if out else '(no output)'}", "command")
            self.command_text.configure(state="normal")
            self.command_text.delete("1.0", tk.END)
            self.command_text.insert(tk.END, out if out else "(no output)")
            self.command_text.configure(state="disabled")
        elif response_type == "gan_complete":
            gan_result = response.get("gan_result", {})
            should_speak, message = self.thinking_engine.should_proactively_speak(self.memory, gan_result)
            if should_speak and message:
                self._add_chat_message(f"AI (proactive): {message}", "autonomous")

    def on_autonomous_speak(self):
        self._add_chat_message("📢 AI decided to speak proactively (thinking...)", "autonomous")

    def detect_emotion(self) -> dict:
        """Detect user emotion using camera. Call this when AI wants to know user's emotional state."""
        result = {"dominant": "neutral", "confidence": 0.0}
        
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
            
            result = {"dominant": dominant, "confidence": float(confidence)}
            
        except Exception as e:
            result = {"error": str(e), "dominant": "unknown", "confidence": 0.0}
        
        return result

    def _resume_idle_engine(self):
        if hasattr(self, "idle_engine") and getattr(self.idle_engine, "paused", False):
            self.idle_engine.resume()

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
            # 控制是否允许自动打破沉默的行为
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
                        # 如果UI设置禁用了自动打破沉默，则跳过执行逻辑
                        if not getattr(self, "auto_break_silence", True):
                            time.sleep(self.check_interval)
                            continue
                        # === 阶段1: AI决定打破沉默 ===
                        # 这只是一个决策信号，不生成对话
                        
                        # === 阶段2: 进行内部思考（准备阶段） ===
                        # 思考是打破沉默的准备，只显示在思考面板，不显示在聊天框
                        if self.thinking_engine:
                            try:
                                # 先运行GAN辩论来进行内部思考
                                self.thinking_engine.queue_gan_task(is_user_topic=False, memory=self.memory)
                            except:
                                pass
                        
                        # === 阶段3: 队列打破沉默任务 ===
                        # 这才是真正的打破沉默 - 生成AI主动对用户说的话
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
