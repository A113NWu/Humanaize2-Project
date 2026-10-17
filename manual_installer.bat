@echo off
echo ========================================
echo    Humanaize2 v2.3.12 安装程序
echo ========================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [✓] 检测到管理员权限
) else (
    echo [!] 警告：建议以管理员身份运行此脚本
    echo.
)

:: 设置默认安装路径
set INSTALL_DIR=%PROGRAMFILES%\Humanaize2-x64
set CURRENT_DIR=%~dp0

echo.
echo 安装信息：
echo   - 安装目录: %INSTALL_DIR%
echo   - 源文件: %CURRENT_DIR%
echo.
echo 正在安装 Humanaize2...
echo.

:: 创建安装目录
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    echo [✓] 创建安装目录: %INSTALL_DIR%
)

:: 复制主程序
if exist "%CURRENT_DIR%installer_output\x86_64\Humanaize2.exe" (
    copy "%CURRENT_DIR%installer_output\x86_64\Humanaize2.exe" "%INSTALL_DIR%\"
    echo [✓] 复制主程序
) else (
    echo [!] 错误：未找到主程序文件
    pause
    exit /b 1
)

:: 复制数据目录
echo 正在复制数据目录...
xcopy "%CURRENT_DIR%config" "%INSTALL_DIR%\config\" /E /I /H /Y >nul 2>&1
xcopy "%CURRENT_DIR%prompt" "%INSTALL_DIR%\prompt\" /E /I /H /Y >nul 2>&1
xcopy "%CURRENT_DIR%languages" "%INSTALL_DIR%\languages\" /E /I /H /Y >nul 2>&1
xcopy "%CURRENT_DIR%Assets" "%INSTALL_DIR%\Assets\" /E /I /H /Y >nul 2>&1
xcopy "%CURRENT_DIR%llama" "%INSTALL_DIR%\llama\" /E /I /H /Y >nul 2>&1

echo [✓] 复制数据目录

:: 创建启动脚本
echo 正在创建启动脚本...

:: 创建 CLI 启动脚本
echo @echo off > "%INSTALL_DIR%\humanaize2.cmd"
echo echo 启动 Humanaize2 CLI 模式... >> "%INSTALL_DIR%\humanaize2.cmd"
echo cd /d "%INSTALL_DIR%" >> "%INSTALL_DIR%\humanaize2.cmd"
echo start "" "Humanaize2.exe" boot -m cli >> "%INSTALL_DIR%\humanaize2.cmd"

echo [✓] 创建启动脚本

:: 创建桌面快捷方式
echo 正在创建快捷方式...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\Humanaize2.lnk'); $s.TargetPath = '%INSTALL_DIR%\Humanaize2.exe'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'Humanaize2 AI Assistant'; $s.Save()"
echo [✓] 创建桌面快捷方式

:: 添加到 PATH (可选)
set ADD_TO_PATH=N
echo.
set /p ADD_TO_PATH="是否添加到 PATH 环境变量? (y/N): "
if /i "%ADD_TO_PATH%"=="y" (
    echo 正在添加到 PATH...
    setx PATH "%PATH%;%INSTALL_DIR%"
    echo [✓] 添加到 PATH 完成 (需要重启命令行生效)
) else (
    echo [✓] 跳过 PATH 设置
)

:: 创建卸载脚本
echo @echo off > "%INSTALL_DIR%\uninstall.bat"
echo echo 正在卸载 Humanaize2... >> "%INSTALL_DIR%\uninstall.bat"
echo echo 请确认删除目录 "%INSTALL_DIR%" >> "%INSTALL_DIR%\uninstall.bat"
echo pause >> "%INSTALL_DIR%\uninstall.bat"
echo rmdir /s /q "%INSTALL_DIR%" >> "%INSTALL_DIR%\uninstall.bat"
echo echo 卸载完成 >> "%INSTALL_DIR%\uninstall.bat"

echo.
echo ========================================
echo    安装完成！
echo ========================================
echo.
echo 启动方式：
echo   - 双击 Humanaize2.exe 启动图形界面
echo   - 双击 humanaize2.cmd 启动 CLI 模式
echo   - 桌面快捷方式
echo.
echo 卸载方式：
echo   - 运行 %INSTALL_DIR%\uninstall.bat
echo.
echo 配置文件位置：%INSTALL_DIR%\config\
echo.
echo 按任意键退出...
pause >nul