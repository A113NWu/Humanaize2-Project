# Humanaize 2.2

> AI-powered personal assistant with self-optimization capabilities and modern GUI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)]()

Humanaize 2.2 is an intelligent personal assistant designed to adapt to user habits and optimize response speed through self-iteration during idle time. Now featuring a **modern Windows GUI** with card-based design.

## ✨ New in v2.2.3

- 🎨 **Modern Windows GUI**: Card-based interface with dark/light theme support
- 📁 **Refactored Architecture**: All core modules now in `src/core/`
- 🔧 **Modular Design**: Clean separation between core and AI self-developed content
- ⚡ **Self-Optimization**: Analyzes performance metrics and code quality during idle time
- 💬 **Natural Language Interface**: Interact with AI through intuitive chat interface
- 📚 **Skill Management**: Extensible skill system for enhanced functionality
- 🌐 **Multilingual Support**: English and Chinese language support

## 📁 Project Structure

```
Humanaize_2_1/
├── src/
│   ├── ai_selfdevelop/    # AI-modifiable files (persists through updates)
│   │   ├── skills/        # Custom skills developed by AI
│   │   ├── preferences/   # User preferences
│   │   ├── learning/      # Learning data and models
│   │   └── customizations/# UI themes and response templates
│   └── core/              # Core application modules (updated via updates)
│       ├── Agent.py       # Main agent class
│       ├── main.py        # Application entry point
│       ├── windows_main.py# Windows-specific entry point
│       ├── thinking_engine.py
│       ├── personality.py
│       ├── autonomous.py
│       ├── internal_state.py
│       ├── Prompt/        # Prompt templates
│       ├── config/        # Configuration management
│       ├── llm/           # LLM integration
│       ├── memory/        # Memory system
│       ├── tools/         # Utility tools
│       ├── ui/            # UI components
│       └── utils/         # Utilities (auto-updater)
├── skills/                # Built-in skills (OpenClaw compatible)
├── config/                # Global configuration
├── docs/                  # Documentation
└── installer/             # Build scripts and installers
```

## 📖 Documentation

Welcome! Here are the available documentation files to help you get started:

### 🚀 Quick Start
- **[Quick Start Guide (Chinese)](./README_zh.md)** - Chinese quick start guide

### 📦 Installation Guides
- **[APT Installation Guide](./APT_INSTALL.md)** - Linux APT repository installation
- **[Building Guide](./BUILDING.md)** - Building from source
- **[Windows Build Guide](./WINDOWS_BUILD_GUIDE.md)** - Windows platform build instructions
- **[Linux Deployment Guide](./DEPLOY_LINUX.md)** - Linux server deployment tutorial

### 🛠️ Troubleshooting & Reference
- **[Troubleshooting](./TROUBLESHOOTING_LINUX.md)** - Common issues and solutions
- **[Directory Structure](./DIRECTORY_STRUCTURE.md)** - Project directory explanation
- **[Version Management](./VERSION_MANAGEMENT.md)** - Version number unified management

## 🌟 Core Features

| Category | Feature |
|----------|---------|
| **Core AI** | Local chat interface, memory system, personality engine, GAN-style self-debate |
| **Skill Framework** | OpenClaw compatible skill system with 9 built-in skills |
| **User Interface** | Modern GUI based on CustomTkinter, CLI support, dark/light themes |
| **Multilingual** | English and Chinese support with automatic detection |
| **Autonomous Capabilities** | Thread-safe architecture, background task processing, idle thinking |
| **Maintenance** | GitHub auto-update, systemd service support (Linux) |

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Windows 10/11 or Linux (Ubuntu 20.04+, Debian 11+, CentOS 7+)
- llama.cpp compatible LLM server
- Recommended minimum 8GB RAM

### Quick Installation

```bash
# Clone the repository
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project

# Install dependencies (Linux)
chmod +x installer/linux/install_deps.sh
sudo ./installer/linux/install_deps.sh

# Run
./humanaize2.sh boot -m gui
```

### Windows Installation

Download the installer from the [Releases page](https://github.com/A113NWu/Humanaize2-Project/releases) and run `Humanaize2-Setup.exe`.

## 📝 Usage

```bash
# GUI mode
python src/core/main.py boot -m gui

# CLI mode
python src/core/main.py boot

# Solve mode
python src/core/main.py boot -m solve

# Update
python src/core/main.py update
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**← [Back to Main Documentation](./README.md)** | [📖 Documentation Navigation](./README.md)