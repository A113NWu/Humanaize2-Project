@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo   Aize Minecraft 机器人启动器
echo ==========================================
echo.
echo 请先在游戏里：ESC -^> 对局域网开放 -^> 记下端口号
echo.
set /p PORT=输入局域网世界端口（直接回车用 config.json 里的 %~1 默认）:
if "%PORT%"=="" (
  node bot.js
) else (
  node bot.js --port %PORT%
)
pause
