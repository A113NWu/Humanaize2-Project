#!/bin/bash
# Build debug APK for Aize Companion

cd "$(dirname "$0")"

echo "Building Aize Companion debug APK..."

./gradlew assembleDebug

APK_PATH="app/build/outputs/apk/debug/app-debug.apk"

if [ -f "$APK_PATH" ]; then
    echo ""
    echo "✓ 构建成功!"
    echo "  APK 路径: $(pwd)/$APK_PATH"
    echo "  文件大小: $(du -h "$APK_PATH" | cut -f1)"
else
    echo "❌ 构建失败，请检查错误信息"
    exit 1
fi
