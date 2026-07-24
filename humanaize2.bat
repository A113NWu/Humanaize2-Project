@echo off
chcp 65001 > nul 2>&1
title Humanaize 2.0 Agent

set "SCRIPT_DIR=%~dp0"

if exist "%SCRIPT_DIR%src" (
    echo [INFO] Running from source code directory
    set "MAIN_DIR=%SCRIPT_DIR%"
) else (
    echo [INFO] Running from installed location
    set "MAIN_DIR=C:\Program Files\Humanaize2"
)

set "PYTHONPATH=%MAIN_DIR%;%MAIN_DIR%src;%MAIN_DIR%src\core;%PYTHONPATH%"
set "PYTHONUNBUFFERED=1"

set "MODEL_DIR=%MAIN_DIR%models"
set "MODEL_FILE=%MODEL_DIR%\tinyllama.gguf"
set "MODEL_URL=https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

set "LLAMA_DIR=%MAIN_DIR%llama"
set "LLAMA_SERVER_FILE=%LLAMA_DIR%\llama-server.exe"
set "LLAMA_SERVER_URL=https://github.com/ggml-org/llama.cpp/releases/download/b7075/llama-b7075-bin-win-cpu-x64.zip"
set "LLAMA_ZIP_FILE=%LLAMA_DIR%\llama-server.zip"

goto :main

:download_model
echo [INFO] Downloading TinyLlama model...
if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"
if exist "%MODEL_FILE%" (
    echo [INFO] Model file already exists at %MODEL_FILE%
    for %%A in ("%MODEL_FILE%") do echo [INFO] File size: %%~zA bytes
    set /p REDOWNLOAD="Do you want to re-download it? (y/N): "
    if /i not "%REDOWNLOAD%"=="y" (
        echo [INFO] Using existing model file.
        goto :EOF
    )
)
echo [INFO] Downloading model from Hugging Face...
powershell -Command "(New-Object System.Net.WebClient).DownloadFile('%MODEL_URL%', '%MODEL_FILE%')"
set "FILESIZE=0"
if exist "%MODEL_FILE%" (
    for %%A in ("%MODEL_FILE%") do set "FILESIZE=%%~zA"
)
if %FILESIZE% gtr 0 (
    echo [SUCCESS] Model downloaded successfully to %MODEL_FILE%
    echo [INFO] Model size: %FILESIZE% bytes
) else (
    echo [ERROR] Downloaded file is empty or corrupted.
    if exist "%MODEL_FILE%" del "%MODEL_FILE%"
    echo [ERROR] Please check your internet connection and try again.
    pause
    exit /b 1
)
goto :EOF

:download_server
echo [INFO] Downloading llama-server...
if not exist "%LLAMA_DIR%" mkdir "%LLAMA_DIR%"
if exist "%LLAMA_SERVER_FILE%" (
    echo [INFO] llama-server already exists at %LLAMA_SERVER_FILE%
    for %%A in ("%LLAMA_SERVER_FILE%") do echo [INFO] File size: %%~zA bytes
    set /p REDOWNLOAD="Do you want to re-download it? (y/N): "
    if /i not "%REDOWNLOAD%"=="y" (
        echo [INFO] Using existing llama-server.
        goto :EOF
    )
)
echo [INFO] Downloading llama-server from GitHub...
powershell -Command "(New-Object System.Net.WebClient).DownloadFile('%LLAMA_SERVER_URL%', '%LLAMA_ZIP_FILE%')"
set "FILESIZE=0"
if exist "%LLAMA_ZIP_FILE%" (
    for %%A in ("%LLAMA_ZIP_FILE%") do set "FILESIZE=%%~zA"
)
if %FILESIZE% gtr 0 (
    echo [INFO] Extracting llama-server...
    powershell -Command "Expand-Archive -Path '%LLAMA_ZIP_FILE%' -DestinationPath '%LLAMA_DIR%' -Force"
    del "%LLAMA_ZIP_FILE%"
    set "SERVERSIZE=0"
    if exist "%LLAMA_SERVER_FILE%" (
        for %%A in ("%LLAMA_SERVER_FILE%") do set "SERVERSIZE=%%~zA"
        echo [SUCCESS] llama-server downloaded and extracted successfully
        if %SERVERSIZE% gtr 0 (
            echo [INFO] File size: %SERVERSIZE% bytes
        )
    ) else (
        echo [INFO] Looking for llama-server.exe in subdirectories...
        for /r "%LLAMA_DIR%" %%F in (llama-server.exe) do (
            copy "%%F" "%LLAMA_SERVER_FILE%" >nul 2>&1
            if errorlevel 0 (
                set "SERVERSIZE=1"
                echo [SUCCESS] Found and copied llama-server.exe to %LLAMA_SERVER_FILE%
                goto :server_found
            )
        )
        :server_found
        if %SERVERSIZE% equ 0 (
            echo [ERROR] llama-server.exe not found in extracted archive
            echo [ERROR] Please download manually from https://github.com/ggml-org/llama.cpp/releases
            pause
            exit /b 1
        )
    )
) else (
    echo [ERROR] Failed to download llama-server.
    if exist "%LLAMA_ZIP_FILE%" del "%LLAMA_ZIP_FILE%"
    echo [ERROR] Please download manually from https://github.com/ggml-org/llama.cpp/releases
    pause
    exit /b 1
)
goto :EOF

:main
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher from: https://www.python.org/downloads/
    pause
    exit /b 1
)

if /i "%~1"=="download-model" (
    call :download_model
    pause
    exit /b 0
)

if /i "%~1"=="download-server" (
    call :download_server
    pause
    exit /b 0
)

if not exist "%MAIN_DIR%src\core\main.py" (
    echo [ERROR] main.py not found. Please reinstall Humanaize 2.0.
    pause
    exit /b 1
)

echo [INFO] Starting Humanaize 2.0...
python -u "%MAIN_DIR%src\core\main.py" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Humanaize 2.0 encountered an error.
    pause
)