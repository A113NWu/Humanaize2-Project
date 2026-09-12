#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Humanaize 2.0 Agent executables for Windows and Linux

Usage:
    python build_exe.py                    # Build current platform (default)
    python build_exe.py x86_64             # Build x86_64
    python build_exe.py arm64              # Build ARM64
    python build_exe.py all                # Build all architectures
    python build_exe.py --zip              # Also create portable zip
    python build_exe.py --installer        # Also create Inno Setup installer
    python build_exe.py --skip-installer   # Skip Inno Setup (requires Windows)
"""

import os
import sys
import subprocess
import shutil
import json
import platform

# Platform-specific path separator for PyInstaller --add-data
DATA_SEP = ";" if sys.platform == "win32" else ":"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_version():
    """Get version from config/version.json"""
    version_file = os.path.join(PROJECT_ROOT, "config", "version.json")
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("version", "2.2.7")
    except Exception:
            return "2.2.7"


def get_release_tag(version: str = None) -> str:
    """返回统一的 Release 标签命名格式：vX.X.X"""
    v = version or get_version()
    v = v.strip()
    if v.startswith("v"):
        return v
    return f"v{v}"


def get_main_script():
    """Determine the correct entry script based on platform"""
    if IS_WINDOWS:
        win_main = os.path.join(PROJECT_ROOT, "src", "core", "windows_main.py")
        if os.path.exists(win_main):
            return "src/core/windows_main.py"
    return "src/core/main.py"


def build_exe(arch="x86_64", create_zip=False, create_installer=False, onefile=False):
    """Build executable for specified architecture"""
    app_name = "Humanaize2"
    version = get_version()
    tag = get_release_tag(version)
    main_script = get_main_script()
    output_dir = os.path.join(PROJECT_ROOT, "dist", arch)
    build_dir = os.path.join(PROJECT_ROOT, "build", arch)

    print("=" * 60)
    print(f"  Humanaize 2.0 {tag} - Building for {arch}")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print(f"  Release tag: {tag}")
    print("=" * 60)

    # Validate key files exist
    icon_path = os.path.join(PROJECT_ROOT, "icon", "humanaize2.png")
    main_script_path = os.path.join(PROJECT_ROOT, main_script)

    print(f"\n[CHECK] Entry script: {main_script_path}")
    if not os.path.exists(main_script_path):
        print(f"  [ERROR] Entry script not found: {main_script_path}")
        sys.exit(1)
    print("  [OK] Found")

    # Check PyInstaller
    try:
        result = subprocess.run(["pyinstaller", "--version"], capture_output=True, text=True)
        print(f"[CHECK] PyInstaller: {result.stdout.strip()}")
    except FileNotFoundError:
        print("[ERROR] PyInstaller not found. Install with: pip install pyinstaller")
        sys.exit(1)

    # Clean the output and onefile analysis cache. Stale TOC entries can keep
    # unrelated DLL/PYD files in the archive after an exclude is added.
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        print(f"[CLEAN] Removed previous output: {output_dir}")
    if onefile and os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        print(f"[CLEAN] Removed onefile analysis cache: {build_dir}")

    # Build PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", app_name,
        "--onefile" if onefile else "--onedir",
        "--noconfirm",
        # Note: 不使用 --clean，让 PyInstaller 复用缓存加速构建
        "--distpath", output_dir,
        "--workpath", build_dir,
        "--paths", os.path.join(PROJECT_ROOT, "src", "core"),
        # Data files
        "--add-data", f"src/core/ui/data{DATA_SEP}src/core/ui/data",
        "--add-data", f"src/core/web{DATA_SEP}web",
        "--add-data", f"prompt{DATA_SEP}prompt",
        "--add-data", f"languages{DATA_SEP}languages",
        "--add-data", f"config/version.json{DATA_SEP}config",
        # Hidden imports
        "--hidden-import", "customtkinter",
        "--hidden-import", "websockets",
        "--hidden-import", "websockets.asyncio.server",
        "--hidden-import", "websockets.asyncio.client",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.messagebox",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "sqlmodel",
        "--hidden-import", "sqlmodel.main",
        "--hidden-import", "pydantic",
        "--hidden-import", "pydantic_core",
        "--hidden-import", "sqlalchemy",
        "--hidden-import", "sqlalchemy.ext.asyncio",
        "--hidden-import", "sqlalchemy.orm",
        "--hidden-import", "requests",
        "--hidden-import", "apscheduler",
        "--hidden-import", "apscheduler.schedulers",
        "--hidden-import", "apscheduler.schedulers.asyncio",
        "--hidden-import", "apscheduler.triggers",
        "--hidden-import", "apscheduler.triggers.interval",
        "--hidden-import", "aiohttp",
        "--hidden-import", "aiohttp.connector",
        "--hidden-import", "aiohttp.web",
        "--collect-submodules", "aiohttp",
        "--hidden-import", "logging",
        "--hidden-import", "json",
        "--hidden-import", "threading",
        "--hidden-import", "queue",
        "--hidden-import", "socket",
        "--hidden-import", "asyncio",
        "--hidden-import", "tools",
        "--hidden-import", "tools.logger",
        # Runtime features import tools.* lazily (updates, notifications,
        # solve/guard modes, IoT and GAN). Collect the package as a unit so
        # onefile builds do not fail on the first optional code path used.
        "--collect-submodules", "tools",
        "--hidden-import", "core.tools",
        "--collect-submodules", "core.tools",
        "--hidden-import", "core.llm",
        "--collect-submodules", "core.llm",
        "--hidden-import", "core.memory",
        "--collect-submodules", "core.memory",
        "--hidden-import", "core.Prompt",
        "--collect-submodules", "core.Prompt",
        "--hidden-import", "core.data",
        "--collect-submodules", "core.data",
        # Exclude heavy unneeded modules (transitive deps not used by core app)
        "--exclude-module", "transformers",
        "--exclude-module", "torch",
        "--exclude-module", "tensorflow",
        "--exclude-module", "scipy",
        "--exclude-module", "cv2",
        "--exclude-module", "onnxruntime",
        "--exclude-module", "grpc",
        "--exclude-module", "datasets",
        "--exclude-module", "jieba",
        "--exclude-module", "Crypto",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "numpy",
        "--exclude-module", "sympy",
        "--exclude-module", "werkzeug",
        "--exclude-module", "flask",
        "--exclude-module", "django",
        "--exclude-module", "rest_framework",
        "--exclude-module", "wx",
        "--exclude-module", "PyQt5",
        "--exclude-module", "PyQt6",
        "--exclude-module", "PySide2",
        "--exclude-module", "PySide6",
        # Additional excludes: astrbot 引入的重型依赖，Humanaize 核心不需要
        "--exclude-module", "pygame",
        "--exclude-module", "psycopg2",
        "--exclude-module", "pyarrow",
        "--exclude-module", "faiss",
        "--exclude-module", "lxml",
        "--exclude-module", "lz4",
        "--exclude-module", "pydub",
        "--exclude-module", "aiofiles",
        "--exclude-module", "dashscope",
        "--exclude-module", "openai",
        "--exclude-module", "anthropic",
        "--exclude-module", "google.generativeai",
        "--exclude-module", "tiktoken",
        "--exclude-module", "chromadb",
        "--exclude-module", "pymilvus",
        "--exclude-module", "qdrant",
        "--exclude-module", "sklearn",
        "--exclude-module", "xgboost",
        "--exclude-module", "lightgbm",
        "--exclude-module", "pyspark",
        "--exclude-module", "selenium",
        "--exclude-module", "playwright",
        "--exclude-module", "docker",
        "--exclude-module", "kubernetes",
        # pywin32 related (causes hook errors, not needed by core app)
        "--exclude-module", "pywintypes",
        "--exclude-module", "pywin32",
        "--exclude-module", "win32com",
        "--exclude-module", "win32api",
        # More heavy/unnecessary modules
        "--exclude-module", "uvicorn",
        "--exclude-module", "anyio",
        "--exclude-module", "bcrypt",
        "--exclude-module", "jsonschema",
        "--exclude-module", "pygments",
        "--exclude-module", "dateutil",
        "--exclude-module", "pytz",
        "--exclude-module", "openpyxl",
        "--exclude-module", "ormsgpack",
        "--exclude-module", "jinja2",
        "--exclude-module", "cryptography",
        "--exclude-module", "speech_recognition",
        "--exclude-module", "tensorflow",
        "--exclude-module", "keras",
        "--exclude-module", "tensorboard",
        "--exclude-module", "setuptools",
        "--exclude-module", "pkg_resources",
        # Not used by the Windows core; excluding these prevents their native
        # DLL/PYD payloads from entering the onefile extraction archive.
        "--exclude-module", "Cython",
        "--exclude-module", "cython",
        # Optional packages that pull unrelated native DLL/PYD files into
        # the onefile archive through ctypes/import scanning.
        "--exclude-module", "pysilk",
        "--exclude-module", "fontTools",
        "--exclude-module", "fonttools",
        "--exclude-module", "jedi",
        "--exclude-module", "IPython",
        "--exclude-module", "jupyter",
        "--exclude-module", "notebook",
        "--exclude-module", "qtpy",
        "--exclude-module", "pyromark",
        "--exclude-module", "python_ripgrep",
        # The QQ/AstrBot integration is intentionally not part of the core
        # Windows app; excluding its ecosystem prevents unrelated native
        # extensions and JDK runtime DLLs from being auto-collected.
        "--exclude-module", "astrbot",
        "--exclude-module", "mcp",
        "--exclude-module", "markitdown",
        "--exclude-module", "google.genai",
        "--exclude-module", "pypdf",
        "--exclude-module", "discord",
        "--exclude-module", "telegram",
        "--exclude-module", "lark_oapi",
        "--exclude-module", "quart",
        "--exclude-module", "hypercorn",
        "--exclude-module", "faiss",
        "--exclude-module", "faiss_cpu",
        "--exclude-module", "PySide6",
        "--exclude-module", "PySide2",
        "--exclude-module", "shiboken6",
    ]

    if onefile:
        cmd.extend([
            "--add-data", f"llama{DATA_SEP}llama",
            # Use a stable per-application extraction directory. This avoids
            # onefile temp-folder races and antivirus locks on native files.
            "--runtime-tmpdir", ".humanaize2_runtime",
        ])

    # Platform-specific options
    if IS_WINDOWS:
        icon_ico = os.path.join(PROJECT_ROOT, "installer", "windows", "icon.ico")
        if os.path.exists(icon_ico):
            cmd.extend(["--icon", icon_ico])
        cmd.append("--windowed")
    elif IS_LINUX:
        cmd.append("--nowindowed")

    cmd.append(main_script)

    # Do not let a user's global PYTHONPATH inject removed integrations or
    # unrelated native extensions into the packaged application.
    build_env = os.environ.copy()
    build_env.pop("PYTHONPATH", None)
    build_env.pop("PYTHONHOME", None)
    # PyInstaller inherits interpreter search paths, including stale .pth or
    # IDE-added paths. Remove deleted integrations before starting analysis.
    build_env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "src")
    build_env["PYTHONNOUSERSITE"] = "1"
    path_entries = build_env.get("PATH", "").split(os.pathsep)
    build_env["PATH"] = os.pathsep.join(
        entry for entry in path_entries
        if not any(token in entry.lower() for token in ("java", "jdk", "eclipse", "adoptium"))
    )

    print(f"\n[BUILD] Running PyInstaller...")
    print(f"  Command: pyinstaller {' '.join(cmd[6:12])} ...")

    log_file = os.path.join(PROJECT_ROOT, f"build_log_{arch}.txt")
    disabled_pth_files = []
    site_packages = os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages")
    if os.path.isdir(site_packages):
        for pth_name in os.listdir(site_packages):
            if not pth_name.lower().endswith(".pth"):
                continue
            pth_path = os.path.join(site_packages, pth_name)
            try:
                with open(pth_path, "r", encoding="utf-8", errors="ignore") as handle:
                    pth_contents = handle.read().lower()
                if any(token in pth_contents for token in ("qq-chat", "astrbot")):
                    disabled_path = pth_path + ".build-disabled"
                    os.replace(pth_path, disabled_path)
                    disabled_pth_files.append((pth_path, disabled_path))
                    print(f"[CLEAN] Temporarily disabled stale path file: {pth_name}")
            except OSError:
                pass
    try:
        with open(log_file, 'w') as log_f:
            log_f.write(f"Building {app_name} v{version} for {arch}\n")
            log_f.write(f"Platform: {platform.system()} {platform.machine()}\n")
            log_f.write(f"Command: {' '.join(cmd)}\n\n")
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                env=build_env,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                timeout=5400
            )

        if result.returncode != 0:
            print(f"\n[ERROR] PyInstaller failed (exit code: {result.returncode})")
            print(f"  Full log: {log_file}")
            print(f"  Last 30 lines of log:")
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-30:]:
                    print(f"    | {line.rstrip()}")
            sys.exit(1)

    except subprocess.TimeoutExpired:
        print(f"\n[ERROR] PyInstaller timed out (90 minutes)")
        print(f"  Full log: {log_file}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Build failed: {e}")
        print(f"  Full log: {log_file}")
        sys.exit(1)
    finally:
        for original_path, disabled_path in disabled_pth_files:
            try:
                os.replace(disabled_path, original_path)
            except OSError:
                print(f"[WARN] Could not restore path file: {original_path}")

    print(f"  [OK] PyInstaller completed (log: {log_file})")

    # Fail early if optional native payloads leak into a onefile build.
    if onefile:
        analysis_dir = os.path.join(build_dir, app_name)
        analysis_files = [
            os.path.join(analysis_dir, "Analysis-00.toc"),
            os.path.join(analysis_dir, "PKG-00.toc"),
        ]
        forbidden_payloads = ("Code.cp313-win_amd64.pyd", "runtime_bootstrap.py")
        leaked_payloads = []
        for analysis_file in analysis_files:
            if not os.path.exists(analysis_file):
                continue
            with open(analysis_file, "r", encoding="utf-8", errors="replace") as handle:
                contents = handle.read().lower()
            leaked_payloads.extend(
                payload for payload in forbidden_payloads
                if payload.lower() in contents and payload not in leaked_payloads
            )
        if leaked_payloads:
            print(f"\n[ERROR] Unwanted native payloads found: {', '.join(leaked_payloads)}")
            print("  Remove the source package or update the exclude list before distributing.")
            sys.exit(1)
        print("  [OK] Native payload audit passed")

    # Verify output (--onedir 模式: dist/x86_64/Humanaize2/Humanaize2.exe)
    if IS_WINDOWS:
        exe_name = f"{app_name}.exe"
    else:
        exe_name = app_name

    onedir_path = os.path.join(output_dir, app_name)
    exe_path = os.path.join(output_dir, exe_name) if onefile else os.path.join(onedir_path, exe_name)
    if not os.path.exists(exe_path) and not onefile:
        # fallback: 检查 output_dir 根目录
        exe_path = os.path.join(output_dir, exe_name)
        onedir_path = output_dir
    if not os.path.exists(exe_path):
        print(f"\n[ERROR] Executable not found: {exe_path}")
        print(f"  Full log: {log_file}")
        print(f"  Contents of {output_dir}:")
        for f in os.listdir(output_dir) if os.path.exists(output_dir) else []:
            print(f"    - {f}")
        sys.exit(1)

    exe_size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"\n[SUCCESS] Executable built:")
    print(f"  Path: {exe_path}")
    print(f"  Size: {exe_size_mb:.2f} MB")

    installer_output_dir = os.path.join(PROJECT_ROOT, "installer_output", arch)
    os.makedirs(installer_output_dir, exist_ok=True)
    if onefile:
        dst_path = os.path.join(installer_output_dir, exe_name)
        shutil.copy2(exe_path, dst_path)
        print(f"[COPY] Copied to installer_output: {dst_path}")
    else:
        dst_dir = os.path.join(installer_output_dir, app_name)
        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.copytree(onedir_path, dst_dir)
        print(f"[COPY] Copied to installer_output: {dst_dir}")

    # Create portable zip
    if create_zip:
        _create_portable_zip(arch, version, exe_path, output_dir)

    # Create Inno Setup installer (Windows only)
    if create_installer and IS_WINDOWS:
        _create_installer(arch, version, exe_path, output_dir)

    return exe_path


def _create_portable_zip(arch, version, exe_path, output_dir):
    """Create a portable zip archive"""
    import zipfile

    zip_dir = os.path.join(PROJECT_ROOT, "installer_output", arch)
    os.makedirs(zip_dir, exist_ok=True)
    zip_name = f"Humanaize2-{version}-{arch}-portable.zip"
    zip_path = os.path.join(zip_dir, zip_name)

    print(f"\n[ZIP] Creating portable archive: {zip_name}")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add executable
        zf.write(exe_path, f"Humanaize2/{os.path.basename(exe_path)}")

        # Add launcher scripts
        bat_content = f"""@echo off
