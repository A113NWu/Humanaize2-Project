# Humanaize v2.1

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![中文](https://img.shields.io/badge/README-中文版-blue.svg)](README_zh.md)

> English | [中文](README_zh.md)

Humanaize v2.1 is a local autonomous AI agent with a modern GUI interface. It runs entirely on your machine using a local LLM server, providing privacy-focused AI interactions with memory, personality, and extensible skills.

## 🌟 Features

### Core Capabilities
- **Local Chat Interface**: Modern CustomTkinter-based UI with chat history
- **Memory System**: Persistent conversation memory and thought tracking
- **Personality Engine**: Customizable AI personality traits
- **GAN-style Self-Debate**: Internal argumentation for enhanced responses
- **Skills System**: Extensible skill framework (OpenClaw-compatible)
- **Auto-update**: Check and install updates from GitHub automatically
- **Thread-safe Architecture**: Non-blocking UI with background task processing

### Built-in Skills
| Skill | Description |
|-------|-------------|
| `shell` | Execute shell commands |
| `file-read` | Read files from the filesystem |
| `file-write` | Write content to files |
| `memory` | Query and manage conversation memory |
| `reminder` | Set timed reminders |
| `web-search` | Search the web |
| `web-fetch` | Fetch content from URLs |
| `detect-emotion` | Analyze user's facial expressions |
| `humanaize-society-network` | Connect with other Humanaize AIs |

### UI Features
- Dark/Light theme support
- Multi-language support (English, 中文)
- Real-time thought display
- Command output panel
- System status monitoring
- GAN result persistence
- **Auto-update** - Check and install updates from GitHub
- **Cross-platform** - Supports Windows and Linux

## 📁 Project Structure

```
.
├── main.py                 # Application entry point
├── ui.py                   # Main GUI interface
├── Agent.py                # Agent execution engine
├── thinking_engine.py      # Async task processing (thread-safe)
├── skills_manager.py       # Skills framework
├── config.py               # Configuration settings
├── llm.py                  # LLM communication
├── llm_enhanced.py         # Enhanced LLM with emotion feedback
├── memory.py               # Memory management
├── memory_summarizer.py    # Memory summarization
├── personality.py          # Personality system
├── autonomous.py           # Autonomous decision engine
├── idle.py                 # Idle engine
├── gan_iteration.py        # GAN self-debate
├── language_adapter.py     # Language detection
├── reflection.py           # Reflection system
├── response_validator.py   # Response validation
├── internal_state.py       # Internal state management
├── prompt_builder.py      # Prompt construction
├── vision.py               # Vision/camera support
├── auto_updater.py        # Auto-update functionality
├── skills_cli.py           # Skills CLI management
├── cli_settings.py         # Settings CLI
├── tools.py                # Utility functions
├── version.json            # Version info
├── requirements.txt        # Python dependencies
├── LICENSE                 # MIT License
├── README.md               # This file
├── README_zh.md            # Chinese version
│
├── skills/                 # Skills directory
│   ├── shell/
│   ├── file-read/
│   ├── file-write/
│   ├── memory/
│   ├── reminder/
│   ├── web-search/
│   ├── web-fetch/
│   ├── detect-emotion/
│   └── HumanaizeSocietyNetwork/
│
├── data/                   # Runtime data
├── llama/                  # Llama.cpp binaries
├── models/                  # LLM model files
├── install.sh              # Linux installer
├── install_deps.sh          # Linux dependency installer
├── uninstall.sh             # Linux uninstaller
├── DEPLOY_LINUX.md         # Linux deployment guide
└── TROUBLESHOOTING_LINUX.md # Linux troubleshooting
```

## ⚙️ Installation

### Prerequisites
- Python 3.10 or higher
- Windows 10/11 or Linux (Ubuntu 20.04+, Debian 11+, CentOS 7+)
- A running LLM server (llama.cpp or similar)

### Windows Installation

#### Step 1: Clone the Repository
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

#### Step 2: Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate
```

#### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 4: Download LLM Model
Place your GGUF model file in the `models/` directory. Recommended: [TinyLlama](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF)

#### Step 5: Start LLM Server
```bash
llama\llama-server.exe -m models\tinyllama.gguf -c 4096 -ngl 999 --host 127.0.0.1 --port 8080 -n 256
```

#### Step 6: Run Humanaize
```bash
python main.py boot          # CLI mode
python main.py boot -m gui   # GUI mode
```

### Linux Installation

#### Step 1: Clone the Repository
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

#### Step 2: Install Dependencies
```bash
chmod +x install_deps.sh
sudo ./install_deps.sh
```

#### Step 3: Install Humanaize
```bash
chmod +x install.sh
sudo ./install.sh
```

For installation with systemd service:
```bash
sudo ./install.sh --with-service
```

#### Step 4: Download LLM Model
Place your GGUF model file in `~/.local/share/Humanaize2/models/`

#### Step 5: Run Humanaize
```bash
humanaize2
```

For more details, see [DEPLOY_LINUX.md](DEPLOY_LINUX.md)

## 🚀 Quick Start

### Using the GUI
```bash
python main.py boot -m gui   # Windows
humanaize2                    # Linux
```

### Using the CLI
```bash
python main.py boot           # Windows
humanaize2 boot               # Linux
```

### Managing Skills
```bash
python main.py skills -list              # List all skills
python main.py skills -enable shell      # Enable a skill
python main.py skills -disable shell     # Disable a skill
python main.py skills -install skill.zip # Install a skill
```

### Auto-Update
Check for updates in Settings (⚙️) or via the auto-updater in the GUI.

## 🎮 Usage

### Starting a Conversation
1. Launch the application in GUI or CLI mode
2. Type your message in the input field
3. Press Enter or click Send
4. The AI will respond with thoughts and answers

### Using Skills
Skills can be invoked through natural language. Example:
```
"Can you read the file at C:\test.txt?"
"What's the weather like?"
"Set a reminder for 5 minutes."
```

### Configuring Settings
Access settings via the ⚙️ button in the GUI:
- Language selection
- Theme (Dark/Light)
- Model configuration
- Skills prompt customization
- GAN toggle
- Auto break silence toggle
- Software updates

## 🔧 Configuration

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080` | LLM server endpoint |

### Config File (`config.py`)
```python
LLAMA_SERVER = "http://127.0.0.1:8080"
MODEL_NAME = "tinyllama"
MAX_TOKENS = 256
TEMPERATURE = 0.7
TOP_P = 0.9
```

## 📦 Creating Custom Skills

### Skill Structure
Create a folder in `skills/` with a `SKILL.md` file:

```
skills/my-skill/
├── SKILL.md
└── __init__.py      # Optional executor
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

## 🧠 Architecture

### Components

1. **ThinkingEngine**: Thread-safe async task processor for chat, GAN, and reflection
2. **Agent**: Executes skills and shell commands
3. **SkillsManager**: Loads and manages skill lifecycle
4. **Memory**: Persists conversation history
5. **Personality**: Manages AI character traits
6. **AutoUpdater**: Manages software updates from GitHub

### Thread Architecture
- **UI Thread**: Handles user input and display updates
- **Decision Thread**: Handles async AI decision-making (non-blocking)
- **Thinking Thread**: Handles GAN and chat task processing
- **Idle/Autonomous Threads**: Handle background AI activity

## 🐛 Troubleshooting

### LLM Server Not Responding
- Ensure llama.cpp server is running
- Check server URL in config.py

### Skills Not Working
- Verify skill is enabled: `python main.py skills -list`
- Check skill configuration in `data/skills_config.json`

### Camera Access Error (detect-emotion)
- Ensure no other application is using the camera
- Grant camera permissions to Python

For Linux troubleshooting, see [TROUBLESHOOTING_LINUX.md](TROUBLESHOOTING_LINUX.md)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Local LLM inference
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern Python UI
- [DeepFace](https://github.com/serengil/deepface) - Facial analysis
- [OpenClaw](https://github.com/secondself/openclaw) - Skill framework inspiration

<<<<<<< HEAD
=======
## 📊 Stats

![GitHub stars](https://img.shields.io/github/stars/A113NWu/Humanaize2-Project?style=social)
![GitHub forks](https://img.shields.io/github/forks/A113NWu/Humanaize2-Project?style=social)

>>>>>>> 3a9f383f5c14069dfb4125a2c7b86c6dc8054580
---

**Note**: This software requires a local LLM server. Humanaize provides the framework but does not include LLM model files due to their size. Download a compatible GGUF model separately.