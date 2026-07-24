@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ==============================================
echo  Aize Companion - Android APK Build
echo  Humanaize 2.0 Agent
echo ==============================================
echo.

:: Check Java
java -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Java is not installed or not in PATH.
    echo         Please install JDK 17+ from: https://adoptium.net/
    pause
    exit /b 1
)

for /f "tokens=3" %%v in ('java -version 2^>^&1 ^| findstr /i "version"') do (
    set "JAVA_VERSION=%%~v"
)
echo [INFO] Java version: %JAVA_VERSION%

:: Check Android SDK
if not defined ANDROID_HOME (
    if exist "%LOCALAPPDATA%\Android\Sdk" (
        set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
    ) else if exist "C:\Android\Sdk" (
        set "ANDROID_HOME=C:\Android\Sdk"
    )
)
echo [INFO] ANDROID_HOME: %ANDROID_HOME%

if not exist "%ANDROID_HOME%\platform-tools\adb.exe" (
    echo [ERROR] Android SDK not found. Please set ANDROID_HOME or install Android Studio.
    echo         Download: https://developer.android.com/studio
    pause
    exit /b 1
)

:: Generate Gradle wrapper if not exists
if not exist "gradlew.bat" (
    echo [INFO] Generating Gradle wrapper...
    gradle wrapper --gradle-version 8.5 2>nul
    if %errorlevel% neq 0 (
        echo [WARNING] Could not generate Gradle wrapper. Using gradle directly.
    )
)

set "BUILD_TYPE=%~1"
if "%BUILD_TYPE%"=="" set "BUILD_TYPE=debug"
if "%BUILD_TYPE%"=="all" (
    call :build_apk debug
    call :build_apk release
    goto :eof
)

if "%BUILD_TYPE%"=="debug" (
    echo.
    echo [BUILD] Building debug APK...
    call gradlew.bat assembleDebug
    set "APK_PATH=app\build\outputs\apk\debug\app-debug.apk"
) else if "%BUILD_TYPE%"=="release" (
    echo.
    echo [BUILD] Building release APK...
    call gradlew.bat assembleRelease
    set "APK_PATH=app\build\outputs\apk\release\app-release.apk"
) else (
    echo [ERROR] Unknown build type: %BUILD_TYPE%
    echo         Usage: build_apk.bat [debug^|release^|all]
    echo         Default: debug
    pause
    exit /b 1
)

if exist "%APK_PATH%" (
    for %%F in ("%APK_PATH%") do set "APK_SIZE=%%~zF"
    set /a "APK_SIZE_MB=!APK_SIZE! / 1048576"
    echo.
    echo ==============================================
    echo  Build successful!
    echo ==============================================
    echo  APK: %cd%\%APK_PATH%
    echo  Size: !APK_SIZE_MB! MB
    echo.
    echo  Install on device:
    echo    adb install "%cd%\%APK_PATH%"
) else (
    echo [ERROR] Build failed. Check the output above for details.
    pause
    exit /b 1
)

goto :eof

:build_apk
set "BUILD_TYPE=%~1"
echo.
echo [BUILD] Building %BUILD_TYPE% APK...
call gradlew.bat assemble%BUILD_TYPE%
set "APK_PATH=app\build\outputs\apk\%BUILD_TYPE%\app-%BUILD_TYPE%.apk"
if exist "%APK_PATH%" (
    for %%F in ("%APK_PATH%") do set "APK_SIZE=%%~zF"
    set /a "APK_SIZE_MB=!APK_SIZE! / 1048576"
    echo [OK] %BUILD_TYPE% APK: %cd%\%APK_PATH% (!APK_SIZE_MB! MB^)
) else (
    echo [WARN] %BUILD_TYPE% APK build failed
)
goto :eof
