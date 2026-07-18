---
name: audio
description: AI音频识别技能，实现语音转文字、音频分析和声音识别
metadata:
  category: audio
  self_developed: true
  version: 1.0
---

Audio Skill

功能描述:
- 语音转文字（STT）
- 音频格式转换
- 声音类型识别（人声、音乐、环境音等）
- 音频内容分析
- 多语言语音识别支持

使用方法:
输出JSON格式调用技能:
{"skill": "audio", "input": {"action": "<action>", "params": {...}}}

支持的动作:
- transcribe: 语音转文字
- analyze: 分析音频内容
- detect_speech: 检测语音片段
- convert_format: 转换音频格式

输入参数:
- transcribe: {"audio_path": "/path/to/audio.wav"} 或 {"audio_base64": "base64_string"}
- analyze: {"audio_path": "/path/to/audio.wav"} 或 {"audio_base64": "base64_string"}
- detect_speech: {"audio_path": "/path/to/audio.wav"} 或 {"audio_base64": "base64_string"}
- convert_format: {"audio_path": "/path/to/audio.wav", "target_format": "mp3"}

输出格式:
返回JSON格式结果，包含识别文本和置信度。

依赖:
- whisper: OpenAI语音识别（首选）
- funasr: 阿里语音识别（备选）
- pydub: 音频格式转换
- librosa: 音频分析（可选）
