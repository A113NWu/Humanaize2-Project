---
name: long-task
description: "长期任务管理：记录带 Deadline 的任务、更新进度、安排休息窗口；action=create/list/update/done/rest/wake"
metadata:
  category: productivity
  self_developed: true
  version: 1.0
---

Long Task Skill

用途:
- 需要很久才能做完的事（例如用一段音频生成完整视频）先登记成长期任务，带截止时间
- 记进度和下一步，休息前把「下次继续时间」记下来，醒了继续做
- 休息窗口到点前，系统会把她所有后台活动暂停，不会忘掉任务

调用格式:
{"skill": "long-task", "input": {"action": "create", "title": "根据上传音频做一支 MV", "detail": "...", "deadline": "2026-11-02 20:00", "next_step": "先分析音频时长和节奏"}}

动作:
- create: title 必填；deadline 支持 "2026-11-02 20:00"
- list: 列出进行中的任务和剩余时间
- update: {"id": 1, "progress": "已完成分镜", "next_step": "渲染前 30 秒", "next_minutes": 25}
- done: {"id": 1}
- rest: {"minutes": 30, "reason": "去刷一会儿社交网站"} 或 {"until": "22:10"}
- wake: 立即结束休息

约定:
- 每完成一小段就 update 一次，写清进度和下一步
- 想休息就用 rest 定好时间；醒来后先 list 看一眼任务，再继续
- 视频这类大任务要分段推进，别一次做到没电
