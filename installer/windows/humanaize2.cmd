@echo off
chcp 65001 > nul 2>&1
REM Humanaize 2.0 Agent command launcher
REM This script must be placed in the same directory as Humanaize2.exe

setlocal
set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%Humanaize2.exe"

if not exist "%EXE_PATH%" (
    echo [ERROR] Humanaize2.exe not found at: %EXE_PATH%
    echo [INFO] Please reinstall Humanaize 2.0 Agent.
    exit /b 1
)

REM Pass all arguments to the main program
"%EXE_PATH%" %*

endlocal
