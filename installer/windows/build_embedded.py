"""
Build Humanaize2 using Python Embedded runtime (much faster than PyInstaller)
- Download Python embedded zip
- Extract to dist/x86_64/Humanaize2
- Copy required site-packages from system Python (no pip install needed)
- Copy project source code and resources
- Generate launcher scripts
- Run Inno Setup installer
"""
import os
import sys
import shutil
import zipfile
import subprocess
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(PROJECT_ROOT, "dist", "x86_64", "Humanaize2")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
SYSPACK = r"D:\Users\Allen Wu\AppData\Local\Programs\Python\Python313\Lib\site-packages"
TEMP_DIR = r"D:\Temp"
ARCH = "x86_64"

def load_version():
    with open(os.path.join(PROJECT_ROOT, "config", "version.json")) as f:
        return json.load(f)["version"]

def mkdirp(p):
    os.makedirs(p, exist_ok=True)

def step(msg):
    print(f"\n=== {msg} ===")

def copy_tree_safe(src, dst, filter_dirs=None, filter_exts=None):
    """Copy directory tree, skipping heavy/unnecessary parts."""
    filter_dirs = filter_dirs or set()
    filter_exts = filter_exts or set()
    mkdirp(dst)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        # Skip filtered dirs
        dirs[:] = [d for d in dirs if d not in filter_dirs and not d.startswith("__pycache__")]
        dst_root = os.path.join(dst, rel) if rel != "." else dst
        mkdirp(dst_root)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in filter_exts:
                continue
            s = os.path.join(root, f)
            d = os.path.join(dst_root, f)
            try:
                shutil.copy2(s, d)
            except Exception as e:
                print(f"  WARN skip {s}: {e}")

# ============================================================
# 1. Core packages needed by Humanaize2 (from system site-packages)
# Only minimal set - everything else is excluded
# ============================================================
CORE_PACKAGES = [
    # UI
    "customtkinter",
    "PIL",
    # HTTP / networking
    "requests",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    # WebSocket
    "websockets",
    # System
    "psutil",
    # Logging
    "loguru",
    "win32_setctime",  # loguru dep on windows
    "colorama",         # loguru colorama dep on windows
    # Config / data formats
    "yaml",
    "pydantic",
    "annotated_types",
    "pydantic_core",
    "typing_extensions",
    # Date / time
    "dateutil",
    "pytz",
    "tzdata",
    # Setuptools (for pkg_resources used by some deps)
    "pkg_resources",
    # Audio
    "edge_tts",
    # Serialization
    "ormsgpack",
    # Crypto
    "crypto",
    "Cryptodome",
    "_cffi_backend",  # cffi pyd for crypto
    "cffi",
    "bcrypt",
    # PyYAML tag: yaml tag is lib dir, need to add PyYAML dist-info free
]

