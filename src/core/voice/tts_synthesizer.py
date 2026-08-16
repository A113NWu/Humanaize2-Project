"""
Humanaize 2.0 - 多 Provider TTS 合成器
参考 tsukuyomi-space tts.js 实现，转换为 Python 并适配 Humanaize 项目结构

支持的 Provider:
  - gpt-sovits     : 本地/内网 GPT-SoVITS API（参考音频 + 权重 + 克隆音色）
  - minimax        : MiniMax t2a_v2（支持 Chinese,Yue/Japanese/Korean language_boost）
  - elevenlabs     : ElevenLabs text-to-speech
  - openai         : OpenAI / OpenAI 兼容 /v1/audio/speech
  - mimo           : 小米 MiMo 音色克隆 API（支持 prompt_audio 参考音频）
  - edge_tts       : 微软 Edge 免费 TTS（edge_tts 库）

返回值统一为 {
    "audio_bytes": bytes,       # 音频二进制
    "content_type": str,        # e.g. audio/wav, audio/mpeg
    "provider": str             # 实际使用的 provider
}
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    import edge_tts
except Exception:  # pragma: no cover
    edge_tts = None


# ============================================================
# 常量与默认配置
# ============================================================

MAX_TTS_AUDIO_BYTES = 32 * 1024 * 1024  # 32 MB

DEFAULT_GPT_SOVITS_API_URL = "http://127.0.0.1:9880/tts"
DEFAULT_MINIMAX_VOICE_ID = "female-shaonv"
DEFAULT_MINIMAX_API_URL = "https://api.minimaxi.com/v1/t2a_v2"
DEFAULT_MIMO_API_URL = "https://api.xiaomimimo.com/v1/chat/completions"
DEFAULT_OPENAI_API_URL = "https://api.openai.com/v1/audio/speech"
DEFAULT_ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"

ALLOWED_TTS_HOSTS = {
    "api.xiaomimimo.com",
    "api.openai.com",
    "api.minimax.chat",
    "api.minimaxi.com",
    "api.elevenlabs.io",
}

ALLOWED_GPT_SOVITS_HOSTS = {"127.0.0.1", "localhost"}
ALLOWED_GPT_SOVITS_PATH_RE = re.compile(r"^/tts/?$", re.IGNORECASE)

LANG_ALIASES = {
    "cn": "zh", "zh-cn": "zh", "zh-hans": "zh",
    "chinese": "zh", "mandarin": "zh", "中文": "zh", "汉语": "zh", "漢語": "zh",
    "jp": "ja", "jpn": "ja", "japanese": "ja", "日语": "ja", "日文": "ja", "日本語": "ja",
    "english": "en", "英语": "en", "英文": "en",
    "cantonese": "yue", "粤语": "yue", "粵語": "yue",
    "korean": "ko", "韩语": "ko", "韓語": "ko",
    "自动": "auto",
}

VALID_GPT_SOVITS_LANGS = {
    "zh", "ja", "en", "yue", "ko", "auto",
    "all_zh", "all_ja", "all_yue", "auto_yue",
}

REF_AUDIO_EXTENSIONS = {"wav", "mp3", "flac", "ogg", "m4a"}


# ============================================================
# 异常类
# ============================================================

class TTSError(Exception):
    """TTS 合成错误，status 可用于 HTTP 层返回码"""
    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.status = status


# ============================================================
# 配置数据结构
# ============================================================

@dataclass
class SynthesizeOptions:
    text: str
    provider: str = ""  # gpt-sovits / minimax / elevenlabs / openai / mimo / edge_tts / auto
    api_key: str = ""
    api_url: str = ""
    voice: str = ""
    model: str = ""
    speed: float = 1.0

    # GPT-SoVITS 专用
    ref_audio_path: str = ""
    prompt_text: str = ""
    prompt_audio: str = ""
    text_lang: str = ""
    prompt_lang: str = ""
    gpt_weight_path: str = ""
    sovits_weight_path: str = ""


# ============================================================
# 工具函数
# ============================================================

def normalize_gpt_sovits_lang(value: str, fallback: str = "zh") -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    normalized = LANG_ALIASES.get(raw, raw) or fallback
    normalized = normalized.replace("-", "_")
    if normalized in VALID_GPT_SOVITS_LANGS:
        return normalized
    return fallback


def minimax_language_boost(text_lang: str) -> str:
    lang = normalize_gpt_sovits_lang(text_lang, "ja")
    mapping = {
        "ja": "Japanese", "all_ja": "Japanese",
        "en": "English",
        "zh": "Chinese", "all_zh": "Chinese",
        "yue": "Chinese,Yue", "all_yue": "Chinese,Yue", "auto_yue": "Chinese,Yue",
        "ko": "Korean",
        "auto": "auto",
    }
    return mapping.get(lang, "Japanese")


def detect_language(text: str, configured_lang: str = "") -> str:
    if configured_lang and configured_lang != "auto":
        return normalize_gpt_sovits_lang(configured_lang, "auto")
    value = str(text or "")
    if re.search(r"[\u3040-\u30ff]", value):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", value):
        return "ko"
    if re.search(r"[\u4e00-\u9fff]", value):
        return "zh"
    return "en"


def _tts_read_instruction(text: str, text_lang: str) -> str:
    lang = detect_language(text, text_lang)
    if lang == "ja":
        return "以下の日本語テキストだけを、柔らかく自然な声で朗読してください。説明、翻訳、括弧内の動作指示、舞台指示は読まないでください。"
    if lang == "en":
        return "Read only the following English text in a soft, natural voice. Do not read explanations, translations, action cues, or stage directions."
    if lang == "ko":
        return "다음 한국어 텍스트만 부드럽고 자연스러운 목소리로 읽어 주세요. 설명, 번역, 괄호 안의 동작 지시나 무대 지시는 읽지 마세요."
    return "只朗读下面的中文文本，语气温柔自然。不要翻译，不要解释，不要读括号里的动作提示或舞台提示。"


def validate_tts_url(url: str, provider: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise TTSError(f"不支持的 TTS API 端点: {exc}", 400)

    if provider == "gpt-sovits":
        if parsed.scheme != "http" or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise TTSError("不支持的 GPT-SoVITS API 端点（仅允许 http://host/tts 形式）", 400)
        host = (parsed.hostname or "").lower()
        path_ok = ALLOWED_GPT_SOVITS_PATH_RE.match(parsed.path or "") is not None
        if host not in ALLOWED_GPT_SOVITS_HOSTS or not path_ok:
            raise TTSError("GPT-SoVITS 仅允许访问本机 /tts 端点", 400)
        return url

    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise TTSError("不支持的 TTS API 端点（必须使用 HTTPS，无查询/凭据片段）", 400)
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_TTS_HOSTS:
        raise TTSError(f"不支持的 TTS API 端点 host: {host}", 400)
    return url


def _decode_audio_bytes(value: Any) -> bytes:
    """从 base64 / hex 字符串解码音频二进制，并校验大小"""
    text = str(value or "").strip()
    text = re.sub(r"^data:audio/\w+;base64,", "", text).strip()

    # 尝试 hex
    if re.fullmatch(r"[0-9a-fA-F]+", text) and len(text) % 2 == 0:
        buf = bytes.fromhex(text)
        if len(buf) > MAX_TTS_AUDIO_BYTES:
            raise TTSError("TTS 音频响应过大", 413)
        return buf

    try:
        buf = base64.b64decode(text, validate=False)
    except Exception as exc:
        raise TTSError(f"无法解码 TTS 音频数据: {exc}", 500)
    if len(buf) > MAX_TTS_AUDIO_BYTES:
        raise TTSError("TTS 音频响应过大", 413)
    return buf


def _pick_audio_base64(data: Any) -> Optional[str]:
    """MiMo / MiniMax 常见响应结构中提取 base64 音频"""
    if not isinstance(data, dict):
        return None
    choices = data.get("choices") or []
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") or {}
        audio = msg.get("audio")
        if isinstance(audio, dict):
            val = audio.get("data")
            if isinstance(val, str) and val:
                return val
        if isinstance(audio, str) and audio:
            return audio
    audio_top = data.get("audio")
    if isinstance(audio_top, dict):
        val = audio_top.get("data")
        if isinstance(val, str) and val:
            return val
    data_wrap = data.get("data")
    if isinstance(data_wrap, dict):
        audio = data_wrap.get("audio")
        if isinstance(audio, str) and audio:
            return audio
    return None


def _managed_resource_path(value: str, label: str, extensions: set,
                           root_pattern: Optional[str] = None) -> str:
    """校验 GPT-SoVITS 所需的相对路径（安全路径检查）"""
    normalized = str(value or "").strip().replace("\\", "/")
    if (not normalized or len(normalized) > 300 or normalized.startswith("/")
            or re.match(r"^[a-zA-Z]:", normalized)
            or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", normalized)):
        raise TTSError(f"{label}必须是受管理目录内的相对路径", 400)

    parts = normalized.split("/")
    if any((not p) or p == "." or p == ".." or re.search(r"[\u0000-\u001f\u007f]", p) for p in parts):
        raise TTSError(f"{label}路径格式非法", 400)

    if root_pattern and not re.match(root_pattern, parts[0], re.IGNORECASE):
        raise TTSError(f"{label}不在允许的权重目录中", 400)

    ext = parts[-1].split(".")[-1].lower() if "." in parts[-1] else ""
    if ext not in extensions:
        raise TTSError(f"{label}文件类型无效（允许: {', '.join(sorted(extensions))}）", 400)
    return normalized


def _requests_or_raise():
    if not requests:
        raise TTSError("requests 库未安装，无法调用云端 TTS API", 500)


def _response_to_audio(response) -> bytes:
    declared = int(response.headers.get("content-length") or 0)
    if declared > MAX_TTS_AUDIO_BYTES:
        raise TTSError("TTS 音频响应过大", 413)
    content = response.content
    if len(content) > MAX_TTS_AUDIO_BYTES:
        raise TTSError("TTS 音频响应过大", 413)
    return content


# ============================================================
# GPT-SoVITS 权重加载（带互斥队列）
# ============================================================

class GptSovitsManager:
    """
    GPT-SoVITS 接口包装：
      - 自动在切换模型时调用 set_gpt_weights / set_sovits_weights
      - 串行队列避免并发请求冲突出错（最多 3 个等待）
    """

    MAX_PENDING = 3

    def __init__(self):
        self._loaded_gpt = ""
        self._loaded_sovits = ""
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._pending = 0
        self._queue = []  # type: ignore

    def _acquire_slot(self):
        with self._cond:
            while self._pending >= self.MAX_PENDING:
                ok = self._cond.wait(timeout=30)
                if not ok and self._pending >= self.MAX_PENDING:
                    raise TTSError("本地语音服务正忙，请稍后重试", 429)
            self._pending += 1

    def _release_slot(self):
        with self._cond:
            self._pending = max(0, self._pending - 1)
            self._cond.notify_all()

    def run_exclusive(self, task: Callable[[], Any]) -> Any:
        self._acquire_slot()
        try:
            return task()
        finally:
            self._release_slot()

    def ensure_weights_loaded(self, base_url: str, gpt_path: str, sovits_path: str):
        """按需调用 set_gpt_weights / set_sovits_weights"""
        _requests_or_raise()
        parsed = urlparse(base_url)

        gpt_target = _managed_resource_path(
            gpt_path or os.getenv("GPT_SOVITS_GPT_WEIGHT_PATH", ""),
            label="GPT 权重路径",
            extensions={"ckpt"},
            root_pattern=r"^GPT_weights(?:_|$)",
        )
        sovits_target = _managed_resource_path(
            sovits_path or os.getenv("GPT_SOVITS_SOVITS_WEIGHT_PATH", ""),
            label="SoVITS 权重路径",
            extensions={"pth"},
            root_pattern=r"^SoVITS_weights(?:_|$)",
        )

        if gpt_target and gpt_target != self._loaded_gpt:
            set_url = f"{parsed.scheme}://{parsed.netloc}/set_gpt_weights"
            try:
                r = requests.get(set_url, params={"weights_path": gpt_target}, timeout=60)
                if not r.ok:
                    raise TTSError(
                        f"GPT-SoVITS set_gpt_weights 失败 ({r.status_code}): {r.text[:240]}",
                        status=r.status_code,
                    )
            except TTSError:
                raise
            except Exception as exc:
                raise TTSError(f"GPT-SoVITS set_gpt_weights 请求异常: {exc}", 500)
            self._loaded_gpt = gpt_target

        if sovits_target and sovits_target != self._loaded_sovits:
            set_url = f"{parsed.scheme}://{parsed.netloc}/set_sovits_weights"
            try:
                r = requests.get(set_url, params={"weights_path": sovits_target}, timeout=60)
                if not r.ok:
                    raise TTSError(
                        f"GPT-SoVITS set_sovits_weights 失败 ({r.status_code}): {r.text[:240]}",
                        status=r.status_code,
                    )
            except TTSError:
                raise
            except Exception as exc:
                raise TTSError(f"GPT-SoVITS set_sovits_weights 请求异常: {exc}", 500)
            self._loaded_sovits = sovits_target

    def reset_weights(self):
        with self._lock:
            self._loaded_gpt = ""
            self._loaded_sovits = ""


_gpt_sovits_manager = GptSovitsManager()


# ============================================================
# 各 Provider 实现
# ============================================================

def _synthesize_gpt_sovits(opts: SynthesizeOptions, api_url: str) -> Dict[str, Any]:
    _requests_or_raise()

    def _do() -> Dict[str, Any]:
        try:
            _gpt_sovits_manager.ensure_weights_loaded(
                api_url, opts.gpt_weight_path, opts.sovits_weight_path
            )
        except TTSError:
            _gpt_sovits_manager.reset_weights()
            raise

        ref_path = (opts.ref_audio_path or opts.voice
                    or os.getenv("GPT_SOVITS_REF_AUDIO_PATH", ""))
        if not ref_path:
            raise TTSError("GPT-SoVITS 需要填写参考音频路径", 400)

        safe_ref = _managed_resource_path(
            ref_path, label="参考音频路径", extensions=REF_AUDIO_EXTENSIONS
        )

        payload = {
            "text": opts.text,
            "text_lang": normalize_gpt_sovits_lang(
                opts.text_lang or os.getenv("GPT_SOVITS_TEXT_LANG", "zh"), "zh"
            ),
            "ref_audio_path": safe_ref,
            "prompt_text": str(opts.prompt_text or opts.prompt_audio
                               or os.getenv("GPT_SOVITS_PROMPT_TEXT", ""))[:2000],
            "prompt_lang": normalize_gpt_sovits_lang(
                opts.prompt_lang or os.getenv("GPT_SOVITS_PROMPT_LANG", "zh"), "zh"
            ),
            "text_split_method": "cut5",
            "batch_size": 1,
            "media_type": "wav",
            "streaming_mode": False,
            "parallel_infer": True,
        }

        try:
            response = requests.post(
                api_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
        except Exception as exc:
            _gpt_sovits_manager.reset_weights()
            raise TTSError(f"GPT-SoVITS 请求异常: {exc}", 500)

        if not response.ok:
            _gpt_sovits_manager.reset_weights()
            raise TTSError(
                f"GPT-SoVITS TTS request failed ({response.status_code}): {response.text[:240]}",
                status=response.status_code,
            )
        audio_bytes = _response_to_audio(response)
        content_type = response.headers.get("content-type") or "audio/wav"
        return {
            "audio_bytes": audio_bytes,
            "content_type": content_type,
            "provider": "gpt-sovits",
        }

    try:
        return _gpt_sovits_manager.run_exclusive(_do)
    except TTSError:
        raise
    except Exception as exc:
        raise TTSError(f"GPT-SoVITS 执行错误: {exc}", 500)


def _synthesize_mimo(opts: SynthesizeOptions, api_url: str) -> Dict[str, Any]:
    _requests_or_raise()
    if not opts.api_key:
        raise TTSError("MiMo TTS API 未配置，请设置 API Key", 400)
    use_voice = opts.voice or "mimo_default"
    use_model = opts.model or "mimo-v2.5-tts"
    payload: Dict[str, Any] = {
        "model": use_model,
        "messages": [
            {"role": "user", "content": _tts_read_instruction(opts.text, opts.text_lang)},
            {"role": "assistant", "content": opts.text},
        ],
        "modalities": ["audio"],
        "audio": {"format": "wav", "voice": use_voice},
    }
    if opts.prompt_audio:
        payload["audio"]["prompt_audio"] = opts.prompt_audio

    try:
        response = requests.post(
            api_url,
            headers={"Content-Type": "application/json", "api-key": opts.api_key},
            json=payload,
            timeout=120,
        )
    except Exception as exc:
        raise TTSError(f"MiMo 请求异常: {exc}", 500)
    if not response.ok:
        raise TTSError(
            f"MiMo TTS request failed ({response.status_code}): {response.text[:240]}",
            status=response.status_code,
        )
    try:
        data = response.json()
    except Exception as exc:
        raise TTSError(f"MiMo 响应 JSON 解析失败: {exc}", 500)

    audio_b64 = _pick_audio_base64(data)
    if not audio_b64:
        raise TTSError("无法解析 MiMo TTS 音频数据", 500)
    return {
        "audio_bytes": _decode_audio_bytes(audio_b64),
        "content_type": "audio/wav",
        "provider": "mimo",
    }


def _synthesize_elevenlabs(opts: SynthesizeOptions, api_url: str) -> Dict[str, Any]:
    _requests_or_raise()
    if not opts.api_key:
        raise TTSError("ElevenLabs TTS API 未配置，请设置 API Key", 400)
    use_model = opts.model or "eleven_multilingual_v2"
    base = api_url.rstrip("/")
    if re.search(r"/text-to-speech/[^/]+/?$", base, re.IGNORECASE):
        request_url = base
    else:
        voice = opts.voice or "21m00Tcm4TlvDq8ikWAM"
        request_url = f"{base}/{voice}"
    payload = {"text": opts.text, "model_id": use_model}
    try:
        response = requests.post(
            request_url,
            headers={"Content-Type": "application/json", "xi-api-key": opts.api_key},
            json=payload,
            timeout=120,
        )
    except Exception as exc:
        raise TTSError(f"ElevenLabs 请求异常: {exc}", 500)
    if not response.ok:
        raise TTSError(
            f"ElevenLabs TTS request failed ({response.status_code}): {response.text[:240]}",
            status=response.status_code,
        )
    return {
        "audio_bytes": _response_to_audio(response),
        "content_type": response.headers.get("content-type") or "audio/mpeg",
        "provider": "elevenlabs",
    }


def _synthesize_minimax(opts: SynthesizeOptions, api_url: str) -> Dict[str, Any]:
    _requests_or_raise()
    if not opts.api_key:
        raise TTSError("MiniMax TTS API 未配置，请设置 API Key", 400)
    use_model = opts.model or "speech-2.8-hd"
    use_voice = opts.voice or DEFAULT_MINIMAX_VOICE_ID
    speed = max(0.25, min(float(opts.speed or 1.0), 4.0))
    payload = {
        "model": use_model,
        "text": opts.text,
        "stream": False,
        "language_boost": minimax_language_boost(opts.text_lang or "ja"),
        "voice_setting": {
            "voice_id": use_voice,
            "speed": speed,
            "vol": 1,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }
    try:
        response = requests.post(
            api_url,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {opts.api_key}"},
            json=payload,
            timeout=120,
        )
    except Exception as exc:
        raise TTSError(f"MiniMax 请求异常: {exc}", 500)
    if not response.ok:
        raise TTSError(
            f"MiniMax TTS request failed ({response.status_code}): {response.text[:240]}",
            status=response.status_code,
        )
    try:
        data = response.json()
    except Exception as exc:
        raise TTSError(f"MiniMax 响应 JSON 解析失败: {exc}", 500)
    audio_b64 = _pick_audio_base64(data)
    if not audio_b64:
        raise TTSError("无法解析 MiniMax TTS 音频数据", 500)
    return {
        "audio_bytes": _decode_audio_bytes(audio_b64),
        "content_type": "audio/mpeg",
        "provider": "minimax",
    }


def _synthesize_openai(opts: SynthesizeOptions, api_url: str) -> Dict[str, Any]:
    _requests_or_raise()
    if not opts.api_key:
        raise TTSError("OpenAI TTS API 未配置，请设置 API Key", 400)
    use_model = opts.model or "tts-1"
    use_voice = opts.voice or "alloy"
    payload: Dict[str, Any] = {
        "model": use_model,
        "input": opts.text,
        "voice": use_voice,
        "response_format": "mp3",
    }
    speed = float(opts.speed or 1.0)
    if 0.25 <= speed <= 4.0:
        payload["speed"] = speed
    try:
        response = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {opts.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
    except Exception as exc:
        raise TTSError(f"OpenAI TTS 请求异常: {exc}", 500)
    if not response.ok:
        raise TTSError(
            f"OpenAI TTS request failed ({response.status_code}): {response.text[:240]}",
            status=response.status_code,
        )
    return {
        "audio_bytes": _response_to_audio(response),
        "content_type": response.headers.get("content-type") or "audio/mpeg",
        "provider": "openai",
    }


def _synthesize_edge_tts(opts: SynthesizeOptions, _api_url: str) -> Dict[str, Any]:
    if not edge_tts:
        raise TTSError("edge_tts 库未安装，请先安装: pip install edge-tts", 500)

    voice = opts.voice or "zh-CN-XiaoxiaoNeural"
    rate = "+0%"
    speed = float(opts.speed or 1.0)
    if abs(speed - 1.0) > 0.01:
        pct = int(round((speed - 1.0) * 100))
        rate = f"{pct:+d}%"

    chunks = []
    content_type = "audio/mpeg"

    async def _do_async():
        nonlocal content_type
        comm = edge_tts.Communicate(text=opts.text, voice=voice, rate=rate)
        received = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                received.extend(chunk["data"])
            elif chunk["type"] == "metadata":
                pass
        return bytes(received)

    try:
        data = asyncio.run(_do_async())
    except Exception as exc:
        raise TTSError(f"Edge TTS 合成失败: {exc}", 500)
    if len(data) > MAX_TTS_AUDIO_BYTES:
        raise TTSError("TTS 音频响应过大", 413)
    return {
        "audio_bytes": data,
        "content_type": content_type,
        "provider": "edge_tts",
    }


# ============================================================
# 路由：synthesize_speech 统一入口
# ============================================================

def _resolve_provider_defaults(opts: SynthesizeOptions) -> Tuple[str, str, str, str]:
    """基于 provider 推断默认的 api_url / api_model / voice"""
    use_provider = (opts.provider or os.getenv("HUMANAIZE_TTS_PROVIDER")
                    or os.getenv("TTS_PROVIDER") or "auto").strip().lower()

    env_api_key = opts.api_key or os.getenv("HUMANAIZE_TTS_API_KEY") or os.getenv("TTS_API_KEY", "")
    env_api_url = opts.api_url or os.getenv("HUMANAIZE_TTS_API_BASE_URL") or os.getenv("TTS_API_URL", "")

    default_voice = opts.voice or os.getenv("HUMANAIZE_TTS_VOICE") or os.getenv("TTS_VOICE", "")
    default_model = opts.model or os.getenv("HUMANAIZE_TTS_API_MODEL") or os.getenv("TTS_MODEL", "")

    use_voice = default_voice
    use_model = default_model
    use_api_url = env_api_url

    if use_provider == "gpt-sovits":
        use_api_url = env_api_url or os.getenv("GPT_SOVITS_API_URL", DEFAULT_GPT_SOVITS_API_URL)
    elif use_provider == "mimo":
        use_api_url = env_api_url or DEFAULT_MIMO_API_URL
        use_voice = default_voice or "mimo_default"
        use_model = default_model or "mimo-v2.5-tts"
    elif use_provider == "minimax":
        use_api_url = env_api_url or DEFAULT_MINIMAX_API_URL
        use_voice = default_voice or DEFAULT_MINIMAX_VOICE_ID
        use_model = default_model or "speech-2.8-hd"
    elif use_provider == "elevenlabs":
        use_api_url = env_api_url or DEFAULT_ELEVENLABS_API_URL
        use_model = default_model or "eleven_multilingual_v2"
    elif use_provider in ("openai", "openai_compatible", "cloud"):
        use_provider = "openai"
        use_api_url = env_api_url or DEFAULT_OPENAI_API_URL
        use_voice = default_voice or "alloy"
        use_model = default_model or "tts-1"
    elif use_provider == "edge_tts":
        use_voice = default_voice or "zh-CN-XiaoxiaoNeural"
        use_api_url = env_api_url or ""
    elif use_provider in ("auto", ""):
        use_provider = "edge_tts" if edge_tts else "pyttsx3"  # 最后由上层回退
        use_voice = default_voice or "zh-CN-XiaoxiaoNeural"
        use_api_url = env_api_url or ""

    return use_provider, env_api_key, use_voice, use_model, use_api_url  # type: ignore


def synthesize_speech(opts: SynthesizeOptions) -> Dict[str, Any]:
    """
    统一 TTS 合成入口。

    返回:
      {
        "audio_bytes": bytes,
        "content_type": str,   # e.g. "audio/wav" / "audio/mpeg"
        "provider": str,       # 实际 provider
      }

    抛出:
      TTSError(message, status)
    """
    normalized_text = str(opts.text or "").strip()
    if not normalized_text or len(normalized_text) > 8000:
        raise TTSError("朗读文本长度必须在 1 到 8000 字之间", 400)
    opts.text = normalized_text

    use_provider, env_api_key, use_voice, use_model, use_api_url = _resolve_provider_defaults(opts)

    opts.provider = use_provider
    opts.api_key = env_api_key
    opts.voice = use_voice
    opts.model = use_model

    if use_provider in {"pyttsx3", "auto"}:
        # 上层 VoiceService 会处理本地引擎，这里抛错让其回退
        raise TTSError(f"Provider '{use_provider}' 由 VoiceService 本地处理", 501)

    if use_provider != "gpt-sovits" and not opts.api_key:
        # edge_tts 不需要密钥
        if use_provider != "edge_tts":
            raise TTSError("TTS API 未配置，请设置 API Key", 400)

    use_api_url_final = validate_tts_url(use_api_url, use_provider) if use_provider != "edge_tts" else ""

    if use_provider == "gpt-sovits":
        return _synthesize_gpt_sovits(opts, use_api_url_final)
    if use_provider == "mimo":
        return _synthesize_mimo(opts, use_api_url_final)
    if use_provider == "elevenlabs":
        return _synthesize_elevenlabs(opts, use_api_url_final)
    if use_provider == "minimax":
        return _synthesize_minimax(opts, use_api_url_final)
    if use_provider == "openai":
        return _synthesize_openai(opts, use_api_url_final)
    if use_provider == "edge_tts":
        return _synthesize_edge_tts(opts, "")

    raise TTSError(f"未知的 TTS provider: {use_provider}", 400)
