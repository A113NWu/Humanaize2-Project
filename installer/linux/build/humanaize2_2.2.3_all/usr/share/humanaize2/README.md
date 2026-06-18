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

## 🔄 Update Mechanism

- **`src/ai_selfdevelop/`**: Protected directory - **NOT** overwritten during updates
  - Contains AI-developed skills, user preferences, and learning data
  - Preserved across version updates

- **`src/core/`**: Updated directory - **IS** overwritten during updates
  - Contains core application code
  - Updated with new features and bug fixes

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
wget https://github.com/A113NWu/Humanaize2-Project/releases/download/v2.2.3/humanaize2_2.2.3_amd64.deb

# Install
sudo dpkg -i humanaize2_2.2.3_amd64.deb
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

### Humanaize2 Core (`src/core/`)
Foundational modules including:
- Agent framework
- Thinking engine
- LLM integration
- Memory system
- UI components
- Auto-updater

### AI Selfdevelop (`src/ai_selfdevelop/`)
AI-modifiable files that persist through updates:
- Custom skills developed by AI
- User preferences and profiles
- Learning data and behavior models
- Personalized UI themes and response templates

## Development

### Build from Source

```bash
# Build Debian packages
./build_all.sh

# Output: installer_output/humanaize2_*.deb
```

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is licensed under the MIT License.

## Version

**v2.2.3**

- 🎨 Modern Windows GUI with card-based design
- 📁 Refactored directory structure (`src/core/` + `src/ai_selfdevelop/`)
- 🌙 Dark/Light theme support
- 🌐 English/Chinese language support
- ⚡ AI self-optimization during idle time
- 🔧 Improved update mechanism
- 🐛 Bug fixes and improvements

## Links

- [GitHub Repository](https://github.com/A113NWu/Humanaize2-Project)
- [Releases Page](https://github.com/A113NWu/Humanaize2-Project/releases)
- [Issue Tracker](https://github.com/A113NWu/Humanaize2-Project/issues)
- [Detailed Documentation](docs/README.md)