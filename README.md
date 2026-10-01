# Humanaize2

本地运行的 AI 桌面伴侣：网页面板聊天、本地/云端模型、记忆、技能（Shell/搜索等）、语音、空闲自主活动。MIT。

> [English](./docs/README_en.md)

## 下载与安装

从 [Releases](https://github.com/A113NWu/Humanaize2-Project/releases) 下载 `Humanaize2-Setup-x86_64-vX.X.X.exe`，运行安装。便携版用 `*-portable.zip` 解压即用。

要求：Windows 10/11 x64，8GB+ 内存（跑本地模型）。模型需自备（GGUF 文件），或用云端 API（见下）。

## 启动方式

| 方式 | 行为 |
|---|---|
| 双击 Humanaize2.exe（默认） | 弹出「Humanaize2 日誌」窗口 + 系统托盘图标，自动打开浏览器面板 `http://127.0.0.1:8082` |
| `Humanaize2.exe --tray` | 无日志窗口，直接最小化到系统托盘 |
| 关掉日志窗口 | 日志隐藏，程序继续在托盘运行（不是退出） |
| 托盘右键 | 「打開管理面板」/「退出 Humanaize2」（退出请走托盘菜单） |
| `humanaize2 boot -m cli` | 终端 CLI 模式 |

首次启动绑定 0.0.0.0 可能弹防火墙提示，点「允许」。

## 配置（重点）

所有配置在浏览器面板左侧 **设置** 页完成，保存后立即生效，无需重启。

### 1. 模型（最关键，先配这个）

二选一：

- **本地模型**：在设置「基础」区填 `model_path`（一个 `.gguf` 文件的完整路径，支持热切换）。程序自动拉起同目录 `llama/` 下的 llama-server（端口 8080）。CPU 机器建议 Qwen2.5-3B-Instruct Q4 起步；2B 以下的小量化模型容易答非所问。
- **云端模型（OpenAI 兼容）**：勾选「启用 OpenAI API 模式」，填三项：
  - OpenAI API Key
  - Base URL（如 `https://api.qnaigc.com/v1`，任何 OpenAI 兼容网关均可）
  - 模型名（如 `minimax/minimax-m3`）

`max_tokens`、`temperature` 同页可调。

### 2. 安全（跨设备访问）

设置 → 安全：

- **允许局域网访问**：开关。关闭时只有本机能打开面板；打开后同一局域网设备可访问 `http://<本机IP>:8082`（建议配合账号密码使用）。
- **登录账号密码**：设置用户名和密码后，打开面板必须先登录（7 天免登录）。留空密码字段表示不修改；清空用户名即关闭登录。

### 3. 技能

设置里有技能总开关；单个技能可用命令管理：

```
humanaize2 skills -list
humanaize2 skills -enable shell
humanaize2 skills -disable shell
humanaize2 skills -install skill.zip
```

`shell` 技能会在本机执行命令，仅在信任环境启用。

### 4. 提示词自定义（Prompt 目录）

安装目录下的 **`Prompt\`** 文件夹有约 40 个 `.txt` 提示词（`system_prompt.txt`、`agent_prompt.txt`、`should_answer_user.txt`、`social_decide.txt` 等）：

- 直接用记事本改，**每次对话实时读取，改完立即生效，不用重启**。
- 升级不会覆盖你改过的文件；删掉的文件重启时恢复默认。

### 5. 数据与记忆

数据在安装目录的 **`data\`** 文件夹：

| 文件 | 内容 |
|---|---|
| `ui_settings.json` | 设置页所有配置（模型路径、API Key、开关等） |
| `memory.json` | 对话记忆（最多保留最近 100 条） |
| `personality.json` | 人格 |
| `sensitive_words.txt` | 敏感词表（每行一个，`#` 注释，热生效） |
| `skills_config.json` | 技能启用状态 |

换电脑时把 `data\` 整个拷走即可迁移记忆和配置。

### 6. 其他常用配置

- **自定义壁纸**：在安装目录建 `Assets\` 文件夹，放入 `Background.jpg`（或 `.jpeg`/`.png`），刷新页面生效。
- **IoT / 守护 / GAN / 主动说话**：均在设置页对应分区开关（`iot_auto_start`、`guard_enabled`、`gan_enabled`、`auto_break_silence`）。
- **语音**：点聊天输入框右下角麦克风（变红脉动=开启），说话自动发送，回复流式朗读；纯打字不会触发语音。语音识别用浏览器 Web Speech API（推荐 Chrome/Edge），朗读用微软 edge-tts（需联网）。

## 常用命令

```
humanaize2 boot [-m cli|gui|win-gui]   # 启动（默认网页面板）
humanaize2 settings                    # 设置
humanaize2 skills -list|-enable|-disable|-install
humanaize2 check-server                # 检查本地 llama-server
humanaize2 update [-f]                 # 检查/强制更新
humanaize2 help
```

CLI 聊天内置命令：`/help` `/mem` `/status` `/gan` `/clear` `/quit`。

## 从源码运行

```
git clone https://github.com/A113NWu/Humanaize2-Project.git
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python src/core/windows_main.py
```

## 常见问题

- **面板打不开**：看日志窗口有没有报错；确认 8082 端口未被占用；`http://127.0.0.1:8082/health` 返回 `ok` 即正常。
- **AI 不回复 / 空回复**：先看设置里模型路径或云端三项是否正确；云端网关可能需要先在服务商处开通推理服务。
- **开了系统代理后连不上**：程序默认绕过系统代理直连；本机代理没运行时请关掉代理软件的系统代理开关。
- **Skill 输出中文乱码**：已做 GBK/UTF-8 自适应解码，如仍出现请反馈所用终端。
- **升级后行为没变**：浏览器按 Ctrl+F5 硬刷新清缓存。
