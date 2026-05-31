# Humanaize v2.1 中文版

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![English](https://img.shields.io/badge/README-English-blue.svg)](README.md)

> [English](README.md) | 中文

Humanaize v2.1 是一款本地自治 AI 代理，配有現代化的 GUI 界面。它完全在您的電腦上運行，連接本地 LLM 服務器，提供注重隱私的 AI 交互體驗，帶有記憶功能、個性化設置和可擴展技能系統。

## 🌟 功能特性

### 核心能力
- **本地聊天界面**：基於 CustomTkinter 的現代化 UI，配有聊天歷史
- **記憶系統**：持久化對話記憶和思維追蹤
- **人格引擎**：可自定義的 AI 人格特徵
- **GAN 風格自我辯論**：內部論證以增強回覆質量
- **技能系統**：可擴展的技能框架（OpenClaw 兼容）
- **自動更新**：自動從 GitHub 檢查和安裝更新
- **線程安全架構**：後台任務處理，UI 不卡頓

### 內建技能
| 技能 | 描述 |
|-------|-------|
| `shell` | 執行 Shell 命令 |
| `file-read` | 讀取文件系統中的文件 |
| `file-write` | 寫入內容到文件 |
| `memory` | 查詢和管理對話記憶 |
| `reminder` | 設置定時提醒 |
| `web-search` | 網頁搜索 |
| `web-fetch` | 獲取網址內容 |
| `detect-emotion` | 分析用戶面部表情 |
| `humanaize-society-network` | 連接其他 Humanaize AI |

### UI 功能
- 深色/淺色主題支持
- 多語言支持（English, 中文）
- 實時思維顯示
- 命令輸出面板
- 系統狀態監控
- GAN 結果持久化
- **自動更新** - 從 GitHub 檢查和安裝更新
- **跨平台** - 支持 Windows 和 Linux

## 📁 項目結構

```
.
├── main.py                 # 應用程序入口
├── ui.py                   # 主 GUI 界面
├── Agent.py                # 代理執行引擎
├── thinking_engine.py      # 異步任務處理（線程安全）
├── skills_manager.py       # 技能框架管理
├── config.py               # 配置設置
├── llm.py                  # LLM 通信
├── llm_enhanced.py         # 增強 LLM（情緒反饋）
├── memory.py               # 記憶管理
├── memory_summarizer.py    # 記憶摘要
├── personality.py          # 人格系統
├── autonomous.py           # 自治決策引擎
├── idle.py                 # 空閒引擎
├── gan_iteration.py        # GAN 自我辯論
├── language_adapter.py     # 語言檢測
├── reflection.py           # 反思系統
├── response_validator.py   # 回覆驗證
├── internal_state.py       # 內部狀態管理
├── prompt_builder.py      # 提示詞構建
├── vision.py               # 視覺/攝像頭支持
├── auto_updater.py        # 自動更新功能
├── skills_cli.py           # 技能 CLI 管理
├── cli_settings.py         # 設置 CLI
├── tools.py                # 工具函數
├── version.json           # 版本信息
├── requirements.txt        # Python 依賴
├── LICENSE                 # MIT 許可證
├── README.md               # 英文說明
├── README_zh.md           # 中文說明
│
├── skills/                 # 技能目錄
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
├── data/                   # 運行時數據
├── llama/                  # Llama.cpp 二進制文件
├── models/                  # LLM 模型文件
├── install.sh              # Linux 安裝腳本
├── install_deps.sh          # Linux 依賴安裝腳本
├── uninstall.sh             # Linux 卸載腳本
├── DEPLOY_LINUX.md         # Linux 部署指南
└── TROUBLESHOOTING_LINUX.md # Linux 故障排除
```

## ⚙️ 安裝

### 前置條件
- Python 3.10 或更高版本
- Windows 10/11 或 Linux (Ubuntu 20.04+, Debian 11+, CentOS 7+)
- 運行的 LLM 服務器（llama.cpp 或類似軟件）

### Windows 安裝

#### 步驟 1：克隆倉庫
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

#### 步驟 2：創建虛擬環境
```bash
python -m venv .venv
.venv\Scripts\activate
```

#### 步驟 3：安裝依賴
```bash
pip install -r requirements.txt
```

#### 步驟 4：下載 LLM 模型
將您的 GGUF 模型文件放入 `models/` 目錄。推薦：[TinyLlama](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF)

#### 步驟 5：啟動 LLM 服務器
```bash
llama\llama-server.exe -m models\tinyllama.gguf -c 4096 -ngl 999 --host 127.0.0.1 --port 8080 -n 256
```

#### 步驟 6：運行 Humanaize
```bash
python main.py boot          # CLI 模式
python main.py boot -m gui   # GUI 模式
```

### Linux 安裝

#### 步驟 1：克隆倉庫
```bash
git clone https://github.com/A113NWu/Humanaize2-Project.git
cd Humanaize2-Project
```

#### 步驟 2：安裝依賴
```bash
chmod +x install_deps.sh
sudo ./install_deps.sh
```

#### 步驟 3：安裝 Humanaize
```bash
chmod +x install.sh
sudo ./install.sh
```

如需安裝 systemd 服務：
```bash
sudo ./install.sh --with-service
```

#### 步驟 4：下載 LLM 模型
將您的 GGUF 模型文件放入 `~/.local/share/Humanaize2/models/`

#### 步驟 5：運行 Humanaize
```bash
humanaize2
```

更多詳細信息，請參閱 [DEPLOY_LINUX.md](DEPLOY_LINUX.md)

## 🚀 快速開始

### 使用 GUI
```bash
python main.py boot -m gui   # Windows
humanaize2                    # Linux
```

### 使用 CLI
```bash
python main.py boot           # Windows
humanaize2 boot               # Linux
```

### 管理技能
```bash
python main.py skills -list              # 列出所有技能
python main.py skills -enable shell      # 啟用技能
python main.py skills -disable shell     # 禁用技能
python main.py skills -install skill.zip # 安裝技能
```

### 自動更新
在設置（⚙️）中檢查更新，或通過 GUI 中的自動更新器進行更新。

## 🎮 使用說明

### 開始對話
1. 以 GUI 或 CLI 模式啟動應用程序
2. 在輸入框中輸入您的消息
3. 按 Enter 或點擊發送
4. AI 將以思維和答案回覆

### 使用技能
技能可以通過自然語言調用。例如：
```
"你能讀取 C:\test.txt 的內容嗎？"
"天氣怎麼樣？"
"設置一個 5 分鐘後的提醒。"
```

### 配置設置
通過 GUI 中的 ⚙️ 按鈕訪問設置：
- 語言選擇
- 主題（深色/淺色）
- 模型配置
- 技能提示自定義
- GAN 開關
- 自動打破沉默開關
- 軟件更新

## 🔧 配置

### 環境變量
| 變量 | 默認值 | 描述 |
|----------|---------|-------------|
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080` | LLM 服務器端點 |

### 配置文件（`config.py`）
```python
LLAMA_SERVER = "http://127.0.0.1:8080"
MODEL_NAME = "tinyllama"
MAX_TOKENS = 256
TEMPERATURE = 0.7
TOP_P = 0.9
```

## 📦 創建自定義技能

### 技能結構
在 `skills/` 創建一個文件夾，包含 `SKILL.md` 文件：

```
skills/my-skill/
├── SKILL.md
└── __init__.py      # 可選的執行器
```

### SKILL.md 格式
```markdown
---
name: my-skill
description: 這個技能的功能
metadata:
  category: utility
  risk_level: low
  requires_approval: false
  version: 1.0.0
---

# 我的技能

## 目的
描述這個技能的功能。

## 輸入格式
帶有輸入數據的 JSON 對象。

## 示例
{"skill": "my-skill", "input": "..."}
```

## 🧠 架構

### 組件

1. **ThinkingEngine**：用於聊天、GAN 和反思的線程安全異步任務處理器
2. **Agent**：執行技能和 Shell 命令
3. **SkillsManager**：加載和管理技能的生命週期
4. **Memory**：持久化對話歷史
5. **Personality**：管理 AI 角色特徵
6. **AutoUpdater**：從 GitHub 管理軟件更新

### 線程架構
- **UI 線程**：處理用戶輸入和顯示更新
- **決策線程**：處理異步 AI 決策（非阻塞）
- **思維線程**：處理 GAN 和聊天任務處理
- **空閒/自治線程**：處理後台 AI 活動

## 🐛 故障排除

### LLM 服務器無響應
- 確保 llama.cpp 服務器正在運行
- 檢查 config.py 中的服務器 URL

### 技能不工作
- 驗證技能已啟用：`python main.py skills -list`
- 檢查 `data/skills_config.json` 中的技能配置

### 攝像頭訪問錯誤（detect-emotion）
- 確保沒有其他應用程序正在使用攝像頭
- 授予 Python 相機權限

有關 Linux 故障排除，請參閱 [TROUBLESHOOTING_LINUX.md](TROUBLESHOOTING_LINUX.md)

## 📄 許可證

本項目採用 MIT 許可證 - 請參閱 [LICENSE](LICENSE) 文件。

## 🙏 致謝

- [llama.cpp](https://github.com/ggerganov/llama.cpp) - 本地 LLM 推理
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 現代化 Python UI
- [DeepFace](https://github.com/serengil/deepface) - 面部分析
- [OpenClaw](https://github.com/secondself/openclaw) - 技能框架靈感

<<<<<<< HEAD
=======
## 📊 統計

![GitHub stars](https://img.shields.io/github/stars/A113NWu/Humanaize2-Project?style=social)
![GitHub forks](https://img.shields.io/github/forks/A113NWu/Humanaize2-Project?style=social)

>>>>>>> 3a9f383f5c14069dfb4125a2c7b86c6dc8054580
---

**注意**：此軟件需要本地 LLM 服務器。Humanaize 提供框架但不包括 LLM 模型文件（因為體積較大）。請單獨下載兼容的 GGUF 模型。