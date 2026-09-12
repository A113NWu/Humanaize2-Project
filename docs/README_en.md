# Humanaize 2.3

> AI-powered local autonomous agent with a modern web dashboard, streaming voice conversations, self-optimization capabilities and multiple UI modes

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)]()

Humanaize 2.3 is a local autonomous AI agent that adapts to user habits and optimizes itself during idle time. It runs fully locally through a llama.cpp-compatible LLM server, with a modern **browser dashboard**, **streaming voice chat (STT + TTS)**, extensible skills, memory, personality engine and an IoT compute network.

## ✨ What's New in v2.3

- 🎙️ **Voice Chat in Web Dashboard**: one-click mic toggle (bottom-right of the input box) — speech is transcribed to text and sent automatically; AI replies are narrated sentence-by-sentence
- 🔊 **Streaming TTS**: replies are synthesized while the AI is still generating (powered by edge-tts, code blocks skipped automatically)
- 🏷️ **Unified Versioning**: every UI version display reads from `config/version.json` — change once, applies everywhere
- 🖥️ **Same-Window CLI**: the CLI chat now runs inside the launching terminal (Windows) with built-in commands (`/help`, `/mem`, `/status`, `/gan`, `/clear`, `/quit`)
- 🧹 **IoT Log Filtering**: compute-network logs only record key events
- 🌊 **Liquid Glass UI**: frosted-glass visual style for the web dashboard

## ✨ Carried over from v2.2

- 🌐 Browser dashboard with streaming chat, live thinking process and status monitoring
- 🎨 Modern Windows GUI with card-based design and dark/light themes
- 🧠 AI self-development module (user customizations preserved across updates)
- ⚡ Self-optimization system analyzing performance during idle time
- 👁️ Vision skills (screen capture, camera, image recognition)
- 📦 Skill installer (install custom skills from archives)
- 📝 Centralized prompt management (all prompts in `prompt/` folder)

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
| **Web Dashboard** | Streaming chat, live thinking process, voice chat (STT + streaming TTS), status monitoring, Liquid Glass style, custom wallpaper |
| **User Interface** | Browser dashboard, modern Windows GUI, classic GUI, same-window CLI, dark/light themes |
| **Multilingual** | English and Chinese support with automatic detection |
| **Voice** | Browser mic input (Web Speech API), streaming reply narration (edge-tts) |
| **Autonomous Capabilities** | Thread-safe architecture, background task processing, idle thinking |
| **Networking** | IoT compute network (join distributed compute nodes) |
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
# Web dashboard (recommended, default mode — opens your browser automatically)
humanaize2 boot

# Windows modern GUI
python src/core/main.py boot -m win-gui

# Classic GUI
python src/core/main.py boot -m gui

# CLI chat (runs inside the same terminal window on Windows)
python src/core/main.py boot -m cli

# Solve mode
python src/core/main.py boot -m solve

# Update
python src/core/main.py update
```

### Command Reference

| Command | Description |
|---------|-------------|
| `humanaize2 boot` | Start browser dashboard (default) |
| `humanaize2 boot -m cli` | Start CLI chat interface (same-window interaction) |
| `humanaize2 boot -m gui` | Start classic GUI interface |
| `humanaize2 boot -m win-gui` | Start Windows modern GUI interface |
| `humanaize2 boot -m solve [-r <file>] [--hsn] [-gan] [--sandbox <dir>] [problem]` | Start problem solving mode |
| `humanaize2 boot -m guard [--background\|-b] [--start-when-boot\|-s]` | Start guard mode |
| `humanaize2 boot -m iot [--host <ip>] [--port <n>]` | Start IoT compute network |
| `humanaize2 settings` | Open settings interface |
| `humanaize2 check-server` | Check the local llama-server |
| `humanaize2 skills -list \| -enable <name> \| -disable <name> \| -install <zip>` | Manage skills |
| `humanaize2 update [-f]` | Check for and install updates (`-f` forces) |
| `humanaize2 help` | Show the command reference |

### Voice Chat (Web Dashboard)

1. Click the **microphone button at the bottom-right of the input box** (it turns red and pulses when active)
2. Allow microphone access when the browser asks
3. Speak — your speech is transcribed into the input box in real time
4. After ~1 second of silence the message is sent automatically, and the reply is **narrated aloud sentence-by-sentence** while it streams
5. Click the microphone button again to stop narration and exit voice mode

> Speech recognition uses the browser's Web Speech API (Chrome/Edge recommended); speech synthesis (edge-tts) requires internet access to Microsoft's TTS service.

### Custom Dashboard Wallpaper

1. Create an `Assets` folder in the install directory (or project root)
2. Place an image named `Background.jpg`, `Background.jpeg` or `Background.png` inside
3. Refresh the browser page — no restart needed
4. Without a wallpaper the Liquid Glass gradient background is used

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**← [Back to Main Documentation](./README.md)** | [📖 Documentation Navigation](./README.md)