# Binary/pyd files needed separately
PYD_FILES = [
    r"psutil\_psutil_windows.pyd",
    r"bcrypt\_bcrypt.pyd",
    r"yaml\_yaml.pyd",
    r"ormsgpack\_ormsgpack.pyd",
    r"pydantic\_migration.cp313-win_amd64.pyd",
    r"pydantic_core\_pydantic_core.cp313-win_amd64.pyd",
    r"PIL\_imaging.cp313-win_amd64.pyd",
    r"PIL\_imagingft.cp313-win_amd64.pyd",
    r"PIL\_imagingmath.cp313-win_amd64.pyd",
    r"PIL\_imagingmorph.cp313-win_amd64.pyd",
    r"Crypto\Cipher\_raw_aes.cp313-win_amd64.pyd",
    r"Crypto\Cipher\_raw_aesni.cp313-win_amd64.pyd",
    r"Crypto\Cipher\_raw_arc4.cp313-win_amd64.pyd",
    r"Crypto\Cipher\_raw_des.cp313-win_amd64.pyd",
    r"Crypto\Cipher\_raw_ecb.cp313-win_amd64.pyd",
    r"Crypto\Cipher\_raw_ocb.cp313-win_amd64.pyd",
    r"Crypto\Util\_cpuid.cp313-win_amd64.pyd",
    r"Crypto\Hash\_ghash_clmul.cp313-win_amd64.pyd",
    r"Crypto\Hash\_sha256.cp313-win_amd64.pyd",
    r"Crypto\Hash\_sha512.cp313-win_amd64.pyd",
    r"Crypto\Hash\_keccak.cp313-win_amd64.pyd",
    r"Crypto\Protocol\_scrypt.cp313-win_amd64.pyd",
    r"Crypto\Math\_modexp.cp313-win_amd64.pyd",
    r"Cryptodome\Cipher\_raw_aes.cp313-win_amd64.pyd",
    r"Cryptodome\Cipher\_raw_aesni.cp313-win_amd64.pyd",
    r"Cryptodome\Cipher\_raw_arc4.cp313-win_amd64.pyd",
    r"Cryptodome\Cipher\_raw_des.cp313-win_amd64.pyd",
    r"Cryptodome\Cipher\_raw_ecb.cp313-win_amd64.pyd",
    r"Cryptodome\Cipher\_raw_ocb.cp313-win_amd64.pyd",
    r"Cryptodome\Util\_cpuid.cp313-win_amd64.pyd",
    r"Cryptodome\Hash\_ghash_clmul.cp313-win_amd64.pyd",
    r"Cryptodome\Hash\_sha256.cp313-win_amd64.pyd",
    r"Cryptodome\Hash\_sha512.cp313-win_amd64.pyd",
    r"Cryptodome\Hash\_keccak.cp313-win_amd64.pyd",
    r"Cryptodome\Protocol\_scrypt.cp313-win_amd64.pyd",
    r"Cryptodome\Math\_modexp.cp313-win_amd64.pyd",
]

