#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频生成技能：浏览器逐帧渲染 -> 抽帧检查 -> FFmpeg 合成。

核心思路：
- Aize 自己写一段 HTML（里面必须有 renderFrame(t) 函数，t 为秒），
  技能用无头 Chrome/Edge 对每一帧单独截图（?frame=i&fps=24 决定 t），
- 先把 PNG 序列渲染出来，可挑几张用 vision 技能检查，
- 再用 ffmpeg 把 PNG 序列拼成 mp4；也可以用 sample_frames 从成片抽帧复查。
"""

import os
import re
import sys
import json
import time
import shutil
import subprocess
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DEFAULT_FPS = 24
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_LAST_WORKDIR: Optional[str] = None


def _latest_workdir() -> Optional[str]:
    """最近一次渲染过帧的作品目录（模型漏写 name 时用于 build/sample 兜底）。"""
    global _LAST_WORKDIR
    if _LAST_WORKDIR and os.path.isdir(os.path.join(_LAST_WORKDIR, "frames")):
        return _LAST_WORKDIR
    root = _media_root()
    best, best_time = None, 0.0
    try:
        for d in os.listdir(root):
            p = os.path.join(root, d)
            f = os.path.join(p, "frames")
            if os.path.isdir(f):
                mt = os.path.getmtime(f)
                if mt > best_time:
                    best, best_time = p, mt
    except Exception:
        return None
    return best


# ---------------------------------------------------------------- paths
def _data_dir() -> str:
    """数据根目录（dev 用 data/，打包用 exe 旁 data/）。"""
    for mod in ("app_paths", "core.app_paths"):
        try:
            m = __import__(mod, fromlist=["app_data_dir"])
            base = m.app_data_dir()
            if base:
                os.makedirs(base, exist_ok=True)
                return base
        except Exception:
            continue
    base = os.path.join(_PROJECT_ROOT, "data")
    os.makedirs(base, exist_ok=True)
    return base


def _media_root() -> str:
    root = os.path.join(_data_dir(), "media", "videos")
    os.makedirs(root, exist_ok=True)
    return root


def _browser_exe() -> Optional[str]:
    """找无头浏览器：环境变量 > Chrome > Edge。"""
    env = os.environ.get("HUMANAIZE_BROWSER")
    if env and os.path.exists(env):
        return env
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    for name in ("chrome", "msedge", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _ffmpeg_exe() -> Optional[str]:
    """找 ffmpeg：PATH > 常见安装路径 > 项目内置。"""
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = [
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.join(_PROJECT_ROOT, "skills", "mc-bot", "node_modules",
                     "@ffmpeg-installer", "win32-x64", "ffmpeg.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    try:
        import imageio_ffmpeg  # 可选依赖
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _safe_name(name: str) -> str:
    name = re.sub(r"[^0-9A-Za-z_\-]+", "_", str(name or "").strip())
    return name or time.strftime("video_%Y%m%d_%H%M%S")


# ---------------------------------------------------------------- render
_HARNESS = """
<script>
window.addEventListener('load', function () {
  try {
    var q = new URLSearchParams(location.search);
    var i = parseInt(q.get('frame') || '0', 10);
    var fps = parseFloat(q.get('fps') || '24');
    if (typeof renderFrame === 'function') { renderFrame(i / fps); }
    if (typeof drawFrame === 'function') { drawFrame(i / fps); }
  } catch (e) { document.title = 'ERR ' + e; }
});
</script>
"""


def _inject_harness(html: str) -> str:
    """把逐帧 harness 注入到 </body> 前（有 renderFrame 才注入）。"""
    if "renderFrame" not in html and "drawFrame" not in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", _HARNESS + "</body>", 1)
    return html + _HARNESS


def _shot(exe: str, page_uri: str, png_path: str, width: int, height: int,
          profile_dir: str) -> bool:
    cmd = [
        exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--disable-extensions", "--mute-audio",
        "--disable-background-networking", "--disable-sync",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        "--virtual-time-budget=1500",
        f"--screenshot={png_path}",
        page_uri,
    ]
    try:
        subprocess.run(cmd, timeout=25, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except Exception:
        return False
    return os.path.exists(png_path) and os.path.getsize(png_path) > 0


class _RenderJsError(RuntimeError):
    """renderFrame(t) 抛出的 JS 异常（要把原始报错回传给模型，让它自己改 HTML）。"""


def _html_digest(payload: str, fps: int, width: int, height: int, total: int) -> str:
    import hashlib
    raw = "%s|%s|%s|%s|%s" % (payload, fps, width, height, total)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _render_with_cdp(page_path: str, frames_dir: str, total: int, fps: int,
                     width: int, height: int) -> Optional[List[int]]:
    """用 Chrome DevTools Protocol 复用同一个浏览器进程逐帧截图。

    CDP 每帧只调一次 renderFrame + captureScreenshot（约几十毫秒），
    比每帧启动一次 Chrome 快几十倍。返回失败帧号；None 表示 CDP 不可用。
    """
    try:
        import base64
        import json as _json
        import urllib.request
        import websocket  # websocket-client
    except Exception:
        return None
    exe = _browser_exe()
    if not exe:
        return None

    port = _free_port()
    # 每次渲染都用全新 profile：旧进程异常残留会锁住同名 profile，
    # 导致 Chrome 啟動後直接轉交舊實例、CDP 連不上，慢到逐帧啟動。
    import tempfile
    profile = tempfile.mkdtemp(prefix="cdp-", dir=os.path.dirname(frames_dir))
    cmd = [
        exe, "--headless=new", f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}", f"--window-size={width},{height}",
        "--disable-gpu", "--hide-scrollbars", "--mute-audio", "--no-first-run",
        "--disable-extensions", "--disable-background-networking", "--disable-sync",
        "--disable-dev-shm-usage", "--force-device-scale-factor=1",
        "--no-proxy-server", "about:blank",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        ws_url = None
        for _ in range(120):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/json/list", timeout=1) as resp:
                    targets = _json.loads(resp.read().decode("utf-8"))
                pages = [t for t in targets if t.get("type") == "page"]
                if pages:
                    ws_url = pages[0].get("webSocketDebuggerUrl")
                    break
            except Exception:
                pass
            time.sleep(0.15)
        if not ws_url:
            return None

        ws = websocket.create_connection(ws_url, timeout=15)
        msg_id = [0]

        def call(method: str, params: Optional[dict] = None) -> dict:
            msg_id[0] += 1
            ws.send(_json.dumps({"id": msg_id[0], "method": method,
                                 "params": params or {}}))
            while True:
                msg = _json.loads(ws.recv())
                if msg.get("id") == msg_id[0]:
                    if "error" in msg:
                        raise RuntimeError(str(msg["error"]))
                    return msg.get("result", {})

        call("Page.enable")
        call("Runtime.enable")
        # 固定視口尺寸，避免 headless 視窗邊框讓截圖尺寸偏小
        call("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height,
            "deviceScaleFactor": 1, "mobile": False,
        })
        page_uri = "file:///" + os.path.abspath(page_path).replace(os.sep, "/")
        call("Page.navigate", {"url": page_uri})
        time.sleep(0.4)
        has_render = call("Runtime.evaluate", {
            "expression": "typeof renderFrame === 'function' || typeof drawFrame === 'function'",
            "returnByValue": True,
        }).get("result", {}).get("value")
        if not has_render:
            return None

        failed = []
        for i in range(total):
            png = os.path.join(frames_dir, "frame_%04d.png" % i)
            if os.path.exists(png):
                continue
            try:
                # renderFrame(t)：t 为秒，每帧只画一次静态画面
                resp = call("Runtime.evaluate", {
                    "expression": "(typeof renderFrame==='function'?renderFrame:drawFrame)(%s)"
                                  % repr(i / float(fps))
                })
                exc = resp.get("exceptionDetails")
                if exc:
                    desc = (exc.get("exception") or {}).get("description") or exc.get("text") or "未知错误"
                    raise _RenderJsError(
                        "renderFrame(%s) 运行出错（第 %d 帧）：%s"
                        % (i / float(fps), i, str(desc).split("\n")[0]))
                shot = call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
                with open(png, "wb") as f:
                    f.write(base64.b64decode(shot.get("data", "")))
            except _RenderJsError:
                raise
            except Exception:
                failed.append(i)
        return failed
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _render_with_selenium(page_uri: str, frames_dir: str, total: int, fps: int,
                          width: int, height: int) -> Optional[List[int]]:
    """用 Selenium 复用同一个浏览器实例逐帧截图（比每帧启动 Chrome 快几十倍）。

    返回失败的帧号列表；返回 None 表示 Selenium/驱动不可用（调用方回退 CLI 方案）。
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except Exception:
        return None
    opts = Options()
    for arg in (
        "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
        "--no-first-run", "--disable-extensions", "--disable-background-networking",
        "--disable-sync", "--disable-dev-shm-usage",
        "--force-device-scale-factor=1", f"--window-size={width},{height}",
    ):
        opts.add_argument(arg)
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception:
        return None
    failed = []
    try:
        driver.get(page_uri)
        time.sleep(0.2)
        has_render = driver.execute_script(
            "return typeof renderFrame === 'function' || typeof drawFrame === 'function'")
        if not has_render:
            return None
        for i in range(total):
            png = os.path.join(frames_dir, "frame_%04d.png" % i)
            if os.path.exists(png):
                continue
            try:
                # renderFrame(t)：t 为秒，每帧只画一次静态画面
                driver.execute_script(
                    "var f=(typeof renderFrame==='function')?renderFrame:drawFrame;"
                    "f(arguments[0]);", i / float(fps))
                driver.save_screenshot(png)
            except Exception:
                failed.append(i)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return failed


