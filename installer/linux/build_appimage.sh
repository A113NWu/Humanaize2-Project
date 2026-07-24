#!/bin/bash
# Build AppImage for Humanaize 2.0 Agent
# A self-contained, portable Linux application bundle

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION=$(grep -o '"version": *"[^"]*"' "$PROJECT_ROOT/config/version.json" | sed 's/"version": *"\([^"]*\)"/\1/')
APP_NAME="Humanaize2"
OUTPUT_DIR="$SCRIPT_DIR/output"
BUILD_DIR="$SCRIPT_DIR/build/appimage"

echo "=============================================="
echo " Building Humanaize 2.0 AppImage"
echo " Version: $VERSION"
echo "=============================================="
echo

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$OUTPUT_DIR"

# Create AppDir structure
APPDIR="$BUILD_DIR/AppDir"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/$APP_NAME"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/lib"

# Copy Python virtual environment or system Python packages
echo "[1/5] Setting up Python environment..."

PYTHON_BIN=$(which python3)
if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] python3 not found in PATH"
    exit 1
fi

# Copy Python interpreter
cp "$PYTHON_BIN" "$APPDIR/usr/bin/python3"

# Copy required Python packages
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    pip3 install --target "$APPDIR/usr/lib/python3/site-packages" -r "$PROJECT_ROOT/requirements.txt" --break-system-packages 2>/dev/null || {
        echo "[WARN] pip install failed, will try to copy from system"
    }
fi

# Copy application source
echo "[2/5] Copying application files..."
cp -r "$PROJECT_ROOT/src" "$APPDIR/usr/share/$APP_NAME/"
cp -r "$PROJECT_ROOT/skills" "$APPDIR/usr/share/$APP_NAME/"
cp -r "$PROJECT_ROOT/prompt" "$APPDIR/usr/share/$APP_NAME/" 2>/dev/null || true
cp "$PROJECT_ROOT/config/version.json" "$APPDIR/usr/share/$APP_NAME/" 2>/dev/null || true
cp "$PROJECT_ROOT/requirements.txt" "$APPDIR/usr/share/$APP_NAME/" 2>/dev/null || true
cp "$PROJECT_ROOT/pyproject.toml" "$APPDIR/usr/share/$APP_NAME/" 2>/dev/null || true
cp "$PROJECT_ROOT/humanaize2.sh" "$APPDIR/usr/bin/" 2>/dev/null || true

# Copy llama binaries
if [ -d "$PROJECT_ROOT/llama" ]; then
    cp -r "$PROJECT_ROOT/llama" "$APPDIR/usr/share/$APP_NAME/"
fi

# Copy models
if [ -d "$PROJECT_ROOT/models" ]; then
    cp -r "$PROJECT_ROOT/models" "$APPDIR/usr/share/$APP_NAME/"
fi

# Copy icon
echo "[3/5] Setting up icon and desktop file..."
cp "$PROJECT_ROOT/icon/humanaize2.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png" 2>/dev/null || {
    # Create a placeholder icon
    convert -size 256x256 xc:orange "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png" 2>/dev/null || true
}

# Create desktop file
cat > "$APPDIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Humanaize 2.0 Agent
Comment=AI Companion with IoT Compute Network
Exec=usr/bin/humanaize2-wrapper
Icon=$APP_NAME
Terminal=true
Categories=Utility;Application;
StartupWMClass=$APP_NAME
EOF

# Create launcher wrapper
cat > "$APPDIR/usr/bin/humanaize2-wrapper" << 'WRAPPER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPDIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="$APPDIR/usr/share/Humanaize2/src:$PYTHONPATH"
export LD_LIBRARY_PATH="$APPDIR/lib:$LD_LIBRARY_PATH"
exec "$APPDIR/usr/bin/python3" "$APPDIR/usr/share/Humanaize2/src/core/main.py" boot -m gui "$@"
WRAPPER
chmod +x "$APPDIR/usr/bin/humanaize2-wrapper"

# Create AppRun
cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export APPDIR="$HERE"
export PYTHONPATH="$APPDIR/usr/share/Humanaize2/src:$PYTHONPATH"
export LD_LIBRARY_PATH="$APPDIR/lib:$LD_LIBRARY_PATH"
exec "$APPDIR/usr/bin/python3" "$APPDIR/usr/share/Humanaize2/src/core/main.py" boot "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "[4/5] Creating AppImage..."

# Download appimagetool if not present
APPIMAGETOOL="$BUILD_DIR/appimagetool"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

if [ ! -f "$APPIMAGETOOL" ]; then
    echo "  Downloading appimagetool..."
    wget -q -O "$APPIMAGETOOL" "$APPIMAGETOOL_URL" 2>/dev/null || \
    curl -sL -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL" 2>/dev/null || {
        echo "[WARN] Could not download appimagetool. Creating .tar.gz fallback."
        cd "$APPDIR"
        tar czf "$OUTPUT_DIR/Humanaize2-$VERSION-x86_64.tar.gz" .
        echo "  Created tar.gz: $OUTPUT_DIR/Humanaize2-$VERSION-x86_64.tar.gz"
        echo "  Extract and run: ./AppRun"
        exit 0
    }
    chmod +x "$APPIMAGETOOL"
fi

# Build AppImage
ARCH="x86_64"
OUTPUT_NAME="$OUTPUT_DIR/Humanaize2-$VERSION-$ARCH.AppImage"
cd "$BUILD_DIR"
"$APPIMAGETOOL" "$APPDIR" -n "$APP_NAME" --updateinformation "gh-releases-zsync|A113NWu/Humanaize2-Project|latest|Humanaize2-$ARCH.AppImage.zsync" -o "$OUTPUT_NAME" 2>/dev/null || {
    # Simpler approach without update info
    "$APPIMAGETOOL" "$APPDIR" -n "$APP_NAME" -o "$OUTPUT_NAME" 2>/dev/null || {
        # Fallback to tar.gz
        echo "[WARN] appimagetool failed. Creating .tar.gz fallback."
        cd "$APPDIR"
        tar czf "$OUTPUT_DIR/Humanaize2-$VERSION-$ARCH.tar.gz" .
        echo "  Created tar.gz: $OUTPUT_DIR/Humanaize2-$VERSION-$ARCH.tar.gz"
        echo "  Extract and run: ./AppRun"
        exit 0
    }
}

echo "[5/5] AppImage built successfully!"
echo
echo "=============================================="
echo " Output: $OUTPUT_NAME"
echo " Size: $(du -h "$OUTPUT_NAME" | cut -f1)"
echo
echo " To install:"
echo "   chmod +x $OUTPUT_NAME"
echo "   $OUTPUT_NAME"
echo "=============================================="
