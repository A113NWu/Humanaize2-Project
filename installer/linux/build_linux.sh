#!/bin/bash
# Unified Linux build script for Humanaize 2.0 Agent
# Builds: .deb, AppImage, and portable tarball

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION=$(grep -o '"version": *"[^"]*"' "$SCRIPT_DIR/../../config/version.json" | sed 's/"version": *"\([^"]*\)"/\1/')

echo "=============================================="
echo " Humanaize 2.0 Agent - Linux Build All"
echo " Version: $VERSION"
echo "=============================================="
echo

BUILD_TYPE="${1:-all}"

case "$BUILD_TYPE" in
    deb)
        echo
        echo ">>> Building Debian package..."
        bash "$SCRIPT_DIR/build_deb.sh"
        ;;
    appimage)
        echo
        echo ">>> Building AppImage..."
        bash "$SCRIPT_DIR/build_appimage.sh"
        ;;
    tarball)
        echo
        echo ">>> Building portable tarball..."
        bash "$SCRIPT_DIR/build_tarball.sh"
        ;;
    all)
        echo
        echo ">>> Building all Linux packages..."
        echo
        echo "[1/3] Debian package..."
        bash "$SCRIPT_DIR/build_deb.sh"
        echo
        echo "[2/3] AppImage..."
        bash "$SCRIPT_DIR/build_appimage.sh"
        echo
        echo "[3/3] Portable tarball..."
        bash "$SCRIPT_DIR/build_tarball.sh"
        echo
        echo "=============================================="
        echo " All Linux packages built!"
        echo " Output directory: $SCRIPT_DIR/output"
        echo "=============================================="
        ls -lh "$SCRIPT_DIR/output/"*.deb "$SCRIPT_DIR/output/"*.AppImage "$SCRIPT_DIR/output/"*.tar.gz 2>/dev/null || true
        ;;
    *)
        echo "Usage: $0 [deb|appimage|tarball|all]"
        echo "  deb      - Debian/Ubuntu package (.deb)"
        echo "  appimage - Self-contained AppImage"
        echo "  tarball  - Portable tar.gz archive"
        echo "  all      - Build all formats"
        exit 1
        ;;
esac
