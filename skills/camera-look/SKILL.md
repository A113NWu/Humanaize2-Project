---
name: camera-look
description: 主动打开主人电脑/手机的摄像头看一眼，并由视觉模型读懂画面。想知道主人在做什么、表情、环境，或需要确认画面内容时使用。
metadata:
  category: vision
  risk_level: low
  requires_approval: false
---

# Camera-Look

## Purpose
让 Aize 在好奇或需要确认时，主动用摄像头看一眼当前画面。

## When to Use
- 想知道主人现在在做什么、是不是在忙
- 想确认主人当下的表情或周围环境
- 对话里需要「看一眼」才能回答

## Input
```json
{"question": "想看什么（可省略）", "timeout": 30}
```

## Behavior
- 向网页面板发起取景请求，网页拍一帧后回传
- 图片保存到本机 uploads，再由视觉模型读成文字返回
- 需要网页面板处于打开状态并允许摄像头权限
- 没有配置视觉模型时，只能返回图片的基本信息，无法描述内容

## 注意
不要频繁调用；每次调用都会短暂占用摄像头。
