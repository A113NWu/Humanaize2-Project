#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Humanaize 2.0 Build Script
Supports building on Linux and Windows

Usage:
    python build.py [platform]
    
    platform: linux | windows | all
    (default: linux on Linux, windows on Windows)
"""

import os
import sys
import subprocess
import shutil

PYINSTALLER_PATH = os.path.expanduser("~/.local/bin/pyinstaller")

def get_platform():
    """Get current platform"""
    if sys.platform.startswith('win'):
        return 'windows'
    elif sys.platform.startswith('linux'):
        return 'linux'
    else:
        return 'linux'

def build_linux():
    """Build Linux executable"""
    print("Building Linux version...")
    
    app_name = "Humanaize2"
    main_script = "src/core/main.py"
    
    # Clean previous builds
    for dir_name in ['dist/linux', 'build/linux']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    cmd = [
        PYINSTALLER_PATH,
        "--name", app_name,
        "--onefile",
        "--windowed",
        "--icon=installer/windows/icon.ico",
        "--add-data", "src/core/ui/ascii.txt:src/core/ui/",
        "--add-data", "src/core/config/*.py:src/core/config/",
        "--add-data", "src/core/*.py:src/core/",
        "--add-data", "src/core/ui/*.py:src/core/ui/",
        "--add-data", "src/core/llm/*.py:src/core/llm/",
        "--add-data", "src/core/memory/*.py:src/core/memory/",
        "--add-data", "src/core/tools/*.py:src/core/tools/",
        "--add-data", "src/core/utils/*.py:src/core/utils/",
        "--add-data", "src/core/Prompt/*.py:src/core/Prompt/",
        "--add-data", "src/core/data/*.py:src/core/data/",
        "--add-data", "src/core/data/prompts/*.txt:src/core/data/prompts/",
        "--add-data", "src/ai_selfdevelop:src/ai_selfdevelop/",
        "--add-data", "skills/*:skills/",
        "--add-data", "prompt/*:prompt/",
        "--add-data", "config/version.json:config/",
        "--hidden-import", "customtkinter",
        "--hidden-import", "requests",
        "--hidden-import", "nltk",
        "--hidden-import", "transformers",
        "--hidden-import", "torch",
        "--hidden-import", "PIL",
        "--distpath", "dist/linux",
        "--workpath", "build/linux",
        main_script
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Linux build completed successfully!")
        print(f"Output: dist/linux/{app_name}")
        return True
    except subprocess.CalledProcessError as e:
        print("✗ Linux build failed!")
        print("Error:", e.stderr[:1000])
        return False

def build_windows():
    """Build Windows executable"""
    print("Building Windows version...")
    
    app_name = "Humanaize2"
    main_script = "src/core/main.py"
    
    # Clean previous builds
    for dir_name in ['dist/windows', 'build/windows']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    cmd = [
        PYINSTALLER_PATH,
        "--name", app_name,
        "--onefile",
        "--windowed",
        "--icon=installer/windows/icon.ico",
        "--add-data", "src/core/ui/ascii.txt;src/core/ui/",
        "--add-data", "src/core/config/*.py;src/core/config/",
        "--add-data", "src/core/*.py;src/core/",
        "--add-data", "src/core/ui/*.py;src/core/ui/",
        "--add-data", "src/core/llm/*.py;src/core/llm/",
        "--add-data", "src/core/memory/*.py;src/core/memory/",
        "--add-data", "src/core/tools/*.py;src/core/tools/",
        "--add-data", "src/core/utils/*.py;src/core/utils/",
        "--add-data", "src/core/Prompt/*.py;src/core/Prompt/",
        "--add-data", "src/core/data/*.py;src/core/data/",
        "--add-data", "src/core/data/prompts/*.txt;src/core/data/prompts/",
        "--add-data", "src/ai_selfdevelop;src/ai_selfdevelop/",
        "--add-data", "skills/*;skills/",
        "--add-data", "prompt/*;prompt/",
        "--add-data", "config/version.json;config/",
        "--hidden-import", "customtkinter",
        "--hidden-import", "requests",
        "--hidden-import", "nltk",
        "--hidden-import", "transformers",
        "--hidden-import", "torch",
        "--hidden-import", "PIL",
        "--distpath", "dist/windows",
        "--workpath", "build/windows",
        main_script
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Windows build completed successfully!")
        print(f"Output: dist/windows/{app_name}.exe")
        return True
    except subprocess.CalledProcessError as e:
        print("✗ Windows build failed!")
        print("Error:", e.stderr[:1000])
        return False

def main():
    # Parse arguments
    target_platform = sys.argv[1] if len(sys.argv) > 1 else get_platform()
    
    print("=" * 60)
    print("Humanaize 2.0 Build Script")
    print("=" * 60)
    print(f"Target Platform: {target_platform}")
    print("=" * 60)
    
    success = False
    
    if target_platform == 'linux' or target_platform == 'all':
        success = build_linux()
    
    if target_platform == 'windows' or target_platform == 'all':
        if get_platform() != 'windows':
            print("\n⚠️  Warning: Building Windows version on non-Windows platform")
            print("  This requires cross-compilation or Wine with Windows Python")
            print("  For best results, run this script on Windows")
        
        success = success or build_windows()
    
    print("\n" + "=" * 60)
    if success:
        print("Build completed successfully!")
    else:
        print("Build failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()