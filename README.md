# Humanaize 2.2

> AI-powered personal assistant with self-optimization capabilities and modern GUI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)]()

Humanaize 2.2 is an intelligent personal assistant designed to adapt to user habits and optimize response speed through self-iteration during idle time. Now featuring a **modern Windows GUI** with card-based design.

## ✨ New in v2.2

- 🎨 **Modern Windows GUI**: Card-based interface with dark/light theme support
- 🧠 **AI Self-Development**: Automatically adapts to user habits and optimizes performance
- 🔧 **Modular Architecture**: Separated Core and AI Selfdevelop modules
- ⚡ **Self-Optimization**: Analyzes performance metrics and code quality during idle time
- 💬 **Natural Language Interface**: Interact with AI through intuitive chat interface
- 📚 **Skill Management**: Extensible skill system for enhanced functionality
- 🌐 **Multilingual Support**: English and Chinese language support

## Architecture

```
Humanaize 2.0
├── src/
│   ├── core/          # Core modules (updated via updates)
│   ├── ui/            # User interface components
│   ├── llm/           # LLM integration
│   ├── memory/        # Memory management
│   ├── tools/         # Utility tools
│   └── ai_selfdevelop/ # AI-modifiable files (persists through updates)
├── skills/            # Extensible skills
├── config/            # Configuration files
└── models/            # AI models (GGUF format)
```

## Installation

### Windows Installation

#### Method 1: Windows Installer (Recommended)

Download the Windows installer with modern GUI:

1. Download `Humanaize2-Setup.exe` from [GitHub Releases](https://github.com/A113NWu/Humanaize2-Project/releases)
2. Run the installer and follow the wizard
3. Launch from Start Menu - modern GUI opens automatically

**Windows GUI Features:**
- 🎨 Modern card-based design
- 🌙 Dark/Light theme support
- 🌐 English/Chinese language
- 📦 Auto model download
- ⚡ Auto-update functionality

#### Method 2: From Source (Windows)

```bash
# Clone the repository
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project

# Install dependencies
pip install -r requirements.txt

# Run modern GUI
python src/core/main.py boot -m win-gui

# Or run traditional GUI
python src/core/main.py boot -m gui
```

### Linux Installation

#### Method 1: APT Install (Recommended)

```bash
# Add repository
echo 'deb [trusted=yes] https://a113nwu.github.io/Humanaize2-Project/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/humanaize2.list

# Update package list
sudo apt update

# Install Humanaize 2.2
sudo apt install humanaize2
```

#### Method 2: Debian Package

Download and install the Debian package:

```bash
# Download from GitHub Releases
wget https://github.com/A113NWu/Humanaize2-Project/releases/download/v2.2.0/humanaize2_2.2.0_amd64.deb

# Install
sudo dpkg -i humanaize2_2.2.0_amd64.deb
sudo apt install -f  # Fix dependencies if needed
```

#### Method 3: From Source (Linux)

```bash
# Clone the repository
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/core/main.py boot
```

## Usage

### Windows

```bash
# Modern Windows GUI (default for installer)
python src/core/main.py boot -m win-gui

# Traditional GUI
python src/core/main.py boot -m gui

# CLI mode
python src/core/main.py boot

# Solve mode
python src/core/main.py boot -m solve
```

### Linux

```bash
# GUI mode (default)
humanaize2

# CLI mode
humanaize2 boot

# Solve mode
humanaize2 boot -m solve
```

## Modules

### Humanaize2 Core
Foundational modules including:
- Skill management
- Agent framework
- UI components
- Memory system

### AI Selfdevelop
AI-modifiable files that persist through updates:
- Custom skills
- User preferences
- Learning data
- Personalized optimizations

## Development

### Build from Source

```bash
# Build Debian packages
./build_all.sh

# Output: installer_output/humanaize2_*.deb
```

### Project Structure

```
src/
├── core/              # Main application entry
│   └── main.py        # Application entry point
├── ui/                # GUI components
│   ├── ui.py          # Main UI layout
│   └── idle.py        # Idle engine for self-optimization
├── llm/               # LLM integration
│   └── model_downloader.py
├── memory/            # Memory management
├── tools/             # Utility tools
│   ├── skills_manager.py
│   └── self_optimizer.py
└── ai_selfdevelop/    # AI self-developed content
    ├── skills/
    ├── preferences/
    ├── learning/
    └── customizations/
```

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is licensed under the MIT License.

## Version

**v2.2.0**

- 🎨 Modern Windows GUI with card-based design
- 🌙 Dark/Light theme support
- 🌐 English/Chinese language support
- 🧠 Modular architecture separation (Core + AI Selfdevelop)
- ⚡ AI self-optimization during idle time
- 🔧 Adaptive UI layout
- 🐛 Bug fixes and improvements

## Screenshots

### Windows Modern GUI
```
┌─────────────────────────────────────────────────────────────┐
│  Humanaize v2.2                                    ●  ⚙    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────┐  ┌─────────────────────────┐ │
│  │      Chat Panel          │  │   Thoughts              │ │
│  │                          │  │                         │ │
│  │  User: Hello!            │  │  AI thinking about...   │ │
│  │  AI: Hi there!           │  │                         │ │
│  │                          │  ├─────────────────────────┤ │
│  │                          │  │   Command Output        │ │
│  │                          │  │                         │ │
│  │                          │  │  $ ls -la               │ │
│  │                          │  │  total 42               │ │
│  │                          │  ├─────────────────────────┤ │
│  │                          │  │   System Status         │ │
│  │                          │  │                         │ │
│  │                          │  │  Model: tinyllama       │ │
│  │                          │  │  Status: Running        │ │
│  └──────────────────────────┘  └─────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Enter your message...                      [Send] [Clr]│  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Links

- [GitHub Repository](https://github.com/A113NWu/Humanaize2-Project)
- [Releases Page](https://github.com/A113NWu/Humanaize2-Project/releases)
- [Issue Tracker](https://github.com/A113NWu/Humanaize2-Project/issues)
- [Detailed Documentation](docs/README.md)
