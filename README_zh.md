# Humanaize v2.0 中文版

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![English](https://img.shields.io/badge/README-English-blue.svg)](README.md)

> [English](README.md) | 中文

Humanaize v2.0 是一款本地自治 AI 代理，配有現代化的 GUI 界面。它完全在您的 Windows 電腦上運行，連接本地 LLM 服務器，提供注重隱私的 AI 交互體驗，帶有記憶功能、個性化設置和可擴展技能系統。

## 🌟 功能特性

### 核心能力
- **本地聊天界面**：基於 CustomTkinter 的現代化 UI，配有聊天歷史
- **記憶系統**：持久化對話記憶和思維追蹤
- **人格引擎**：可自定義的 AI 人格特徵
- **GAN 風格自我辯論**：內部論證以增強回覆質量
- **技能系統**：可擴展的技能框架（OpenClaw 兼容）

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

## 📁 項目結構

```
.
├── main.py                 # 應用程序入口
├── ui.py                   # 主 GUI 界面
├── Agent.py                # 代理執行引擎
├── thinking_engine.py       # 異步任務處理
├── skills_manager.py       # 技能框架管理
├── config.py               # 配置設置
├── llm.py                  # LLM 通信
├── memory.py               # 記憶管理
├── personality.py          # 人格系統
├── autonomous.py           # 自治決策引擎
├── idle.py                 # 空閒引擎
├── gan_iteration.py        # GAN 自我辯論
├── language_adapter.py     # 語言檢測
├── tools.py                # 工具函數
├── requirements.txt        # Python 依賴
├── LICENSE                 # MIT 許可證
├── README.md               # 英文說明
├── README_zh.md           # 中文說明
│
├── skills/                 # 技能目錄
│   ├── SKILL.md           # 技能定義格式
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
├── data/                   # 運行時數據（不追蹤）
│   ├── agent_prompt.txt    # AI 指令
│   ├── memory.json        # 對話記憶
│   ├── personality.json   # 人格配置
│   └── ui_settings.json   # UI 偏好
│
├── llama/                  # Llama.cpp 二進制文件（不追蹤）
└── models/                  # LLM 模型文件（不追蹤）
```

## ⚙️ 安裝

### 前置條件
- Python 3.10 或更高版本
- Windows 操作系統
- 運行的 LLM 服務器（llama.cpp 或類似軟件）

### 步驟 1：克隆倉庫
```bash
git clone https://github.com/A113NWu/Humanaize2 Project.git
cd Humanaize2 Project
```

### 步驟 2：創建虛擬環境
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 步驟 3：安裝依賴
```bash
pip install -r requirements.txt
```

### 步驟 4：下載 LLM 模型
將您的 GGUF 模型文件放入 `models/` 目錄。推薦：[TinyLlama](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF)

### 步驟 5：啟動 LLM 服務器
```bash
cd llama
start_server.bat
```

或手動：
```bash
llama\llama-server.exe -m models\tinyllama.gguf -c 2048 -port 8080
```

### 步驟 6：運行 Humanaize
```bash
python main.py boot          # CLI 模式
python main.py boot -m gui   # GUI 模式
```

## 🚀 快速開始

### 使用 GUI
```bash
python main.py boot -m gui
```

### 使用 CLI
```bash
python main.py boot
```

### 管理技能
```bash
python main.py skills -list              # 列出所有技能
python main.py skills -enable shell       # 啟用技能
python main.py skills -disable shell       # 禁用技能
python main.py skills -install skill.zip  # 安裝技能
```

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

對於直接調用，AI 輸出 JSON：
```json
{"skill": "shell", "input": "dir"}
```

### 配置設置
通過 GUI 中的 ⚙️ 按鈕訪問設置：
- 語言選擇
- 主題（深色/淺色）
- 模型配置
- 技能提示自定義
- GAN 開關
- 自動打破沉默開關

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

### AI 指令
編輯 `data/agent_prompt.txt` 來自定義 AI 行為：
```
You are an assistant that can execute shell commands and use skills...
```

## 📦 創建自定義技能

### 技能結構
在 `skills/` 創建一個文件夾，包含 `SKILL.md` 文件：

```
skills/my-skill/
└── SKILL.md
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

1. **ThinkingEngine**：用於聊天、GAN 和反思的異步任務處理器
2. **Agent**：執行技能和 Shell 命令
3. **SkillsManager**：加載和管理技能的生命週期
4. **Memory**：持久化對話歷史
5. **Personality**：管理 AI 角色特徵

### 數據流
```
用戶輸入 → ThinkingEngine → LLM → Agent → 技能 → 回覆
                ↓
            記憶/持久化
```

## 🐛 故障排除

### LLM 服務器無響應
- 確保 llama.cpp 服務器正在運行：`llama\llama-server.exe -m models\model.gguf`
- 檢查 config.py 中的服務器 URL

### 技能不工作
- 驗證技能已啟用：`python main.py skills -list`
- 檢查 `data/skills_config.json` 中的技能配置

### 攝像頭訪問錯誤（detect-emotion）
- 確保沒有其他應用程序正在使用攝像頭
- 授予 Python 相機權限

## 📄 許可證

本項目採用 MIT 許可證 - 請參閱 [LICENSE](LICENSE) 文件。

## 🙏 致謝

- [llama.cpp](https://github.com/ggerganov/llama.cpp) - 本地 LLM 推理
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 現代化 Python UI
- [DeepFace](https://github.com/serengil/deepface) - 面部分析
- [OpenClaw](https://github.com/secondself/openclaw) - 技能框架靈感

## 📊 統計

![GitHub stars](https://img.shields.io/github/stars/A113NWu/Humanaize2-Project?style=social)
![GitHub forks](https://img.shields.io/github/forks/A113NWu/Humanaize2-Project?style=social)

---

**注意**：此軟件需要本地 LLM 服務器。Humanaize 提供框架但不包括 LLM 模型文件（因為體積較大）。請單獨下載兼容的 GGUF 模型。
