# Humanaize v2.1

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)]()
[![中文](https://img.shields.io/badge/README-中文版-blue.svg)](README_zh.md)

> English | [中文](README_zh.md)

Humanaize v2.1 is a **local autonomous AI agent** with a modern GUI interface. It runs entirely on your machine using a local LLM server, providing privacy-focused AI interactions with memory, personality, and extensible skills.

## 🎯 Key Features

| Category | Features |
|----------|----------|
| **Core AI** | Local chat interface, Memory system, Personality engine, GAN-style self-debate |
| **Skills Framework** | OpenClaw-compatible skill system with 9 built-in skills |
| **User Interface** | Modern CustomTkinter GUI, CLI support, Dark/Light themes |
| **Multilingual** | English and Chinese support with automatic language detection |
| **Autonomy** | Thread-safe architecture, background task processing, idle thinking |
| **Maintenance** | Auto-update from GitHub, systemd service support (Linux) |

---

## 🌟 Core Capabilities

### 1. Local Chat Interface
- Modern CustomTkinter-based UI with chat history
- Real-time thought display showing AI's internal reasoning
- Both GUI and CLI modes available
- Command output panel for skill execution results

### 2. Memory System
- Persistent conversation memory across sessions
- Thought tracking and decision logging
- Memory summarization for efficient context management
- Configurable memory limits (default: 100 messages)

### 3. Personality Engine
- Customizable AI personality traits (curiosity, empathy, creativity)
- Dynamic personality adaptation based on interactions
- Initial prompt customization

### 4. GAN-Style Self-Debate
- Internal argumentation for enhanced response quality
- Automatic decision on when to use deep reflection
- Synthesis of multiple perspectives

### 5. Skills System (OpenClaw Compatible)
- Extensible skill framework
- Support for custom skill development
- Skill enable/disable management
- JSON-based skill invocation

---

## 📦 Built-in Skills

| Skill | Description | Risk Level |
|-------|-------------|------------|
| `shell` | Execute shell commands | High |
| `file-read` | Read files from the filesystem | Medium |
| `file-write` | Write content to files | High |
| `memory` | Query and manage conversation memory | Low |
| `reminder` | Set timed reminders | Low |
| `web-search` | Search the web | Low |
| `web-fetch` | Fetch content from URLs | Low |
| `detect-emotion` | Analyze user's facial expressions via camera | Medium |
| `humanaize-society-network` | Connect with other Humanaize AIs | Medium |

---

## 📁 Project Structure

```
Humanaize_2_1/
├── src/
│   ├── core/              # Core components
│   │   ├── main.py        # Application entry point
│   │   ├── Agent.py       # Agent execution engine
│   │   ├── thinking_engine.py  # Async task processing
│   │   ├── autonomous.py  # Autonomous decision engine
│   │   ├── personality.py # Personality system
│   │   ├── reflection.py  # Reflection system
│   │   └── internal_state.py   # Internal state management
│   ├── llm/               # LLM communication
│   │   ├── llm.py         # Basic LLM client
│   │   ├── llm_enhanced.py # Enhanced LLM with emotion feedback
│   │   ├── prompt_builder.py  # Prompt construction
│   │   ├── response_validator.py # Response validation
│   │   └── model_downloader.py # Model download utilities
│   ├── memory/            # Memory management
│   │   ├── memory.py      # Core memory operations
│   │   └── memory_summarizer.py # Memory summarization
│   ├── config/            # Configuration
│   │   ├── config.py      # Global settings
│   │   └── language_adapter.py # Language detection
│   ├── tools/             # Tools and utilities
│   │   ├── skills_manager.py # Skills framework
│   │   ├── skills_cli.py  # Skills CLI management
│   │   ├── gan_iteration.py # GAN self-debate
│   │   ├── solve_mode.py  # Problem solving mode
│   │   ├── vision.py      # Camera/vision support
│   │   └── tools.py       # General utilities
│   ├── ui/                # User interface
│   │   ├── ui.py          # Main GUI interface
│   │   ├── cli.py         # CLI interface
│   │   ├── cli_settings.py # Settings CLI
│   │   └── idle.py        # Idle engine
│   └── utils/             # Utility modules
│       └── auto_updater.py # Auto-update functionality
├── skills/                # Skills directory
│   ├── shell/
│   ├── file-read/
│   ├── file-write/
│   ├── memory/
│   ├── reminder/
│   ├── web-search/
│   ├── web-fetch/
│   ├── detect-emotion/
│   └── HumanaizeSocietyNetwork/
├── data/                  # Runtime data storage
├── docs/                  # Documentation
│   ├── DEPLOY_LINUX.md
│   ├── DIRECTORY_STRUCTURE.md
│   └── TROUBLESHOOTING_LINUX.md
├── installer/             # Installer scripts
│   ├── linux/             # Debian/RPM package builders
│   │   ├── debian/        # Debian package structure
│   │   ├── build_deb.sh  # Build Debian package
│   │   └── build_rpm.sh   # Build RPM package
│   └── windows/           # Windows installer
│       ├── build_all.bat  # Build Windows installer
│       ├── build_exe.py   # Python build script
│       └── humanaize2.iss # Inno Setup script
├── Humanaize2/            # Virtual environment
├── models/                 # LLM model files
├── llama/                  # Llama.cpp binaries
├── version.json           # Version information
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Build configuration
├── humanaize2.sh          # Linux launch script
├── humanaize2.bat         # Windows launch script
├── humanaize2.service.template # systemd service template
├── Humanaize2.spec        # RPM spec file
├── LICENSE                # MIT License
└── README.md              # This file
```

---

## ⚙️ Installation

### Prerequisites

| Requirement | Version | Description |
|-------------|---------|-------------|
| Python | 3.10+ | Core runtime |
| OS | Windows 10/11 or Linux (Ubuntu 20.04+, Debian 11+, CentOS 7+) | Supported platforms |
| LLM Server | llama.cpp compatible | Required for AI inference |
| RAM | Minimum 8GB recommended | For model loading |

### Quick Download Command

Use the built-in download command to get TinyLlama automatically:

```bash
# Linux
./humanaize2.sh download-model

# Windows
humanaize2.bat download-model
```

### Windows Installation

#### Method 1: Using Installer (Recommended)

1. Download the latest `Humanaize2-Setup.exe` from the releases page
2. Run the installer and follow the installation wizard
3. Launch Humanaize 2.0 from the Start Menu

#### Method 2: Manual Installation

##### Step 1: Clone the Repository
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

##### Step 2: Create Virtual Environment
```bash
python -m venv Humanaize2
Humanaize2\Scripts\activate
```

##### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

##### Step 4: Download LLM Model
Use the built-in download command:
```bash
humanaize2.bat download-model
```

Or manually place your GGUF model file in the `models/` directory. Recommended: [TinyLlama-1.1B-Chat-v1.0-GGUF](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF)

##### Step 5: Download Llama.cpp Server

Download the Windows version of llama-server from [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases) and place it in the `llama/` directory.

##### Step 6: Run Humanaize
```bash
python src/core/main.py boot          # CLI mode
python src/core/main.py boot -m gui   # GUI mode
```

Or use the launch script:
```bash
humanaize2.bat boot
humanaize2.bat boot -m gui
```

### Linux Installation

#### Method 1: Using Installer (Recommended)

1. Download the latest `.deb` or `.rpm` package from the releases page
2. Install using your package manager:

**For Debian/Ubuntu:**
```bash
sudo dpkg -i humanaize2_*.deb
# or
sudo apt install ./humanaize2_*.deb
```

**For Fedora/RHEL/CentOS:**
```bash
sudo rpm -i humanaize2_*.rpm
# or
sudo dnf install ./humanaize2_*.rpm
```

3. Download the LLM model:
```bash
humanaize2 download-model
```

4. Run Humanaize:
```bash
humanaize2
```

#### Method 2: Manual Installation

##### Step 1: Clone the Repository
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

##### Step 2: Install System Dependencies
```bash
chmod +x installer/linux/install_deps.sh
sudo ./installer/linux/install_deps.sh
```

This will install:
- Python 3.11 (if not present)
- python3-tk
- Required system libraries

##### Step 3: Install Humanaize
```bash
chmod +x install.sh
sudo ./install.sh
```

For installation with systemd service:
```bash
sudo ./install.sh --with-service
```

##### Step 4: Download LLM Model
Use the built-in download command:
```bash
./humanaize2.sh download-model
```

Or manually place your GGUF model file in `~/.local/share/Humanaize2/models/`

##### Step 5: Download Llama.cpp Server

Download the Linux version of llama-server from [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases) and place it in the `~/.local/share/Humanaize2/llama/` directory.

##### Step 6: Run Humanaize
```bash
humanaize2
```

For more details, see [docs/DEPLOY_LINUX.md](docs/DEPLOY_LINUX.md)

---

## 🚀 Quick Start

### Using the GUI
```bash
# Linux
humanaize2
# or
./humanaize2.sh boot -m gui

# Windows
humanaize2.bat boot -m gui
# or
python src/core/main.py boot -m gui
```

### Using the CLI
```bash
# Linux
humanaize2 boot
# or
./humanaize2.sh boot

# Windows
humanaize2.bat boot
# or
python src/core/main.py boot
```

### Managing Skills
```bash
# List all skills
python src/core/main.py skills -list

# Enable a skill
python src/core/main.py skills -enable shell

# Disable a skill
python src/core/main.py skills -disable shell

# Install a skill from file
python src/core/main.py skills -install skill.zip
```

### Auto-Update
```bash
# Check for updates
python src/core/main.py update

# Force update
python src/core/main.py update -f
```

### Settings
```bash
python src/core/main.py settings
```

---

## 🎮 Usage

### Starting a Conversation
1. Launch the application in GUI or CLI mode
2. Type your message in the input field
3. Press Enter or click Send
4. The AI will respond with thoughts and answers

### Using Skills
Skills can be invoked through natural language. Example:
```
"Can you read the file at /home/user/test.txt?"
"What's the weather like today?"
"Set a reminder for 5 minutes from now."
"Execute: ls -la"
```

### Configuring Settings
Access settings via the ⚙️ button in the GUI:
- Language selection (English/中文)
- Theme (Dark/Light)
- Model configuration
- Skills prompt customization
- GAN toggle
- Auto break silence toggle
- Software updates

### Solve Mode
For problem-solving tasks:
```bash
python src/core/main.py boot -m solve
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080/completion` | LLM server endpoint |

### Config File (`src/config/config.py`)

```python
# LLM Configuration
LLAMA_SERVER = "http://127.0.0.1:8080"
LLAMA_SERVER_URL = f"{LLAMA_SERVER}/completion"
MODEL_NAME = "tinyllama"
MAX_TOKENS = 256
TEMPERATURE = 0.7
TOP_P = 0.9

# UI Configuration
UI_WIDTH = 1200
UI_HEIGHT = 900

# Memory Configuration
MEMORY_FILE = "data/memory.json"
MAX_MEMORY = 100

# Personality Configuration
DEFAULT_PERSONALITY = {
    "traits": {"curiosity": 0.7, "empathy": 0.5, "creativity": 0.6},
    "initial_prompt": "You are a friendly helpful AI."
}

# Autonomous Behavior
SCREENSHOT_INTERVAL = 300  # seconds
REFLECTION_INTERVAL = 1800
AUTONOMOUS_CHECK_INTERVAL = 300
```

---

## 📦 Creating Custom Skills

### Skill Structure
Create a folder in `skills/` with a `SKILL.md` file:

```
skills/my-skill/
├── SKILL.md          # Required skill definition
└── __init__.py       # Optional executor module
```

### SKILL.md Format
```markdown
---
name: my-skill
description: What this skill does
metadata:
  category: utility
  risk_level: low
  requires_approval: false
  version: 1.0.0
---

# My Skill

## Purpose
Describe what this skill does.

## Input Format
JSON object with input data.

## Example
{"skill": "my-skill", "input": "..."}
```

### Executor Module (`__init__.py`)
```python
def execute(input_data):
    """Execute the skill with given input"""
    # Your skill logic here
    return {"status": "success", "result": "output"}
```

---

## 🧠 Architecture

### Core Components

1. **ThinkingEngine** - Thread-safe async task processor for chat, GAN, and reflection
2. **Agent** - Executes skills and shell commands
3. **SkillsManager** - Loads and manages skill lifecycle
4. **Memory** - Persists conversation history and thoughts
5. **Personality** - Manages AI character traits
6. **AutoUpdater** - Manages software updates from GitHub

### Thread Architecture

| Thread | Purpose |
|--------|---------|
| **UI Thread** | Handles user input and display updates |
| **Decision Thread** | Handles async AI decision-making (non-blocking) |
| **Thinking Thread** | Handles GAN and chat task processing |
| **Idle/Autonomous Threads** | Handle background AI activity |

### Data Flow

```
User Input → Language Detection → ThinkingEngine → LLM Query
    ↓                      ↓
Memory Store ← Skill Execution ← Agent
    ↓
Response Generation → User Interface
```

---

## 🛠️ Building Installation Packages

### Windows Installer

#### Prerequisites
- Windows 10/11
- Python 3.10+ (for building)
- Inno Setup 6.x (for creating the installer)

#### Build Steps

1. Navigate to the installer directory:
```bash
cd installer/windows
```

2. Run the build script:
```bash
build_all.bat
```

This will:
- Create a virtual environment
- Install all dependencies
- Download TinyLlama model
- Build the executable using PyInstaller
- Create the installer using Inno Setup

3. Find the installer at:
```
dist/Humanaize2-Setup.exe
```

### Linux Packages

#### Debian/Ubuntu (.deb)

```bash
cd installer/linux
chmod +x build_deb.sh
sudo ./build_deb.sh
```

The package will be created at:
```
dist/humanaize2_*.deb
```

#### Fedora/RHEL (.rpm)

```bash
cd installer/linux
chmod +x build_rpm.sh
sudo ./build_rpm.sh
```

The package will be created at:
```
dist/humanaize2-*.rpm
```

---

## 🐛 Troubleshooting

### LLM Server Not Responding
- Ensure llama.cpp server is running
- Check server URL in `src/config/config.py`
- Verify model file path is correct
- Ensure port 8080 is not blocked by firewall

### Skills Not Working
- Verify skill is enabled: `python src/core/main.py skills -list`
- Check skill configuration in `data/skills_config.json`
- Ensure skill executor module has proper `execute` function

### Camera Access Error (detect-emotion)
- Ensure no other application is using the camera
- Grant camera permissions to Python
- Check OpenCV installation: `pip install opencv-python`

### GUI Issues
- Update CustomTkinter: `pip install --upgrade customtkinter`
- Check Python version compatibility
- Try running in CLI mode first to isolate UI issues
- Check for tkinter installation: `python -c "import tkinter"`

### Installation Issues (Linux)
- Ensure you have root/sudo privileges
- Check that Python 3.10+ is installed
- Verify system dependencies are installed
- Check logs in `/var/log/humanaize2/` if using systemd

For Linux-specific troubleshooting, see [docs/TROUBLESHOOTING_LINUX.md](docs/TROUBLESHOOTING_LINUX.md)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

### Guidelines
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and commit: `git commit -m 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

### Code Standards
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Include docstrings for all functions and classes
- Add tests for new functionality

### Reporting Issues
- Use GitHub Issues for bug reports and feature requests
- Include version information and error logs
- Provide reproduction steps for bugs

---

## 🙏 Acknowledgments

- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Local LLM inference
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern Python UI
- [DeepFace](https://github.com/serengil/deepface) - Facial analysis
- [OpenClaw](https://github.com/secondself/openclaw) - Skill framework inspiration

---

## 📊 Stats

![GitHub stars](https://img.shields.io/github/stars/A113NWu/Humanaize2-Project?style=social)
![GitHub forks](https://img.shields.io/github/forks/A113NWu/Humanaize2-Project?style=social)

---

**Note**: This software requires a local LLM server. Humanaize provides the framework but does not include LLM model files due to their size. Download a compatible GGUF model separately.

---

## 🔗 Useful Links

- [GitHub Repository](https://github.com/A113NWu/Humanaize2-Project)
- [Releases Page](https://github.com/A113NWu/Humanaize2-Project/releases)
- [Issue Tracker](https://github.com/A113NWu/Humanaize2-Project/issues)
- [Wiki/Documentation](https://github.com/A113NWu/Humanaize2-Project/wiki)
- [TinyLlama Model](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)