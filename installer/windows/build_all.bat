@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ==============================================
echo Humanaize 2.0 Agent - Windows Build Script
echo ==============================================
echo.

:: Create output directories
mkdir installer_output 2>nul
mkdir installer_output\x86_64 2>nul
mkdir installer_output\arm64 2>nul
mkdir output 2>nul

:: Step 1: Create icon
echo [Step 1/5] Creating icon...
python create_icon.py
if %errorlevel% neq 0 (
    echo [WARNING] Failed to create icon, using default
)

:: Step 2: Check pyinstaller
echo.
echo [Step 2/5] Checking PyInstaller...
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

:: Step 3: Build executables for all architectures
echo.
echo [Step 3/5] Building executables for x86_64 and ARM64...
cd ..\..
python installer/windows/build_exe.py all
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build executables.
    pause
    exit /b 1
)

:: Step 4: Build installers
echo.
echo [Step 4/5] Building installers...
cd installer\windows

:: Check Inno Setup
iscc /? >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Inno Setup is not installed.
    echo Download from: https://jrsoftware.org/isdl.php
    echo Skipping installer creation...
    echo.
    echo ==============================================
    echo Build completed (partial)!
    echo ==============================================
    echo.
    echo Executables:
    echo   x86_64: ..\..\dist\x86_64\Humanaize2.exe
    echo   ARM64: ..\..\dist\arm64\Humanaize2.exe
    echo Installers: Not built (requires Inno Setup)
    echo.
    pause
    exit /b 0
)

:: Build x86_64 installer
echo Building x86_64 installer...
iscc humanaize2-x86_64.iss
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build x86_64 installer.
    pause
    exit /b 1
)

:: Build ARM64 installer
echo Building ARM64 installer...
iscc humanaize2-arm64.iss
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build ARM64 installer.
    pause
    exit /b 1
)

:: Step 5: Copy installers to output directory
echo.
echo [Step 5/5] Copying installers...
copy output\Humanaize2-Setup-x86_64.exe ..\..\installer_output\ 2>nul
copy output\Humanaize2-Setup-arm64.exe ..\..\installer_output\ 2>nul

echo.
echo ==============================================
echo Build completed successfully!
echo ==============================================
echo.
echo Output files:
echo.
echo Executables:
echo   x86_64: ..\..\dist\x86_64\Humanaize2.exe
echo   ARM64: ..\..\dist\arm64\Humanaize2.exe
echo.
echo Installers:
echo   x86_64: ..\..\installer_output\Humanaize2-Setup-x86_64.exe
echo   ARM64: ..\..\installer_output\Humanaize2-Setup-arm64.exe
echo.
pause