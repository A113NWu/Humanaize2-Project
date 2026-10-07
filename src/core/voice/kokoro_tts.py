# -*- coding: utf-8 -*-
"""Kokoro 本地神經語音（sherpa-onnx 推理）。

替換 edge-tts：純本地、免 API Key、免聯網，
音質接近商業級神經 TTS。

- 模型：kokoro-multi-lang-v1_1（中英，103 個音色，24kHz）
- 權重優先用 fp32 model.onnx：無 AVX-VNNI 的舊 Intel CPU 上 fp32 比 int8 快約 3 倍；
  model.onnx 缺失時回退 model.int8.onnx（新 CPU/磁盤空間受限場景）
- 首次加載約 10-25 秒，進程內只加載一次；支持後台預熱
- 輸出：WAV（PCM16 mono 24kHz）
"""

import io
import os
import sys
import wave
import struct
import threading
import logging

logger = logging.getLogger(__name__)

_MODEL_DIRNAME = "kokoro-multi-lang-v1_1"

# sid -> 音色名（v1.1 中英模型官方映射，3-57 中文女聲 zf_*，58-102 中文男聲 zm_*）
_VOICE_BY_SID = {
    0: "af_maple", 1: "af_sol", 2: "bf_vale", 3: "zf_001",
    4: "zf_002", 5: "zf_003", 6: "zf_004", 7: "zf_005",
    8: "zf_006", 9: "zf_007", 10: "zf_008", 11: "zf_017",
    12: "zf_018", 13: "zf_019", 14: "zf_021", 15: "zf_022",
    16: "zf_023", 17: "zf_024", 18: "zf_026", 19: "zf_027",
    20: "zf_028", 21: "zf_032", 22: "zf_036", 23: "zf_038",
    24: "zf_039", 25: "zf_040", 26: "zf_042", 27: "zf_043",
    28: "zf_044", 29: "zf_046", 30: "zf_047", 31: "zf_048",
    32: "zf_049", 33: "zf_051", 34: "zf_059", 35: "zf_060",
    36: "zf_067", 37: "zf_070", 38: "zf_071", 39: "zf_072",
    40: "zf_073", 41: "zf_074", 42: "zf_075", 43: "zf_076",
    44: "zf_077", 45: "zf_078", 46: "zf_079", 47: "zf_083",
    48: "zf_084", 49: "zf_085", 50: "zf_086", 51: "zf_087",
    52: "zf_088", 53: "zf_090", 54: "zf_092", 55: "zf_093",
    56: "zf_094", 57: "zf_099", 58: "zm_009", 59: "zm_010",
    60: "zm_011", 61: "zm_012", 62: "zm_013", 63: "zm_014",
    64: "zm_015", 65: "zm_016", 66: "zm_020", 67: "zm_025",
    68: "zm_029", 69: "zm_030", 70: "zm_031", 71: "zm_033",
    72: "zm_034", 73: "zm_035", 74: "zm_037", 75: "zm_041",
    76: "zm_045", 77: "zm_050", 78: "zm_052", 79: "zm_053",
    80: "zm_054", 81: "zm_055", 82: "zm_056", 83: "zm_057",
    84: "zm_058", 85: "zm_061", 86: "zm_062", 87: "zm_063",
    88: "zm_064", 89: "zm_065", 90: "zm_066", 91: "zm_068",
    92: "zm_069", 93: "zm_080", 94: "zm_081", 95: "zm_082",
    96: "zm_089", 97: "zm_091", 98: "zm_095", 99: "zm_096",
    100: "zm_097", 101: "zm_098", 102: "zm_100",
}
_SID_BY_VOICE = {name: sid for sid, name in _VOICE_BY_SID.items()}
DEFAULT_SID = 3  # zf_001：年輕中文女聲，Aize 預設嗓音

# 按句切分（Kokoro 單次只處理一句，長文需客戶端拼接）
_SENT_SPLIT = __import__("re").compile(r"[^，。！？!?；;\n]+[，。！？!?；;\n]?")

# espeak-zh 無法音素化的拉丁專有名詞 -> 中文諧音（避免漏讀）
_NAME_FIX = __import__("re").compile(r"\bAize\b", __import__("re").IGNORECASE)


def _fix_text(text: str) -> str:
    return _NAME_FIX.sub("艾澤", str(text or ""))


