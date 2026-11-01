---
name: music-gen
description: "音乐生成：按曲风收集音频→NumPy 提取频谱→傅里叶逆变换合成新曲；action=collect/analyze/compose/list"
metadata:
  category: media
  self_developed: true
  version: 1.0
---

Music Gen Skill

功能:
- 按曲风从 archive.org 收集公共领域音频（也可以直接给 urls）
- 用 NumPy 把每条音频的频谱（FFT 幅度谱）提取成特征文件
- 汇总成曲风的"音色包络"档案
- 按曲风档案 + 分轨编曲（鼓组 / Bass / 琶音 / Saw Lead / Pad）合成波形，产出 wav/mp3

调用格式:
{"skill": "music-gen", "input": {"action": "compose", "title": "作品名", "genre": "jazz", "duration": 60, "seed": 123}}

注意: input 里用 action 字段（不是 command）；每个动作的必填参数必须带齐，缺什么就报错，不要靠猜。

曲风（genre）取值:
jazz / classical / blues / rock / electronic / folk / ambient / hiphop / pop / chinese / trance
（也可以写中文：爵士、古典、蓝调、摇滚、电子、民谣、氛围、嘻哈、流行、国风、迷幻/出神）
trance 就是 Uplifting Trance：138 BPM、A 小调为中心、i–VI–III–VII 和弦进行，
每拍底鼓 + 正拍十六分滚奏 Bass + 十六分琶音 + 三声部失谐 Saw Lead + 宽 Pad，并带侧链"泵"感。

动作:
- list: {"action": "list"} → 每个曲风已有的语料数量、是否已有频谱档案
- collect: {"action": "collect", "genre": "jazz", "limit": 3} → 下载到 corpus/<曲风>/，返回本地路径
  也可以自己给直链：{"action": "collect", "genre": "jazz", "urls": ["https://...mp3"]}
- analyze: {"action": "analyze", "genre": "jazz"} → 解码成 22050Hz 单声道，NumPy 做 FFT，
  保存每条曲目的频谱 npz，并写出该曲风的音色档案 profiles/<曲风>.json
- compose: {"action": "compose", "title": "我的第一首", "genre": "jazz", "duration": 60, "seed": 7}
  → 输出 works/<作品名>/song.mp3（另有 song.wav 与 meta.json）

合成原理（写曲子时用得上）:
1. 振荡器用傅里叶级数：锯齿波 = Σ sin(kωt)/k，方波 = 奇次 Σ sin(kωt)/k，谐波封顶 8kHz；
2. 每轨音色独立：Saw Lead 五声部失谐(±20 音分)+共振低通+混响，Bass 低通 700Hz，Pad 五声部做宽，鼓组单独合成；
3. 编曲按曲风：trance 是每拍底鼓 + 正拍 16 分滚奏 Bass + 16 分琶音 + Saw Lead + Pad + 侧链泵感；
   jazz 是 walking bass + 2/4 拍钢琴 comping + swing 旋律 + ride；
4. 各轨相加后做母线饱和，旋律/琶音/Pad 在右声道加 9ms Haas 延迟做立体声宽度，
   归一化到 0.92，首尾淡入淡出（输出为双声道 22050Hz）。
   同一个 seed 必须得到同一首曲子，想换风格就换 seed 或 genre。

推荐流程:
1. list 看有没有语料；没有就先 collect 2-3 首，再 analyze
2. 用 compose 生成（duration 按需要，60 秒就是 60）
3. 想换感觉时换 seed / genre 重跑一次，不要改代码里的公式

限制:
- 需要 ffmpeg（系统里有）；没有 ffmpeg 时仍能生成 wav，但无法解码 mp3 语料
- 收集需要联网；网络失败时 collect 会返回 errors，但 compose 仍能用语料的备用音色参数工作
