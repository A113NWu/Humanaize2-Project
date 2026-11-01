---
name: qq-group-chat
description: "QQ 群持续聊天：后台驱动 Tulpa 的 MCP 群聊循环（wait→决策→plan→send），带频率/静默时段限制；action=status/start/stop/set"
metadata:
  category: social
  self_developed: true
  version: 1.0
---

QQ Group Chat Skill

功能:
- 在授权的 QQ 群里让 Aize 持续接话：Tulpa 提供实时群消息，本技能负责「等消息 → 想想要不要接 → 规划 → 发送」这一整条循环
- 人格 = Aize 自己的自我人格 + 少量白龙娘式群聊语气（短、直接、冷幽默、不客服腔）
- 频率限制：最小间隔、每小时上限、凌晨静默时段，避免在别人的群里刷屏
- 托管读取：Tulpa 托管 SnowLuma 掉线（account_mismatch 等）时自动重试，把 QQ 链路拉回来

调用格式:
{"skill": "qq-group-chat", "input": {"action": "status"}}
{"skill": "qq-group-chat", "input": {"action": "start"}}
{"skill": "qq-group-chat", "input": {"action": "stop"}}
{"skill": "qq-group-chat", "input": {"action": "set", "enabled": true, "max_replies_per_hour": 3}}

注意:
- 只有 config.json 里 enabled=true 才会在服务启动后自动运行；换群、换人格、改频率都用 set 动作
- 发送权限来自 Tulpa 连接本身，本技能不扩权；停止会话后不会再发
- 群聊内容只用于当前这轮判断，不会写进长期记忆
