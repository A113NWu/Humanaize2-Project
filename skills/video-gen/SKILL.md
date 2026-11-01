---
name: video-gen
description: "生成视频：写含 renderFrame(t) 的 HTML，无头浏览器逐帧截图，FFmpeg 合成 mp4，从成片抽帧检查；action=download_assets/render_frames/build_video/sample_frames"
metadata:
  category: media
  self_developed: true
  version: 1.0
---

Video Gen Skill

功能:
- 用无头 Chrome/Edge 在浏览器里逐帧渲染你写的 HTML 动画
- PNG 序列用 FFmpeg 合成 mp4
- 从成片每秒抽一帧，便于检查画面
- 下载网上图片素材到本次作品目录

调用格式:
{"skill": "video-gen", "input": {"action": "render_frames", "name": "作品名", "html": "<完整 HTML>", "fps": 24, "duration": 60, "width": 1280, "height": 720}}

注意: input 里用 action 字段（不是 command）；每个 action 的必填参数必须带齐，缺参数会直接报错。
render_frames 的 duration 必须写成你的视频总秒数（例如 60 秒的视频就写 60），漏写会直接报错，不会猜。
HTML 里的标签属性统一用单引号（如 class='box'），避免和 JSON 字符串的双引号冲突导致解析失败。

动作:
- download_assets: {"action": "download_assets", "urls": ["https://...jpg"], "name": "作品名"} → 返回本地素材路径（urls 必填）
- render_frames: {"action": "render_frames", "html": "<完整 HTML>", "name": "作品名", "fps": 24, "duration": 60, "width": 1280, "height": 720} → 渲染 PNG 序列，返回 frames_dir 和 preview（首/中/末帧）。不需要外部图片时，第一步直接用这个，不要先调 download_assets
- build_video: {"action": "build_video", "name": "作品名", "fps": 24} → 合成 <作品目录>/video.mp4
- sample_frames: {"action": "sample_frames", "video": "视频绝对路径", "count": 6} → 从成片抽帧

HTML 约定（必须遵守，违反会导致整片空白/错位）:
- 必须定义 renderFrame(t)（或 drawFrame(t)），t 单位为秒；每帧只依据 t 画一次静态画面
- 禁止 requestAnimationFrame / setInterval / setTimeout / Date.now / 自播 animate() 循环；
  渲染器是「外部反复调用 renderFrame(t) 再截图」，页面自己跑动画会串帧。整幅画面必须在一次 renderFrame(t) 内同步画完。
- 同一个 t 必须永远得到同一画面：不要用「按调用次数累加」的变量（如 spot.x += speed），位置一律用 t 计算。
- 文字必须画在画面中心再叠加位移：y 坐标用 canvas.height/2 + offset，不要直接把 offset 当绝对 y（否则文字跑到顶部）。
- drawScene(i, ...) 这类函数里不要引用 renderFrame 循环内的局部变量（如 lt）；需要的时间/进度必须作为参数传进去。
- 多场景：用循环遍历所有场景，每个场景算局部时间 lt = t - i*段长，只在 lt 处于可见区间时绘制（相邻场景自然交叉过渡）。
- 画面尺寸固定为 width × height，body 无边距、无滚动条
- 需要图片素材时先用 download_assets 下载，HTML 里用返回的本地绝对路径（file:/// 或相对路径均可）

参考骨架（只示范结构，内容自己写）:
```
const scenes = [{title:'…', subtitle:'…'}, …];
const SEG = 60 / scenes.length;          // 每段秒数
function drawScene(i, alpha, yOffset) {
  const s = scenes[i];
  ctx.globalAlpha = alpha;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = 'bold 48px Microsoft YaHei';
  ctx.fillText(s.title, canvas.width/2, canvas.height/2 + yOffset);
  ctx.font = '24px Microsoft YaHei';
  ctx.fillText(s.subtitle, canvas.width/2, canvas.height/2 + 60 + yOffset);
}
function renderFrame(t) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  /* 背景：只用 t 算 */ 
  for (let i = 0; i < scenes.length; i++) {
    const lt = t - i * SEG;
    if (lt < -1.2 || lt >= SEG) continue;           // 不在可见区间
    let alpha = 1, y = 0;
    const exitStart = SEG - 1.4;
    if (lt < 0)        { const p = (lt + 1.2) / 1.2; alpha = p;         y = 40 * (1 - p); }
    else if (lt >= exitStart) { const p = (lt - exitStart) / 1.4; alpha = 1 - p; y = -30 * p; }
    drawScene(i, alpha, y);                          // 只画一次，绝不重复画同一场景
  }
}
```

每次修改后请用新的作品名（如 v2、v3、v4…）：渲染器会跳过已存在的帧，沿用旧名会导致新 HTML 根本没重新渲染。

推荐流程:
1. 确定分镜与时长（通常 3-6 秒，fps 24，1280x720）
2. 只有确实需要网上图片素材时，才先 download_assets（必须给 urls）；纯代码动画跳过这步
3. 写 HTML → render_frames
4. 用 vision 技能分析 preview 帧，画面没问题再 build_video
5. sample_frames 抽帧复查，最后把视频路径告诉用户

限制:
- 帧率、时长不设上限，由你按需要决定（帧数越多渲染越久，长视频可以在长任务里分段做）
- 依赖系统里的 Chrome/Edge 与 ffmpeg
