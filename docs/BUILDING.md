# Humanaize 2.0 Agent - Build Guide

**← [返回主文档](./README.md)** | [📖 文档导航](./README.md)

This document describes how to build Humanaize 2.0 Agent for both Linux and Windows platforms.

## 📋 Prerequisites

### Linux (Debian/Ubuntu)
```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install -y build-essential devscripts debhelper fakeroot
```

### Windows
- Python 3.8+
- PyInstaller (`pip install pyinstaller`)
- Inno Setup (for creating installers) - Download from https://jrsoftware.org/isdl.php

## 🏗️ Building

### Linux (Debian Package)

```bash
# Navigate to project directory
cd Humanaize_2_1

# Build Debian package
cd installer/linux
chmod +x build_deb.sh
sudo ./build_deb.sh

# The package will be created at:
# installer/linux/output/humanaize2_2.2.3_all.deb
```

### Windows (Executable & Installer)

**Note:** Must be run on Windows system.

```batch
:: Navigate to project directory
cd Humanaize_2_1

:: Build both x86_64 and ARM64 versions
cd installer\windows
build_all.bat

:: Or build specific architecture
python build_exe.py x86_64   :: Build x86_64 only
python build_exe.py arm64    :: Build ARM64 only
python build_exe.py all      :: Build both architectures
```

## 📦 Output Files

### Linux
| File | Description |
|------|-------------|
| `installer/linux/output/humanaize2_2.2.3_all.deb` | Debian package (works on both x86_64 and ARM64) |

### Windows
| Architecture | Executable | Installer |
|--------------|-----------|-----------|
| x86_64 | `dist/x86_64/Humanaize2.exe` | `installer_output/Humanaize2-Setup-x86_64.exe` |
| ARM64 | `dist/arm64/Humanaize2.exe` | `installer_output/Humanaize2-Setup-arm64.exe` |

## 🚀 Installation

### Linux
```bash
sudo dpkg -i humanaize2_2.2.3_all.deb
sudo apt-get install -f  # Install dependencies if needed
```

### Windows
1. Run the installer executable (`Humanaize2-Setup-x86_64.exe` or `Humanaize2-Setup-arm64.exe`)
2. Follow the installation wizard
3. Desktop shortcut will be created automatically

## 📁 Project Structure

```
Humanaize_2_1/
├── src/                    # Source code
│   ├── core/              # Core components
│   ├── ui/                # GUI/CLI interfaces
│   ├── llm/               # LLM communication
│   ├── memory/            # Memory system
│   ├── tools/             # Tools and utilities
│   └── config/            # Configuration
├── skills/                # Built-in skills
├── installer/
│   ├── linux/             # Linux build scripts
│   │   ├── build_deb.sh   # Debian package builder
│   │   ├── build_rpm.sh   # RPM package builder
│   │   └── debian/        # Debian package structure
│   └── windows/           # Windows build scripts
│       ├── build_all.bat  # Build all architectures
│       ├── build_exe.py   # PyInstaller build script
│       ├── humanaize2-x86_64.iss  # x86_64 installer config
│       └── humanaize2-arm64.iss   # ARM64 installer config
└── docs/                  # Documentation
```

## ⚠️ Notes

1. **Windows ARM64 Build**: To build ARM64 version, you need to run the build script on an ARM64 Windows device or use cross-compilation tools.

2. **Dependencies**: Both Linux and Windows packages include all necessary dependencies. However, the application requires a local LLM server (e.g., llama.cpp) to be running.

3. **Desktop Shortcuts**: Both Linux and Windows installers create desktop shortcuts that launch the GUI directly.

4. **Icon**: The application includes a custom icon for both platforms.

## 🔧 Build Options

### Linux Build Script (`build_deb.sh`)
- Creates Debian package with:
  - Desktop shortcut (`.desktop` file)
  - Application icon
  - Systemd service (optional)
  - Full source code

### Windows Build Script (`build_all.bat`)
- Builds executables for both architectures
- Creates installers with:
  - Desktop shortcuts
  - Start menu entries
  - Uninstaller
  - Full application resources

## 📝 Version Information

- **Version**: 2.2.3
- **Build Date**: Built from source
- **Supported Platforms**:
  - Linux: Debian/Ubuntu (all architectures via .deb)
  - Windows: x86_64 and ARM64