def model_dir() -> str:
    """定位模型目錄，查找順序：
    1. 打包內置 _MEIPASS/voice/models/...
    2. onefile 外置：exe 同級 data/voice/models/...（推薦，避免每次啟動解壓 ~200MB）
    3. onefile 外置：exe 同級 voice/models/...
    4. 開發態 src/core/voice/models/...
    """
    candidates = []
    mei = getattr(sys, "_MEIPASS", "")
    if mei:
        candidates.append(os.path.join(mei, "voice", "models", _MODEL_DIRNAME))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "data", "voice", "models", _MODEL_DIRNAME))
        candidates.append(os.path.join(exe_dir, "voice", "models", _MODEL_DIRNAME))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "models", _MODEL_DIRNAME))
    for c in candidates:
        if model_file(c):
            return c
    return ""


def model_file(directory: str) -> str:
    """模型權重路徑：優先 fp32 model.onnx，回退 int8。

    11 代及更早 Intel 移動 CPU（Tiger Lake 等）無 AVX-VNNI，onnxruntime
    int8 kernel 走慢路徑，實測 fp32 比 int8 快約 3 倍（RTF 0.76 vs 2.35）。
    """
    for name in ("model.onnx", "model.int8.onnx"):
        p = os.path.join(directory, name)
        if os.path.exists(p):
            return p
    return ""


def available() -> bool:
    try:
        import sherpa_onnx  # noqa: F401
    except Exception:
        return False
    return bool(model_dir())


def resolve_sid(voice: str) -> int:
    """音色參數 -> sid。支持 'zf_001' / 'zm_009' / '3' / 空（預設）。
    非 Kokoro 體系的名字（如 edge 的 zh-CN-XiaoxiaoNeural）一律回落預設。"""
    v = str(voice or "").strip().lower()
    if not v:
        return DEFAULT_SID
    if v in _SID_BY_VOICE:
        return _SID_BY_VOICE[v]
    if v.isdigit():
        sid = int(v)
        if 0 <= sid < len(_VOICE_BY_SID):
            return sid
    return DEFAULT_SID


def _to_wav_bytes(samples, sample_rate: int) -> bytes:
    pcm = bytearray()
    for s in samples:
        v = int(max(-1.0, min(1.0, float(s))) * 32767)
        pcm += struct.pack("<h", v)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(pcm))
    return buf.getvalue()


class KokoroTTS:
    """進程內單例：模型只加載一次，合成串行（sherpa 句柄非線程安全）。"""

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._tts = None
        self._load_lock = threading.Lock()
        self._synth_lock = threading.Lock()
        self._failed = False

    @classmethod
    def instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def is_ready(self) -> bool:
        return self._tts is not None

    def warmup_async(self):
        """後台預熱：應用啟動後調用，首次朗讀時模型通常已就緒。"""
        threading.Thread(target=self._ensure_loaded, daemon=True).start()

    def _ensure_loaded(self):
        if self._tts is not None or self._failed:
            return self._tts
        with self._load_lock:
            if self._tts is not None or self._failed:
                return self._tts
            try:
                import sherpa_onnx
                d = model_dir()
                if not d:
                    raise FileNotFoundError("Kokoro 模型目錄缺失")
                cfg = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(
                        kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                            model=model_file(d),
                            voices=os.path.join(d, "voices.bin"),
                            tokens=os.path.join(d, "tokens.txt"),
                            data_dir=os.path.join(d, "espeak-ng-data"),
                            dict_dir=os.path.join(d, "dict"),
                            lexicon=os.path.join(d, "lexicon-zh.txt"),
                            lang="zh",
                        ),
                        num_threads=4,
                        debug=False,
                    ),
                    rule_fsts=",".join(os.path.join(d, f) for f in
                                       ("date-zh.fst", "number-zh.fst", "phone-zh.fst")),
                    max_num_sentences=1,
                )
                self._tts = sherpa_onnx.OfflineTts(cfg)
                logger.info("[Kokoro] 模型加載完成（%d 個音色）", self._tts.num_speakers)
            except Exception as e:
                self._failed = True
                logger.warning("[Kokoro] 模型加載失敗: %s", e)
        return self._tts

    def synthesize(self, text: str, voice: str = "", speed: float = 1.0) -> bytes:
        """文本 -> WAV bytes。長文本按句合成後拼接。"""
        tts = self._ensure_loaded()
        if tts is None:
            raise RuntimeError("Kokoro TTS 不可用（模型加載失敗）")
        sid = resolve_sid(voice)
        speed = float(speed or 1.0)
        pieces = [m.group(0) for m in _SENT_SPLIT.finditer(_fix_text(text))] or [text]
        all_samples = []
        rate = tts.sample_rate
        with self._synth_lock:
            for piece in pieces:
                piece = piece.strip()
                if not piece:
                    continue
                audio = tts.generate(piece[:200], sid=sid, speed=speed)
                all_samples.extend(list(audio.samples))
                all_samples.extend([0.0] * (rate // 8))  # 句間 125ms 停頓
        return _to_wav_bytes(all_samples, rate)
