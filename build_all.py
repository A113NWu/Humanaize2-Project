#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Humanaize 2.0 - Unified Build Entry Point

Builds installation packages for all supported platforms:
  - Windows:  PyInstaller exe + portable zip + Inno Setup installer
  - Linux:    .deb package + AppImage + portable tarball
  - Android:  debug APK + release APK

Usage:
    python build_all.py                      # Build current platform
    python build_all.py windows              # Build Windows packages
    python build_all.py linux                # Build Linux packages
    python build_all.py android              # Build Android APK
    python build_all.py all                  # Build all platforms
    python build_all.py --output-dir DIR     # Specify output directory
    python build_all.py --skip-installer     # Skip installers (faster)
"""

import os
import sys
import json
import subprocess
import platform
import shutil

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
VERSION_FILE = os.path.join(PROJECT_ROOT, "config", "version.json")


def get_version():
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("version", "2.2.7")
    except Exception:
        return "2.2.7"


def get_release_tag(version: str = None) -> str:
    """返回统一的 Release 标签命名格式：vX.X.X"""
    v = version or get_version()
    v = v.strip()
    if v.startswith("v"):
        return v
    return f"v{v}"


def print_header():
    version = get_version()
    tag = get_release_tag(version)
    print()
    print("=" * 70)
    print(f"  Humanaize 2.0 Agent {tag} - Universal Build")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print(f"  Python:   {sys.version.split()[0]}")
    print(f"  Project:  {PROJECT_ROOT}")
    print(f"  Release:  https://github.com/A113NWu/Humanaize2-Project/releases/tag/{tag}")
    print("=" * 70)
    print()


def print_section(title):
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}")


def run_command(cmd, cwd=None, timeout=None):
    """Run a command and return success status"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            print(f"  [WARN] Command returned {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:300]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] Command timed out")
        return False
    except FileNotFoundError:
        print(f"  [ERROR] Command not found: {cmd[0]}")
        return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def build_windows(skip_installer=False):
    """Build Windows packages"""
    print_section("Building Windows Packages")

    build_script = os.path.join(PROJECT_ROOT, "installer", "windows", "build_exe.py")
    if not os.path.exists(build_script):
        print("  [ERROR] Windows build script not found")
        return False

    # Build exe with zip
    zip_flag = "--zip"
    installer_flag = ""
    if not skip_installer:
        installer_flag = "--installer"

    success = run_command(
        [sys.executable, build_script, "x86_64", zip_flag] +
        ([installer_flag] if installer_flag else []),
        timeout=600
    )

    if success:
        print("  [OK] x86_64 Windows build completed")
    else:
        print("  [ERROR] x86_64 Windows build failed")

    # List outputs
    output_dirs = [
        os.path.join(PROJECT_ROOT, "dist", "x86_64"),
        os.path.join(PROJECT_ROOT, "installer_output", "x86_64"),
    ]
    for d in output_dirs:
        if os.path.exists(d):
            print(f"\n  Outputs in {d}:")
            for f in os.listdir(d):
                fpath = os.path.join(d, f)
                size_mb = os.path.getsize(fpath) / (1024 * 1024) if os.path.isfile(fpath) else 0
                print(f"    - {f} ({size_mb:.1f} MB)")

    return success


def build_linux():
    """Build Linux packages"""
    print_section("Building Linux Packages")

    build_scripts = [
        ("Debian Package", os.path.join(PROJECT_ROOT, "installer", "linux", "build_deb.sh")),
        ("AppImage", os.path.join(PROJECT_ROOT, "installer", "linux", "build_appimage.sh")),
        ("Portable Tarball", os.path.join(PROJECT_ROOT, "installer", "linux", "build_tarball.sh")),
    ]

    results = {}
    for name, script in build_scripts:
        if not os.path.exists(script):
            print(f"\n  [SKIP] {name} script not found: {script}")
            results[name] = False
            continue

        print(f"\n  Building {name}...")
        success = run_command(["bash", script], timeout=300)
        results[name] = success
        if success:
            print(f"  [OK] {name} built successfully")
        else:
            print(f"  [WARN] {name} build failed")

    # List outputs
    output_dir = os.path.join(PROJECT_ROOT, "installer", "linux", "output")
    if os.path.exists(output_dir):
        print(f"\n  Outputs in {output_dir}:")
        for f in os.listdir(output_dir):
            fpath = os.path.join(output_dir, f)
            if os.path.isfile(fpath):
                size_mb = os.path.getsize(fpath) / (1024 * 1024)
                print(f"    - {f} ({size_mb:.1f} MB)")

    return all(results.values())


