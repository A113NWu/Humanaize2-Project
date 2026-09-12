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

REM Switch to the install directory so the onefile runtime extracts
REM (and the app writes data/logs) next to the installation, regardless
REM of the caller's current directory.
cd /d "%SCRIPT_DIR%"

REM Pass all arguments to the main program.
REM The exe is built as a GUI-subsystem app, so a bare invocation returns to
REM the prompt immediately and the CLI would lose the console. With args
REM (boot -m cli / settings / solve ...) use `start /wait` so the program
REM attaches to THIS window and cmd waits for it to exit; no-arg dashboard
REM launch stays non-blocking.
if "%~1"=="" (
    "%EXE_PATH%"
) else (
    start "Humanaize2" /b /wait "%EXE_PATH%" %*
)

endlocal
