#!/bin/bash
# Build Debian package for Humanaize 2.0 Agent
# Supports multiple architectures: amd64, arm64, all

set -e

# Default configuration
PACKAGE_NAME="humanaize2"
VERSION="2.1.0"
ARCH="all"  # Default to architecture-independent (Python)
BUILD_DIR="build"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --arch|-a)
            ARCH="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate architecture
VALID_ARCHES=("amd64" "arm64" "all")
if [[ ! " ${VALID_ARCHES[@]} " =~ " ${ARCH} " ]]; then
    echo "Invalid architecture: $ARCH"
    echo "Valid architectures: ${VALID_ARCHES[*]}"
    exit 1
fi

echo "Building ${PACKAGE_NAME}_${VERSION}_${ARCH}.deb..."

# Clean previous build
rm -rf "$BUILD_DIR"

# Create build directory structure
PKG_DIR="$BUILD_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/share/humanaize2"
mkdir -p "$PKG_DIR/etc/systemd/system"
mkdir -p "$PKG_DIR/var/lib/humanaize"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/512x512/apps"

# Copy control files
cp debian/DEBIAN/control "$PKG_DIR/DEBIAN/"
cp debian/DEBIAN/preinst "$PKG_DIR/DEBIAN/"
cp debian/DEBIAN/postinst "$PKG_DIR/DEBIAN/"
cp debian/DEBIAN/prerm "$PKG_DIR/DEBIAN/"
cp debian/DEBIAN/postrm "$PKG_DIR/DEBIAN/"

# Update control file with architecture
sed -i "s/Architecture: all/Architecture: $ARCH/" "$PKG_DIR/DEBIAN/control"

# Set permissions for control files
chmod 755 "$PKG_DIR/DEBIAN/preinst"
chmod 755 "$PKG_DIR/DEBIAN/postinst"
chmod 755 "$PKG_DIR/DEBIAN/prerm"
chmod 755 "$PKG_DIR/DEBIAN/postrm"

# Copy application files
cp -r ../../src "$PKG_DIR/usr/share/humanaize2/"
cp -r ../../skills "$PKG_DIR/usr/share/humanaize2/"
cp ../../config/version.json "$PKG_DIR/usr/share/humanaize2/"
cp ../../requirements.txt "$PKG_DIR/usr/share/humanaize2/"
cp ../../pyproject.toml "$PKG_DIR/usr/share/humanaize2/"
cp ../../docs/LICENSE "$PKG_DIR/usr/share/humanaize2/"
cp ../../docs/README.md "$PKG_DIR/usr/share/humanaize2/"
cp ../../humanaize2.sh "$PKG_DIR/usr/share/humanaize2/"

# Copy systemd service
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/debian/etc/systemd/system/humanaize2.service" "$PKG_DIR/etc/systemd/system/"

# Copy desktop shortcut and icon
cp "$SCRIPT_DIR/debian/usr/share/applications/humanaize2.desktop" "$PKG_DIR/usr/share/applications/"
cp "$SCRIPT_DIR/debian/usr/share/icons/hicolor/512x512/apps/humanaize2.png" "$PKG_DIR/usr/share/icons/hicolor/512x512/apps/"

# Create data directories
touch "$PKG_DIR/var/lib/humanaize/.gitkeep"

# Build the package
dpkg-deb --build "$PKG_DIR"

# Move package to output directory
mkdir -p output
mv "$PKG_DIR.deb" output/

echo "Debian package built successfully!"
echo "Package location: output/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"