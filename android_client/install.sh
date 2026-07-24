#!/bin/bash
# Install Aize Companion APK to connected device

cd "$(dirname "$0")"

APK_PATH="app/build/outputs/apk/debug/app-debug.apk"

if [ ! -f "$APK_PATH" ]; then
    echo "APK 不存在，请先运行 build.sh"
    exit 1
fi

# Check for connected devices
DEVICE_COUNT=$(adb devices | grep -v "List" | grep -c "device$" || true)

if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo "⚠️  未检测到连接的设备"
    echo "   请连接 Android 设备并启用 USB 调试"
    echo "   或使用模拟器: adb emu"
    exit 1
fi

echo "✓ 检测到 $DEVICE_COUNT 台设备"
echo ""

echo "正在安装..."
adb install -r "$APK_PATH"

echo ""
echo "✓ 安装成功!"
echo "可以在设备上打开 Aize Companion 应用"
