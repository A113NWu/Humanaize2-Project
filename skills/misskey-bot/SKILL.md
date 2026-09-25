---
name: misskey-bot
description: Misskey 機器人技能，讓 Aize 在 hub.imikufans.com 發文、回覆提及、讀取時間線；賬號標註為機器人，所有發出內容經敏感詞過濾
metadata:
  category: social
  risk_level: medium
  requires_approval: false
  version: 1.0.0
---

# Misskey 機器人技能

接入 Misskey 實例（預設 hub.imikufans.com），支持：
- `configure` 配置實例地址與 access token（保存在技能目錄 config.json，勿提交）
- `set_bot` 調用 `i/update` 把賬號標註為機器人（isBot=true）
- `post` 發文（notes/create，可設 visibility）
- `reply` 回覆指定帖子
- `mentions` 讀取提及通知
- `timeline` 讀取本地/首頁時間線
- `status` 查看配置與連線狀態

所有發出內容（post/reply）一律經過 content_filter 過濾；命中敏感詞直接拒絕發送。

## 配置方式

```json
{"skill": "misskey-bot", "input": {"action": "configure", "params": {"host": "hub.imikufans.com", "token": "你的access token"}}}
```

token 獲取：登入目標實例 → 設定 → API → 生成訪問令牌（權限勾選 write:notes, read:notifications, write:account）。
配置後務必執行一次 `set_bot` 完成機器人標註。
