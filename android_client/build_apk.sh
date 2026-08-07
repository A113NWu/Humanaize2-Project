#!/bin/bash
# Aize Companion - Android APK Build Script
# Humanaize 2.0 Agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo " Aize Companion - Android APK Build"
echo " Humanaize 2.0 Agent"
echo "=============================================="
echo

BUILD_TYPE="${1:-debug}"

# Check Java
if ! command -v java &> /dev/null; then
    echo "[ERROR] Java is not installed or not in PATH."
    echo "        Please install JDK 17+ from: https://adoptium.net/"
    exit 1
fi

echo "[INFO] Java version: $(java -version 2>&1 | head -1)"

# Check Gradle
if ! command -v gradle &> /dev/null; then
    if [ -f "gradlew" ]; then
        GRADLE_CMD="./gradlew"
    elif [ -f "gradle/wrapper/gradle-wrapper.jar" ]; then
        echo "[INFO] Gradle wrapper JAR exists but gradlew script missing."
        echo "       Please run: gradle wrapper"
        exit 1
    else
        echo "[ERROR] Gradle is not installed and no wrapper found."
        echo "        Install Gradle or generate wrapper: gradle wrapper"
        exit 1
    fi
else
    GRADLE_CMD="${GRADLE_CMD:-gradle}"
fi

# Generate gradle wrapper if needed
if [ ! -f "gradlew" ] && command -v gradle &> /dev/null; then
    echo "[INFO] Generating Gradle wrapper..."
    gradle wrapper --gradle-version 8.5
    chmod +x gradlew
    GRADLE_CMD="./gradlew"
fi

build_apk() {
    local type="$1"
    echo
    echo "[BUILD] Building $type APK..."
    $GRADLE_CMD "assemble$(echo "$type" | sed 's/.*/\u&/')"

    local apk_path="app/build/outputs/apk/$type/app-$type.apk"
    if [ -f "$apk_path" ]; then
        local apk_size=$(du -h "$apk_path" | cut -f1)
        # 重命名 APK 包含版本号（vX.X.X）
        local version=$(grep 'versionName' app/build.gradle.kts | head -1 | sed 's/.*"\(.*\)".*/\1/')
        local versioned_apk="AizeCompanion-v${version}-${type}.apk"
        cp "$apk_path" "$versioned_apk"
        echo "[OK] $type APK: $SCRIPT_DIR/$versioned_apk ($apk_size)"
    else
        echo "[ERROR] $type APK build failed"
        return 1
    fi
}

if [ "$BUILD_TYPE" = "all" ]; then
    build_apk debug
    build_apk release
elif [ "$BUILD_TYPE" = "debug" ] || [ "$BUILD_TYPE" = "release" ]; then
    build_apk "$BUILD_TYPE"
else
    echo "[ERROR] Unknown build type: $BUILD_TYPE"
    echo "        Usage: $0 [debug|release|all]"
    echo "        Default: debug"
    exit 1
fi

echo
echo "=============================================="
echo " Build complete!"
echo "=============================================="
echo
echo " Install on device:"
echo "   adb install $SCRIPT_DIR/AizeCompanion-v*-release.apk"
