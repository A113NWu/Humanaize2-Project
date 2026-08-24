"""
Humanaize v2.0 - Windows 专用启动入口
默认启动现代化 GUI 界面
"""

import sys
import os

# PyInstaller --windowed 模式下 sys.stdout/stderr 可能为 None，需要修复
# 否则 loguru 等库尝试添加 sys.stdout 作为 sink 时会报 TypeError
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# 添加 src 和 core 目录到 Python 路径
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, src_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Windows 专用主入口 - 直接启动现代化 GUI"""
    # 检查并启动 LLM 服务器
    from main import _check_and_start_server
    _check_and_start_server()
    
    # 后台检查更新
    from main import _check_updates_background
    _check_updates_background()
    
    import warnings
    warnings.filterwarnings("ignore")
    
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
    
    try:
        import tensorflow as tf
        tf.get_logger().setLevel('ERROR')
    except:
        pass
    
    # 启动 Windows 现代化 GUI
    from ui.windows_gui import ModernWindowsUI
    import customtkinter as ctk
    
    # 设置主题
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk()
    app = ModernWindowsUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()