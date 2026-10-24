---
name: meeting-attend
description: 接入線上會議（騰訊會議/Zoom 等任意會議軟件）的語音——捕獲系統音頻轉寫逐字稿，定期生成會議摘要。當用戶要求 Aize 旁聽/記錄/總結會議時使用。
---

# Meeting Attend

Aize 旁聽線上會議：捕獲會議聲音 → 實時語音轉寫 → 每 5 分鐘自動生成摘要推送到聊天中樞。

## 工作原理
- 音頻源：WASAPI loopback（直接捕獲揚聲器輸出，無需虛擬聲卡）；不可用時退回麥克風（會議需外放）
- 識別：Google 語音識別（網絡，中文優先，英文兜底），無需本地模型
- 逐字稿落盤：`%LOCALAPPDATA%\Humanaize2\data\meeting\transcript.txt`
- 摘要：每 5 分鐘且新內容 ≥200 字時自動生成，推送到聊天中樞（web UI 可見）

## Actions
- `start`: 開始旁聽 `{action:"start"}`
- `stop`: 停止旁聽 `{action:"stop"}`
- `status`: 狀態（運行中/音頻源/行數/最新摘要）`{action:"status"}`
- `summary`: 立即生成一次摘要 `{action:"summary"}`
- `transcript`: 取最近逐字稿 `{action:"transcript", limit:50}`

## 使用節奏
- 用戶說「開始旁聽會議/記錄會議」→ start；「總結一下剛才的會議」→ summary 後取 status 裡的 summary 回答
- 會議結束記得主動 stop，避免空跑浪費識別請求
- 若 status 的 error 非空，告訴用戶具體錯誤（常見：識別網絡不通、無音頻後端）
