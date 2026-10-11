@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo   Aize Minecraft 机器人启动器
echo ==========================================
echo.
echo 默认连接本机专用服务器 127.0.0.1:22565（config.json）
echo 若要改连「对局域网开放」的房间，请输入该端口号
echo.
set /p PORT=输入端口（直接回车用默认 22565）:
if "%PORT%"=="" (
  node bot.js
) else (
  node bot.js --port %PORT%
)
pause
