# 项目目录结构说明

**← [返回主文档](./README.md)** | [📖 文档导航](./README.md)

## 概述

本项目采用模块化架构设计，将代码按功能模块进行分类组织，便于维护和扩展。

## 目录结构

```
Humanaize_2_1/
├── src/                    # 源代码目录
│   ├── core/               # 核心模块
│   ├── ui/                 # 用户界面模块
│   ├── llm/                # 大语言模型模块
│   ├── memory/             # 记忆系统模块
│   ├── tools/              # 工具和技能模块
│   ├── config/             # 配置管理模块
│   └── utils/              # 工具函数模块
├── skills/                 # 技能插件目录
├── data/                   # 数据存储目录
├── installer/              # 安装包配置目录
│   ├── windows/            # Windows安装包配置
│   └── linux/              # Linux安装包配置
├── docs/                   # 文档目录
└── 根目录文件               # 配置文件和启动脚本
```

## 目录详细说明

### src/core/ - 核心模块

包含项目的核心业务逻辑和主要执行流程：

- `Agent.py` - 主Agent类，协调各模块工作
- `main.py` - 程序入口点
- `thinking_engine.py` - 思考引擎，处理推理逻辑
- `autonomous.py` - 自主决策模块
- `reflection.py` - 反思模块
- `personality.py` - 个性系统
- `internal_state.py` - 内部状态管理

### src/ui/ - 用户界面模块

负责与用户交互的界面实现：

- `ui.py` - 图形用户界面（GUI）
- `cli.py` - 命令行界面（CLI）
- `cli_settings.py` - CLI设置管理
- `idle.py` - 空闲状态界面
- `ascii.txt` - ASCII艺术资源

### src/llm/ - 大语言模型模块

处理与大语言模型的交互：

- `llm.py` - LLM核心接口
- `llm_enhanced.py` - 增强型LLM功能
- `prompt_builder.py` - 提示词构建器
- `response_validator.py` - 响应验证器
- `model_downloader.py` - 模型下载器

### src/memory/ - 记忆系统模块

管理Agent的记忆功能：

- `memory.py` - 记忆核心模块
- `memory_summarizer.py` - 记忆摘要器

### src/tools/ - 工具和技能模块

提供各种工具功能和技能管理：

- `tools.py` - 工具函数集
- `skills_manager.py` - 技能管理器
- `skills_cli.py` - 技能命令行接口
- `vision.py` - 视觉处理模块
- `gan_iteration.py` - GAN迭代模块
- `_check_imports.py` - 导入检查工具

### src/config/ - 配置管理模块

处理配置和语言设置：

- `config.py` - 配置管理
- `language_adapter.py` - 语言适配

### src/utils/ - 工具函数模块

提供通用工具功能：

- `auto_updater.py` - 自动更新模块

### skills/ - 技能插件目录

存放各种技能插件：

- `DetectEmotion/` - 情感检测技能
- `HumanaizeSocietyNetwork/` - 社交网络技能
- `file-read/` - 文件读取技能
- `file-write/` - 文件写入技能
- `memory/` - 记忆技能
- `reminder/` - 提醒技能
- `shell/` - 命令行执行技能
- `web-fetch/` - 网页抓取技能
- `web-search/` - 网页搜索技能

### data/ - 数据存储目录

运行时数据存储位置，包含用户数据、配置缓存等。

### installer/ - 安装包配置目录

存放安装包构建配置文件：

- `windows/` - Windows安装包配置（Inno Setup脚本）
- `linux/` - Linux安装包配置（deb/rpm打包配置）

### docs/ - 文档目录

项目文档存储位置。

## 根目录文件说明

- `humanaize2.bat` - Windows启动脚本
- `humanaize2.sh` - Linux/Mac启动脚本
- `server.bat` - Windows服务器模式启动脚本
- `server.sh` - Linux/Mac服务器模式启动脚本
- `requirements.txt` - Python依赖列表
- `pyproject.toml` - 项目配置文件
- `version.json` - 版本信息
- `LICENSE` - 许可证文件
- `README.md` - 项目说明文档
- `.gitignore` - Git忽略配置