def _render_frames(html: str, workdir: str, fps: int, duration: float,
                   width: int, height: int) -> Dict[str, Any]:
    exe = _browser_exe()
    if not exe:
        return {"success": False, "error": "找不到 Chrome/Edge，无法在浏览器里渲染"}
    if "renderFrame" not in html and "drawFrame" not in html:
        return {"success": False,
                "error": "HTML 里必须有 renderFrame(t) 函数（t 为秒），每帧画一次画面"}
    total = int(round(float(fps) * float(duration)))
    if total <= 0:
        return {"success": False, "error": "帧数必须大于 0"}

    os.makedirs(workdir, exist_ok=True)
    frames_dir = os.path.join(workdir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    page_path = os.path.join(workdir, "page.html")
    payload = _inject_harness(html)
    digest = _html_digest(payload, fps, width, height, total)
    hash_path = os.path.join(workdir, ".html_hash")
    old_digest = ""
    try:
        with open(hash_path, "r", encoding="utf-8") as f:
            old_digest = f.read().strip()
    except Exception:
        old_digest = ""
    if old_digest != digest:
        # HTML/参数变了：旧帧与当前画面不一致，必须先作废
        for fn in os.listdir(frames_dir):
            if fn.startswith("frame_") and fn.endswith(".png"):
                try:
                    os.remove(os.path.join(frames_dir, fn))
                except Exception:
                    pass
        try:
            with open(hash_path, "w", encoding="utf-8") as f:
                f.write(digest)
        except Exception:
            pass
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(payload)
    page_uri = "file:///" + os.path.abspath(page_path).replace(os.sep, "/")
    profile = os.path.join(workdir, ".browser")
    os.makedirs(profile, exist_ok=True)

    try:
        failed = _render_with_cdp(page_path, frames_dir, total, fps, width, height)
    except _RenderJsError as e:
        return {"success": False, "error": str(e), "frames_dir": frames_dir}
    if failed is None:
        failed = _render_with_selenium(page_uri, frames_dir, total, fps, width, height)
    if failed is None:
        # 快路径不可用：回退为逐帧启动浏览器
        failed = []
        for i in range(total):
            png = os.path.join(frames_dir, "frame_%04d.png" % i)
            if os.path.exists(png):
                continue
            ok = _shot(exe, f"{page_uri}?frame={i}&fps={fps}&total={total}", png,
                       width, height, profile)
            if not ok:
                failed.append(i)
    if failed:
        return {"success": False, "error": f"有 {len(failed)} 帧渲染失败（例如第 {failed[:5]} 帧）",
                "frames_dir": frames_dir}

    preview_idx = [0, total // 2, total - 1]
    return {
        "success": True,
        "message": f"已渲染 {total} 帧",
        "frames_dir": frames_dir,
        "total_frames": total,
        "fps": fps,
        "width": width,
        "height": height,
        "preview": [os.path.join(frames_dir, "frame_%04d.png" % i) for i in preview_idx],
    }


def _build_video(frames_dir: str, output: str, fps: int) -> Dict[str, Any]:
    exe = _ffmpeg_exe()
    if not exe:
        return {"success": False, "error": "找不到 ffmpeg，无法合成视频"}
    cmd = [
        exe, "-y", "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", output,
    ]
    try:
        proc = subprocess.run(cmd, timeout=180, capture_output=True, text=True)
    except Exception as e:
        return {"success": False, "error": f"ffmpeg 运行失败：{e}"}
    if proc.returncode != 0 or not os.path.exists(output):
        return {"success": False, "error": "ffmpeg 合成失败",
                "stderr": (proc.stderr or "")[-400:]}
    size = os.path.getsize(output)
    return {"success": True, "message": "视频合成完成", "video": output,
            "size_bytes": size}


def _sample_frames(video: str, workdir: str, count: int = 6) -> Dict[str, Any]:
    exe = _ffmpeg_exe()
    if not exe:
        return {"success": False, "error": "找不到 ffmpeg，无法抽帧"}
    if not os.path.exists(video):
        return {"success": False, "error": f"视频不存在：{video}"}
    out_dir = os.path.join(workdir, "review")
    os.makedirs(out_dir, exist_ok=True)
    cmd = [exe, "-y", "-i", video, "-vf", "fps=1",
           "-frames:v", str(max(1, int(count))),
           os.path.join(out_dir, "shot_%02d.png")]
    try:
        proc = subprocess.run(cmd, timeout=90, capture_output=True, text=True)
    except Exception as e:
        return {"success": False, "error": f"ffmpeg 抽帧失败：{e}"}
    if proc.returncode != 0:
        return {"success": False, "error": "ffmpeg 抽帧失败",
                "stderr": (proc.stderr or "")[-400:]}
    files = sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir)
                   if f.startswith("shot_") and f.endswith(".png"))
    return {"success": True, "message": f"抽出 {len(files)} 张检查帧",
            "frames": files, "review_dir": out_dir}


