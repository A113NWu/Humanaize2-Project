---
name: live2d
description: 控制 Aize 的 Live2D 虛擬形象——說話（帶唇形同步）、動作、表情；管理 B 站直播彈幕接入與虛擬攝像頭（進會議/直播軟件）。當需要讓 Aize 以虛擬形象表現、參與會議或直播互動時使用。
metadata:
  category: avatar
  risk_level: low
  requires_approval: false
---

# Live2D Skill

## Purpose
Aize 的 Live2D 形象運行在 `http://localhost:8082/live2d`（免費默認模型 Hiyori）。
此技能讓 Aize 控制形象說話、做動作表情，並接入直播彈幕與虛擬攝像頭。

## When to Use
- 日常對話中帶著情緒或動作回應時：主動用 `motion`/`expression` 配合你說的話（例如打招呼、開心、無奈、思考時），讓形象是「活的」而不是只動嘴
- 想讓 Aize 用 Live2D 形象說某句話（帶 TTS 與唇形）
- 直播/會議中讓形象做動作、換表情
- 開始/停止接收 B 站直播間彈幕
- 需要虛擬攝像頭進會議軟件時查設置方法或啟動 OBS

## 對話中的使用節奏
- 你每次回覆時可以順手調用一次 motion（推薦 TapBody），讓身體配合語氣；不要連續刷動作，一個回合 0~1 次即可
- 有明顯情緒時加 expression；平實回答就不用
- 注意：日常聊天頁回覆時系統已自動讓形象動作和開口，普通對話你不需要**频繁**調 speak/motion；只有你想指定特定動作/表情，或在直播、會議等特殊場景時才主動調用

## Actions
- `speak`: 讓形象說話 `{action:"speak", text:"..."}`
- `motion`: 播放動作 `{action:"motion", group:"TapBody", index:0}`（index 可選，不給則隨機；可用組：Idle、TapBody）
- `expression`: 切換表情 `{action:"expression", name:"..."}`
- `chat`: 注入一條外部聊天消息進互動閉環 `{action:"chat", text:"...", user:"名字", source:"meeting"}`
- `danmu_start`: 接入 B 站彈幕 `{action:"danmu_start", room_id:12345}`
- `danmu_stop`: 停止彈幕
- `start_obs`: 啟動 OBS 並開虛擬攝像頭
- `vcam_guide`: 查看虛擬攝像頭/直播接入完整設置說明
- `status`: 查看中樞與彈幕狀態

## Examples

**說話：**
```json
{"skill": "live2d", "input": {"action": "speak", "text": "大家好，歡迎來到直播間！"}}
```

**直播彈幕：**
```json
{"skill": "live2d", "input": {"action": "danmu_start", "room_id": 22603245}}
```

## Notes
- 彈幕消息流程：danmu → chat_in → Live2D 頁面 → /api/live2d/chat → Aize 回復 → speak。Aize 可以聊天框回復也可以語音回復（語音由頁面 TTS 播放）。
- 人聲語音輸入：打開 Live2D 頁面點 🎤 按鈕（瀏覽器語音識別）。
- 依賴 websockets + brotli（僅彈幕功能需要）。