def main():
    version = load_version()
    print(f"Humanaize2 v{version} - Embedded Python build for {ARCH}")

    # Clean dist
    if os.path.exists(os.path.dirname(DIST_DIR)):
        shutil.rmtree(os.path.dirname(DIST_DIR))
    mkdirp(DIST_DIR)

    # ----------------------------------------------------------
    # Step 1: Extract Python embedded zip
    # ----------------------------------------------------------
    step("Extracting Python 3.13 Embedded runtime")
    zip_path = os.path.join(TEMP_DIR, "python-embedded.zip")
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Python embed zip not found: {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(DIST_DIR)
    print(f"  Extracted {len(os.listdir(DIST_DIR))} items to {DIST_DIR}")

    # Fix python313._pth: enable site module, add Lib/site-packages
    pth_file = os.path.join(DIST_DIR, "python313._pth")
    os.remove(pth_file)
    with open(pth_file, "w") as f:
        f.write("python313.zip\n.\nLib\nLib\\site-packages\nimport site\n")
    print(f"  Configured: {pth_file}")

    # Create Lib/site-packages directory
    lib_dir = os.path.join(DIST_DIR, "Lib")
    sp_dir = os.path.join(lib_dir, "site-packages")
    mkdirp(lib_dir)
    mkdirp(sp_dir)

    # ----------------------------------------------------------
    # Step 2: Copy Python standard library (Lib folder)
    # Embedded python has stdlib packed in python313.zip
    # BUT tkinter is NOT included there - copy it explicitly
    # Also need ensurepip/venv-less parts
    # ----------------------------------------------------------
    step("Copying standard library components (tkinter, sqlite3, etc.)")
    stdlib_src = r"D:\Users\Allen Wu\AppData\Local\Programs\Python\Python313\Lib"

    # Copy tkinter package (embedded Python excludes GUI components)
    src_tk = os.path.join(stdlib_src, "tkinter")
    dst_tk = os.path.join(lib_dir, "tkinter")
    copy_tree_safe(src_tk, dst_tk, filter_dirs={"test", "__pycache__"})
    print(f"  tkinter copied")

    # Copy tcl/tk dlls - these are needed by tkinter, embedded has them?
    # Actually embedded package doesn't include tcl - check later if needed
    # tkinter dlls are in DLLs dir of system python

    # Also copy idlelib? No. Copy turtle? No. Only tkinter.
    # Copy ensurepip? No, not needed.
    # Copy venv? No.

    # ----------------------------------------------------------
    # Step 3: Copy tkinter DLLs (tcl/tk runtime)
    # ----------------------------------------------------------
    step("Copying Tcl/Tk runtime DLLs (for tkinter)")
    dlls_src = r"D:\Users\Allen Wu\AppData\Local\Programs\Python\Python313\DLLs"
    # tkinter needs:
    tk_dlls = [
        "tcl86t.dll",
        "tk86t.dll",
    ]
    for dll in tk_dlls:
        s = os.path.join(dlls_src, dll)
        d = os.path.join(DIST_DIR, dll)  # Put beside python.exe
        if os.path.exists(s):
            shutil.copy2(s, d)
            print(f"  {dll} copied")
        else:
            print(f"  WARN: {dll} not found at {s}")

    # Also need tcl lib directory
    tcl_lib_src = r"D:\Users\Allen Wu\AppData\Local\Programs\Python\Python313\tcl"
    if os.path.exists(tcl_lib_src):
        tcl_lib_dst = os.path.join(DIST_DIR, "tcl")
        copy_tree_safe(tcl_lib_src, tcl_lib_dst)
        print(f"  tcl lib directory copied")

    # ----------------------------------------------------------
    # Step 4: Copy core site-packages from system Python
    # ----------------------------------------------------------
    step("Copying core site-packages")
    for pkg in CORE_PACKAGES:
        s = os.path.join(SYSPACK, pkg)
        d = os.path.join(sp_dir, pkg)
        if os.path.isdir(s):
            # Skip tests, examples, __pycache__, .pyc etc.
            copy_tree_safe(
                s, d,
                filter_dirs={"tests", "test", "__pycache__", "examples",
                             "doc", "docs", "demo"},
                filter_exts={".pyc", ".pyo"}
            )
            print(f"  {pkg} (dir)")
        elif os.path.isfile(s):
            shutil.copy2(s, d)
            print(f"  {pkg} (file)")
        else:
            print(f"  SKIP: {pkg} not found")

    # Copy standalone pyd files that live inside packages
    for pyd_rel in PYD_FILES:
        s = os.path.join(SYSPACK, pyd_rel)
        d = os.path.join(sp_dir, pyd_rel)
        if os.path.exists(s):
            mkdirp(os.path.dirname(d))
            shutil.copy2(s, d)

    # Also need top-level single-file modules
    for top_mod in ["certifi", "charset_normalizer", "idna"]:
        # Already handled as directories above?
        pass

    # Copy some top-level .py files from site-packages
    for modname in ["six", "pkg_resources", "dateutil", "pytz", "tzdata"]:
        # Actually let's just copy if exist - keep minimal
        s = os.path.join(SYSPACK, modname)
        if os.path.isdir(s):
            d = os.path.join(sp_dir, modname)
            copy_tree_safe(s, d, filter_dirs={"__pycache__", "test", "tests"})
            print(f"  extra: {modname}")

    # ----------------------------------------------------------
    # Step 5: Copy project source code
    # ----------------------------------------------------------
    step("Copying project source code")
    # We embed src/core directly, and also maintain src/ path for imports
    # Actually source code goes as-is to support import paths like:
    #   from core.main import ...
    #   from src.core.main import ... (if we use src in path)

    # Copy src/ directory (all source, but skip large non-essential)
    dst_src = os.path.join(DIST_DIR, "src")
    src_root = os.path.join(PROJECT_ROOT, "src")
    skip_src_dirs = {"__pycache__", "test", "tests", "node_modules", ".git"}
    copy_tree_safe(
        src_root, dst_src,
        filter_dirs=skip_src_dirs,
        filter_exts={".pyc", ".pyo", ".log"}
    )
    print(f"  src/ copied")

    # ----------------------------------------------------------
    # Step 6: Copy project resources (skills, prompt, languages, config)
    # ----------------------------------------------------------
    step("Copying project resources")
    resources = [
        ("skills", "skills"),
        ("prompt", "prompt"),
        ("languages", "languages"),
    ]
    for src_name, dst_name in resources:
        s = os.path.join(PROJECT_ROOT, src_name)
        d = os.path.join(DIST_DIR, dst_name)
        if os.path.exists(s):
            copy_tree_safe(s, d, filter_dirs={"__pycache__"})
            print(f"  {dst_name}/ copied")

    # Copy config/version.json
    s = os.path.join(PROJECT_ROOT, "config", "version.json")
    d = os.path.join(DIST_DIR, "config")
    mkdirp(d)
    shutil.copy2(s, os.path.join(d, "version.json"))
    print(f"  config/version.json copied")

    # Also copy ui/data directory (images etc.)
    s = os.path.join(src_root, "core", "ui", "data")
    if os.path.exists(s):
        d = os.path.join(dst_src, "core", "ui", "data")
        copy_tree_safe(s, d)
        print(f"  src/core/ui/data copied")

    # Copy core/tools directory
    s = os.path.join(src_root, "core", "tools")
    if os.path.exists(s):
        d = os.path.join(dst_src, "core", "tools")
        copy_tree_safe(s, d, filter_dirs={"__pycache__"})
        print(f"  src/core/tools copied")

    # ----------------------------------------------------------
    # Step 7: Generate launcher scripts
    # ----------------------------------------------------------
    step("Generating launcher scripts")

    # Main launcher script (sets PYTHONPATH, then runs pythonw.exe)
    launcher = f'''@echo off
chcp 65001 > nul 2>&1
setlocal
REM Get script directory
set "APP_DIR=%~dp0"
REM Add paths so imports work
set "PYTHONPATH=%APP_DIR%src;%APP_DIR%;%PYTHONPATH%"
REM Launch with pythonw (no console window) -- use python.exe for debug
if "%1"=="" (
    start "" "%APP_DIR%pythonw.exe" -c "from core.windows_main import main; main()" boot -m gui
) else (
    "%APP_DIR%python.exe" -c "from core.windows_main import main; main()" %*
)
endlocal
'''
    launcher_path = os.path.join(DIST_DIR, "Humanaize2.bat")
    with open(launcher_path, "w") as f:
        f.write(launcher)
    print(f"  Humanaize2.bat launcher created")

    # CLI launcher (humanaize2.cmd - ASCII only)
    cli_launcher = '''@echo off
chcp 65001 > nul 2>&1
REM Humanaize 2.0 Agent command launcher
REM Place this script in the same directory as python.exe and pythonw.exe

setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHON=%SCRIPT_DIR%python.exe"
set "PYTHONPATH=%SCRIPT_DIR%src;%SCRIPT_DIR%;%PYTHONPATH%"

if not exist "%PYTHON%" (
    echo [ERROR] python.exe not found at: %PYTHON%
    echo [INFO] Please reinstall Humanaize 2.0 Agent.
    exit /b 1
)

REM Pass all arguments to main entry point: core.windows_main.main()
"%PYTHON%" -c "from core.windows_main import main; main()" %*

endlocal
'''
    cli_path = os.path.join(DIST_DIR, "humanaize2.cmd")
    with open(cli_path, "w") as f:
        f.write(cli_launcher)
    print(f"  humanaize2.cmd CLI created")

    # ----------------------------------------------------------
    # Step 8: Quick sanity test (import check)
    # ----------------------------------------------------------
    step("Sanity test: import check")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{os.path.join(DIST_DIR, 'src')};{DIST_DIR};"
    test_cmds = [
        ("import tkinter", "tkinter import"),
        ("import customtkinter", "customtkinter import"),
        ("import requests", "requests import"),
        ("import psutil", "psutil import"),
        ("import yaml", "yaml import"),
        ("import loguru", "loguru import"),
        ("from core.windows_main import main", "entry import"),
    ]
    py_exe = os.path.join(DIST_DIR, "python.exe")
    passed = 0
    for code, label in test_cmds:
        r = subprocess.run(
            [py_exe, "-c", code],
            env=env, capture_output=True, text=True, timeout=60
        )
        status = "PASS" if r.returncode == 0 else "FAIL"
        if r.returncode != 0:
            print(f"  [{status}] {label}: {r.stderr[:200]}")
        else:
            print(f"  [{status}] {label}")
            passed += 1
    print(f"  {passed}/{len(test_cmds)} checks passed")

    # ----------------------------------------------------------
    # Step 9: Copy to installer_output directory
    # ----------------------------------------------------------
    step("Copying to installer_output")
    inst_out = os.path.join(PROJECT_ROOT, "installer_output", ARCH)
    if os.path.exists(inst_out):
        shutil.rmtree(inst_out)
    mkdirp(inst_out)

    # Copy entire Humanaize2 directory
    dst_hr = os.path.join(inst_out, "Humanaize2")
    copy_tree_safe(DIST_DIR, dst_hr)

    # Also copy humanaize2.cmd for ISS file (ISS copies separately but we ensure present)
    shutil.copy2(cli_path, os.path.join(inst_out, "humanaize2.cmd"))

    dir_size = sum(os.path.getsize(os.path.join(dp, f))
                   for dp, dn, fn in os.walk(dst_hr) for f in fn) / (1024*1024)
    print(f"  installer_output/{ARCH}/Humanaize2: {dir_size:.1f} MB")

    # ----------------------------------------------------------
    # Step 10: Run Inno Setup installer
    # ----------------------------------------------------------
    step("Building Inno Setup installer")
    iss_file = os.path.join(PROJECT_ROOT, "installer", "windows", f"humanaize2-{ARCH}.iss")
    if not os.path.exists(iss_file):
        iss_file = os.path.join(PROJECT_ROOT, "installer", "windows", "humanaize2.iss")

    # Find ISCC
    iscc_candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
    ]
    iscc = None
    for c in iscc_candidates:
        if os.path.exists(c):
            iscc = c; break
    if not iscc:
        try:
            r = subprocess.run(["iscc", "/?"], capture_output=True, timeout=5)
            if r.returncode == 0:
                iscc = "iscc"
        except Exception:
            pass

    if not iscc:
        print("  SKIP: Inno Setup not found. Install from https://jrsoftware.org/isdl.php")
    else:
        tag = f"v{version}"
        r = subprocess.run(
            [
                iscc,
                f"/DAppVersion={version}",
                f"/DReleaseTag={tag}",
                f"/Oinstaller\\windows\\output",
                iss_file,
            ],
            cwd=os.path.join(PROJECT_ROOT, "installer", "windows"),
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode == 0:
            print("  [OK] Inno Setup built")
            # Copy installer to installer_output
            out_d = os.path.join(PROJECT_ROOT, "installer", "windows", "output")
            for fn in os.listdir(out_d):
                if fn.endswith(".exe"):
                    src = os.path.join(out_d, fn)
                    dst = os.path.join(inst_out, fn)
                    shutil.copy2(src, dst)
                    mb = os.path.getsize(dst) / (1024*1024)
                    print(f"  Installer: {dst} ({mb:.1f} MB)")
        else:
            print(f"  [FAIL] Inno Setup exit {r.returncode}")
            if r.stdout: print("  STDOUT:", r.stdout[:500])
            if r.stderr: print("  STDERR:", r.stderr[:500])

    print("\n=== BUILD COMPLETE ===")
    print(f"Version: {version}")
    print(f"Runtime dir: {dst_hr}")
    print(f"Installer output: {inst_out}")

if __name__ == "__main__":
    main()
