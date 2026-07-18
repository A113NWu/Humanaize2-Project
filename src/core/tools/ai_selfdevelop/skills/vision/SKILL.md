---
name: vision
description: AI图像识别技能，实现图片内容分析、OCR文字提取和图像理解
metadata:
  category: vision
  self_developed: true
  version: 1.0
---

Vision Skill

功能描述:
- 图片内容分析和理解
- OCR文字识别和提取
- 图像特征检测（人脸、物体、场景）
- 图片描述生成
- 多语言文字识别支持

使用方法:
输出JSON格式调用技能:
{"skill": "vision", "input": {"action": "<action>", "params": {...}}}

支持的动作:
- analyze: 分析图片内容
- ocr: 识别图片中的文字
- describe: 描述图片内容
- detect_objects: 检测图片中的物体
- extract_text: 提取图片中的文字

输入参数:
- analyze: {"image_path": "/path/to/image.jpg"} 或 {"image_base64": "base64_string"}
- ocr: {"image_path": "/path/to/image.jpg"} 或 {"image_base64": "base64_string"}
- describe: {"image_path": "/path/to/image.jpg"} 或 {"image_base64": "base64_string"}
- detect_objects: {"image_path": "/path/to/image.jpg"} 或 {"image_base64": "base64_string"}
- extract_text: {"image_path": "/path/to/image.jpg"} 或 {"image_base64": "base64_string"}

输出格式:
返回JSON格式结果，包含识别结果和置信度。

依赖:
- pillow: 图片处理
- pytesseract: OCR识别（需要安装tesseract-ocr）
- transformers: 图像理解模型（可选）
