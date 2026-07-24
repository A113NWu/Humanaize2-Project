#!/bin/bash
# Build portable tarball for Humanaize 2.0 Agent
# A simple .tar.gz archive that can be extracted and run anywhere

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION=$(grep -o '"version": *"[^"]*"' "$PROJECT_ROOT/config/version.json" | sed 's/"version": *"\([^"]*\)"/\1/')
ARCH="$(uname -m)"
APP_NAME="Humanaize2"
OUTPUT_DIR="$SCRIPT_DIR/output"
BUILD_DIR="$SCRIPT_DIR/build/tarball"

echo "=============================================="
echo " Building Humanaize 2.0 Portable Tarball"
echo " Version: $VERSION"
echo " Architecture: $ARCH"
echo "=============================================="
echo

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/$APP_NAME"
mkdir -p "$OUTPUT_DIR"

STAGING="$BUILD_DIR/$APP_NAME"

echo "[1/4] Copying application files..."

# Copy source
cp -r "$PROJECT_ROOT/src" "$STAGING/"
cp -r "$PROJECT_ROOT/skills" "$STAGING/"
if [ -d "$PROJECT_ROOT/prompt" ]; then
    cp -r "$PROJECT_ROOT/prompt" "$STAGING/"
fi
if [ -d "$PROJECT_ROOT/data" ]; then
    cp -r "$PROJECT_ROOT/data" "$STAGING/"
fi
if [ -d "$PROJECT_ROOT/llama" ]; then
    cp -r "$PROJECT_ROOT/llama" "$STAGING/"
fi
if [ -d "$PROJECT_ROOT/models" ]; then
    cp -r "$PROJECT_ROOT/models" "$STAGING/"
fi
if [ -d "$PROJECT_ROOT/icon" ]; then
    cp -r "$PROJECT_ROOT/icon" "$STAGING/"
fi
if [ -d "$PROJECT_ROOT/config" ]; then
    cp -r "$PROJECT_ROOT/config" "$STAGING/"
fi
if [ -d "$PROJECT_ROOT/languages" ]; then
    cp -r "$PROJECT_ROOT/languages" "$STAGING/"
fi

# Copy config files
cp "$PROJECT_ROOT/requirements.txt" "$STAGING/" 2>/dev/null || true
cp "$PROJECT_ROOT/pyproject.toml" "$STAGING/" 2>/dev/null || true
cp "$PROJECT_ROOT/humanaize2.sh" "$STAGING/" 2>/dev/null || true
cp "$PROJECT_ROOT/README.md" "$STAGING/" 2>/dev/null || true
cp "$PROJECT_ROOT/LICENSE" "$STAGING/" 2>/dev/null || true

echo "[2/4] Setting up launcher scripts..."

# Update launcher scripts to use relative paths
cat > "$STAGING/humanaize2" << 'LAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
export PYTHONUNBUFFERED=1
cd "$SCRIPT_DIR"
exec python3 src/core/main.py "$@"
LAUNCHER
chmod +x "$STAGING/humanaize2"

cat > "$STAGING/install.sh" << 'INSTALLER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Humanaize 2.0 Agent..."

# Install to /usr/local by default, or ~/.local for user install
if [ "$1" = "--user" ] || [ "$1" = "-u" ]; then
    INSTALL_DIR="$HOME/.local/share/humanaize2"
    BIN_DIR="$HOME/.local/bin"
    echo "  Installing to user directory: $INSTALL_DIR"
else
    INSTALL_DIR="/usr/local/share/humanaize2"
    BIN_DIR="/usr/local/bin"
    echo "  Installing to system directory: $INSTALL_DIR (requires sudo)"
fi

mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"

# Create symlink in bin directory
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/humanaize2" << EOF
#!/bin/bash
exec "$INSTALL_DIR/humanaize2" "\$@"
EOF
chmod +x "$BIN_DIR/humanaize2"

echo
echo "Installation complete!"
echo "  Binary: $BIN_DIR/humanaize2"
echo "  To run: humanaize2 boot"
echo
echo "  If $BIN_DIR is not in PATH, add it:"
echo "    export PATH=\"$BIN_DIR:\$PATH\""
INSTALLER
chmod +x "$STAGING/install.sh"

# Create uninstaller
cat > "$STAGING/uninstall.sh" << 'UNINSTALLER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$1" = "--user" ] || [ "$1" = "-u" ]; then
    INSTALL_DIR="$HOME/.local/share/humanaize2"
    BIN_DIR="$HOME/.local/bin"
else
    INSTALL_DIR="/usr/local/share/humanaize2"
    BIN_DIR="/usr/local/bin"
fi

echo "Uninstalling Humanaize 2.0 Agent..."
rm -rf "$INSTALL_DIR"
rm -f "$BIN_DIR/humanaize2"
echo "Done."
UNINSTALLER
chmod +x "$STAGING/uninstall.sh"

echo "[3/4] Creating tarball..."

OUTPUT_NAME="$OUTPUT_DIR/Humanaize2-$VERSION-$ARCH.tar.gz"
cd "$BUILD_DIR"
tar czf "$OUTPUT_NAME" "$APP_NAME"

echo "[4/4] Verifying..."

if [ -f "$OUTPUT_NAME" ]; then
    TARBALL_SIZE=$(du -h "$OUTPUT_NAME" | cut -f1)
    echo
    echo "=============================================="
    echo " Tarball built successfully!"
    echo " Output: $OUTPUT_NAME"
    echo " Size: $TARBALL_SIZE"
    echo
    echo " To install:"
    echo "   tar xzf Humanaize2-$VERSION-$ARCH.tar.gz"
    echo "   cd Humanaize2"
    echo "   ./install.sh          # system-wide"
    echo "   ./install.sh --user   # user-only"
    echo
    echo " Or just run directly:"
    echo "   ./humanaize2 boot"
    echo "=============================================="
else
    echo "[ERROR] Failed to create tarball"
    exit 1
fi