def _check_android_sdk():
    """Check if Android SDK is available"""
    android_dir = os.path.join(PROJECT_ROOT, "android_client")
    
    # Check Java
    java_ok = False
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            java_ok = True
            print(f"  [OK] Java found")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    if not java_ok:
        print("  [ERROR] Java not found. Please install JDK 17+")
        print("          Download: https://adoptium.net/")
        return False
    
    # Check Android SDK
    sdk_path = os.environ.get("ANDROID_HOME", "")
    if not sdk_path:
        sdk_path = os.environ.get("ANDROID_SDK_ROOT", "")
    if not sdk_path and sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(local_app_data, "Android", "Sdk"),
            r"C:\Android\Sdk",
        ]
        for c in candidates:
            if os.path.exists(os.path.join(c, "platform-tools", "adb.exe")):
                sdk_path = c
                break
    
    if not sdk_path or not os.path.exists(os.path.join(sdk_path, "platform-tools")):
        print("  [WARN] Android SDK not found. Please set ANDROID_HOME or install Android Studio")
        print("          Download: https://developer.android.com/studio")
        print("          Building may fail without SDK.")
        return False
    
    print(f"  [OK] Android SDK found: {sdk_path}")
    
    # Create local.properties
    local_props = os.path.join(android_dir, "local.properties")
    with open(local_props, 'w', encoding='utf-8') as f:
        if sys.platform == "win32":
            sdk_path_escaped = sdk_path.replace("\\", "\\\\")
        else:
            sdk_path_escaped = sdk_path
        f.write(f"sdk.dir={sdk_path_escaped}\n")
    print(f"  [OK] Created local.properties")
    
    return True


def build_android():
    """Build Android APK"""
    print_section("Building Android APK")

    android_dir = os.path.join(PROJECT_ROOT, "android_client")
    
    # Check prerequisites
    if not _check_android_sdk():
        print("  [WARN] Prerequisites missing. Attempting build anyway...")
    
    # Determine gradle executable
    if sys.platform == "win32":
        gradle_cmd = os.path.join(android_dir, "gradlew.bat")
    else:
        gradle_cmd = os.path.join(android_dir, "gradlew")
    
    if not os.path.exists(gradle_cmd):
        print(f"  [ERROR] Gradle wrapper not found: {gradle_cmd}")
        return False
    
    if sys.platform != "win32":
        os.chmod(gradle_cmd, 0o755)
    
    # Verify gradle wrapper jar
    wrapper_jar = os.path.join(android_dir, "gradle", "wrapper", "gradle-wrapper.jar")
    if not os.path.exists(wrapper_jar):
        print(f"  [ERROR] gradle-wrapper.jar not found: {wrapper_jar}")
        print("          Run: python android_client/setup_gradle_wrapper.py")
        return False
    
    # Build debug APK
    print(f"\n  Building debug APK...")
    debug_success = run_command(
        [gradle_cmd, "assembleDebug"],
        cwd=android_dir,
        timeout=600
    )
    if debug_success:
        print("  [OK] Debug APK built")
    else:
        print("  [WARN] Debug APK build failed")
    
    # Build release APK
    print(f"\n  Building release APK...")
    release_success = run_command(
        [gradle_cmd, "assembleRelease"],
        cwd=android_dir,
        timeout=600
    )
    if release_success:
        print("  [OK] Release APK built")
    else:
        print("  [WARN] Release APK build failed")
    
    # List outputs
    apk_dir = os.path.join(android_dir, "app", "build", "outputs", "apk")
    if os.path.exists(apk_dir):
        print(f"\n  Output APKs:")
        for root, dirs, files in os.walk(apk_dir):
            for f in files:
                if f.endswith(".apk"):
                    fpath = os.path.join(root, f)
                    size_mb = os.path.getsize(fpath) / (1024 * 1024)
                    print(f"    - {fpath} ({size_mb:.1f} MB)")
    
    return debug_success or release_success


def build_current_platform(skip_installer=False):
    """Build for the current platform"""
    system = platform.system()
    if system == "Windows":
        return build_windows(skip_installer)
    elif system == "Linux":
        return build_linux()
    elif system == "Darwin":
        print("  [INFO] macOS detected. Building Linux packages as fallback.")
        return build_linux()
    else:
        print(f"  [ERROR] Unsupported platform: {system}")
        return False


def main():
    print_header()

    targets = []
    skip_installer = False
    output_dir = None

    args = sys.argv[1:]

    for arg in args:
        if arg in ("windows", "win", "w"):
            targets.append("windows")
        elif arg in ("linux", "l"):
            targets.append("linux")
        elif arg in ("android", "apk", "a"):
            targets.append("android")
        elif arg == "all":
            targets = ["windows", "linux", "android"]
        elif arg == "--skip-installer":
            skip_installer = True
        elif arg == "--output-dir":
            continue  # handled next
        elif arg.startswith("--output-dir="):
            output_dir = arg.split("=", 1)[1]
        elif arg in ("--help", "-h", "help"):
            print(__doc__)
            return
        else:
            print(f"  [ERROR] Unknown argument: {arg}")
            print(__doc__)
            sys.exit(1)

    if not targets:
        targets = ["current"]

    results = {}

    for target in targets:
        if target == "current":
            results["current"] = build_current_platform(skip_installer)
        elif target == "windows":
            results["windows"] = build_windows(skip_installer)
        elif target == "linux":
            results["linux"] = build_linux()
        elif target == "android":
            results["android"] = build_android()

    # Print summary
    print(f"\n{'='*70}")
    print("  Build Summary")
    print(f"{'='*70}")
    for target, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {target}")

    all_passed = all(results.values())
    if all_passed:
        print(f"\n  All builds completed successfully!")
    else:
        print(f"\n  Some builds failed. Check the output above for details.")

    print(f"\n{'='*70}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
