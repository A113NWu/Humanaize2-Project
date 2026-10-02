---
name: mc-bot
description: Minecraft 機器人技能，讓 Aize 進入 Java 版（1.20.1 離線/局域網）世界自主遊玩：規避危險、收集資源、跟隨玩家、收發聊天，大腦決策走本機 Aize API
metadata:
  category: gaming
  risk_level: medium
  requires_approval: false
  version: 1.0.0
  config_ui: config_ui.html
  config_file: config.json
  config_secret_fields:
    - aize.password
  service:
    command: node bot.js
---

# Minecraft 機器人技能

基於 mineflayer 的 Java 版 Minecraft 機器人（離線模式，1.20.1），讓 Aize 作為玩家進入局域網世界：

- 生存反射（不經 LLM，硬編碼保命）：苦力怕貼臉逃跑、低血逃跑、自動進食、被貼身時反擊
- 自主決策：每 45 秒向本機 Aize API 請求下一步行動（跟隨/砍樹/挖礦/探索/聊天）
- 遊戲內聊天：讀取聊天欄、由 Aize 生成回覆並發送
- 語音面板：隨服務啟動在 3939 端口提供網頁語音/文字對話（瀏覽器語音識別 → 遊戲內聊天）

## 運行方式

由 Dashboard 技能管理頁啟停（service.command），或手動執行 `node bot.js`（可用 `--host` / `--port` 覆蓋配置）。

## 配置

`config.json`（可從 Dashboard 技能配置界面修改）：

- `host` / `port` / `username` / `version`：目標伺服器與登錄名（離線模式）
- `aize.*`：本機 Aize API 地址、登錄賬號密碼（密碼在接口中脫敏）、決策間隔
- `web.port`：語音面板端口（預設 3939）
- `safety.*`：逃跑血量、進食飢餓值、危險掃描半徑等
