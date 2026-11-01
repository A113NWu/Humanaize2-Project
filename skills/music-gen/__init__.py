#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音乐生成技能：收集乐曲 → NumPy 提取波形/频谱 → 傅里叶逆变换合成新曲。

流程：
- collect：按曲风从 archive.org 抓公共领域音频（也可给 urls），存到 corpus/<曲风>/
- analyze：ffmpeg 解码成 22050Hz 单声道 → NumPy 做 FFT → 保存每条曲目的频谱 npz，
  并汇总成该曲风的"音色包络" profiles/<曲风>.json
- compose：按曲风包络 + 和弦/旋律规划，在频域叠加谐波，最后 irfft 一次性还原整段波形，
  写 wav 再转 mp3
- list：查看语料与曲风档案

所有随机都用 seed 控制，同一个 seed 必须得到同一首曲子。
"""

import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import wave
from typing import Any, Dict, List, Optional

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SR = 22050
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

_GENRES = {
    "jazz": ["jazz", "爵士"],
    "classical": ["classical", "古典"],
    "blues": ["blues", "蓝调"],
    "rock": ["rock", "摇滚"],
    "electronic": ["electronic", "电子"],
    "folk": ["folk", "民谣", "民歌"],
    "ambient": ["ambient", "氛围"],
    "hiphop": ["hip hop", "hiphop", "嘻哈"],
    "pop": ["pop", "流行"],
    "chinese": ["chinese", "国风", "民乐"],
    "trance": ["trance", "uplifting", "迷幻", "出神"],
}

# 没有语料时的备用音色参数（谐波滚降、基频、速度）
_FALLBACK = {
    # 和弦表按 C 大调写，根音必须是 C（261.6Hz），否则整首会被移调、和弦音全部错位
    "jazz":      {"rolloff": 1.4, "root": 261.6, "bpm": 96, "swing": 0.12},
    "classical": {"rolloff": 2.2, "root": 261.6, "bpm": 72, "swing": 0.0},
    "blues":     {"rolloff": 1.6, "root": 220.0, "bpm": 88, "swing": 0.16},
    "rock":      {"rolloff": 1.1, "root": 196.0, "bpm": 110, "swing": 0.0},
    "electronic": {"rolloff": 0.9, "root": 246.9, "bpm": 128, "swing": 0.0},
    "folk":      {"rolloff": 2.0, "root": 261.6, "bpm": 84, "swing": 0.0},
    "ambient":   {"rolloff": 2.6, "root": 174.6, "bpm": 60, "swing": 0.0},
    "hiphop":    {"rolloff": 1.3, "root": 207.7, "bpm": 92, "swing": 0.1},
    "pop":       {"rolloff": 1.5, "root": 261.6, "bpm": 112, "swing": 0.0},
    "chinese":   {"rolloff": 1.9, "root": 293.7, "bpm": 76, "swing": 0.0},
    # Uplifting Trance：138 BPM、亮而厚的谐波、以 A 小调为中心
    "trance":    {"rolloff": 1.1, "root": 220.0, "bpm": 138, "swing": 0.0},
}


# ---------------------------------------------------------------- paths
def _data_dir() -> str:
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


def _music_root() -> str:
    root = os.path.join(_data_dir(), "media", "music")
    os.makedirs(root, exist_ok=True)
    return root


def _corpus_dir(genre: str) -> str:
    d = os.path.join(_music_root(), "corpus", _normalize_genre(genre))
    os.makedirs(d, exist_ok=True)
    return d


def _profile_path(genre: str) -> str:
    d = os.path.join(_music_root(), "profiles")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.json" % _normalize_genre(genre))


def _work_dir(name: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_\-一-龥]+", "_", str(name or "").strip()) or time.strftime("song_%Y%m%d_%H%M%S")
    d = os.path.join(_music_root(), "works", safe)
    os.makedirs(d, exist_ok=True)
    return d


def _normalize_genre(genre: str) -> str:
    g = (genre or "pop").strip().lower()
    for key, aliases in _GENRES.items():
        if g == key or any(a in g for a in aliases):
            return key
    return "pop"


def _ffmpeg_exe() -> Optional[str]:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for p in (
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.join(_PROJECT_ROOT, "skills", "mc-bot", "node_modules",
                     "@ffmpeg-installer", "win32-x64", "ffmpeg.exe"),
    ):
        if os.path.exists(p):
            return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


# ---------------------------------------------------------------- collect
def _archive_urls(keyword: str, limit: int) -> List[str]:
    """从 archive.org 找公共领域音频的直链。"""
    query = "mediatype:audio AND %s" % keyword
    api = ("https://archive.org/advancedsearch.php?q=%s&fl[]=identifier&rows=%d"
           "&sort[]=downloads+desc&output=json"
           % (urllib.parse.quote(query), max(1, min(limit * 4, 40))))
    req = urllib.request.Request(api, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    identifiers = [d.get("identifier") for d in (data.get("response") or {}).get("docs") or []
                   if d.get("identifier")]

    urls = []
    for ident in identifiers:
        if len(urls) >= limit:
            break
        try:
            meta_url = "https://archive.org/metadata/%s" % urllib.parse.quote(ident)
            req = urllib.request.Request(meta_url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                meta = json.loads(resp.read().decode("utf-8", "replace"))
            for f in meta.get("files") or []:
                name = f.get("name") or ""
                fmt = (f.get("format") or "").lower()
                if not name.lower().endswith((".mp3", ".ogg", ".wav")):
                    continue
                if "mp3" in fmt or name.lower().endswith(".mp3"):
                    urls.append("https://archive.org/download/%s/%s"
                                % (urllib.parse.quote(ident), urllib.parse.quote(name)))
                    break
        except Exception:
            continue
    return urls


def _oga_urls(keyword: str, limit: int) -> List[str]:
    """备用源：opengameart.org 的 CC 音乐（archive.org 连不上时用），页内直链可下载。"""
    search = "https://opengameart.org/art-search?keys=%s" % urllib.parse.quote(keyword)
    req = urllib.request.Request(search, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", "replace")
    slugs: List[str] = []
    for m in re.finditer(r'href="/content/([^"/?#]+)"', html):
        if m.group(1) not in slugs:
            slugs.append(m.group(1))
    urls: List[str] = []
    for slug in slugs:
        if len(urls) >= limit:
            break
        try:
            page = "https://opengameart.org/content/%s" % urllib.parse.quote(slug)
            req = urllib.request.Request(page, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8", "replace")
            found = re.findall(
                r'https://opengameart\.org/sites/default/files/[^"\'\s<>]+\.(?:mp3|ogg|wav)', body)
            found = [u for u in found if "/styles/" not in u and "/audio_preview/" not in u]
            if found:
                urls.append(found[0])
        except Exception:
            continue
    return urls


def _download(url: str, dest: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        return os.path.getsize(dest) > 1024
    except Exception:
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except Exception:
            pass
        return False


def _collect(genre: str, limit: int, urls: List[str]) -> Dict[str, Any]:
    g = _normalize_genre(genre)
    out_dir = _corpus_dir(g)
    saved, errors = [], []
    targets = list(urls or [])
    if targets:
        limit = min(len(targets), max(1, limit))
    else:
        try:
            targets = _archive_urls(_GENRES[g][0], limit)
        except Exception as e:
            errors.append("archive 搜索失败：%s" % e)
    if not targets and not urls:
        try:
            targets = _oga_urls(_GENRES[g][0], limit)
        except Exception as e:
            errors.append("备用源搜索失败：%s" % e)
    # 记录已下载过的直链，重复 collect 时不再重复保存同一首
    index_path = os.path.join(out_dir, "_sources.json")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            known = json.load(f)
    except Exception:
        known = {}
    for url in targets[:limit]:
        if url in known and os.path.exists(known[url]):
            continue
        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".mp3"
        dest = os.path.join(out_dir, "%s_%s%s" % (g, time.strftime("%H%M%S"), ext))
        if _download(url, dest):
            saved.append(dest)
            known[url] = dest
        else:
            errors.append("下载失败：%s" % url)
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(known, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return {"success": bool(saved), "genre": g, "saved": saved,
            "count": len(saved), "errors": errors,
            "total_in_genre": len(_list_audio(out_dir))}


def _list_audio(folder: str) -> List[str]:
    try:
        names = sorted(os.listdir(folder))
    except Exception:
        return []
    return [os.path.join(folder, n) for n in names
            if n.lower().endswith((".mp3", ".wav", ".ogg", ".m4a", ".flac"))]


# ---------------------------------------------------------------- analyze
def _decode_wav(src: str, dest: str, seconds: float = 30.0) -> bool:
    ff = _ffmpeg_exe()
    if not ff:
        return False
    cmd = [ff, "-y", "-v", "error", "-i", src, "-t", str(seconds),
           "-ac", "1", "-ar", str(_SR), "-f", "wav", dest]
    try:
        subprocess.run(cmd, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return False
    return os.path.exists(dest) and os.path.getsize(dest) > 1024


def _read_wav_mono(path: str) -> Optional[np.ndarray]:
    try:
        with wave.open(path, "rb") as w:
            frames = w.readframes(w.getnframes())
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            if w.getnchannels() > 1:
                data = data[::w.getnchannels()]
        return data
    except Exception:
        return None


def _spectrum(src: str, tmp_wav: str) -> Optional[Dict[str, Any]]:
    if os.path.splitext(src)[1].lower() == ".wav":
        wav_path = src
    else:
        if not _decode_wav(src, tmp_wav):
            return None
        wav_path = tmp_wav
    data = _read_wav_mono(wav_path)
    if data is None or data.size < _SR * 2:
        return None
    n_fft = 2048
    hop = 512
    win = np.hanning(n_fft).astype(np.float32)
    mags = []
    for start in range(0, max(1, data.size - n_fft), hop):
        seg = data[start:start + n_fft]
        if seg.size < n_fft:
            break
        mags.append(np.abs(np.fft.rfft(seg * win)).astype(np.float32))
    if not mags:
        return None
    avg = np.mean(np.stack(mags), axis=0)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / _SR)
    energy = float(np.sum(avg))
    centroid = float(np.sum(avg * freqs) / energy) if energy > 0 else 0.0
    return {"avg_mag": avg, "freqs": freqs, "centroid": centroid,
            "duration": round(float(data.size) / _SR, 2)}


def _analyze(genre: str) -> Dict[str, Any]:
    g = _normalize_genre(genre)
    folder = _corpus_dir(g)
    tracks = _list_audio(folder)
    if not tracks:
        return {"success": False, "error": "曲风 %s 还没有语料，先 collect" % g, "genre": g}
    os.makedirs(os.path.join(_music_root(), "features"), exist_ok=True)
    specs, analyzed, failed = [], [], []
    for i, src in enumerate(tracks):
        tmp = os.path.join(_music_root(), "features", "_tmp_%02d.wav" % i)
        spec = _spectrum(src, tmp)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        if not spec:
            failed.append(os.path.basename(src))
            continue
        np.savez_compressed(
            os.path.join(_music_root(), "features", "%s_%02d.npz" % (g, i)),
            avg_mag=spec["avg_mag"], freqs=spec["freqs"],
            centroid=spec["centroid"], duration=spec["duration"])
        specs.append(spec)
        analyzed.append({"file": os.path.basename(src),
                         "duration": spec["duration"],
                         "centroid_hz": round(spec["centroid"], 1)})
    if not specs:
        return {"success": False, "error": "没有可分析的音频", "genre": g, "failed": failed}

    # 汇总成音色包络：对数频段 64 点，做归一化，方便作曲时取任意频率的强度
    mags = np.stack([s["avg_mag"] for s in specs])
    avg = np.mean(mags, axis=0).astype(np.float64)
    freqs = specs[0]["freqs"]
    bands = np.geomspace(60.0, _SR / 2.0, 65)
    env = []
    for lo, hi in zip(bands[:-1], bands[1:]):
        m = (freqs >= lo) & (freqs < hi)
        env.append(float(np.mean(avg[m])) if np.any(m) else 0.0)
    env = np.asarray(env)
    env = env / (np.max(env) + 1e-9)

    profile = {
        "genre": g,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tracks": len(analyzed),
        "tracks_info": analyzed,
        "avg_centroid_hz": round(float(np.mean([s["centroid"] for s in specs])), 1),
        "sr": _SR,
        "band_hz": [float(b) for b in bands],
        "envelope": [round(float(v), 4) for v in env],
        "failed": failed,
    }
    with open(_profile_path(g), "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False)
    return {"success": True, "genre": g, "tracks": len(analyzed),
            "avg_centroid_hz": profile["avg_centroid_hz"],
            "profile": _profile_path(g),
            "tracks_info": analyzed, "failed": failed}


def _load_profile(genre: str) -> Optional[Dict[str, Any]]:
    try:
        with open(_profile_path(genre), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _envelope_at(profile: Optional[Dict[str, Any]], freq: np.ndarray, genre: str) -> np.ndarray:
    """按曲风包络给出任意频率处的相对强度（无语料时用备用滚降曲线）。"""
    if profile and profile.get("envelope") and profile.get("band_hz"):
        bands = np.asarray(profile["band_hz"], dtype=np.float64)
        env = np.asarray(profile["envelope"], dtype=np.float64)
        centers = np.sqrt(bands[:-1] * bands[1:])
        return np.interp(freq, centers, env, left=env[0], right=env[-1])
    cfg = _FALLBACK.get(_normalize_genre(genre), _FALLBACK["pop"])
    return (200.0 / np.maximum(freq, 40.0)) ** cfg["rolloff"]


# ---------------------------------------------------------------- compose
_PROGRESSIONS = {
    "jazz": [0, 5, 9, 7], "classical": [0, 7, 5, 0], "blues": [0, 5, 7, 9],
    "rock": [0, 7, 9, 5], "electronic": [0, 5, 7, 9], "folk": [0, 7, 5, 0],
    "ambient": [0, 5, 0, 7], "hiphop": [0, 5, 7, 9], "pop": [0, 7, 9, 5],
    "chinese": [0, 7, 2, 9],
}

# ---------------------------------------------------------------- synth core
_HARMONIC_CAP_HZ = 8000.0   # 谐波上限，避免锯齿波在 22050Hz 采样率下产生刺耳混叠


def _adsr(n: int, attack: float = 0.01, release: float = 0.1, decay: float = 0.0) -> np.ndarray:
    """包络：attack 线性起音，decay 指数衰减（打击/拨弦感），release 收尾。"""
    t = np.arange(n, dtype=np.float64) / _SR
    env = np.ones(n, dtype=np.float64)
    if decay > 0:
        env = np.exp(-t / float(decay))
    a = min(n, int(attack * _SR))
    if a > 1:
        env[:a] *= np.linspace(0.0, 1.0, a)
    r = min(n, int(release * _SR))
    if r > 1:
        env[-r:] *= np.linspace(1.0, 0.0, r) ** 1.2
    return env


def _osc(freq: float, n: int, kind: str = "saw", vibrato=(0.0, 0.0)) -> np.ndarray:
    """傅里叶级数振荡器：锯齿 1/k、方波奇次 1/k，谐波封顶在 _HARMONIC_CAP_HZ。"""
    if kind == "sine":
        t = np.arange(n, dtype=np.float64) / _SR
        ph = 2.0 * np.pi * freq * t
        if vibrato[0] > 0:
            ph += vibrato[0] * np.sin(2.0 * np.pi * vibrato[1] * t)
        return np.sin(ph)
    t = np.arange(n, dtype=np.float64) / _SR
    ph = 2.0 * np.pi * freq * t
    if vibrato[0] > 0:
        ph += vibrato[0] * np.sin(2.0 * np.pi * vibrato[1] * t)
    k_max = int(max(1, min(64, _HARMONIC_CAP_HZ / max(freq, 20.0))))
    ks = np.arange(1, k_max + 1, dtype=np.float64)[:, None]
    if kind == "square":
        amps = np.where((ks % 2) == 1, 1.0 / ks, 0.0)
    else:
        amps = 1.0 / ks
    return (np.sin(ks * ph[None, :]) * amps).sum(axis=0) * 0.5


def _fft_filter(x: np.ndarray, lowpass: Optional[float] = None,
                highpass: Optional[float] = None, order: int = 2) -> np.ndarray:
    """频域二阶滤波器：用来塑造每轨音色（这是真正用 FFT 的地方）。"""
    n = int(x.size)
    if n < 16:
        return x
    f = np.fft.rfftfreq(n, 1.0 / _SR)
    h = np.ones_like(f)
    if lowpass:
        h *= 1.0 / (1.0 + (f / float(lowpass)) ** order)
    if highpass:
        r = (f / float(highpass)) ** order
        h *= r / (1.0 + r)
    return np.fft.irfft(np.fft.rfft(x) * h, n=n)


def _resonant_lowpass(x: np.ndarray, fc: float, q: float = 0.5) -> np.ndarray:
    """带共振峰的低通，让合成音色不那么"芯片音乐"，更像模拟合成器。"""
    n = int(x.size)
    if n < 16:
        return x
    f = np.fft.rfftfreq(n, 1.0 / _SR)
    h = 1.0 / (1.0 + (f / float(fc)) ** 2)
    h *= 1.0 + float(q) * np.exp(-((f - fc) / (0.25 * fc + 1e-9)) ** 2)
    return np.fft.irfft(np.fft.rfft(x) * h, n=n)


def _reverb(x: np.ndarray, decay: float = 0.35, wet: float = 0.22) -> np.ndarray:
    """用衰减噪声冲激响应做卷积混响，补上 Trance 需要的空间厚度。"""
    n = int(x.size)
    if n < 256:
        return x
    ir_n = int(0.55 * _SR)
    rng = np.random.default_rng(23)
    ir = rng.standard_normal(ir_n) * np.exp(-np.arange(ir_n) / (float(decay) * _SR))
    ir /= float(np.sqrt(np.sum(ir ** 2)) + 1e-9)
    size = 1
    while size < n + ir_n:
        size <<= 1
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:n]
    return x + y * float(wet)


def _note(freq: float, dur: float, amp: float, kind: str = "saw", cutoff: Optional[float] = None,
          voices: int = 1, detune: float = 0.0, attack: float = 0.01,
          release: float = 0.1, decay: float = 0.0, vibrato=(0.0, 0.0),
          resq: float = 0.0) -> np.ndarray:
    n = max(16, int(dur * _SR))
    if voices > 1:
        buf = np.zeros(n, dtype=np.float64)
        for i in range(voices):
            cents = (i - (voices - 1) / 2.0) * detune
            buf += _osc(freq * 2 ** (cents / 1200.0), n, kind=kind, vibrato=vibrato)
        buf /= float(voices)
    else:
        buf = _osc(freq, n, kind=kind, vibrato=vibrato)
    buf *= _adsr(n, attack=attack, release=release, decay=decay)
    if cutoff:
        buf = _fft_filter(buf, lowpass=cutoff)
        if resq:
            buf = _resonant_lowpass(buf, cutoff, resq)
    return buf * amp


def _add(stem: np.ndarray, start_s: float, buf: np.ndarray) -> None:
    start = int(max(0.0, start_s) * _SR)
    if start >= stem.size:
        return
    end = min(stem.size, start + buf.size)
    if end > start:
        stem[start:end] += buf[:end - start]


# ---------------------------------------------------------------- drums
def _kick_buf(amp: float = 1.0) -> np.ndarray:
    n = int(0.24 * _SR)
    t = np.arange(n, dtype=np.float64) / _SR
    f = 135.0 * np.exp(-t * 26.0) + 45.0
    ph = 2.0 * np.pi * np.cumsum(f) / _SR
    body = np.sin(ph) * np.exp(-t * 20.0)
    click = np.random.default_rng(7).standard_normal(n) * np.exp(-t * 80.0) * 0.18
    return (body + click) * amp


def _hat_buf(amp: float = 1.0, dur: float = 0.07) -> np.ndarray:
    n = int(dur * _SR)
    t = np.arange(n, dtype=np.float64) / _SR
    x = np.random.default_rng(11).standard_normal(n) * np.exp(-t * 55.0)
    x = _fft_filter(x, highpass=6500.0)
    return x * amp


def _clap_buf(amp: float = 1.0) -> np.ndarray:
    n = int(0.13 * _SR)
    t = np.arange(n, dtype=np.float64) / _SR
    base = np.random.default_rng(13).standard_normal(n)
    base = _fft_filter(base, highpass=1100.0, lowpass=9000.0)
    env = np.zeros(n, dtype=np.float64)
    for off in (0.0, 0.017, 0.034):
        i = int(off * _SR)
        if i < n:
            env[i:] = np.maximum(env[i:], np.exp(-t[i:] * 55.0))
    return base * env * amp


def _ride_buf(amp: float = 1.0) -> np.ndarray:
    n = int(0.10 * _SR)
    t = np.arange(n, dtype=np.float64) / _SR
    x = np.random.default_rng(17).standard_normal(n) * np.exp(-t * 32.0)
    return _fft_filter(x, highpass=3800.0) * amp


# ---------------------------------------------------------------- arrangements
# 和弦音一律写成"相对主音 A/C 的绝对半音"，且全部落在自然小调/自然大调音阶内，
# 这样琶音和旋律换和弦时不会跑出调外。
_TRANCE_CHORDS = [
    (0, (0, 3, 7)),     # i   Am  (A C E)
    (-4, (-4, 0, 3)),   # VI  F   (F A C)
    (3, (3, 7, 10)),    # III C   (C E G)
    (-2, (-2, 2, 5)),   # VII G   (G B D)
]
_TRANCE_ARP = (0, 1, 2, 3, 2, 1, 0, 1)
# A 自然小调内的旋律动机（0=A, 音阶 {0,2,3,5,7,8,10}）
_TRANCE_MELODY = (
    (0, 3, 7, 10), (12, 10, 7, 3), (5, 7, 10, 12), (7, 3, 0, 3),
)

# C 大调的 ii–V–I，同样用绝对半音（0=C, 音阶 {0,2,4,5,7,9,11}）
_JAZZ_CHORDS = [
    (2, (2, 5, 9, 0)),     # Dm7
    (7, (7, 11, 2, 5)),    # G7
    (0, (0, 4, 7, 11)),    # Cmaj7
    (9, (9, 0, 4, 7)),     # Am7
]
_JAZZ_SCALE = (0, 2, 4, 5, 7, 9, 11)


def _cents(root: float, semitones: float) -> float:
    return float(root) * 2 ** (float(semitones) / 12.0)


def _brightness(profile: Optional[Dict[str, Any]], genre: str) -> float:
    """用学到的频谱能量中心决定音色滤镜亮度（无语料时退回默认）。"""
    centroid = 2600.0
    if profile and profile.get("avg_centroid_hz"):
        centroid = float(profile["avg_centroid_hz"])
    elif genre == "trance":
        centroid = 3200.0
    return float(np.clip(centroid, 900.0, 6000.0))


def _render_trance(profile, cfg, root, rng, total) -> Dict[str, np.ndarray]:
    bpm = float(cfg.get("bpm", 138))
    beat = 60.0 / bpm
    bar = beat * 4
    bright = _brightness(profile, "trance")
    lead_cut = float(np.clip(bright * 2.2, 2600.0, 9000.0))
    arp_cut = float(np.clip(bright * 1.6, 2200.0, 7500.0))
    pad_cut = float(np.clip(bright * 0.9, 1500.0, 4200.0))
    bass_cut = 700.0

    stems = {k: np.zeros(total, dtype=np.float64)
             for k in ("kick", "hat", "clap", "bass", "arp", "lead", "pad")}
    kick_buf = _kick_buf(1.0)
    hat_buf = _hat_buf(1.0)
    clap_buf = _clap_buf(1.0)

    nbar = int(np.ceil(total / (bar * _SR)))
    for b in range(nbar):
        t0 = b * bar
        if t0 >= total / _SR:
            break
        deg, tones = _TRANCE_CHORDS[b % len(_TRANCE_CHORDS)]
        # 前两小节做前奏：只有 pad/arp/hats，铺出氛围
        intro = b < 2
        section = b >= 4

        # Pad：整小节的宽 Pad（5 声部超锯 + 共振低通）
        for sem in tones:
            _add(stems["pad"], t0,
                 _note(_cents(root, sem), bar * 0.97, 0.12, kind="saw", cutoff=pad_cut,
                       voices=5, detune=7.0, attack=0.30, release=0.45, resq=0.4))

        # Arp：16 分琶音，只用本和弦的和弦音与八度，换和弦也不会跑调
        arp_notes = list(tones) + [tones[0] + 12, tones[1] + 12]
        for k in range(16):
            at = t0 + k * beat / 4.0
            idx = _TRANCE_ARP[k % len(_TRANCE_ARP)]
            f = _cents(root, arp_notes[min(idx, len(arp_notes) - 1)]) * 2
            amp = 0.24 if intro else 0.32
            _add(stems["arp"], at,
                 _note(f, beat / 4.0 * 0.96, amp, kind="saw", cutoff=arp_cut,
                       attack=0.004, release=0.05, decay=0.10, resq=0.35))

        # 滚奏 Bass：正拍 16 分音符连续滚动（不是反拍）
        if not intro:
            for k in range(16):
                bt = t0 + k * beat / 4.0
                amp = 0.26 if (k % 4 == 0) else 0.20
                _add(stems["bass"], bt,
                     _note(_cents(root, deg - 12), beat / 4.0 * 0.94, amp,
                           kind="saw", cutoff=bass_cut, attack=0.006,
                           release=0.04, decay=0.09))

        # 鼓组：每拍底鼓；反拍八分 hi-hat；2、4 拍 clap
        if not intro:
            for k in range(4):
                _add(stems["kick"], t0 + k * beat, kick_buf * 0.48)
            for k in range(4):
                _add(stems["hat"], t0 + k * beat + beat * 0.5, hat_buf * 0.50)
            for k in (1, 3):
                _add(stems["clap"], t0 + k * beat, clap_buf * 0.50)

        # Lead：第 4 小节起进入，长句超锯 Saw Lead（5 声部 ±20 音分做宽）
        if section:
            motif = _TRANCE_MELODY[(b // 2) % len(_TRANCE_MELODY)]
            for k, sem in enumerate(motif):
                lt = t0 + k * beat
                _add(stems["lead"], lt,
                     _note(_cents(root, sem) * 2, beat * 1.55, 0.55,
                           kind="saw", cutoff=lead_cut, voices=5, detune=20.0,
                           attack=0.06, release=0.30, vibrato=(0.18, 5.5), resq=0.6))

    # 混响只加在旋律/琶音/Pad 上：去掉干扁的芯片音乐感，又不会糊住鼓和 Bass
    for key in ("arp", "lead", "pad"):
        stems[key] = _reverb(stems[key], decay=0.40, wet=0.22)

    # 侧链：每拍跟随底鼓压下去再恢复，给 bass/arp/pad 泵感
    nbeat = max(1, int(beat * _SR))
    ph = np.arange(nbeat, dtype=np.float64) / nbeat
    duck_shape = 0.42 + 0.58 * np.minimum(1.0, ph / 0.34)
    duck = np.tile(duck_shape, int(np.ceil(total / nbeat)) + 1)[:total]
    for key in ("bass", "arp", "pad"):
        stems[key] *= duck * 0.8 + 0.2
    return stems


def _render_jazz(profile, cfg, root, rng, total) -> Dict[str, np.ndarray]:
    bpm = 96.0
    beat = 60.0 / bpm
    bar = beat * 4
    swing = 0.60                      # 反拍落在 60% 拍长处 → 真正的摇摆感
    bright = _brightness(profile, "jazz")
    bass_cut = 1500.0
    piano_cut = float(np.clip(bright * 1.4, 2200.0, 5200.0))
    lead_cut = float(np.clip(bright * 1.8, 2600.0, 6000.0))

    stems = {k: np.zeros(total, dtype=np.float64)
             for k in ("bass", "piano", "lead", "kick", "ride")}
    kick_buf = _kick_buf(1.0)
    ride_buf = _ride_buf(1.0)

    nbar = int(np.ceil(total / (bar * _SR)))
    for b in range(nbar):
        t0 = b * bar
        if t0 >= total / _SR:
            break
        deg, tones = _JAZZ_CHORDS[b % len(_JAZZ_CHORDS)]

        # Walking Bass：每拍一个音（根—五—和弦音—逼近音），整体降两个八度才像倍低音提琴
        for k in range(4):
            if k == 0:
                sem = deg
            elif k == 1:
                sem = deg + 7
            elif k == 2:
                sem = tones[(1 + b) % len(tones)]
            else:
                # 半音逼近下一个和弦根音，是爵士 walking bass 的标志
                sem = _JAZZ_CHORDS[(b + 1) % len(_JAZZ_CHORDS)][0] - 1
            _add(stems["bass"], t0 + k * beat,
                 _note(_cents(root, sem) / 4.0, beat * 0.92, 0.22, kind="saw",
                       cutoff=bass_cut, attack=0.012, release=0.10, decay=0.35))

        # 钢琴 comping：2、4 拍切进去的短促和弦（用本和弦的绝对和弦音，保证在调内）
        for k in (1, 3):
            ct = t0 + k * beat
            for sem in tones:
                _add(stems["piano"], ct,
                     _note(_cents(root, sem), 0.42, 0.12, kind="saw", cutoff=piano_cut,
                           voices=2, detune=4.0, attack=0.006, release=0.16,
                           decay=0.14, resq=0.3))

        # 鼓：1、3 拍轻底鼓 + 每拍落点上的 ride（摇摆八分）
        for k in (0, 2):
            _add(stems["kick"], t0 + k * beat, kick_buf * 0.22)
        for k in range(4):
            _add(stems["ride"], t0 + k * beat, ride_buf * 0.22)
            _add(stems["ride"], t0 + k * beat + beat * swing, ride_buf * 0.16)

        # 旋律：C 大调音阶（绝对半音），第 4 拍落在和弦音上；奇数拍延后 = swing
        for k in range(4):
            nt = t0 + k * beat + (0.0 if k % 2 == 0 else beat * swing)
            if k == 3:
                sem = tones[(b + 1) % len(tones)]
            else:
                sem = _JAZZ_SCALE[(k + b) % len(_JAZZ_SCALE)]
            # 高一个八度，避免和钢琴铺底同区打架
            f = _cents(root, sem) * (4.0 if (b + k) % 5 == 0 else 2.0)
            _add(stems["lead"], nt,
                 _note(f, beat * 0.85, 0.32, kind="saw", cutoff=lead_cut,
                       voices=3, detune=8.0, attack=0.05, release=0.18,
                       vibrato=(0.35, 5.8), resq=0.35))

    for key in ("piano", "lead"):
        stems[key] = _reverb(stems[key], decay=0.30, wet=0.15)
    return stems


def _render_generic(profile, cfg, root, rng, total) -> Dict[str, np.ndarray]:
    bpm = float(cfg.get("bpm", 100))
    beat = 60.0 / bpm
    bar = beat * 4
    swing = float(cfg.get("swing", 0.0))
    bright = _brightness(profile, "pop")
    stems = {k: np.zeros(total, dtype=np.float64) for k in ("bass", "chord", "lead")}
    progression = _PROGRESSIONS.get("pop", [0, 7, 9, 5])
    scale = (0, 2, 4, 7, 9)
    nbar = int(np.ceil(total / (bar * _SR)))
    for b in range(nbar):
        t0 = b * bar
        if t0 >= total / _SR:
            break
        deg = progression[b % len(progression)]
        chord_root = _cents(root, deg)
        # 低音：正拍四分
        for k in range(4):
            _add(stems["bass"], t0 + k * beat,
                 _note(_cents(chord_root, -12), beat * 0.9, 0.22, kind="saw",
                       cutoff=900.0, attack=0.01, release=0.08, decay=0.25))
        # 和弦：短促切分，而不是一直铺着
        for k in (0, 2):
            for iv in (0, 4, 7):
                _add(stems["chord"], t0 + k * beat + beat * swing * 0.5,
                     _note(_cents(chord_root, iv), beat * 1.4, 0.10, kind="saw",
                           cutoff=bright * 1.2, voices=2, detune=5.0,
                           attack=0.01, release=0.2, decay=0.3))
        # 旋律：四分音符为主，有起伏
        for k in range(4):
            nt = t0 + k * beat + (beat * swing if k % 2 else 0.0)
            iv = scale[(k + b) % len(scale)]
            _add(stems["lead"], nt,
                 _note(_cents(chord_root, iv), beat * 0.9, 0.30, kind="saw",
                       cutoff=bright * 1.8, voices=2, detune=8.0,
                       attack=0.02, release=0.15, vibrato=(0.25, 5.0)))
    return stems


def _render_track(genre: str, profile, cfg, root, rng, total) -> Dict[str, np.ndarray]:
    if genre == "trance":
        return _render_trance(profile, cfg, root, rng, total)
    if genre == "jazz":
        return _render_jazz(profile, cfg, root, rng, total)
    return _render_generic(profile, cfg, root, rng, total)


def _master_stereo(stems: Dict[str, np.ndarray]) -> tuple:
    """母线：鼓与 Bass 居中，旋律/琶音/Pad 在右声道做 9ms Haas 延迟。

    单声道是"芯片音乐"听感的主要来源之一，Trance 需要明显的立体宽度。
    """
    total = max((s.size for s in stems.values()), default=0)
    left = np.zeros(total, dtype=np.float64)
    right = np.zeros(total, dtype=np.float64)
    delay = max(1, int(0.009 * _SR))
    for key, s in stems.items():
        if not s.size:
            continue
        left[:s.size] += s
        if key in ("lead", "arp", "pad"):
            end = min(total, s.size + delay)
            right[delay:end] += s[:end - delay]
        else:
            right[:s.size] += s
    # 柔和的母线饱和，压住瞬态尖峰
    left = np.tanh(left * 0.85) / 0.85
    right = np.tanh(right * 0.85) / 0.85
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    return left / peak * 0.92, right / peak * 0.92


def _compose(title: str, genre: str, duration: float, seed: int) -> Dict[str, Any]:
    g = _normalize_genre(genre)
    cfg = dict(_FALLBACK.get(g, _FALLBACK["pop"]))
    profile = _load_profile(g)
    rng = np.random.default_rng(int(seed))
    total = int(max(4.0, min(duration, 300.0)) * _SR)
    root = float(cfg["root"])

    # 分轨合成：鼓组 / 正拍滚奏 Bass / 琶音 / Saw Lead / Pad 各走独立音色链
    stems = _render_track(g, profile, cfg, root, rng, total)
    left, right = _master_stereo(stems)

    fade = int(0.4 * _SR)
    if left.size > fade * 2:
        ramp_in = np.linspace(0.0, 1.0, fade)
        ramp_out = np.linspace(1.0, 0.0, fade)
        left[:fade] *= ramp_in
        right[:fade] *= ramp_in
        left[-fade:] *= ramp_out
        right[-fade:] *= ramp_out

    frames = np.empty(left.size * 2, dtype=np.float64)
    frames[0::2] = left
    frames[1::2] = right

    work = _work_dir(title)
    wav_path = os.path.join(work, "song.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(_SR)
        w.writeframes((frames * 32767).astype(np.int16).tobytes())

    mp3_path = os.path.join(work, "song.mp3")
    ff = _ffmpeg_exe()
    if ff:
        try:
            subprocess.run([ff, "-y", "-v", "error", "-i", wav_path,
                            "-codec:a", "libmp3lame", "-b:a", "160k", mp3_path],
                           timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    meta = {
        "title": title, "genre": g, "seed": int(seed),
        "duration": round(total / _SR, 2), "sr": _SR, "channels": 2,
        "bpm": cfg["bpm"], "root_hz": root,
        "profile_used": bool(profile), "tracks_learned": (profile or {}).get("tracks", 0),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(work, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return {"success": True, "audio": mp3_path if os.path.exists(mp3_path) else wav_path,
            "wav": wav_path, "meta": meta}


# ---------------------------------------------------------------- entry
def execute(params: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    p = dict(params or {})
    merged = dict(p)
    if isinstance(p.get("input"), dict):
        merged.update(p["input"])
    action = str(merged.get("action") or merged.get("command") or "").strip().lower()

    if action in ("collect", "download"):
        genre = merged.get("genre") or merged.get("style") or "pop"
        limit = int(merged.get("limit") or 3)
        urls = merged.get("urls") or []
        if isinstance(urls, str):
            urls = [urls]
        return _collect(genre, limit, urls)

    if action in ("analyze", "analyse", "learn"):
        genre = merged.get("genre") or merged.get("style") or "pop"
        return _analyze(genre)

    if action in ("compose", "generate", "make"):
        genre = merged.get("genre") or merged.get("style") or "pop"
        title = merged.get("title") or merged.get("name") or time.strftime("song_%Y%m%d_%H%M%S")
        duration = float(merged.get("duration") or 30)
        seed = merged.get("seed")
        if seed is None:
            seed = abs(hash(str(title))) % 100000
        return _compose(title, genre, duration, int(seed))

    if action in ("list", "status"):
        root = _music_root()
        genres = {}
        for key in _GENRES:
            folder = os.path.join(root, "corpus", key)
            tracks = _list_audio(folder) if os.path.isdir(folder) else []
            prof = _load_profile(key)
            genres[key] = {"tracks": len(tracks),
                           "profile": bool(prof),
                           "tracks_learned": (prof or {}).get("tracks", 0)}
        works = []
        wdir = os.path.join(root, "works")
        if os.path.isdir(wdir):
            works = sorted(os.listdir(wdir))[-10:]
        return {"success": True, "root": root, "genres": genres, "works": works}

    return {"success": False,
            "error": "未知 action：%s（可用 collect / analyze / compose / list）" % (action or "(空)")}
