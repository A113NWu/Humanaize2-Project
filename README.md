# Humanaize 2.0

> AI-powered personal assistant with self-optimization capabilities

Humanaize 2.0 is an intelligent personal assistant designed to adapt to user habits and optimize response speed through self-iteration during idle time.

## Features

- 🧠 **AI Self-Development**: Automatically adapts to user habits and optimizes performance
- 🔧 **Modular Architecture**: Separated Core and AI Selfdevelop modules
- ⚡ **Self-Optimization**: Analyzes performance metrics and code quality during idle time
- 💬 **Natural Language Interface**: Interact with AI through intuitive chat interface
- 📚 **Skill Management**: Extensible skill system for enhanced functionality

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

### Method 1: APT Install (Recommended)

```bash
# Add repository
echo 'deb [trusted=yes] https://a113nwu.github.io/Humanaize2-Project/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/humanaize2.list

# Update package list
sudo apt update

# Install Humanaize 2.0
sudo apt install humanaize2
```

### Method 2: Debian Package

Download and install the Debian package:

```bash
# Download from GitHub Releases
wget https://github.com/A113NWu/Humanaize2-Project/releases/download/v2.2.0/humanaize2_2.2.0_amd64.deb

# Install
sudo dpkg -i humanaize2_2.2.0_amd64.deb
sudo apt install -f  # Fix dependencies if needed
```

### Method 3: From Source

```bash
# Clone the repository
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/core/main.py
```

## Usage

```bash
# Run in CLI mode
python src/core/main.py --cli

# Run in GUI mode (default)
python src/core/main.py --gui

# Show help
python src/core/main.py --help
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

- Modular architecture separation (Core + AI Selfdevelop)
- AI self-optimization during idle time
- Adaptive UI layout
- Bug fixes and improvements
