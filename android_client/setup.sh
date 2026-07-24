#!/bin/bash
#
# Aize Companion - Android Client Setup Script
#
# This script helps set up the Android client development environment
# and provides common commands for building and testing.
#

set -e

echo "=========================================="
echo "  Aize Companion - 安卓客户端设置"
echo "=========================================="
echo ""

# Check for Android SDK
if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
    echo "⚠️  警告: 未检测到 ANDROID_HOME 环境变量"
    echo "   请先安装 Android Studio 并设置环境变量"
    echo "   下载: https://developer.android.com/studio"
    echo ""
fi

# Check for Java
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -1 | awk -F '"' '{print $2}')
    echo "✓ Java 已安装: $JAVA_VERSION"
else
    echo "⚠️  警告: 未检测到 Java"
    echo "   需要 JDK 17 或更高版本"
    echo ""
fi

# Check for Gradle
if command -v gradle &> /dev/null || [ -f "./gradlew" ]; then
    echo "✓ Gradle 可用"
else
    echo "⚠️  警告: 未检测到 Gradle"
    echo "   Android Studio 自带 Gradle，建议使用"
    echo ""
fi

echo ""
echo "常用命令:"
echo "  ./build.sh     - 构建 debug APK"
echo "  ./install.sh   - 安装到连接的设备"
echo "  ./run.sh       - 安装并启动应用"
echo ""
echo "或直接用 Android Studio:"
echo "  1. 打开 Android Studio"
echo "  2. File → Open → 选择 android_client 目录"
echo "  3. Build → Make Project"
echo "  4. Run → Run 'app'"
echo ""
echo "详细说明请参阅 android_client/README.md"
