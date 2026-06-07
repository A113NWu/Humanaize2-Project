#!/bin/bash
# Humanaize 2.0 Agent - Build All Platforms
# Builds packages for Linux (amd64, arm64) and creates Windows build scripts

set -e

echo "=============================================="
echo "Humanaize 2.0 Agent - Build All Platforms"
echo "=============================================="
echo

# Create output directory
mkdir -p installer_output

# ==============================================
# Linux Builds
# ==============================================
echo "[BUILD] Linux Packages"
echo "---------------------"

cd installer/linux

# Build amd64 package
echo "Building Linux amd64..."
./build_deb.sh --arch amd64
cp output/humanaize2_2.1.0_amd64.deb ../../installer_output/

# Build arm64 package
echo "Building Linux arm64..."
./build_deb.sh --arch arm64
cp output/humanaize2_2.1.0_arm64.deb ../../installer_output/

# Build architecture-independent package (default)
echo "Building Linux all (universal)..."
./build_deb.sh --arch all
cp output/humanaize2_2.1.0_all.deb ../../installer_output/

cd ../..

# ==============================================
# Windows Build Scripts
# ==============================================
echo ""
echo "[CONFIG] Windows Build Scripts"
echo "------------------------------"
echo "Windows build scripts are ready in installer/windows/"
echo "Run build_all.bat on Windows to build x86_64 and ARM64 versions"

# ==============================================
# Summary
# ==============================================
echo ""
echo "=============================================="
echo "Build Summary"
echo "=============================================="
echo ""
echo "Linux Packages:"
echo "  - installer_output/humanaize2_2.1.0_amd64.deb"
echo "  - installer_output/humanaize2_2.1.0_arm64.deb"
echo "  - installer_output/humanaize2_2.1.0_all.deb"
echo ""
echo "Windows Build:"
echo "  - Run installer/windows/build_all.bat on Windows"
echo "  - Output: Humanaize2-Setup-x86_64.exe"
echo "  - Output: Humanaize2-Setup-arm64.exe"
echo ""
echo "=============================================="