def _download_assets(urls: List[str], workdir: str) -> Dict[str, Any]:
    os.makedirs(workdir, exist_ok=True)
    assets_dir = os.path.join(workdir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    saved, errors = [], []
    for idx, url in enumerate(urls[:8]):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read(12 * 1024 * 1024)
            ext = ".png"
            ctype = ""
            try:
                ctype = resp.headers.get("Content-Type", "")
            except Exception:
                pass
            if "jpeg" in ctype or "jpg" in ctype:
                ext = ".jpg"
            elif "webp" in ctype:
                ext = ".webp"
            elif "gif" in ctype:
                ext = ".gif"
            path = os.path.join(assets_dir, f"asset_{idx + 1}{ext}")
            with open(path, "wb") as f:
                f.write(data)
            try:
                from PIL import Image
                with Image.open(path) as im:
                    im.verify()
            except Exception:
                try:
                    os.remove(path)
                except Exception:
                    pass
                raise
            saved.append(path)
        except Exception as e:
            errors.append(f"{url} -> {e}")
    return {"success": bool(saved), "assets": saved, "assets_dir": assets_dir,
            "errors": errors}


# ---------------------------------------------------------------- audio / MV
def _decode_pcm(audio: str, max_seconds: float):
    """用 ffmpeg 解成 22050Hz 单声道 s16le 原始样本，避免引入 numpy。"""
    exe = _ffmpeg_exe()
    if not exe:
        raise RuntimeError("找不到 ffmpeg")
    cmd = [exe, "-v", "error", "-i", audio, "-t", str(max_seconds),
           "-ac", "1", "-ar", "22050", "-f", "s16le", "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=150)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or b"").decode("utf-8", "ignore")[-300:])
    return proc.stdout, 22050


def _analyze_audio(audio: str, max_seconds: float = 180) -> Dict[str, Any]:
    """分析曲子的 BPM / 拍号 / 重音位置，供分镜卡点。"""
    from array import array
    import math
    if not os.path.exists(audio):
        return {"success": False, "error": f"音频不存在：{audio}"}
    try:
        raw, rate = _decode_pcm(audio, max_seconds)
    except Exception as e:
        return {"success": False, "error": f"解码失败：{e}"}
    hop = 512
    samples = array("h")
    samples.frombytes(raw[: len(raw) - len(raw) % 2])
    energy = []
    for i in range(0, len(samples) - hop, hop):
        chunk = samples[i:i + hop]
        energy.append(sum(abs(v) for v in chunk) / hop)

    if len(energy) < 16:
        return {"success": False, "error": "音频太短，无法分析"}

    peak = max(energy) or 1.0
    energy = [v / peak for v in energy]
    onset = [max(0.0, energy[i] - energy[i - 1]) for i in range(1, len(energy))]
    smooth = [sum(onset[max(0, i - 1):i + 2]) / 3.0 for i in range(len(onset))]

    frame_rate = rate / hop
    mean = sum(smooth) / len(smooth)
    centered = [v - mean for v in smooth]

    def _lag_score(lag):
        if lag <= 0 or lag >= len(centered):
            return 0.0
        total = sum(centered[i] * centered[i + lag] for i in range(len(centered) - lag))
        return total / (len(centered) - lag)

    min_lag = max(2, int(frame_rate * 60 / 240))
    max_lag = min(len(centered) // 2, int(frame_rate * 60 / 30))
    best_lag, best_score = 0, 0.0
    for lag in range(min_lag, max_lag + 1):
        score = _lag_score(lag)
        bpm = 60 * frame_rate / lag
        if bpm < 60:
            score *= 0.7   # 优先 60-180 的常见速度
        if score > best_score:
            best_lag, best_score = lag, score

    bpm = 60 * frame_rate / best_lag if best_lag else 0.0
    while bpm and bpm < 70:
        bpm *= 2
    while bpm and bpm > 180:
        bpm /= 2
    best_lag = int(round(60 * frame_rate / bpm)) if bpm else best_lag

    # 拍号：比较 3 拍 / 4 拍重复的强度；只有 3 拍明显更强才判 3/4
    meter = "4/4"
    if best_lag:
        score3 = _lag_score(best_lag * 3)
        score4 = _lag_score(best_lag * 4)
        if score4 > 0 and score3 > score4 * 1.8:
            meter = "3/4"

    # 相位：找一个偏移，让拍点落在能量上升处
    phase, phase_score = 0, -1.0
    if best_lag:
        for offset in range(best_lag):
            total = sum(smooth[i] for i in range(offset, len(smooth), best_lag))
            if total > phase_score:
                phase, phase_score = offset, total

    duration = len(samples) / rate
    beats = []
    t = phase / frame_rate if best_lag else 0.0
    step = best_lag / frame_rate if best_lag else 0.0
    while step and t < duration and len(beats) < 400:
        beats.append(round(t, 2))
        t += step

    # 重音：能量上升的局部峰，用来卡大动作/转场
    accents = []
    threshold = mean + (math.sqrt(sum((v - mean) ** 2 for v in smooth) / len(smooth)) * 1.3)
    min_gap = max(1, int(frame_rate * 0.12))
    last_idx = -min_gap
    for i in range(1, len(smooth) - 1):
        if smooth[i] >= threshold and smooth[i] >= smooth[i - 1] and smooth[i] >= smooth[i + 1] \
                and i - last_idx >= min_gap:
            accents.append(round(i / frame_rate, 2))
            last_idx = i
        if len(accents) >= 80:
            break

    return {
        "success": True,
        "audio": audio,
        "duration": round(duration, 2),
        "bpm": round(bpm, 1),
        "beat_interval": round(step, 3),
        "meter": meter,
        "beats": beats,
        "accents": accents,
        "analyzed_seconds": round(duration, 2),
    }


def _build_mv(video: str, audio: str, workdir: str, output: str = "",
              start: float = 0.0, audio_volume: float = 1.0,
              keep_original: bool = False, original_volume: float = 0.25) -> Dict[str, Any]:
    """把画面和曲子合成 MV（H.264 + AAC，faststart）。"""
    exe = _ffmpeg_exe()
    if not exe:
        return {"success": False, "error": "找不到 ffmpeg，无法合成 MV"}
    for path, label in ((video, "视频"), (audio, "音频")):
        if not os.path.exists(path):
            return {"success": False, "error": f"{label}不存在：{path}"}
    out = output or os.path.join(workdir, "mv.mp4")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    has_original = False
    if keep_original:
        try:
            probe = subprocess.run([exe, "-i", video], capture_output=True, text=True, timeout=30)
            has_original = "Audio:" in (probe.stderr or "")
        except Exception:
            has_original = False

    cmd = [exe, "-y", "-i", video]
    if start:
        cmd += ["-ss", str(start)]
    cmd += ["-i", audio]
    if has_original:
        cmd += ["-filter_complex",
                f"[0:a]volume={original_volume}[a0];[1:a]volume={audio_volume}[a1];"
                "[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a", "-af", f"volume={audio_volume}"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out]
    try:
        proc = subprocess.run(cmd, timeout=300, capture_output=True, text=True)
    except Exception as e:
        return {"success": False, "error": f"ffmpeg 运行失败：{e}"}
    if proc.returncode != 0 or not os.path.exists(out):
        return {"success": False, "error": "MV 合成失败",
                "stderr": (proc.stderr or "")[-400:]}
    return {"success": True, "message": "MV 合成完成", "video": out,
            "size_bytes": os.path.getsize(out), "keep_original": has_original}


def _parse_lrc(text: str) -> Dict[str, Any]:
    """解析 LRC 歌词：[mm:ss.xx] 行，支持一行多个时间标签。"""
    lines, meta = [], {}
    for raw in str(text or "").splitlines():
        line = raw.strip()
        tag = re.match(r"\[(\w+):([^\]]*)\]", line)
        if tag and not re.match(r"\[\d+:\d+", line):
            meta[tag.group(1).lower()] = tag.group(2).strip()
            continue
        stamps = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", line)
        content = re.sub(r"\[[^\]]*\]", "", line).strip()
        if not stamps or not content:
            continue
        for minute, second in stamps:
            lines.append({"time": round(int(minute) * 60 + float(second), 2),
                          "text": content})
    lines.sort(key=lambda item: item["time"])
    return {"success": bool(lines), "lines": lines, "meta": meta}


# ---------------------------------------------------------------- dispatch
def execute(input_data: Any) -> Dict[str, Any]:
    if not isinstance(input_data, dict):
        return {"success": False, "error": "input 必须是对象"}
    params = input_data.get("params") if isinstance(input_data.get("params"), dict) else {}
    merged = dict(params)
    merged.update({k: v for k, v in input_data.items() if k not in ("params",)})
    # 模型有時會把參數再包一層 input，例如
    # {"action":"analyze_audio","input":{"audio_path":"..."}}
    # 把內層參數攤平，避免技能因拿不到 audio 直接失敗
    nested = input_data.get("input")
    if isinstance(nested, dict):
        inner = nested.get("input") if isinstance(nested.get("input"), dict) else nested
        for key, value in inner.items():
            merged.setdefault(key, value)
    if not merged.get("audio"):
        merged["audio"] = merged.get("audio_path") or merged.get("path") or ""

    action = str(merged.get("action") or merged.get("command") or "").strip().lower()
    if not action:
        return {"success": False, "error": "缺少 action（render_frames / build_video / sample_frames / download_assets）"}

    global _LAST_WORKDIR
    raw_name = merged.get("name") or merged.get("title") or ""
    if not raw_name and action in ("build", "build_video", "stitch", "sample", "sample_frames", "review"):
        # 模型常常漏寫 name，沿用最近一次渲染的作品目錄
        workdir = _latest_workdir() or os.path.join(_media_root(), _safe_name(""))
    else:
        name = _safe_name(raw_name)
        workdir = os.path.join(_media_root(), name)

    if action in ("render", "render_frames", "frames"):
        html = merged.get("html") or ""
        if not html and merged.get("html_path"):
            try:
                with open(merged["html_path"], "r", encoding="utf-8") as f:
                    html = f.read()
            except Exception as e:
                return {"success": False, "error": f"读取 html_path 失败：{e}"}
        if not html:
            return {"success": False, "error": "缺少 html 内容"}
        fps = int(merged.get("fps") or _DEFAULT_FPS)
        if merged.get("duration") in (None, "", 0):
            return {"success": False,
                    "error": "缺少 duration：必须显式传入视频总时长（秒），例如 {\"action\":\"render_frames\","
                             "\"duration\":60,\"fps\":24,\"width\":1280,\"height\":720}"}
        duration = float(merged.get("duration"))
        width = int(merged.get("width") or 1280) // 2 * 2
        height = int(merged.get("height") or 720) // 2 * 2
        res = _render_frames(html, workdir, fps, duration, width, height)
        res["dir"] = workdir
        if res.get("success"):
            _LAST_WORKDIR = workdir
        return res

    if action in ("build", "build_video", "stitch"):
        frames_dir = merged.get("frames_dir") or os.path.join(workdir, "frames")
        if not os.path.isdir(frames_dir):
            return {"success": False, "error": f"帧目录不存在：{frames_dir}"}
        fps = int(merged.get("fps") or _DEFAULT_FPS)
        out = merged.get("output") or os.path.join(workdir, "video.mp4")
        res = _build_video(frames_dir, out, fps)
        res["video"] = out
        res["dir"] = workdir
        return res

    if action in ("sample", "sample_frames", "review"):
        video = merged.get("video") or os.path.join(workdir, "video.mp4")
        base = os.path.dirname(os.path.abspath(video)) or workdir
        return _sample_frames(video, base, int(merged.get("count") or 6))

    if action in ("assets", "download_assets", "download"):
        urls = merged.get("urls") or merged.get("url") or []
        if isinstance(urls, str):
            urls = [urls]
        if not urls:
            return {"success": False, "error": "缺少 urls"}
        res = _download_assets(list(urls), workdir)
        res["dir"] = workdir
        return res

    if action in ("analyze_audio", "analyze_song", "audio_analysis"):
        audio = merged.get("audio") or merged.get("path") or ""
        if not audio:
            return {"success": False, "error": "缺少 audio（上传曲子的路径）"}
        res = _analyze_audio(audio, float(merged.get("max_seconds") or 180))
        res["dir"] = workdir
        return res

    if action in ("build_mv", "mv", "mux"):
        video = merged.get("video") or os.path.join(workdir, "video.mp4")
        audio = merged.get("audio") or ""
        if not audio:
            return {"success": False, "error": "缺少 audio（曲子路径）"}
        res = _build_mv(video, audio, workdir,
                        output=merged.get("output") or "",
                        start=float(merged.get("start") or 0),
                        audio_volume=float(merged.get("audio_volume") or 1.0),
                        keep_original=bool(merged.get("keep_original")),
                        original_volume=float(merged.get("original_volume") or 0.25))
        res["dir"] = workdir
        return res

    if action in ("parse_lrc", "lrc"):
        text = merged.get("lrc") or ""
        if not text and merged.get("lrc_path"):
            try:
                with open(merged["lrc_path"], "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                return {"success": False, "error": f"读取 LRC 失败：{e}"}
        if not text:
            return {"success": False, "error": "缺少 lrc 文本或 lrc_path"}
        res = _parse_lrc(text)
        res["dir"] = workdir
        return res

    return {"success": False, "error": f"未知 action：{action}"}
