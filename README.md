# Humanaize v2.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![中文](https://img.shields.io/badge/README-中文版-blue.svg)](README_zh.md)

> English | [中文](README_zh.md)

Humanaize v2.0 is a local autonomous AI agent with a modern GUI interface. It runs entirely on your Windows machine using a local LLM server, providing privacy-focused AI interactions with memory, personality, and extensible skills.

## 🌟 Features

### Core Capabilities
- **Local Chat Interface**: Modern CustomTkinter-based UI with chat history
- **Memory System**: Persistent conversation memory and thought tracking
- **Personality Engine**: Customizable AI personality traits
- **GAN-style Self-Debate**: Internal argumentation for enhanced responses
- **Skills System**: Extensible skill framework (OpenClaw-compatible)

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

## 📁 Project Structure

```
.
├── main.py                 # Application entry point
├── ui.py                   # Main GUI interface
├── Agent.py                # Agent execution engine
├── thinking_engine.py       # Async task processing
├── skills_manager.py       # Skills framework
├── config.py               # Configuration settings
├── llm.py                  # LLM communication
├── memory.py               # Memory management
├── personality.py          # Personality system
├── autonomous.py           # Autonomous decision engine
├── idle.py                 # Idle engine
├── gan_iteration.py        # GAN self-debate
├── language_adapter.py     # Language detection
├── tools.py                # Utility functions
├── requirements.txt        # Python dependencies
├── LICENSE                 # MIT License
├── README.md               # This file
│
├── skills/                 # Skills directory
│   ├── SKILL.md           # Skill definition format
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
├── data/                   # Runtime data (not tracked)
│   ├── agent_prompt.txt    # Agent instructions
│   ├── memory.json        # Conversation memory
│   ├── personality.json   # Personality config
│   └── ui_settings.json   # UI preferences
│
├── llama/                  # Llama.cpp binaries (not tracked)
└── models/                  # LLM model files (not tracked)
```

## ⚙️ Installation

### Prerequisites
- Python 3.10 or higher
- Windows operating system
- A running LLM server (llama.cpp or similar)

### Step 1: Clone the Repository
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

### Step 2: Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Download LLM Model
Place your GGUF model file in the `models/` directory. Recommended: [TinyLlama](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF)

### Step 5: Start LLM Server
```bash
cd llama
start_server.bat
```

Or manually:
```bash
llama\llama-server.exe -m models\tinyllama.gguf -c 2048 -port 8080
```

### Step 6: Run Humanaize
```bash
python main.py boot          # CLI mode
python main.py boot -m gui   # GUI mode
```

## 🚀 Quick Start

### Using the GUI
```bash
python main.py boot -m gui
```

### Using the CLI
```bash
python main.py boot
```

### Managing Skills
```bash
python main.py skills -list              # List all skills
python main.py skills -enable shell       # Enable a skill
python main.py skills -disable shell       # Disable a skill
python main.py skills -install skill.zip  # Install a skill
```

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

For direct invocation, the AI outputs JSON:
```json
{"skill": "shell", "input": "dir"}
```

### Configuring Settings
Access settings via the ⚙️ button in the GUI:
- Language selection
- Theme (Dark/Light)
- Model configuration
- Skills prompt customization
- GAN toggle
- Auto break silence toggle

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

### Agent Prompt
Edit `data/agent_prompt.txt` to customize AI behavior:
```
You are an assistant that can execute shell commands and use skills...
```

## 📦 Creating Custom Skills

### Skill Structure
Create a folder in `skills/` with a `SKILL.md` file:

```
skills/my-skill/
└── SKILL.md
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

1. **ThinkingEngine**: Async task processor for chat, GAN, and reflection
2. **Agent**: Executes skills and shell commands
3. **SkillsManager**: Loads and manages skill lifecycle
4. **Memory**: Persists conversation history
5. **Personality**: Manages AI character traits

### Data Flow
```
User Input → ThinkingEngine → LLM → Agent → Skills → Response
                ↓
            Memory/Persistence
```

## 🐛 Troubleshooting

### LLM Server Not Responding
- Ensure llama.cpp server is running: `llama\llama-server.exe -m models\model.gguf`
- Check server URL in config.py

### Skills Not Working
- Verify skill is enabled: `python main.py skills -list`
- Check skill configuration in `data/skills_config.json`

### Camera Access Error (detect-emotion)
- Ensure no other application is using the camera
- Grant camera permissions to Python

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Local LLM inference
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern Python UI
- [DeepFace](https://github.com/serengil/deepface) - Facial analysis
- [OpenClaw](https://github.com/secondself/openclaw) - Skill framework inspiration

## 📊 Stats

![GitHub stars](https://img.shields.io/github/stars/A113NWu/Humanaize2-Project?style=social)
![GitHub forks](https://img.shields.io/github/forks/A113NWu/Humanaize2-Project?style=social)

---

**Note**: This software requires a local LLM server. Humanaize provides the framework but does not include LLM model files due to their size. Download a compatible GGUF model separately.
