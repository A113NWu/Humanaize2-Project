# -*- coding: utf-8 -*-
"""
游戏技能GUI配置界面
支持创建、编辑、删除游戏配置文件
包含激活触发、操作映射、死亡检测三个配置面板
"""

import os
import sys
import json
import threading
import time
from tkinter import (
    Tk, Frame, Label, Entry, Button, Listbox, Scrollbar,
    Checkbutton, IntVar, StringVar, Radiobutton, Spinbox,
    Toplevel, Canvas, Menu, messagebox, ttk
)

_PYAUTOGUI_MODULE = None
_PIL_MODULE = None
_KEYBOARD_MODULE = None

def _lazy_import_pyautogui():
    global _PYAUTOGUI_MODULE
    if _PYAUTOGUI_MODULE is None:
        try:
            import pyautogui
            _PYAUTOGUI_MODULE = pyautogui
        except ImportError:
            pass
    return _PYAUTOGUI_MODULE

def _lazy_import_pil():
    global _PIL_MODULE
    if _PIL_MODULE is None:
        try:
            from PIL import Image, ImageGrab, ImageTk
            _PIL_MODULE = (Image, ImageGrab, ImageTk)
        except ImportError:
            pass
    return _PIL_MODULE

def _lazy_import_keyboard():
    global _KEYBOARD_MODULE
    if _KEYBOARD_MODULE is None:
        try:
            import keyboard
            _KEYBOARD_MODULE = keyboard
        except ImportError:
            pass
    return _KEYBOARD_MODULE


