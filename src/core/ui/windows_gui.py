"""
Humanaize v2.0 - Windows 专属现代化 GUI 界面
专为 Windows 安装包设计的现代化用户界面

设计特点:
- 毛玻璃效果
- 流畅动画过渡
- 现代化卡片式布局
- 响应式设计
- 深色/浅色主题支持
- 丰富的微交互效果
"""

import json
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import queue
import customtkinter as ctk
from PIL import Image, ImageTk

# 添加必要的路径
import sys
core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, core_dir)

from Agent import Agent
from thinking_engine import ThinkingEngine
from memory.memory import load_memory, save_memory, add
from personality import load_personality, save_personality
from ui.idle import IdleEngine
from tools.tools import SimpleLogger, check_llm_server
import config


class ModernWindowsUI:
    """Windows 专属现代化 GUI 界面"""
    
    def __init__(self, root):
        self.root = root
        self.title = getattr(config, "UI_TITLE", "Humanaize v2.0")
        self.width = getattr(config, "UI_WIDTH", 1280)
        self.height = getattr(config, "UI_HEIGHT", 800)
        
        # 设置窗口
        self.root.title(self.title)
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.minsize(1000, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 加载资源
        self._load_assets()
        
        # 初始化数据
        self.memory = load_memory()
        self.personality = load_personality()
        self.logger = SimpleLogger()
        
        # 加载设置
        self.settings = self._load_settings()
        self.language = self.settings.get("language", "中文")
        self.theme = self.settings.get("theme", "Dark")
        
        # 语言映射
        self._language_code_map = {
            "English": "en",
            "中文": "zh",
            "en": "en",
            "zh": "zh"
        }
        
        # 初始化引擎
        self.thinking_engine = ThinkingEngine(on_response_callback=self.on_engine_response)
        self.thinking_engine.set_language(self.get_language_code())
        
        # 翻译字典
        self._init_translations()
        
        # 自主引擎和空闲引擎
        self._init_autonomous_engine()
        self.idle_engine = IdleEngine(self.memory, self.on_engine_response, gan_enabled=True)
        
        # 创建UI
        self._setup_theme()
        self._create_main_ui()
        
        # 事件队列
        self._event_queue = queue.Queue()
        self.root.after(50, self._process_event_queue)
        
        # 状态更新定时器
        self._update_status()
        
        self.logger.info("Humanaize Windows GUI started successfully")
    
    def _load_assets(self):
        """加载图标和资源"""
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(ui_dir, "icons")
        
        # 尝试加载应用图标
        try:
            self.app_icon = ImageTk.PhotoImage(Image.open(os.path.join(icon_path, "app_icon.png")).resize((32, 32)))
        except:
            self.app_icon = None
    
    def _init_translations(self):
        """初始化翻译字典"""
        self.translations = {
            "中文": {
                "chat": "对话",
                "thoughts": "思考",
                "system": "系统",
                "command_output": "命令输出",
                "input_placeholder": "输入您的问题...",
                "send": "发送",
                "clear": "清空",
                "settings": "设置",
                "language": "语言",
                "theme": "主题",
                "model": "模型",
                "custom_model": "自定义模型",
                "skills": "技能",
                "save": "保存",
                "cancel": "取消",
                "ai_thinking": "AI 正在思考...",
                "gan_enabled": "启用 GAN",
                "auto_break": "自动打破沉默",
                "check_updates": "检查更新",
                "download_update": "下载更新",
                "update_available": "有可用更新",
                "up_to_date": "已是最新版本"
            },
            "English": {
                "chat": "Chat",
                "thoughts": "Thoughts",
                "system": "System",
                "command_output": "Command Output",
                "input_placeholder": "Enter your message...",
                "send": "Send",
                "clear": "Clear",
                "settings": "Settings",
                "language": "Language",
                "theme": "Theme",
                "model": "Model",
                "custom_model": "Custom Model",
                "skills": "Skills",
                "save": "Save",
                "cancel": "Cancel",
                "ai_thinking": "AI is thinking...",
                "gan_enabled": "Enable GAN",
                "auto_break": "Auto Break Silence",
                "check_updates": "Check Updates",
                "download_update": "Download Update",
                "update_available": "Update Available",
                "up_to_date": "Up to Date"
            }
        }
    
    def _init_autonomous_engine(self):
        """初始化自主引擎"""
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
                                "message": "对话已暂停，AI正在回顾上下文...",
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
            auto_break_silence=True,
        )
        self.autonomous_engine.start()
    
    def _load_settings(self):
        """加载用户设置"""
        settings_path = os.path.join(os.path.dirname(__file__), "data", "ui_settings.json")
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"language": "中文", "theme": "Dark"}
    
    def _save_settings(self, settings):
        """保存用户设置"""
        settings_path = os.path.join(os.path.dirname(__file__), "data", "ui_settings.json")
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        self.settings = settings
        self.language = settings.get("language", "中文")
        self.theme = settings.get("theme", "Dark")
    
    def _setup_theme(self):
        """设置主题"""
        ctk.set_appearance_mode("Dark" if self.theme == "Dark" else "Light")
        ctk.set_default_color_theme("blue")
        
        # 自定义颜色方案
        self.colors = {
            "Dark": {
                "bg": "#0d1117",
                "card": "#161b22",
                "card_hover": "#21262d",
                "border": "#30363d",
                "text": "#e6edf3",
                "text_dim": "#8b949e",
                "accent": "#58a6ff",
                "accent_hover": "#79c0ff",
                "success": "#3fb950",
                "warning": "#d29922",
                "error": "#f85149",
                "input_bg": "#0d1117",
                "scrollbar": "#21262d"
            },
            "Light": {
                "bg": "#ffffff",
                "card": "#f6f8fa",
                "card_hover": "#f0f6fc",
                "border": "#d0d7de",
                "text": "#21262d",
                "text_dim": "#6e7681",
                "accent": "#0969da",
                "accent_hover": "#1f6feb",
                "success": "#238636",
                "warning": "#9e6a03",
                "error": "#da3633",
                "input_bg": "#ffffff",
                "scrollbar": "#d0d7de"
            }
        }
        
        self.current_colors = self.colors[self.theme]
    
    def _create_main_ui(self):
        """创建主界面"""
        # 主背景
        self.root.configure(bg=self.current_colors["bg"])
        
        # 主容器
        self.main_container = ctk.CTkFrame(
            self.root,
            fg_color=self.current_colors["bg"],
            bg_color=self.current_colors["bg"],
            corner_radius=0,
            border_width=0
        )
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=0)
        self.main_container.grid_columnconfigure(1, weight=1)
        
        # 当前活动面板
        self.active_panel = "chat"
        
        # 左侧导航栏（侧拉栏入口）
        self._create_sidebar()
        
        # 主内容区域
        self._create_main_content()
        
        # 底部输入区域
        self._create_input_panel()
    
    def _create_sidebar(self):
        """创建侧边导航栏"""
        sidebar = ctk.CTkFrame(
            self.main_container,
            fg_color=self.current_colors["card"],
            corner_radius=20,
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
            "fg_color": self.current_colors["card_hover"],
            "hover_color": self.current_colors["border"],
            "text_color": self.current_colors["text_dim"]
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
                    fg_color=self.current_colors["accent"],
                    text_color="white",
                    hover_color=self.current_colors["accent_hover"]
                )
            else:
                btn.configure(
                    fg_color=self.current_colors["card_hover"],
                    text_color=self.current_colors["text_dim"],
                    hover_color=self.current_colors["border"]
                )
    
    def _create_main_content(self):
        """创建主内容区域容器"""
        self.content_container = ctk.CTkFrame(
            self.main_container,
            fg_color=self.current_colors["bg"],
            corner_radius=0,
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
        # 聊天容器
        self.chat_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=self.current_colors["card"],
            corner_radius=20,
            border_width=0
        )
        self.chat_frame.grid_rowconfigure(1, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        
        # 聊天头部
        header_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        header_frame.grid_columnconfigure(0, weight=1)
        
        # 标题
        self.chat_title = ctk.CTkLabel(
            header_frame,
            text=self._t("chat"),
            font=("Segoe UI", 20, "bold"),
            text_color=self.current_colors["text"],
            anchor="w"
        )
        self.chat_title.grid(row=0, column=0, sticky="w")
        
        # 状态指示器
        self.status_indicator = ctk.CTkLabel(
            header_frame,
            text="●",
            font=("Segoe UI", 14),
            text_color=self.current_colors["success"]
        )
        self.status_indicator.grid(row=0, column=1, padx=8)
        
        # 设置按钮
        self.settings_btn = ctk.CTkButton(
            header_frame,
            text="⚙",
            width=40,
            height=40,
            fg_color=self.current_colors["card_hover"],
            hover_color=self.current_colors["border"],
            corner_radius=12,
            font=("Segoe UI", 16),
            command=self._open_settings
        )
        self.settings_btn.grid(row=0, column=2, padx=(8, 0))
        
        # 聊天内容区域
        self.chat_box = ctk.CTkTextbox(
            self.chat_frame,
            wrap=tk.WORD,
            fg_color=self.current_colors["bg"],
            text_color=self.current_colors["text"],
            border_width=0,
            corner_radius=16,
            font=("Segoe UI", 14),
            state="disabled",
            scrollbar_button_color=self.current_colors["scrollbar"],
            scrollbar_button_hover_color=self.current_colors["border"]
        )
        self.chat_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        # 标签配置
        self.chat_box.tag_config("user", foreground=self.current_colors["accent"])
        self.chat_box.tag_config("ai", foreground=self.current_colors["text"])
        self.chat_box.tag_config("system", foreground=self.current_colors["text_dim"])
        self.chat_box.tag_config("thinking", foreground=self.current_colors["warning"])
        
        # 添加欢迎消息
        self._add_welcome_message()
    
    def _create_thoughts_panel(self):
        """创建思考面板"""
        self.thoughts_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=self.current_colors["card"],
            corner_radius=20,
            border_width=0
        )
        self.thoughts_frame.grid_rowconfigure(0, weight=1)
        self.thoughts_frame.grid_columnconfigure(0, weight=1)
        
        # 头部
        header_frame = ctk.CTkFrame(self.thoughts_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        header_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            header_frame,
            text=self._t("thoughts"),
            font=("Segoe UI", 20, "bold"),
            text_color=self.current_colors["text"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w")
        
        # 思考内容区域
        self.thought_text = ctk.CTkTextbox(
            self.thoughts_frame,
            wrap=tk.WORD,
            fg_color=self.current_colors["bg"],
            text_color=self.current_colors["text"],
            border_width=0,
            corner_radius=16,
            font=("Segoe UI", 14),
            state="disabled",
            scrollbar_button_color=self.current_colors["scrollbar"],
            scrollbar_button_hover_color=self.current_colors["border"]
        )
        self.thought_text.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
    
    def _create_command_panel(self):
        """创建命令输出面板"""
        self.command_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=self.current_colors["card"],
            corner_radius=20,
            border_width=0
        )
        self.command_frame.grid_rowconfigure(0, weight=1)
        self.command_frame.grid_columnconfigure(0, weight=1)
        
        # 头部
        header_frame = ctk.CTkFrame(self.command_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        header_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            header_frame,
            text=self._t("command_output"),
            font=("Segoe UI", 20, "bold"),
            text_color=self.current_colors["text"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w")
        
        # 命令输出内容区域
        self.command_text = ctk.CTkTextbox(
            self.command_frame,
            wrap=tk.NONE,
            fg_color=self.current_colors["bg"],
            text_color=self.current_colors["text"],
            border_width=0,
            corner_radius=16,
            font=("Consolas", 12),
            state="disabled",
            scrollbar_button_color=self.current_colors["scrollbar"],
            scrollbar_button_hover_color=self.current_colors["border"]
        )
        self.command_text.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
    
    def _create_status_panel(self):
        """创建系统状态面板"""
        self.status_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=self.current_colors["card"],
            corner_radius=20,
            border_width=0
        )
        self.status_frame.grid_rowconfigure(0, weight=1)
        self.status_frame.grid_columnconfigure(0, weight=1)
        
        # 头部
        header_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        header_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            header_frame,
            text=self._t("system"),
            font=("Segoe UI", 20, "bold"),
            text_color=self.current_colors["text"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w")
        
        # 状态内容区域
        self.status_text = ctk.CTkTextbox(
            self.status_frame,
            wrap=tk.WORD,
            fg_color=self.current_colors["bg"],
            text_color=self.current_colors["text"],
            border_width=0,
            corner_radius=16,
            font=("Segoe UI", 14),
            state="disabled",
            scrollbar_button_color=self.current_colors["scrollbar"],
            scrollbar_button_hover_color=self.current_colors["border"]
        )
        self.status_text.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
    
    def _create_info_panel(self):
        """创建右侧信息面板（保留以兼容旧代码）"""
        pass
    
    def _create_thought_section(self, parent):
        """创建思考区域（保留以兼容旧代码）"""
        pass
    
    def _create_command_section(self, parent):
        """创建命令输出区域（保留以兼容旧代码）"""
        pass
    
    def _create_status_section(self, parent):
        """创建系统状态区域（保留以兼容旧代码）"""
        pass
    
    def _create_input_panel(self):
        """创建底部输入面板"""
        input_frame = ctk.CTkFrame(
            self.root,
            fg_color=self.current_colors["card"],
            corner_radius=20,
            border_width=0
        )
        input_frame.pack(fill=tk.X, padx=16, pady=(0, 16))
        input_frame.grid_columnconfigure(1, weight=1)
        
        # 输入框
        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text=self._t("input_placeholder"),
            fg_color=self.current_colors["bg"],
            text_color=self.current_colors["text"],
            placeholder_text_color=self.current_colors["text_dim"],
            border_width=0,
            corner_radius=16,
            font=("Segoe UI", 14),
            height=52
        )
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=12, pady=12)
        self.input_entry.bind("<Return>", lambda e: self._send_message())
        
        # 发送按钮
        self.send_btn = ctk.CTkButton(
            input_frame,
            text=self._t("send"),
            width=100,
            height=52,
            fg_color=self.current_colors["accent"],
            hover_color=self.current_colors["accent_hover"],
            corner_radius=16,
            font=("Segoe UI", 14, "bold"),
            text_color="white",
            command=self._send_message
        )
        self.send_btn.grid(row=0, column=2, padx=(0, 12), pady=12)
        
        # 清空按钮
        self.clear_btn = ctk.CTkButton(
            input_frame,
            text=self._t("clear"),
            width=80,
            height=52,
            fg_color=self.current_colors["card_hover"],
            hover_color=self.current_colors["border"],
            corner_radius=16,
            font=("Segoe UI", 14),
            text_color=self.current_colors["text"],
            command=self._clear_chat
        )
        self.clear_btn.grid(row=0, column=3, padx=(0, 12), pady=12)
    
    def _add_welcome_message(self):
        """添加欢迎消息"""
        welcome_text = {
            "中文": "欢迎使用 Humanaize v2.0！\n\n我是您的AI助手，可以帮助您解决问题、获取信息和完成任务。\n\n请输入您的问题，我会尽力为您解答。",
            "English": "Welcome to Humanaize v2.0!\n\nI am your AI assistant, here to help you solve problems, gather information, and complete tasks.\n\nPlease enter your question, and I will do my best to assist you."
        }
        
        self.chat_box.configure(state="normal")
        self.chat_box.insert(tk.END, welcome_text[self.language], "system")
        self.chat_box.insert(tk.END, "\n\n")
        self.chat_box.configure(state="disabled")
    
    def _send_message(self):
        """发送消息"""
        text = self.input_entry.get().strip()
        if not text:
            return
        
        # 清空输入
        self.input_entry.delete(0, tk.END)
        
        # 禁用按钮
        self.send_btn.configure(state="disabled")
        self.input_entry.configure(state="disabled")
        
        # 添加用户消息
        self._add_message(f"您: {text}", "user")
        
        # 保存到记忆
        add(self.memory, "user", text)
        save_memory(self.memory)
        
        # 暂停空闲引擎
        if hasattr(self, "idle_engine"):
            self.idle_engine.pause()
        self.autonomous_engine.on_user_message()
        
        # 显示思考状态
        self._add_message(self._t("ai_thinking"), "thinking")
        
        # 异步处理
        self._process_message_async(text)
    
    def _process_message_async(self, text):
        """异步处理消息"""
        def on_answer_decision(result):
            should_answer, answer_reason = result
            
            if not should_answer:
                self._add_message(f"系统: AI 选择不回复。原因: {answer_reason}", "system")
                self._resume_idle()
                return
            
            context = self._build_context()
            prompt = f"{context}\n\n用户: {text}\n助手:"
            
            def on_response(response):
                self._add_message(f"AI: {response}", "ai")
                add(self.memory, "assistant", response)
                save_memory(self.memory)
                self._resume_idle()
            
            # 调用思考引擎
            try:
                self.thinking_engine.queue_chat_task(prompt, memory=self.memory, use_gan_decision=True, user_text=text)
            except TypeError:
                self.thinking_engine.queue_chat_task(prompt)
        
        self.thinking_engine.should_answer_user_async(text, on_answer_decision)
    
    def _resume_idle(self):
        """恢复空闲状态"""
        if hasattr(self, "idle_engine"):
            self.idle_engine.resume()
        self.send_btn.configure(state="normal")
        self.input_entry.configure(state="normal")
        self.input_entry.focus()
    
    def _add_message(self, text, message_type="normal"):
        """添加消息到聊天框"""
        self.chat_box.configure(state="normal")
        
        if message_type == "user":
            self.chat_box.insert(tk.END, text + "\n\n", "user")
        elif message_type == "ai":
            self.chat_box.insert(tk.END, text + "\n\n", "ai")
        elif message_type == "system":
            self.chat_box.insert(tk.END, text + "\n\n", "system")
        elif message_type == "thinking":
            self.chat_box.insert(tk.END, text + "\n", "thinking")
        else:
            self.chat_box.insert(tk.END, text + "\n\n")
        
        self.chat_box.see(tk.END)
        self.chat_box.configure(state="disabled")
    
    def _clear_chat(self):
        """清空聊天"""
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", tk.END)
        self._add_welcome_message()
        self.chat_box.configure(state="disabled")
    
    def _build_context(self):
        """构建上下文"""
        messages = self.memory.get("messages", [])[-8:]
        context = "最近对话:"
        for msg in messages:
            role = msg.get("role", "").capitalize()
            content = msg.get("content", "")[:100]
            context += f"\n{role}: {content}"
        return context
    
    def _open_settings(self):
        """打开设置窗口"""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title(self._t("settings"))
        settings_window.geometry("700x600")
        settings_window.minsize(600, 500)
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # 设置背景
        settings_window.configure(bg=self.current_colors["bg"])
        
        # 主框架
        main_frame = ctk.CTkFrame(settings_window, fg_color=self.current_colors["card"], corner_radius=20)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 滚动区域
        scroll_frame = ctk.CTkScrollableFrame(main_frame, fg_color="transparent")
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        row = 0
        
        # 标题
        title_label = ctk.CTkLabel(scroll_frame, text=self._t("settings"), font=("Segoe UI", 20, "bold"), text_color=self.current_colors["accent"])
        title_label.grid(row=row, column=0, sticky="w", pady=(0, 20))
        row += 1
        
        # 语言设置
        lang_frame = ctk.CTkFrame(scroll_frame, fg_color=self.current_colors["bg"], corner_radius=12)
        lang_frame.grid(row=row, column=0, sticky="ew", pady=(0, 15))
        
        ctk.CTkLabel(lang_frame, text=self._t("language"), font=("Segoe UI", 12, "bold"), text_color=self.current_colors["text"]).grid(row=0, column=0, sticky="w", padx=15, pady=12)
        
        lang_var = tk.StringVar(value=self.language)
        lang_option = ctk.CTkOptionMenu(
            lang_frame,
            values=["中文", "English"],
            variable=lang_var,
            fg_color=self.current_colors["card_hover"],
            button_color=self.current_colors["accent"],
            button_hover_color=self.current_colors["accent_hover"],
            text_color=self.current_colors["text"]
        )
        lang_option.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 12))
        row += 1
        
        # 主题设置
        theme_frame = ctk.CTkFrame(scroll_frame, fg_color=self.current_colors["bg"], corner_radius=12)
        theme_frame.grid(row=row, column=0, sticky="ew", pady=(0, 15))
        
        ctk.CTkLabel(theme_frame, text=self._t("theme"), font=("Segoe UI", 12, "bold"), text_color=self.current_colors["text"]).grid(row=0, column=0, sticky="w", padx=15, pady=12)
        
        theme_var = tk.StringVar(value=self.theme)
        theme_option = ctk.CTkOptionMenu(
            theme_frame,
            values=["Dark", "Light"],
            variable=theme_var,
            fg_color=self.current_colors["card_hover"],
            button_color=self.current_colors["accent"],
            button_hover_color=self.current_colors["accent_hover"],
            text_color=self.current_colors["text"]
        )
        theme_option.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 12))
        row += 1
        
        # 按钮区域
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        save_btn = ctk.CTkButton(
            btn_frame,
            text=self._t("save"),
            fg_color=self.current_colors["accent"],
            hover_color=self.current_colors["accent_hover"],
            corner_radius=12,
            font=("Segoe UI", 14, "bold"),
            command=lambda: self._save_settings_and_close(settings_window, lang_var, theme_var)
        )
        save_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text=self._t("cancel"),
            fg_color=self.current_colors["card_hover"],
            hover_color=self.current_colors["border"],
            corner_radius=12,
            font=("Segoe UI", 14),
            text_color=self.current_colors["text"],
            command=settings_window.destroy
        )
        cancel_btn.pack(side=tk.RIGHT)
    
    def _save_settings_and_close(self, window, lang_var, theme_var):
        """保存设置并关闭窗口"""
        settings = {
            "language": lang_var.get(),
            "theme": theme_var.get()
        }
        self._save_settings(settings)
        
        # 如果主题改变，提示重启
        if theme_var.get() != self.theme:
            messagebox.showinfo("提示", "主题已更改，请重启应用以生效")
        
        window.destroy()
    
    def _update_status(self):
        """更新系统状态"""
        status_info = []
        status_info.append(f"模型: {config.MODEL_NAME}")
        status_info.append(f"消息数: {len(self.memory.get('messages', []))}")
        status_info.append(f"状态: 运行中")
        
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", tk.END)
        self.status_text.insert(tk.END, "\n".join(status_info))
        self.status_text.configure(state="disabled")
        
        # 定时更新
        self.root.after(5000, self._update_status)
    
    def _process_event_queue(self):
        """处理事件队列"""
        while not self._event_queue.empty():
            event = self._event_queue.get()
            if event["type"] == "message":
                self._add_message(event["content"], event.get("type", "normal"))
        
        self.root.after(50, self._process_event_queue)
    
    def on_engine_response(self, response):
        """处理引擎响应"""
        if isinstance(response, dict):
            content = response.get("message", "")
            if content:
                self._event_queue.put({"type": "system", "content": content})
        elif isinstance(response, str):
            self._event_queue.put({"type": "ai", "content": f"AI: {response}"})
    
    def on_autonomous_speak(self, message):
        """处理自主发言"""
        self._event_queue.put({"type": "system", "content": f"系统: {message}"})
    
    def get_language_code(self):
        """获取语言代码"""
        return self._language_code_map.get(self.language, "zh")
    
    def _t(self, key):
        """翻译工具"""
        return self.translations.get(self.language, self.translations["中文"]).get(key, key)
    
    def on_closing(self):
        """关闭窗口处理"""
        if hasattr(self, "autonomous_engine"):
            self.autonomous_engine.stop()
        if hasattr(self, "idle_engine"):
            self.idle_engine.stop()
        save_memory(self.memory)
        self.root.destroy()


