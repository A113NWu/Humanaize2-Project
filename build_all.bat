@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ==============================================
echo  Humanaize 2.0 Agent - Universal Build
echo  Windows Packaging Script
echo ==============================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Please install Python 3.8+ from: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Parse arguments
set "TARGET=%~1"
set "SKIP_INSTALLER="

if /i "%TARGET%"=="--skip-installer" (
    set "SKIP_INSTALLER=--skip-installer"
    set "TARGET=%~2"
)

if "%TARGET%"=="" set "TARGET=windows"

echo [INFO] Target: %TARGET%
echo [INFO] Skip installer: %SKIP_INSTALLER%
echo.

:: Ensure output directories exist
if not exist "installer_output" mkdir "installer_output"
if not exist "dist" mkdir "dist"

:: Run the unified build script
python build_all.py %TARGET% %SKIP_INSTALLER%

if %errorlevel% neq 0 (
    echo.
    echo [WARN] Some builds may have failed.
) else (
    echo.
    echo [OK] Build completed successfully!
)

echo.
echo Output directories:
echo   Executables:    dist\
echo   Installers:     installer_output\
echo   Android APKs:   android_client\app\build\outputs\apk\
echo   Linux packages: installer\linux\output\
echo.

pause
