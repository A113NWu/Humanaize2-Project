@echo off
chcp 65001 > nul 2>&1
title Humanaize 2.0 Agent

REM Model configuration
set "MODEL_DIR=%~dp0models"
set "MODEL_FILE=%MODEL_DIR%\tinyllama.gguf"
set "MODEL_URL=https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

REM Function to download TinyLlama model
:download_model
echo [INFO] Downloading TinyLlama model...
if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"
if exist "%MODEL_FILE%" (
    echo [INFO] Model file already exists at %MODEL_FILE%
    set /p REDOWNLOAD="Do you want to re-download it? (y/N): "
    if /i not "%REDOWNLOAD%"=="y" (
        echo [INFO] Using existing model file.
        goto :EOF
    )
)
echo [INFO] Downloading model from Hugging Face...
powershell -Command "Invoke-WebRequest -Uri '%MODEL_URL%' -OutFile '%MODEL_FILE%' -ProgressPreference SilentlyContinue"
if exist "%MODEL_FILE%" (
    echo [SUCCESS] Model downloaded successfully to %MODEL_FILE%
    for %%A in ("%MODEL_FILE%") do echo [INFO] Model size: %%~zA bytes
) else (
    echo [ERROR] Failed to download model.
    pause
    exit /b 1
)
goto :EOF

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Set PYTHONPATH to project root
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

REM Check for download-model command
if /i "%~1"=="download-model" (
    call :download_model
    pause
    exit /b 0
)

REM Check if main.py exists
if not exist "%~dp0src\core\main.py" (
    echo [ERROR] main.py not found. Please reinstall Humanaize 2.0.
    pause
    exit /b 1
)

REM Run main.py with all arguments
python "%~dp0src\core\main.py" %*

REM Keep window open if error occurred
if errorlevel 1 (
    echo.
    echo [ERROR] Humanaize 2.0 encountered an error.
    pause
)