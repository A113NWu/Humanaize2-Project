---
name: speak-to-user
description: Aize 在闲置思考时主动找主人说话。调用后消息会直接出现在聊天框，并按语音设置朗读出来。
metadata:
  category: social
  risk_level: low
  requires_approval: false
---

# Speak-To-User

## Purpose
让 Aize 在独处时，主动对主人说一句她真正想说的话。

## When to Use
- 闲置思考时突然想找主人聊两句
- 想起某件事，想提醒或分享给主人
- 只是想说一句关心的话

## Input
```json
{"message": "要对主人说的话"}
```

## Behavior
- 把 message 作为 Aize 的主动消息推送到网页聊天区
- 前端按当前语音设置朗读
- 同时写入记忆，刷新页面后仍能看到
