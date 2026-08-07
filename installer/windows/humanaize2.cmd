@echo off
chcp 65001 > nul 2>&1
REM Humanaize 2.0 Agent command launcher
REM 此脚本应放在与 Humanaize2-x86_64.exe 同一目录，由安装包部署

setlocal
set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%Humanaize2-x86_64.exe"

if not exist "%EXE_PATH%" (
    echo [ERROR] Humanaize2-x86_64.exe not found at: %EXE_PATH%
    echo [INFO] Please reinstall Humanaize 2.0 Agent.
    exit /b 1
)

REM 傳遞所有參數到主程式
"%EXE_PATH%" %*

endlocal
