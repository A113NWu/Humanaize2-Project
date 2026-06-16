#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Humanaize 2.0 Agent as a single executable
Supports Windows (x86_64, ARM64) and Linux

Usage:
    python build_exe.py           # Build x86_64 (default)
    python build_exe.py x86_64    # Build x86_64
    python build_exe.py arm64     # Build ARM64
    python build_exe.py all       # Build all architectures
"""

import os
import sys
import subprocess
import shutil

# 使用平台特定的路径分隔符
DATA_SEP = ";" if sys.platform == "win32" else ":"

def build_exe(arch="x86_64"):
    """
    Build executable for specified architecture
    
    Args:
        arch: Target architecture ("x86_64" or "arm64")
    """
    # Configuration
    app_name = "Humanaize2"
    version = "2.2.0"
    # Windows 专用入口脚本，默认启动现代化 GUI
    main_script = "src/core/windows_main.py"
    
    # Output directory based on architecture
    output_dir = f"dist/{arch}"
    
    # Clean previous builds
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    # PyInstaller command with architecture-specific options
    cmd = [
        "pyinstaller",
        "--name", app_name,
        "--onefile",
        "--windowed",
        "--icon=icon.ico",
        # 添加数据文件
        "--add-data", f"src/ui/ascii.txt{DATA_SEP}src/ui/",
        "--add-data", f"src/config/*.py{DATA_SEP}src/config/",
        "--add-data", f"src/core/*.py{DATA_SEP}src/core/",
        "--add-data", f"src/ui/*.py{DATA_SEP}src/ui/",
        "--add-data", f"src/llm/*.py{DATA_SEP}src/llm/",
        "--add-data", f"src/memory/*.py{DATA_SEP}src/memory/",
        "--add-data", f"src/tools/*.py{DATA_SEP}src/tools/",
        "--add-data", f"src/utils/*.py{DATA_SEP}src/utils/",
        "--add-data", f"src/ai_selfdevelop{DATA_SEP}src/ai_selfdevelop/",
        "--add-data", f"skills/*{DATA_SEP}skills/",
        "--add-data", f"config/version.json{DATA_SEP}config/",
        "--add-data", f"requirements.txt{DATA_SEP}.",
        # Hidden imports
        "--hidden-import", "customtkinter",
        "--hidden-import", "requests",
        "--hidden-import", "nltk",
        "--hidden-import", "transformers",
        "--hidden-import", "torch",
        "--hidden-import", "PIL",
        "--hidden-import", "ctypes",
        "--hidden-import", "json",
        "--hidden-import", "threading",
        "--hidden-import", "queue",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.messagebox",
        "--hidden-import", "tkinter.filedialog",
        # Output options
        "--distpath", output_dir,
        "--workpath", f"build/{arch}",
        # Windows GUI mode by default
        "--add-binary", f"icon.ico{DATA_SEP}.",
        main_script
    ]
    
    print("=" * 50)
    print(f"Building Humanaize 2.0 v{version} for {arch}")
    print("=" * 50)
    print("\nPyInstaller command:", " ".join(cmd[:8]) + " ...")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("\n✓ Build succeeded!")
        
        # Create installer directory
        installer_dir = f"installer_output/{arch}"
        if not os.path.exists(installer_dir):
            os.makedirs(installer_dir)
        
        # Copy exe to installer directory with architecture suffix
        exe_path = os.path.join(output_dir, app_name + ".exe")
        if os.path.exists(exe_path):
            dest_exe = f"{app_name}-{arch}.exe"
            shutil.copy(exe_path, os.path.join(installer_dir, dest_exe))
            print(f"✓ Executable copied to {installer_dir}/{dest_exe}")
            print(f"  Size: {os.path.getsize(exe_path) / 1024 / 1024:.2f} MB")
        else:
            print(f"✗ Error: Executable not found at {exe_path}")
            
    except subprocess.CalledProcessError as e:
        print("\n✗ Build failed!")
        if e.stderr:
            print("Error:", e.stderr[:500])
        sys.exit(1)
    except FileNotFoundError:
        print("\n✗ Error: pyinstaller not found.")
        print("  Please install pyinstaller: pip install pyinstaller")
        sys.exit(1)

def build_all():
    """Build executables for all supported architectures"""
    architectures = ["x86_64", "arm64"]
    
    for arch in architectures:
        print(f"\n=== Building {arch} version ===")
        build_exe(arch)
        print(f"=== {arch} build completed ===\n")

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            build_all()
        elif sys.argv[1] in ["x86_64", "arm64"]:
            build_exe(sys.argv[1])
        else:
            print(f"Unknown architecture: {sys.argv[1]}")
            print("Supported architectures: x86_64, arm64")
            print("Use 'all' to build both")
            sys.exit(1)
    else:
        # Default to x86_64
        build_exe("x86_64")