class _AutonomousAdapter:
    """自主引擎适配器"""
    
    def __init__(self, memory, on_auto_speak, on_decision_callback, thinking_engine, auto_break_silence=True):
        self.memory = memory
        self.on_auto_speak = on_auto_speak
        self.on_decision_callback = on_decision_callback
        self.thinking_engine = thinking_engine
        self.auto_break_silence = auto_break_silence
        self._running = False
        self._thread = None
        self._last_message_time = time.time()
    
    def start(self):
        """启动自主引擎"""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止自主引擎"""
        self._running = False
    
    def on_user_message(self):
        """处理用户消息"""
        self._last_message_time = time.time()
    
    def _run(self):
        """运行自主引擎"""
        while self._running:
            time.sleep(1)
            if not self.auto_break_silence:
                continue
            
            elapsed = time.time() - self._last_message_time
            if elapsed > 60:  # 60秒无活动
                try:
                    result = check_silence_and_decide(self.memory, 60)
                    if result and result.get("action") == "AUTO_THINK":
                        self.on_auto_speak(result.get("message", "AI正在思考..."))
                        # 触发思考
                        context = self._build_context()
                        prompt = f"{context}\n\n用户已暂停，AI自主思考:"
                        self.thinking_engine.queue_chat_task(prompt)
                        self._last_message_time = time.time()
                except Exception:
                    pass


def main():
    """主函数"""
    app = ctk.CTk()
    ModernWindowsUI(app)
    app.mainloop()


if __name__ == "__main__":
    main()