class GamingConfigGUI:
    """游戏技能配置界面"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("游戏技能配置 - Humanaize Gaming Skill")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        
        self._profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
        self._current_config = None
        self._current_profile_name = ""
        self._recording_key = False
        self._selected_control_index = -1
        self._selected_death_method = ""
        
        self._setup_styles()
        self._create_widgets()
        self._load_profiles()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('Title.TLabel', font=('Microsoft YaHei', 12, 'bold'))
        style.configure('Header.TLabel', font=('Microsoft YaHei', 10, 'bold'))
        style.configure('Normal.TLabel', font=('Microsoft YaHei', 9))
        
        style.configure('Action.TButton', font=('Microsoft YaHei', 9))
        style.map('Action.TButton',
                  foreground=[('active', 'white'), ('pressed', 'white')],
                  background=[('active', '#4CAF50'), ('pressed', '#45a049')])
    
    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        left_panel = ttk.Frame(main_frame, width=220)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)
        
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side='right', fill='both', expand=True)
        
        self._create_left_panel(left_panel)
        self._create_right_panel(right_panel)
    
    def _create_left_panel(self, parent):
        """创建左侧配置列表面板"""
        title_label = ttk.Label(parent, text="游戏配置列表", style='Title.TLabel')
        title_label.pack(pady=(0, 10))
        
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True)
        
        self.profile_listbox = Listbox(list_frame, font=('Microsoft YaHei', 9), selectmode='single')
        self.profile_listbox.pack(side='left', fill='both', expand=True)
        
        scrollbar = Scrollbar(list_frame, orient='vertical', command=self.profile_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.profile_listbox.config(yscrollcommand=scrollbar.set)
        
        self.profile_listbox.bind('<<ListboxSelect>>', self._on_profile_select)
        
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="新建配置", command=self._create_new_profile, style='Action.TButton').pack(fill='x', pady=2)
        ttk.Button(button_frame, text="删除配置", command=self._delete_profile, style='Action.TButton').pack(fill='x', pady=2)
        ttk.Button(button_frame, text="保存配置", command=self._save_profile, style='Action.TButton').pack(fill='x', pady=2)
        
        detect_button_frame = ttk.Frame(parent)
        detect_button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(detect_button_frame, text="检测窗口标题", command=self._detect_window_title, style='Action.TButton').pack(fill='x', pady=2)
        
        self.detected_title_var = StringVar(value="未检测")
        ttk.Label(parent, textvariable=self.detected_title_var, style='Normal.TLabel', wraplength=200).pack(pady=(5, 0))
    
    def _create_right_panel(self, parent):
        """创建右侧配置编辑面板"""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill='both', expand=True)
        
        self.tab_trigger = ttk.Frame(notebook)
        self.tab_controls = ttk.Frame(notebook)
        self.tab_time_limit = ttk.Frame(notebook)
        self.tab_death = ttk.Frame(notebook)
        
        notebook.add(self.tab_trigger, text="激活触发")
        notebook.add(self.tab_controls, text="操作映射")
        notebook.add(self.tab_time_limit, text="时间限制")
        notebook.add(self.tab_death, text="死亡检测")
        
        self._create_trigger_tab(self.tab_trigger)
        self._create_controls_tab(self.tab_controls)
        self._create_time_limit_tab(self.tab_time_limit)
        self._create_death_tab(self.tab_death)
    
    def _create_trigger_tab(self, parent):
        """创建激活触发配置面板"""
        frame = ttk.LabelFrame(parent, text="激活条件", padding="10")
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="游戏名称:", style='Normal.TLabel').grid(row=0, column=0, sticky='w', pady=5)
        self.game_name_entry = ttk.Entry(frame, width=50)
        self.game_name_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        ttk.Label(frame, text="游戏描述:", style='Normal.TLabel').grid(row=1, column=0, sticky='w', pady=5)
        self.description_entry = ttk.Entry(frame, width=50)
        self.description_entry.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        ttk.Label(frame, text="窗口标题匹配:", style='Normal.TLabel').grid(row=2, column=0, sticky='w', pady=5)
        self.window_title_entry = ttk.Entry(frame, width=50)
        self.window_title_entry.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))
        ttk.Button(frame, text="录制", command=self._record_window_title).grid(row=2, column=2, padx=(5, 0))
        
        ttk.Label(frame, text="匹配模式:", style='Normal.TLabel').grid(row=3, column=0, sticky='w', pady=5)
        self.match_mode_var = StringVar(value="contains")
        match_frame = ttk.Frame(frame)
        match_frame.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Radiobutton(match_frame, text="包含", variable=self.match_mode_var, value="contains").pack(side='left', padx=5)
        ttk.Radiobutton(match_frame, text="等于", variable=self.match_mode_var, value="equals").pack(side='left', padx=5)
        ttk.Radiobutton(match_frame, text="正则", variable=self.match_mode_var, value="regex").pack(side='left', padx=5)
        
        ttk.Label(frame, text="游戏提示:", style='Normal.TLabel').grid(row=4, column=0, sticky='nw', pady=5)
        self.tips_text = TextEditor(frame, height=4, width=50, auto_layout=False)
        self.tips_text.grid(row=4, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        frame.grid_columnconfigure(1, weight=1)
    
    def _create_controls_tab(self, parent):
        """创建操作映射配置面板"""
        frame = ttk.LabelFrame(parent, text="操作列表", padding="10")
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        controls_list_frame = ttk.Frame(frame, height=200)
        controls_list_frame.pack(fill='x', pady=(0, 10))
        controls_list_frame.pack_propagate(False)
        
        self.controls_listbox = Listbox(controls_list_frame, font=('Microsoft YaHei', 9))
        self.controls_listbox.pack(side='left', fill='both', expand=True)
        
        scrollbar = Scrollbar(controls_list_frame, orient='vertical', command=self.controls_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.controls_listbox.config(yscrollcommand=scrollbar.set)
        
        self.controls_listbox.bind('<<ListboxSelect>>', self._on_control_select)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(button_frame, text="添加操作", command=self._add_control).pack(side='left', padx=5)
        ttk.Button(button_frame, text="编辑操作", command=self._edit_control).pack(side='left', padx=5)
        ttk.Button(button_frame, text="删除操作", command=self._delete_control).pack(side='left', padx=5)
        
        detail_frame = ttk.LabelFrame(frame, text="操作详情")
        detail_frame.pack(fill='both', expand=True)
        
        ttk.Label(detail_frame, text="操作名称:", style='Normal.TLabel').grid(row=0, column=0, sticky='w', pady=5, padx=5)
        self.control_name_entry = ttk.Entry(detail_frame, width=20)
        self.control_name_entry.grid(row=0, column=1, sticky='w', pady=5, padx=5)
        
        ttk.Label(detail_frame, text="操作标识符:", style='Normal.TLabel').grid(row=0, column=2, sticky='w', pady=5, padx=5)
        self.control_action_entry = ttk.Entry(detail_frame, width=20)
        self.control_action_entry.grid(row=0, column=3, sticky='w', pady=5, padx=5)
        
        ttk.Label(detail_frame, text="操作类型:", style='Normal.TLabel').grid(row=1, column=0, sticky='w', pady=5, padx=5)
        self.control_type_var = StringVar(value="key")
        type_frame = ttk.Frame(detail_frame)
        type_frame.grid(row=1, column=1, columnspan=3, sticky='w', pady=5, padx=5)
        ttk.Radiobutton(type_frame, text="键盘按键", variable=self.control_type_var, value="key").pack(side='left', padx=10)
        ttk.Radiobutton(type_frame, text="鼠标点击", variable=self.control_type_var, value="mouse_click").pack(side='left', padx=10)
        ttk.Radiobutton(type_frame, text="鼠标移动", variable=self.control_type_var, value="mouse_move").pack(side='left', padx=10)
        
        self.control_keys_frame = ttk.Frame(detail_frame)
        self.control_keys_frame.grid(row=2, column=0, columnspan=4, sticky='ew', pady=5, padx=5)
        
        ttk.Label(self.control_keys_frame, text="按键列表:", style='Normal.TLabel').pack(side='left')
        self.control_keys_entry = ttk.Entry(self.control_keys_frame, width=30)
        self.control_keys_entry.pack(side='left', padx=5)
        ttk.Button(self.control_keys_frame, text="录制按键", command=self._record_keys).pack(side='left', padx=5)
        
        self.control_button_frame = ttk.Frame(detail_frame)
        self.control_button_frame.grid(row=3, column=0, columnspan=4, sticky='ew', pady=5, padx=5)
        
        ttk.Label(self.control_button_frame, text="鼠标按钮:", style='Normal.TLabel').pack(side='left')
        self.control_button_var = StringVar(value="left")
        ttk.Radiobutton(self.control_button_frame, text="左键", variable=self.control_button_var, value="left").pack(side='left', padx=10)
        ttk.Radiobutton(self.control_button_frame, text="右键", variable=self.control_button_var, value="right").pack(side='left', padx=10)
        ttk.Radiobutton(self.control_button_frame, text="中键", variable=self.control_button_var, value="middle").pack(side='left', padx=10)
        
        self.control_button_frame.grid_remove()
        
        ttk.Label(detail_frame, text="操作说明:", style='Normal.TLabel').grid(row=4, column=0, sticky='w', pady=5, padx=5)
        self.control_desc_entry = ttk.Entry(detail_frame, width=40)
        self.control_desc_entry.grid(row=4, column=1, columnspan=3, sticky='ew', pady=5, padx=5)
        
        detail_frame.grid_columnconfigure(3, weight=1)
        
        self.control_type_var.trace('w', self._on_control_type_change)
    
    def _create_time_limit_tab(self, parent):
        """创建时间限制配置面板"""
        frame = ttk.LabelFrame(parent, text="时间限制设置", padding="10")
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.time_limit_enabled_var = IntVar(value=0)
        ttk.Checkbutton(frame, text="启用时间限制检测", variable=self.time_limit_enabled_var).pack(anchor='w', pady=5)
        
        settings_frame = ttk.LabelFrame(frame, text="时间设置")
        settings_frame.pack(fill='x', pady=(10, 0))
        
        tl_row1 = ttk.Frame(settings_frame)
        tl_row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(tl_row1, text="关卡总时间 (秒):", style='Normal.TLabel').pack(side='left')
        self.tl_total_time_spin = Spinbox(tl_row1, from_=0, to=600, width=8)
        self.tl_total_time_spin.pack(side='left', padx=5)
        ttk.Label(tl_row1, text="设为0则优先使用屏幕OCR检测").pack(side='left', padx=5)
        
        tl_row2 = ttk.Frame(settings_frame)
        tl_row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(tl_row2, text="紧急阈值 (%):", style='Normal.TLabel').pack(side='left')
        self.tl_urgency_spin = Spinbox(tl_row2, from_=1, to=100, width=5)
        self.tl_urgency_spin.pack(side='left', padx=5)
        ttk.Label(tl_row2, text="剩余时间低于此百分比时触发紧急状态").pack(side='left', padx=5)
        
        tl_row3 = ttk.Frame(settings_frame)
        tl_row3.pack(fill='x', padx=10, pady=5)
        ttk.Label(tl_row3, text="超时时执行动作:", style='Normal.TLabel').pack(side='left')
        self.tl_action_entry = ttk.Entry(tl_row3, width=20)
        self.tl_action_entry.pack(side='left', padx=5)
        ttk.Label(tl_row3, text="(如 restart)").pack(side='left', padx=5)
        
        region_frame = ttk.LabelFrame(frame, text="屏幕计时器区域（百分比坐标）")
        region_frame.pack(fill='x', pady=(10, 0))
        
        tl_region_row1 = ttk.Frame(region_frame)
        tl_region_row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(tl_region_row1, text="X:", style='Normal.TLabel').pack(side='left')
        self.tl_region_x_spin = Spinbox(tl_region_row1, from_=0, to=100, width=5)
        self.tl_region_x_spin.pack(side='left', padx=5)
        ttk.Label(tl_region_row1, text="Y:", style='Normal.TLabel').pack(side='left')
        self.tl_region_y_spin = Spinbox(tl_region_row1, from_=0, to=100, width=5)
        self.tl_region_y_spin.pack(side='left', padx=5)
        
        tl_region_row2 = ttk.Frame(region_frame)
        tl_region_row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(tl_region_row2, text="宽度:", style='Normal.TLabel').pack(side='left')
        self.tl_region_w_spin = Spinbox(tl_region_row2, from_=1, to=50, width=5)
        self.tl_region_w_spin.pack(side='left', padx=5)
        ttk.Label(tl_region_row2, text="高度:", style='Normal.TLabel').pack(side='left')
        self.tl_region_h_spin = Spinbox(tl_region_row2, from_=1, to=50, width=5)
        self.tl_region_h_spin.pack(side='left', padx=5)
        
        ttk.Label(region_frame, text="OCR会在此区域内识别时间显示（如 1:45）", style='Normal.TLabel').pack(anchor='w', padx=10, pady=5)
        
        keywords_frame = ttk.LabelFrame(frame, text="时间警告关键词")
        keywords_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(keywords_frame, text="时间警告关键词（每行一个）:", style='Normal.TLabel').pack(anchor='w', padx=10, pady=5)
        self.tl_keywords_text = TextEditor(keywords_frame, height=3, width=60)
        self.tl_keywords_text.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(keywords_frame, text="OCR检测到这些关键词时会触发时间警告", style='Normal.TLabel').pack(anchor='w', padx=10, pady=5)
    
    def _create_death_tab(self, parent):
        """创建死亡检测配置面板"""
        frame = ttk.LabelFrame(parent, text="死亡检测策略", padding="10")
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        methods_frame = ttk.LabelFrame(frame, text="启用的检测方法")
        methods_frame.pack(fill='x', pady=(0, 10))
        
        self.death_methods = {
            "text": IntVar(value=0),
            "health_bar": IntVar(value=0),
            "scene_change": IntVar(value=0),
            "visual_cues": IntVar(value=0)
        }
        
        ttk.Checkbutton(methods_frame, text="文字检测 (OCR识别Game Over等文字)", variable=self.death_methods["text"]).pack(anchor='w', padx=10, pady=2)
        ttk.Checkbutton(methods_frame, text="血条检测 (监控血条颜色变化)", variable=self.death_methods["health_bar"]).pack(anchor='w', padx=10, pady=2)
        ttk.Checkbutton(methods_frame, text="画面突变 (检测场景切换)", variable=self.death_methods["scene_change"]).pack(anchor='w', padx=10, pady=2)
        ttk.Checkbutton(methods_frame, text="视觉线索 (LLM分析画面)", variable=self.death_methods["visual_cues"]).pack(anchor='w', padx=10, pady=2)
        
        ttk.Button(methods_frame, text="重置为默认", command=self._reset_death_methods).pack(anchor='w', padx=10, pady=5)
        
        details_frame = ttk.Frame(frame)
        details_frame.pack(fill='both', expand=True)
        
        self.text_frame = ttk.LabelFrame(details_frame, text="文字检测配置")
        self.text_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(self.text_frame, text="死亡关键词（用逗号分隔）:", style='Normal.TLabel').pack(anchor='w', padx=10, pady=5)
        self.text_keywords_text = TextEditor(self.text_frame, height=3, width=60)
        self.text_keywords_text.pack(fill='x', padx=10, pady=5)
        
        self.health_bar_frame = ttk.LabelFrame(details_frame, text="血条检测配置")
        self.health_bar_frame.pack(fill='x', pady=(0, 10))
        
        hb_row1 = ttk.Frame(self.health_bar_frame)
        hb_row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(hb_row1, text="区域X:", style='Normal.TLabel').pack(side='left')
        self.hb_x_spin = Spinbox(hb_row1, from_=0, to=100, width=5)
        self.hb_x_spin.pack(side='left', padx=5)
        ttk.Label(hb_row1, text="Y:", style='Normal.TLabel').pack(side='left')
        self.hb_y_spin = Spinbox(hb_row1, from_=0, to=100, width=5)
        self.hb_y_spin.pack(side='left', padx=5)
        ttk.Label(hb_row1, text="宽度:", style='Normal.TLabel').pack(side='left')
        self.hb_w_spin = Spinbox(hb_row1, from_=1, to=50, width=5)
        self.hb_w_spin.pack(side='left', padx=5)
        ttk.Label(hb_row1, text="高度:", style='Normal.TLabel').pack(side='left')
        self.hb_h_spin = Spinbox(hb_row1, from_=1, to=50, width=5)
        self.hb_h_spin.pack(side='left', padx=5)
        
        ttk.Button(self.health_bar_frame, text="截取屏幕并选择区域", command=self._select_health_region).pack(padx=10, pady=5)
        
        hb_row2 = ttk.Frame(self.health_bar_frame)
        hb_row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(hb_row2, text="空血条颜色 (RGB):", style='Normal.TLabel').pack(side='left')
        self.hb_color_entry = ttk.Entry(hb_row2, width=20)
        self.hb_color_entry.pack(side='left', padx=5)
        ttk.Label(hb_row2, text="阈值:", style='Normal.TLabel').pack(side='left')
        self.hb_threshold_spin = Spinbox(hb_row2, from_=1, to=255, width=5)
        self.hb_threshold_spin.pack(side='left', padx=5)
        
        self.scene_frame = ttk.LabelFrame(details_frame, text="画面突变配置")
        self.scene_frame.pack(fill='x', pady=(0, 10))
        
        sf_row1 = ttk.Frame(self.scene_frame)
        sf_row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(sf_row1, text="像素变化阈值 (%):", style='Normal.TLabel').pack(side='left')
        self.scene_threshold_spin = Spinbox(sf_row1, from_=1, to=100, width=5)
        self.scene_threshold_spin.pack(side='left', padx=5)
        
        self.visual_frame = ttk.LabelFrame(details_frame, text="视觉线索配置")
        self.visual_frame.pack(fill='x', pady=(0, 10))
        
        vf_row1 = ttk.Frame(self.visual_frame)
        vf_row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(vf_row1, text="置信度阈值:", style='Normal.TLabel').pack(side='left')
        self.visual_threshold_spin = Spinbox(vf_row1, from_=0.1, to=1.0, increment=0.05, width=8)
        self.visual_threshold_spin.pack(side='left', padx=5)
    
    def _load_profiles(self):
        """加载配置文件列表"""
        self.profile_listbox.delete(0, 'end')
        
        if not os.path.exists(self._profiles_dir):
            os.makedirs(self._profiles_dir, exist_ok=True)
        
        for filename in sorted(os.listdir(self._profiles_dir)):
            if filename.endswith(".json") and filename != "schema.json":
                self.profile_listbox.insert('end', filename[:-5])
        
        if self.profile_listbox.size() > 0:
            self.profile_listbox.select_set(0)
            self._on_profile_select(None)
    
    def _on_profile_select(self, event):
        """选择配置文件"""
        selection = self.profile_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        profile_name = self.profile_listbox.get(index)
        self._current_profile_name = profile_name
        
        self._load_profile(profile_name)
    
    def _load_profile(self, profile_name):
        """加载配置文件内容"""
        profile_path = os.path.join(self._profiles_dir, f"{profile_name}.json")
        
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                self._current_config = json.load(f)
        except Exception as e:
            messagebox.showerror("错误", f"加载配置文件失败: {str(e)}")
            return
        
        self._fill_trigger_form()
        self._fill_controls_list()
        self._fill_time_limit_form()
        self._fill_death_form()
    
    def _fill_trigger_form(self):
        """填充激活触发表单"""
        config = self._current_config
        
        self.game_name_entry.delete(0, 'end')
        self.game_name_entry.insert(0, config.get("game_name", ""))
        
        self.description_entry.delete(0, 'end')
        self.description_entry.insert(0, config.get("description", ""))
        
        trigger = config.get("trigger", {})
        self.window_title_entry.delete(0, 'end')
        self.window_title_entry.insert(0, trigger.get("window_title", ""))
        
        self.match_mode_var.set(trigger.get("match_mode", "contains"))
        
        tips = config.get("tips", [])
        self.tips_text.set_text("\n".join(tips))
    
    def _fill_controls_list(self):
        """填充操作列表"""
        self.controls_listbox.delete(0, 'end')
        
        controls = self._current_config.get("controls", [])
        for i, control in enumerate(controls):
            name = control.get("name", "")
            action = control.get("action", "")
            ctrl_type = control.get("type", "")
            self.controls_listbox.insert('end', f"{i+1}. {name} ({action}) - {ctrl_type}")
        
        self._clear_control_form()
    
    def _fill_time_limit_form(self):
        """填充时间限制表单"""
        time_limit = self._current_config.get("time_limit", {})
        
        self.time_limit_enabled_var.set(1 if time_limit.get("enabled", False) else 0)
        
        self.tl_total_time_spin.delete(0, 'end')
        self.tl_total_time_spin.insert(0, str(time_limit.get("total_time", 0)))
        
        self.tl_urgency_spin.delete(0, 'end')
        self.tl_urgency_spin.insert(0, str(time_limit.get("urgency_threshold", 30)))
        
        self.tl_action_entry.delete(0, 'end')
        self.tl_action_entry.insert(0, time_limit.get("action_on_timeout", "restart"))
        
        timer_region = time_limit.get("timer_region", {})
        self.tl_region_x_spin.delete(0, 'end')
        self.tl_region_x_spin.insert(0, str(timer_region.get("x", 0)))
        self.tl_region_y_spin.delete(0, 'end')
        self.tl_region_y_spin.insert(0, str(timer_region.get("y", 0)))
        self.tl_region_w_spin.delete(0, 'end')
        self.tl_region_w_spin.insert(0, str(timer_region.get("width", 0)))
        self.tl_region_h_spin.delete(0, 'end')
        self.tl_region_h_spin.insert(0, str(timer_region.get("height", 0)))
        
        warning_messages = time_limit.get("warning_messages", [])
        self.tl_keywords_text.set_text("\n".join(warning_messages))
    
    def _fill_death_form(self):
        """填充死亡检测表单"""
        death_detection = self._current_config.get("death_detection", {})
        enabled_methods = death_detection.get("enabled_methods", [])
        
        for method, var in self.death_methods.items():
            var.set(1 if method in enabled_methods else 0)
        
        text_config = death_detection.get("text", {})
        keywords = text_config.get("keywords", [])
        self.text_keywords_text.set_text("\n".join(keywords))
        
        health_bar_config = death_detection.get("health_bar", {})
        region = health_bar_config.get("region", {})
        self.hb_x_spin.delete(0, 'end')
        self.hb_x_spin.insert(0, str(region.get("x", 0)))
        self.hb_y_spin.delete(0, 'end')
        self.hb_y_spin.insert(0, str(region.get("y", 0)))
        self.hb_w_spin.delete(0, 'end')
        self.hb_w_spin.insert(0, str(region.get("width", 10)))
        self.hb_h_spin.delete(0, 'end')
        self.hb_h_spin.insert(0, str(region.get("height", 5)))
        
        empty_color = health_bar_config.get("empty_color", [0, 0, 0])
        self.hb_color_entry.delete(0, 'end')
        self.hb_color_entry.insert(0, f"{empty_color[0]}, {empty_color[1]}, {empty_color[2]}")
        
        self.hb_threshold_spin.delete(0, 'end')
        self.hb_threshold_spin.insert(0, str(health_bar_config.get("threshold", 50)))
        
        scene_change_config = death_detection.get("scene_change", {})
        self.scene_threshold_spin.delete(0, 'end')
        self.scene_threshold_spin.insert(0, str(scene_change_config.get("threshold", 30)))
        
        visual_cues_config = death_detection.get("visual_cues", {})
        self.visual_threshold_spin.delete(0, 'end')
        self.visual_threshold_spin.insert(0, str(visual_cues_config.get("confidence_threshold", 0.7)))
    
    def _on_control_select(self, event):
        """选择操作项"""
        selection = self.controls_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        self._selected_control_index = index
        
        controls = self._current_config.get("controls", [])
        if index < len(controls):
            control = controls[index]
            self._fill_control_form(control)
    
    def _fill_control_form(self, control):
        """填充操作详情表单"""
        self.control_name_entry.delete(0, 'end')
        self.control_name_entry.insert(0, control.get("name", ""))
        
        self.control_action_entry.delete(0, 'end')
        self.control_action_entry.insert(0, control.get("action", ""))
        
        self.control_type_var.set(control.get("type", "key"))
        
        keys = control.get("keys", [])
        self.control_keys_entry.delete(0, 'end')
        self.control_keys_entry.insert(0, ", ".join(keys))
        
        self.control_button_var.set(control.get("button", "left"))
        
        self.control_desc_entry.delete(0, 'end')
        self.control_desc_entry.insert(0, control.get("description", ""))
    
    def _clear_control_form(self):
        """清空操作详情表单"""
        self.control_name_entry.delete(0, 'end')
        self.control_action_entry.delete(0, 'end')
        self.control_type_var.set("key")
        self.control_keys_entry.delete(0, 'end')
        self.control_button_var.set("left")
        self.control_desc_entry.delete(0, 'end')
        self._selected_control_index = -1
    
    def _on_control_type_change(self, *args):
        """操作类型变化处理"""
        ctrl_type = self.control_type_var.get()
        
        if ctrl_type == "key":
            self.control_keys_frame.grid()
            self.control_button_frame.grid_remove()
        elif ctrl_type == "mouse_click":
            self.control_keys_frame.grid_remove()
            self.control_button_frame.grid()
        else:
            self.control_keys_frame.grid_remove()
            self.control_button_frame.grid_remove()
    
    def _create_new_profile(self):
        """创建新配置"""
        name = self._get_unique_name("new_game")
        self._current_profile_name = name
        self._current_config = {
            "game_name": "新游戏",
            "description": "",
            "trigger": {
                "window_title": "",
                "match_mode": "contains"
            },
            "controls": [
                {"name": "什么都不做", "action": "do_nothing", "type": "key", "keys": [], "description": "保持当前状态"}
            ],
            "time_limit": {
                "enabled": False,
                "total_time": 0,
                "urgency_threshold": 30,
                "action_on_timeout": "restart",
                "timer_region": {"x": 0, "y": 0, "width": 0, "height": 0},
                "warning_messages": []
            },
            "death_detection": {
                "enabled_methods": ["text", "visual_cues"],
                "text": {"keywords": ["game over", "you died", "失败", "死亡"], "enabled": True},
                "health_bar": {"enabled": False},
                "scene_change": {"enabled": False, "threshold": 30},
                "visual_cues": {"enabled": True, "confidence_threshold": 0.7}
            },
            "ui_regions": {},
            "tips": []
        }
        
        self.profile_listbox.insert('end', name)
        self.profile_listbox.select_set(self.profile_listbox.size() - 1)
        
        self._fill_trigger_form()
        self._fill_controls_list()
        self._fill_time_limit_form()
        self._fill_death_form()
        
        messagebox.showinfo("提示", f"已创建新配置: {name}")
    
    def _get_unique_name(self, base_name):
        """获取唯一配置文件名"""
        names = [self.profile_listbox.get(i) for i in range(self.profile_listbox.size())]
        counter = 1
        new_name = base_name
        
        while new_name in names:
            new_name = f"{base_name}_{counter}"
            counter += 1
        
        return new_name
    
    def _delete_profile(self):
        """删除配置"""
        selection = self.profile_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个配置")
            return
        
        index = selection[0]
        profile_name = self.profile_listbox.get(index)
        
        if messagebox.askyesno("确认删除", f"确定要删除配置 '{profile_name}' 吗？"):
            profile_path = os.path.join(self._profiles_dir, f"{profile_name}.json")
            
            try:
                os.remove(profile_path)
                self.profile_listbox.delete(index)
                
                self._current_config = None
                self._current_profile_name = ""
                self._clear_control_form()
                
                messagebox.showinfo("提示", "配置已删除")
            except Exception as e:
                messagebox.showerror("错误", f"删除失败: {str(e)}")
    
    def _save_profile(self):
        """保存配置"""
        if not self._current_profile_name:
            messagebox.showwarning("警告", "请先创建或选择一个配置")
            return
        
        self._collect_trigger_data()
        self._collect_controls_data()
        self._collect_time_limit_data()
        self._collect_death_data()
        
        profile_path = os.path.join(self._profiles_dir, f"{self._current_profile_name}.json")
        
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(self._current_config, f, indent=4, ensure_ascii=False)
            
            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")
    
    def _collect_trigger_data(self):
        """收集激活触发数据"""
        if self._current_config is None:
            return
        
        self._current_config["game_name"] = self.game_name_entry.get().strip()
        self._current_config["description"] = self.description_entry.get().strip()
        
        if "trigger" not in self._current_config:
            self._current_config["trigger"] = {}
        
        self._current_config["trigger"]["window_title"] = self.window_title_entry.get().strip()
        self._current_config["trigger"]["match_mode"] = self.match_mode_var.get()
        
        tips_text = self.tips_text.get_text()
        self._current_config["tips"] = [t.strip() for t in tips_text.split('\n') if t.strip()]
    
    def _collect_controls_data(self):
        """收集操作映射数据"""
        if self._current_config is None:
            return
        
        controls = []
        for i in range(self.controls_listbox.size()):
            control = self._current_config.get("controls", [])[i]
            controls.append(control)
        
        self._current_config["controls"] = controls
    
    def _collect_time_limit_data(self):
        """收集时间限制数据"""
        if self._current_config is None:
            return
        
        time_limit = {
            "enabled": self.time_limit_enabled_var.get() == 1,
            "total_time": int(self.tl_total_time_spin.get()),
            "urgency_threshold": int(self.tl_urgency_spin.get()),
            "action_on_timeout": self.tl_action_entry.get().strip(),
            "timer_region": {
                "x": int(self.tl_region_x_spin.get()),
                "y": int(self.tl_region_y_spin.get()),
                "width": int(self.tl_region_w_spin.get()),
                "height": int(self.tl_region_h_spin.get())
            },
            "warning_messages": [k.strip() for k in self.tl_keywords_text.get_text().split('\n') if k.strip()]
        }
        
        self._current_config["time_limit"] = time_limit
    
    def _collect_death_data(self):
        """收集死亡检测数据"""
        if self._current_config is None:
            return
        
        enabled_methods = []
        for method, var in self.death_methods.items():
            if var.get() == 1:
                enabled_methods.append(method)
        
        death_detection = {
            "enabled_methods": enabled_methods,
            "text": {
                "keywords": [k.strip() for k in self.text_keywords_text.get_text().split('\n') if k.strip()],
                "enabled": True if "text" in enabled_methods else False
            },
            "health_bar": {
                "enabled": True if "health_bar" in enabled_methods else False,
                "region": {
                    "x": float(self.hb_x_spin.get()),
                    "y": float(self.hb_y_spin.get()),
                    "width": float(self.hb_w_spin.get()),
                    "height": float(self.hb_h_spin.get())
                },
                "empty_color": self._parse_color(self.hb_color_entry.get()),
                "threshold": int(self.hb_threshold_spin.get())
            },
            "scene_change": {
                "enabled": True if "scene_change" in enabled_methods else False,
                "threshold": int(self.scene_threshold_spin.get())
            },
            "visual_cues": {
                "enabled": True if "visual_cues" in enabled_methods else False,
                "confidence_threshold": float(self.visual_threshold_spin.get())
            }
        }
        
        self._current_config["death_detection"] = death_detection
    
    def _parse_color(self, color_str):
        """解析颜色字符串"""
        try:
            values = [int(v.strip()) for v in color_str.split(',')]
            while len(values) < 3:
                values.append(0)
            return values[:3]
        except Exception:
            return [0, 0, 0]
    
    def _add_control(self):
        """添加操作"""
        if self._current_config is None:
            messagebox.showwarning("警告", "请先创建或选择一个配置")
            return
        
        controls = self._current_config.get("controls", [])
        
        new_control = {
            "name": "新操作",
            "action": f"action_{len(controls) + 1}",
            "type": "key",
            "keys": [],
            "description": ""
        }
        
        controls.append(new_control)
        self._fill_controls_list()
        
        self.controls_listbox.select_set(len(controls) - 1)
        self._on_control_select(None)
    
    def _edit_control(self):
        """编辑操作"""
        if self._selected_control_index < 0:
            messagebox.showwarning("警告", "请先选择一个操作")
            return
        
        if self._current_config is None:
            return
        
        controls = self._current_config.get("controls", [])
        if self._selected_control_index >= len(controls):
            return
        
        control = controls[self._selected_control_index]
        
        control["name"] = self.control_name_entry.get().strip()
        control["action"] = self.control_action_entry.get().strip()
        control["type"] = self.control_type_var.get()
        
        ctrl_type = control["type"]
        if ctrl_type == "key":
            keys_str = self.control_keys_entry.get().strip()
            control["keys"] = [k.strip() for k in keys_str.split(',')] if keys_str else []
            control.pop("button", None)
        elif ctrl_type == "mouse_click":
            control["button"] = self.control_button_var.get()
            control.pop("keys", None)
        
        control["description"] = self.control_desc_entry.get().strip()
        
        self._fill_controls_list()
        
        self.controls_listbox.select_set(self._selected_control_index)
        self._on_control_select(None)
    
    def _delete_control(self):
        """删除操作"""
        if self._selected_control_index < 0:
            messagebox.showwarning("警告", "请先选择一个操作")
            return
        
        if self._current_config is None:
            return
        
        controls = self._current_config.get("controls", [])
        if len(controls) <= 1:
            messagebox.showwarning("警告", "至少需要保留一个操作")
            return
        
        controls.pop(self._selected_control_index)
        self._fill_controls_list()
    
    def _record_keys(self):
        """录制按键"""
        keyboard_module = _lazy_import_keyboard()
        if not keyboard_module:
            messagebox.showwarning("警告", "keyboard库未安装，请先安装: pip install keyboard")
            return
        
        self._recording_key = True
        self.control_keys_entry.delete(0, 'end')
        self.control_keys_entry.insert(0, "正在录制，请按下按键...")
        
        def record_thread():
            recorded_keys = []
            start_time = time.time()
            
            while self._recording_key and (time.time() - start_time < 5):
                event = keyboard_module.read_event(suppress=False)
                if event.event_type == 'down' and event.name not in recorded_keys:
                    recorded_keys.append(event.name)
                    self.control_keys_entry.delete(0, 'end')
                    self.control_keys_entry.insert(0, ", ".join(recorded_keys))
            
            self._recording_key = False
            if not recorded_keys:
                self.control_keys_entry.delete(0, 'end')
                self.control_keys_entry.insert(0, "未录制到按键")
        
        threading.Thread(target=record_thread, daemon=True).start()
    
    def _record_window_title(self):
        """录制窗口标题"""
        self.detected_title_var.set("正在检测...")
        
        def detect_thread():
            time.sleep(1)
            title = self._get_active_window_title()
            self.detected_title_var.set(title if title else "未检测到")
            
            if title:
                self.window_title_entry.delete(0, 'end')
                self.window_title_entry.insert(0, title)
        
        threading.Thread(target=detect_thread, daemon=True).start()
    
    def _detect_window_title(self):
        """检测窗口标题"""
        title = self._get_active_window_title()
        self.detected_title_var.set(title if title else "未检测到")
        
        if title:
            for i in range(self.profile_listbox.size()):
                profile_name = self.profile_listbox.get(i)
                profile_path = os.path.join(self._profiles_dir, f"{profile_name}.json")
                
                try:
                    with open(profile_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    
                    trigger = config.get("trigger", {})
                    window_title = trigger.get("window_title", "")
                    match_mode = trigger.get("match_mode", "contains")
                    
                    if window_title:
                        if match_mode == "contains" and window_title.lower() in title.lower():
                            self.profile_listbox.select_set(i)
                            self._on_profile_select(None)
                            messagebox.showinfo("匹配成功", f"检测到窗口: {title}\n已加载配置: {profile_name}")
                            return
                        elif match_mode == "equals" and window_title.lower() == title.lower():
                            self.profile_listbox.select_set(i)
                            self._on_profile_select(None)
                            messagebox.showinfo("匹配成功", f"检测到窗口: {title}\n已加载配置: {profile_name}")
                            return
                except Exception:
                    pass
            
            messagebox.showinfo("结果", f"检测到窗口: {title}\n未找到匹配的配置")
    
    def _get_active_window_title(self):
        """获取活动窗口标题"""
        try:
            if sys.platform == 'win32':
                import win32gui
                return win32gui.GetWindowText(win32gui.GetForegroundWindow())
            elif sys.platform == 'linux':
                import subprocess
                result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                       capture_output=True, text=True)
                return result.stdout.strip()
            elif sys.platform == 'darwin':
                import subprocess
                result = subprocess.run(['osascript', '-e', 'tell application "System Events" to get name of first process whose frontmost is true'],
                                       capture_output=True, text=True)
                return result.stdout.strip()
        except Exception:
            pass
        
        return "无法获取窗口标题"
    
    def _select_health_region(self):
        """选择血条区域"""
        pil_import = _lazy_import_pil()
        if not pil_import:
            messagebox.showwarning("警告", "PIL库未安装，请先安装: pip install pillow")
            return
        
        Image, ImageGrab, ImageTk = pil_import
        
        self.root.iconify()
        
        try:
            screenshot = ImageGrab.grab()
            screenshot.save("/tmp/humanaize_gaming_screenshot.png")
            
            region_window = RegionSelector("/tmp/humanaize_gaming_screenshot.png")
            region = region_window.get_region()
            
            if region:
                img_width, img_height = screenshot.size
                x_pct = (region[0] / img_width) * 100
                y_pct = (region[1] / img_height) * 100
                w_pct = (region[2] / img_width) * 100
                h_pct = (region[3] / img_height) * 100
                
                self.hb_x_spin.delete(0, 'end')
                self.hb_x_spin.insert(0, str(int(x_pct)))
                self.hb_y_spin.delete(0, 'end')
                self.hb_y_spin.insert(0, str(int(y_pct)))
                self.hb_w_spin.delete(0, 'end')
                self.hb_w_spin.insert(0, str(int(w_pct)))
                self.hb_h_spin.delete(0, 'end')
                self.hb_h_spin.insert(0, str(int(h_pct)))
                
                health_region = screenshot.crop((region[0], region[1], region[0]+region[2], region[1]+region[3]))
                avg_color = tuple(int(sum(x) / len(x)) for x in zip(*health_region.getdata()))
                self.hb_color_entry.delete(0, 'end')
                self.hb_color_entry.insert(0, f"{avg_color[0]}, {avg_color[1]}, {avg_color[2]}")
                
                messagebox.showinfo("成功", f"已选择区域:\nX: {int(x_pct)}% Y: {int(y_pct)}%\n宽度: {int(w_pct)}% 高度: {int(h_pct)}%")
        except Exception as e:
            messagebox.showerror("错误", f"截图失败: {str(e)}")
        finally:
            self.root.deiconify()
    
    def _reset_death_methods(self):
        """重置死亡检测方法"""
        self.death_methods["text"].set(1)
        self.death_methods["health_bar"].set(0)
        self.death_methods["scene_change"].set(0)
        self.death_methods["visual_cues"].set(1)
        
        self.text_keywords_text.set_text("\n".join([
            "game over", "gameover", "you died", "you are dead",
            "你死了", "失败", "死亡", "挑战失败", "关卡失败"
        ]))
        
        self.hb_threshold_spin.delete(0, 'end')
        self.hb_threshold_spin.insert(0, "50")
        self.scene_threshold_spin.delete(0, 'end')
        self.scene_threshold_spin.insert(0, "30")
        self.visual_threshold_spin.delete(0, 'end')
        self.visual_threshold_spin.insert(0, "0.7")
    
    def _on_close(self):
        """关闭窗口"""
        if self._recording_key:
            self._recording_key = False
        
        self.root.destroy()


class TextEditor:
    """简单文本编辑器"""
    
    def __init__(self, parent, height=3, width=50, auto_layout=True):
        self.frame = ttk.Frame(parent)
        
        self.text = TextEditor._create_text_widget(self.frame, height, width)
        
        scrollbar = Scrollbar(self.frame, orient='vertical', command=self.text.yview)
        scrollbar.pack(side='right', fill='y')
        self.text.config(yscrollcommand=scrollbar.set)
        
        if auto_layout:
            self.frame.pack(fill='x')
    
    @staticmethod
    def _create_text_widget(parent, height, width):
        try:
            from tkinter import Text
            text_widget = Text(parent, height=height, width=width, font=('Microsoft YaHei', 9))
            text_widget.pack(side='left', fill='x', expand=True)
            return text_widget
        except ImportError:
            from tkinter import Text
            text_widget = Text(parent, height=height, width=width)
            text_widget.pack(side='left', fill='x', expand=True)
            return text_widget
    
    def get_text(self):
        """获取文本内容"""
        return self.text.get('1.0', 'end-1c')
    
    def set_text(self, content):
        """设置文本内容"""
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', content)
    
    def grid(self, **kwargs):
        """网格布局"""
        self.frame.grid(**kwargs)
    
    def pack(self, **kwargs):
        """包布局"""
        self.frame.pack(**kwargs)


class RegionSelector:
    """区域选择器"""
    
    def __init__(self, image_path):
        self.image_path = image_path
        self.region = None
        self.start_x = 0
        self.start_y = 0
        self.current_x = 0
        self.current_y = 0
        self.drawing = False
        
        self._create_window()
    
    def _create_window(self):
        """创建选择窗口"""
        self.window = Toplevel()
        self.window.title("选择区域")
        self.window.attributes('-fullscreen', True)
        self.window.attributes('-topmost', True)
        
        self.canvas = Canvas(self.window, cursor='crosshair', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        
        self.image = Image.open(self.image_path)
        self.photo = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
        
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        
        self.window.bind('<Escape>', lambda e: self._close())
        
        self.window.focus_force()
        self.window.grab_set()
        self.window.wait_window()
    
    def _on_press(self, event):
        """按下鼠标"""
        self.drawing = True
        self.start_x = event.x
        self.start_y = event.y
        self.current_x = event.x
        self.current_y = event.y
    
    def _on_drag(self, event):
        """拖动鼠标"""
        if not self.drawing:
            return
        
        self.current_x = event.x
        self.current_y = event.y
        
        self.canvas.delete('selection')
        
        x1 = min(self.start_x, self.current_x)
        y1 = min(self.start_y, self.current_y)
        x2 = max(self.start_x, self.current_x)
        y2 = max(self.start_y, self.current_y)
        
        self.canvas.create_rectangle(x1, y1, x2, y2, outline='red', width=2, tags='selection')
        self.canvas.create_rectangle(x1-1, y1-1, x2+1, y2+1, outline='white', width=1, tags='selection')
    
    def _on_release(self, event):
        """释放鼠标"""
        if not self.drawing:
            return
        
        self.drawing = False
        
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        
        if x2 > x1 and y2 > y1:
            self.region = (x1, y1, x2 - x1, y2 - y1)
        
        self._close()
    
    def _close(self):
        """关闭窗口"""
        self.window.destroy()
    
    def get_region(self):
        """获取选择的区域"""
        return self.region


def run_gui():
    """运行GUI界面"""
    root = Tk()
    app = GamingConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()