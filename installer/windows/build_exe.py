#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Humanaize 2.0 Agent as a single executable for Windows
Supports x86_64 and ARM64 architectures
"""

import os
import sys
import subprocess
import shutil

def build_exe(arch="x86_64"):
    """
    Build executable for specified architecture
    
    Args:
        arch: Target architecture ("x86_64" or "arm64")
    """
    # Configuration
    app_name = "Humanaize2"
    version = "2.1.0"
    main_script = "src/core/main.py"
    
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
        "--add-data", "src/ui/ascii.txt;src/ui/",
        "--add-data", "src/config/*.py;src/config/",
        "--add-data", "src/core/*.py;src/core/",
        "--add-data", "src/ui/*.py;src/ui/",
        "--add-data", "src/llm/*.py;src/llm/",
        "--add-data", "src/memory/*.py;src/memory/",
        "--add-data", "src/tools/*.py;src/tools/",
        "--add-data", "src/utils/*.py;src/utils/",
        "--add-data", "skills/*;skills/",
        "--add-data", "version.json;. ",
        "--add-data", "requirements.txt;. ",
        "--hidden-import", "customtkinter",
        "--hidden-import", "requests",
        "--hidden-import", "nltk",
        "--hidden-import", "transformers",
        "--hidden-import", "torch",
        "--distpath", output_dir,
        "--workpath", f"build/{arch}",
        main_script
    ]
    
    print("Building executable with PyInstaller...")
    print("Command:", " ".join(cmd))
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build succeeded!")
        print("Output:", result.stdout)
        
        # Create installer directory
        installer_dir = f"installer_output/{arch}"
        if not os.path.exists(installer_dir):
            os.makedirs(installer_dir)
        
        # Copy exe to installer directory with architecture suffix
        exe_path = os.path.join(output_dir, app_name + ".exe")
        if os.path.exists(exe_path):
            dest_exe = f"{app_name}-{arch}.exe"
            shutil.copy(exe_path, os.path.join(installer_dir, dest_exe))
            print(f"Executable copied to {installer_dir}/{dest_exe}")
        else:
            print(f"Error: Executable not found at {exe_path}")
            
    except subprocess.CalledProcessError as e:
        print("Build failed!")
        print("Error:", e.stderr)
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