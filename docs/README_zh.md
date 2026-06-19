# Humanaize v2.2

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)]()
[![English](https://img.shields.io/badge/README-English-blue.svg)](./README_en.md)

> [English](./README_en.md) | 中文

Humanaize v2.2 是一款**本地自治 AI 代理**，具有现代化的图形界面。它完全在本地运行，通过本地 LLM 服务器提供注重隐私的 AI 交互，支持记忆系统、人格引擎和可扩展的技能框架。

**v2.2 新功能：**
- ✨ Windows 现代化 GUI 界面（卡片式设计）
- ✨ AI 自我发展模块（用户个性化定制，更新时保留）
- ✨ 自我优化系统（AI 空闲时间自动分析优化）
- ✨ 用户行为模式分析
- ✨ 性能监控和优化建议
- ✨ CLI/Solve 模式日志修复

## 🎯 核心特性

| 类别 | 功能 |
|------|------|
| **核心 AI** | 本地聊天界面、记忆系统、人格引擎、GAN 风格自我辩论 |
| **技能框架** | OpenClaw 兼容的技能系统，包含 9 个内置技能 |
| **用户界面** | 基于 CustomTkinter 的现代 GUI、CLI 支持、深色/浅色主题 |
| **多语言** | 支持英语和中文，自动检测语言 |
| **自治能力** | 线程安全架构、后台任务处理、空闲思考 |
| **维护** | GitHub 自动更新、systemd 服务支持（Linux） |

---

## 🌟 核心能力

### 1. 本地聊天界面
- 基于 CustomTkinter 的现代 UI，带聊天历史
- 实时显示 AI 的内部推理过程
- 支持 GUI 和 CLI 两种模式
- 技能执行结果输出面板

### 2. 记忆系统
- 跨会话持久化对话记忆
- 思考过程和决策记录
- 高效上下文管理的记忆摘要
- 可配置的内存限制（默认：100 条消息）

### 3. 人格引擎
- 可定制的 AI 人格特质（好奇心、同理心、创造力）
- 基于交互的动态人格适应
- 可自定义初始提示词

### 4. GAN 风格自我辩论
- 内部论证以提升回复质量
- 自动决定何时使用深度反思
- 多视角综合分析

### 5. 技能系统（OpenClaw 兼容）
- 可扩展的技能框架
- 支持自定义技能开发
- 技能启用/禁用管理
- 基于 JSON 的技能调用

---

## 📦 内置技能

| 技能 | 描述 | 风险等级 |
|------|------|----------|
| `shell` | 执行 shell 命令 | 高 |
| `file-read` | 读取文件系统中的文件 | 中 |
| `file-write` | 向文件写入内容 | 高 |
| `memory` | 查询和管理对话记忆 | 低 |
| `reminder` | 设置定时提醒 | 低 |
| `web-search` | 网络搜索 | 低 |
| `web-fetch` | 获取 URL 内容 | 低 |
| `detect-emotion` | 通过摄像头分析用户面部表情 | 中 |
| `humanaize-society-network` | 连接其他 Humanaize AI | 中 |

---

## 📁 项目结构

```
Humanaize_2_1/
├── src/
│   ├── core/              # 核心组件
│   │   ├── main.py        # 应用入口
│   │   ├── Agent.py       # 代理执行引擎
│   │   ├── thinking_engine.py  # 异步任务处理
│   │   ├── autonomous.py  # 自治决策引擎
│   │   ├── personality.py # 人格系统
│   │   ├── reflection.py  # 反思系统
│   │   └── internal_state.py   # 内部状态管理
│   ├── llm/               # LLM 通信
│   │   ├── llm.py         # 基础 LLM 客户端
│   │   ├── llm_enhanced.py # 带情感反馈的增强 LLM
│   │   ├── prompt_builder.py  # 提示词构建
│   │   ├── response_validator.py # 响应验证
│   │   └── model_downloader.py # 模型下载工具
│   ├── memory/            # 记忆管理
│   │   ├── memory.py      # 核心记忆操作
│   │   └── memory_summarizer.py # 记忆摘要
│   ├── config/            # 配置
│   │   ├── config.py      # 全局设置
│   │   └── language_adapter.py # 语言检测
│   ├── tools/             # 工具和实用程序
│   │   ├── skills_manager.py # 技能框架
│   │   ├── skills_cli.py  # 技能 CLI 管理
│   │   ├── gan_iteration.py # GAN 自我辩论
│   │   ├── solve_mode.py  # 问题解决模式
│   │   ├── vision.py      # 摄像头/视觉支持
│   │   └── tools.py       # 通用工具
│   ├── ui/                # 用户界面
│   │   ├── ui.py          # 主 GUI 界面
│   │   ├── cli.py         # CLI 界面
│   │   ├── cli_settings.py # 设置 CLI
│   │   └── idle.py        # 空闲引擎
│   └── utils/             # 实用程序模块
│       └── auto_updater.py # 自动更新功能
├── skills/                # 技能目录
│   ├── shell/
│   ├── file-read/
│   ├── file-write/
│   ├── memory/
│   ├── reminder/
│   ├── web-search/
│   ├── web-fetch/
│   ├── detect-emotion/
│   └── HumanaizeSocietyNetwork/
├── data/                  # 运行时数据存储
├── docs/                  # 文档
│   ├── DEPLOY_LINUX.md
│   ├── DIRECTORY_STRUCTURE.md
│   └── TROUBLESHOOTING_LINUX.md
├── installer/             # 安装脚本
│   ├── linux/             # Debian/RPM 包构建器
│   │   ├── debian/        # Debian 包结构
│   │   ├── build_deb.sh  # 构建 Debian 包
│   │   └── build_rpm.sh   # 构建 RPM 包
│   └── windows/           # Windows 安装程序
│       ├── build_all.bat  # 构建 Windows 安装程序
│       ├── build_exe.py   # Python 构建脚本
│       └── humanaize2.iss # Inno Setup 脚本
├── Humanaize2/            # 虚拟环境
├── models/                 # LLM 模型文件
├── llama/                  # Llama.cpp 可执行文件
├── version.json           # 版本信息
├── requirements.txt       # Python 依赖
├── pyproject.toml         # 构建配置
├── humanaize2.sh          # Linux 启动脚本
├── humanaize2.bat         # Windows 启动脚本
├── humanaize2.service.template # systemd 服务模板
├── Humanaize2.spec        # RPM spec 文件
├── LICENSE                # MIT 许可证
└── README_zh.md           # 本文件
```

---

## ⚙️ 安装

### 系统要求

| 要求 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 核心运行时 |
| 操作系统 | Windows 10/11 或 Linux (Ubuntu 20.04+, Debian 11+, CentOS 7+) | 支持的平台 |
| LLM 服务器 | llama.cpp 兼容 | AI 推理必需 |
| 内存 | 推荐最低 8GB | 用于加载模型 |

### 快速下载命令

使用内置下载命令自动获取 TinyLlama：

```bash
# Linux
./humanaize2.sh download-model

# Windows
humanaize2.bat download-model
```

### Windows 安装

#### 方法 1：使用安装程序（推荐）

1. 从 [Releases 页面](https://github.com/A113NWu/Humanaize2-Project/releases) 下载最新的 `Humanaize2-Setup.exe`
2. 运行安装程序并按照安装向导操作
3. 从开始菜单启动 Humanaize 2.2，现代化 GUI 自动打开

**Windows 安装包特性：**
- 🎨 现代化卡片式 GUI 界面
- 🌙 深色/浅色主题支持
- 🌐 中文/英文语言支持
- 📦 首次启动自动下载模型
- ⚡ 自动更新功能

#### 方法 2：手动安装

##### 步骤 1：克隆仓库
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

##### 步骤 2：创建虚拟环境
```bash
python -m venv Humanaize2
Humanaize2\Scripts\activate
```

##### 步骤 3：安装依赖
```bash
pip install -r requirements.txt
```

##### 步骤 4：下载 LLM 模型
使用内置下载命令：
```bash
humanaize2.bat download-model
```

或手动将 GGUF 模型文件放入 `models/` 目录。推荐使用：[TinyLlama-1.1B-Chat-v1.0-GGUF](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF)

##### 步骤 5：下载 Llama.cpp 服务器

从 [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases) 下载 Windows 版本的 llama-server，放置在 `llama/` 目录中。

##### 步骤 6：运行 Humanaize
```bash
python src/core/main.py boot          # CLI 模式
python src/core/main.py boot -m gui   # GUI 模式
```

或使用启动脚本：
```bash
humanaize2.bat boot
humanaize2.bat boot -m gui
```

### Linux 安装

#### 方法 1：使用安装程序（推荐）

1. 从 releases 页面下载最新的 `.deb` 或 `.rpm` 包
2. 使用包管理器安装：

**Debian/Ubuntu:**
```bash
sudo dpkg -i humanaize2_*.deb
# 或
sudo apt install ./humanaize2_*.deb
```

**Fedora/RHEL/CentOS:**
```bash
sudo rpm -i humanaize2_*.rpm
# 或
sudo dnf install ./humanaize2_*.rpm
```

3. 下载 LLM 模型：
```bash
humanaize2 download-model
```

4. 运行 Humanaize：
```bash
humanaize2
```

#### 方法 2：手动安装

##### 步骤 1：克隆仓库
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

##### 步骤 2：安装系统依赖
```bash
chmod +x installer/linux/install_deps.sh
sudo ./installer/linux/install_deps.sh
```

这将安装：
- Python 3.11（如不存在）
- python3-tk
- 所需的系统库

##### 步骤 3：安装 Humanaize
```bash
chmod +x install.sh
sudo ./install.sh
```

如需安装 systemd 服务：
```bash
sudo ./install.sh --with-service
```

##### 步骤 4：下载 LLM 模型
使用内置下载命令：
```bash
./humanaize2.sh download-model
```

或手动将 GGUF 模型文件放入 `~/.local/share/Humanaize2/models/`

##### 步骤 5：下载 Llama.cpp 服务器

从 [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases) 下载 Linux 版本的 llama-server，放置在 `~/.local/share/Humanaize2/llama/` 目录中。

##### 步骤 6：运行 Humanaize
```bash
humanaize2
```

更多详细信息，请参阅 [docs/DEPLOY_LINUX.md](docs/DEPLOY_LINUX.md)

---

## 🚀 快速开始

### 使用 Windows 现代化 GUI
```bash
# Windows 安装包默认启动现代化 GUI
# 从源代码启动：
python src/core/main.py boot -m win-gui
```

### 使用传统 GUI
```bash
# Linux
humanaize2
# 或
./humanaize2.sh boot -m gui

# Windows
humanaize2.bat boot -m gui
# 或
python src/core/main.py boot -m gui
```

### 使用 CLI
```bash
# Linux
humanaize2 boot
# 或
./humanaize2.sh boot

# Windows
humanaize2.bat boot
# 或
python src/core/main.py boot
```

### 管理技能
```bash
# 列出所有技能
python src/core/main.py skills -list

# 启用技能
python src/core/main.py skills -enable shell

# 禁用技能
python src/core/main.py skills -disable shell

# 从文件安装技能
python src/core/main.py skills -install skill.zip
```

### 自动更新
```bash
# 检查更新
python src/core/main.py update

# 强制更新
python src/core/main.py update -f
```

### 设置
```bash
python src/core/main.py settings
```

---

## 🎮 使用

### 开始对话
1. 以 GUI 或 CLI 模式启动应用程序
2. 在输入框中输入您的消息
3. 按 Enter 或点击发送
4. AI 将通过思考和答案进行回复

### 使用技能
技能可以通过自然语言调用。例如：
```
"你能读取 /home/user/test.txt 这个文件吗？"
"今天天气怎么样？"
"5分钟后设置一个提醒。"
"执行：ls -la"
```

### 配置设置
通过 GUI 中的 ⚙️ 按钮访问设置：
- 语言选择（English/中文）
- 主题（深色/浅色）
- 模型配置
- 技能提示词自定义
- GAN 开关
- 自动打破沉默开关
- 软件更新

### 解决模式
用于问题解决任务：
```bash
python src/core/main.py boot -m solve
```

---

## 🔧 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080/completion` | LLM 服务器端点 |

### 配置文件（`src/config/config.py`）

```python
# LLM 配置
LLAMA_SERVER = "http://127.0.0.1:8080"
LLAMA_SERVER_URL = f"{LLAMA_SERVER}/completion"
MODEL_NAME = "tinyllama"
MAX_TOKENS = 256
TEMPERATURE = 0.7
TOP_P = 0.9

# UI 配置
UI_WIDTH = 1200
UI_HEIGHT = 900

# 记忆配置
MEMORY_FILE = "data/memory.json"
MAX_MEMORY = 100

# 人格配置
DEFAULT_PERSONALITY = {
    "traits": {"curiosity": 0.7, "empathy": 0.5, "creativity": 0.6},
    "initial_prompt": "You are a friendly helpful AI."
}

# 自治行为
SCREENSHOT_INTERVAL = 300  # 秒
REFLECTION_INTERVAL = 1800
AUTONOMOUS_CHECK_INTERVAL = 300
```

---

## 📦 创建自定义技能

### 技能结构
在 `skills/` 中创建一个包含 `SKILL.md` 文件的文件夹：

```
skills/my-skill/
├── SKILL.md          # 必需的技能定义
└── __init__.py       # 可选的执行器模块
```

### SKILL.md 格式
```markdown
---
name: my-skill
description: 技能的功能描述
metadata:
  category: utility
  risk_level: low
  requires_approval: false
  version: 1.0.0
---

# 我的技能

## 用途
描述这个技能的功能。

## 输入格式
包含输入数据的 JSON 对象。

## 示例
{"skill": "my-skill", "input": "..."}
```

### 执行器模块（`__init__.py`）
```python
def execute(input_data):
    """使用给定输入执行技能"""
    # 你的技能逻辑
    return {"status": "success", "result": "output"}
```

---

## 🧠 架构

### 核心组件

1. **ThinkingEngine** - 用于聊天、GAN 和反思的线程安全异步任务处理器
2. **Agent** - 执行技能和 shell 命令
3. **SkillsManager** - 加载和管理技能生命周期
4. **Memory** - 持久化对话历史和思考
5. **Personality** - 管理 AI 角色特质
6. **AutoUpdater** - 管理 GitHub 软件更新

### 线程架构

| 线程 | 用途 |
|------|------|
| **UI 线程** | 处理用户输入和显示更新 |
| **决策线程** | 处理异步 AI 决策（非阻塞） |
| **思考线程** | 处理 GAN 和聊天任务处理 |
| **空闲/自治线程** | 处理后台 AI 活动 |

### 数据流

```
用户输入 → 语言检测 → ThinkingEngine → LLM 查询
    ↓                      ↓
记忆存储 ← 技能执行 ← Agent
    ↓
响应生成 → 用户界面
```

---

## 🛠️ 构建安装包

### Windows 安装程序

#### 前提条件
- Windows 10/11
- Python 3.10+（用于构建）
- Inno Setup 6.x（用于创建安装程序）

#### 构建步骤

1. 导航到安装目录：
```bash
cd installer/windows
```

2. 运行构建脚本：
```bash
build_all.bat
```

这将：
- 创建虚拟环境
- 安装所有依赖
- 下载 TinyLlama 模型
- 使用 PyInstaller 构建可执行文件
- 使用 Inno Setup 创建安装程序

3. 安装程序位置：
```
dist/Humanaize2-Setup.exe
```

### Linux 包

#### Debian/Ubuntu (.deb)

```bash
cd installer/linux
chmod +x build_deb.sh
sudo ./build_deb.sh
```

包将创建在：
```
dist/humanaize2_*.deb
```

#### Fedora/RHEL (.rpm)

```bash
cd installer/linux
chmod +x build_rpm.sh
sudo ./build_rpm.sh
```

包将创建在：
```
dist/humanaize2-*.rpm
```

---

## 🐛 故障排除

### LLM 服务器无响应
- 确保 llama.cpp 服务器正在运行
- 检查 `src/config/config.py` 中的服务器 URL
- 验证模型文件路径是否正确
- 确保防火墙未阻止 8080 端口

### 技能不工作
- 验证技能已启用：`python src/core/main.py skills -list`
- 检查 `data/skills_config.json` 中的技能配置
- 确保技能执行器模块具有正确的 `execute` 函数

### 摄像头访问错误（detect-emotion）
- 确保没有其他应用程序正在使用摄像头
- 授予 Python 摄像头权限
- 检查 OpenCV 安装：`pip install opencv-python`

### GUI 问题
- 更新 CustomTkinter：`pip install --upgrade customtkinter`
- 检查 Python 版本兼容性
- 先尝试在 CLI 模式下运行以隔离 UI 问题
- 检查 tkinter 安装：`python -c "import tkinter"`

### Linux 安装问题
- 确保您有 root/sudo 权限
- 检查是否已安装 Python 3.10+
- 验证系统依赖已安装
- 如果使用 systemd，检查 `/var/log/humanaize2/` 中的日志

Linux 特定故障排除，请参阅 [docs/TROUBLESHOOTING_LINUX.md](docs/TROUBLESHOOTING_LINUX.md)

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 🤝 贡献

### 指南
1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature-name`
3. 提交您的更改：`git commit -m 'Add feature'`
4. 推送到分支：`git push origin feature-name`
5. 提交 Pull Request

### 代码标准
- 遵循 PEP 8 风格指南
- 在适当的地方使用类型提示
- 为所有函数和类添加文档字符串
- 为新功能添加测试

### 报告问题
- 使用 GitHub Issues 报告错误和功能请求
- 包含版本信息和错误日志
- 提供错误重现步骤

---

## 🙏 致谢

- [llama.cpp](https://github.com/ggerganov/llama.cpp) - 本地 LLM 推理
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 现代 Python UI
- [DeepFace](https://github.com/serengil/deepface) - 人脸分析
- [OpenClaw](https://github.com/secondself/openclaw) - 技能框架灵感

---

## 📊 统计

![GitHub stars](https://img.shields.io/github/stars/A113NWu/Humanaize2-Project?style=social)
![GitHub forks](https://img.shields.io/github/forks/A113NWu/Humanaize2-Project?style=social)

---

**注意**：此软件需要本地 LLM 服务器。Humanaize 提供框架但由于文件大小不包含 LLM 模型文件。请单独下载兼容的 GGUF 模型。

---

## 🔗 链接

- [GitHub 仓库](https://github.com/A113NWu/Humanaize2-Project)
- [Releases 页面](https://github.com/A113NWu/Humanaize2-Project/releases)
- [问题跟踪器](https://github.com/A113NWu/Humanaize2-Project/issues)
- [Wiki/文档](https://github.com/A113NWu/Humanaize2-Project/wiki)
- [TinyLlama 模型](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)