chcp 65001 > nul
title Humanaize 2.0 Agent
"%~dp0Humanaize2.exe" %*
pause
"""
        zf.writestr("Humanaize2/humanaize2.bat", bat_content)

        # Add skills
        skills_dir = os.path.join(PROJECT_ROOT, "skills")
        if os.path.exists(skills_dir):
            for root, dirs, files in os.walk(skills_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    arc_name = "Humanaize2/skills/" + os.path.relpath(full_path, skills_dir)
                    zf.write(full_path, arc_name)

        # Add config
        config_dir = os.path.join(PROJECT_ROOT, "config")
        if os.path.exists(config_dir):
            for f in os.listdir(config_dir):
                full_path = os.path.join(config_dir, f)
                if os.path.isfile(full_path):
                    zf.write(full_path, f"Humanaize2/config/{f}")

        # Add README
        readme_content = f"""Humanaize 2.0 Agent v{version} - Portable Version

Getting Started:
1. Extract this zip to any folder
2. Double-click humanaize2.bat or Humanaize2.exe
3. The AI will start automatically

Features:
- Modern AI companion with personality
- IoT compute network support
- Multi-language support
- Autonomous AI agent
- Skill system for extensibility

Visit: https://github.com/A113NWu/Humanaize2-Project
"""
        zf.writestr("Humanaize2/README.txt", readme_content)

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  [OK] Created: {zip_path}")
    print(f"  Size: {zip_size_mb:.2f} MB")


def _create_installer(arch, version, exe_path, output_dir):
    """Create Inno Setup installer (Windows only)"""
    # 常见 Inno Setup 安装路径
    iscc_candidates = [
        "iscc",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
        r"C:\Users\Allen Wu\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 5\ISCC.exe"),
    ]
    iscc_path = None
    for cand in iscc_candidates:
        try:
            if cand == "iscc":
                result = subprocess.run([cand, "/?"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    iscc_path = cand
                    break
            elif os.path.exists(cand):
                iscc_path = cand
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if not iscc_path:
        print(f"\n[SKIP] Inno Setup not found. Download from: https://jrsoftware.org/isdl.php")
        print(f"       Skipping installer creation. Portable zip is available instead.")
        return

    print(f"\n[INSTALLER] Inno Setup found: {iscc_path}")

    iss_file = os.path.join(PROJECT_ROOT, "installer", "windows", f"humanaize2-{arch}.iss")
    if not os.path.exists(iss_file):
        iss_file = os.path.join(PROJECT_ROOT, "installer", "windows", "humanaize2.iss")

    print(f"[INSTALLER] Using ISS file: {iss_file}")

    # 带版本号的输出文件名
    tag = get_release_tag(version)
    # Use an absolute /O path: a relative one is resolved against the ISCC
    # working directory and would nest installer\windows twice.
    installer_output_path = os.path.join(PROJECT_ROOT, "installer", "windows", "output")
    try:
        result = subprocess.run(
            [
                iscc_path,
                f"/DAppVersion={version}",
                f"/DReleaseTag={tag}",
                f"/O{installer_output_path}",
                iss_file,
            ],
            cwd=os.path.join(PROJECT_ROOT, "installer", "windows"),
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode == 0:
            print(f"  [OK] Inno Setup built successfully")
            # 查找输出文件并拷贝到 installer_output
            output_dir_installer = os.path.join(PROJECT_ROOT, "installer", "windows", "output")
            if os.path.exists(output_dir_installer):
                for f in os.listdir(output_dir_installer):
                    if f.endswith(".exe"):
                        src = os.path.join(output_dir_installer, f)
                        dest_dir = os.path.join(PROJECT_ROOT, "installer_output", arch)
                        os.makedirs(dest_dir, exist_ok=True)
                        # 重命名输出为规范命名：Humanaize2-Setup-x86_64-vX.X.X.exe
                        # ISS 默认已用 OutputBaseFilename=Humanaize2-Setup-x86_64-v2.2.6
                        dest = os.path.join(dest_dir, f)
                        shutil.copy2(src, dest)
                        inst_size = os.path.getsize(dest) / (1024 * 1024)
                        print(f"  Installer: {dest} ({inst_size:.2f} MB)")
        else:
            print(f"  [WARN] Inno Setup returned non-zero: {result.returncode}")
            if result.stdout:
                print(f"  STDOUT: {result.stdout[-800:]}")
            if result.stderr:
                print(f"  STDERR: {result.stderr[-800:]}")
    except Exception as e:
        print(f"  [WARN] Installer creation failed: {e}")


def build_all(create_zip=False, create_installer=False, onefile=False):
    """Build all architectures"""
    architectures = ["x86_64", "arm64"]
    for arch in architectures:
        print(f"\n{'='*60}")
        print(f"  Building {arch} version...")
        print(f"{'='*60}")
        build_exe(arch, create_zip=create_zip, create_installer=create_installer, onefile=onefile)


if __name__ == "__main__":
    arch = "x86_64"
    create_zip = False
    create_installer = False
    onefile = False

    for arg in sys.argv[1:]:
        if arg == "--zip":
            create_zip = True
        elif arg == "--installer":
            create_installer = True
        elif arg == "--skip-installer":
            create_installer = False
        elif arg == "--onefile":
            onefile = True
        elif arg in ("all", "x86_64", "arm64"):
            arch = arg
        else:
            print(f"Unknown argument: {arg}")
            print(f"Usage: python build_exe.py [x86_64|arm64|all] [--zip] [--installer] [--skip-installer] [--onefile]")
            sys.exit(1)

    if arch == "all":
        build_all(create_zip=create_zip, create_installer=create_installer, onefile=onefile)
    else:
        build_exe(arch, create_zip=create_zip, create_installer=create_installer, onefile=onefile)
