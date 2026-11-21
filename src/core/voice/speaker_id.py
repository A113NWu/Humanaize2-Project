# -*- coding: utf-8 -*-
"""離線聲紋識別：登記具名說話人 + 即時麥克風匹配。

基於 sherpa-onnx SpeakerEmbeddingExtractor + SpeakerEmbeddingManager（CPU、不聯網）。
模型首次缺失時會嘗試從 GitHub 下載到 data/models/speaker/；下載失敗則清晰降級，
絕不崩潰，也絕不在揚聲器播放任何聲音。

共享狀態 get_current_speaker() 供 thinking_engine 在組 prompt 時注入，讓 Aize
知道「現在是誰在說話」。
"""
import json
import logging
import os
import threading
import time
import urllib.request
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import sherpa_onnx as _so
except Exception:  # pragma: no cover
    _so = None

try:
    import pyaudio
except Exception:  # pragma: no cover
    pyaudio = None

MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/"
    "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
)
SAMPLE_RATE = 16000
DEFAULT_THRESHOLD = 0.55        # 餘弦相似度閾值，越高越嚴格
DEFAULT_ENROLL_SECONDS = 6      # 登記採樣秒數
WINDOW_SECONDS = 3.0            # 即時識別滑窗
SILENCE_RMS = 0.012             # 低於此視為靜音，直接跳過
SPEAKER_TTL = 30.0              # 當前說話人狀態有效期（秒）


def _data_dir() -> str:
    try:
        from app_paths import app_data_dir
        return app_data_dir()
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")


def _model_path() -> str:
    return os.path.join(_data_dir(), "models", "speaker", "3dspeaker_sv.onnx")


def _registry_path() -> str:
    return os.path.join(_data_dir(), "speaker", "registry.json")


# ---------------- 共享當前說話人狀態（prompt 注入用） ----------------

_current_lock = threading.Lock()
_current = {"name": None, "since": 0.0, "score": 0.0}


def get_current_speaker() -> Optional[dict]:
    """回傳目前偵測到的說話人 {name, score}，逾時或無人則 None。"""
    with _current_lock:
        name = _current["name"]
        if not name:
            return None
        if time.time() - _current["since"] > SPEAKER_TTL:
            return None
        return {"name": name, "score": _current["score"]}


def set_current_speaker(name: Optional[str], score: float = 0.0) -> None:
    with _current_lock:
        _current["name"] = name
        _current["since"] = time.time()
        _current["score"] = float(score or 0.0)


# ---------------- 核心 ----------------

class SpeakerId:
    _instance: "Optional[SpeakerId]" = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()
        self._ext = None
        self._mgr = None
        self._dim = None
        self._load_error: Optional[str] = None
        self._registry: dict = {}
        self._listener_thread: Optional[threading.Thread] = None
        self._listener_stop = threading.Event()
        self._on_change: Optional[Callable[[Optional[str]], None]] = None
        self._load_registry()

    @classmethod
    def get(cls) -> "SpeakerId":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ---- 模型 / 提取器 ----

    def _ensure_model(self) -> Tuple[bool, str]:
        path = _model_path()
        if os.path.isfile(path) and os.path.getsize(path) > 1_000_000:
            return True, path
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            logger.info("[speaker] 聲紋模型缺失，從 GitHub 下載中…")
            urllib.request.urlretrieve(MODEL_URL, path)
        except Exception as e:
            self._load_error = f"模型下載失敗：{e}"
            return False, self._load_error
        if not (os.path.isfile(path) and os.path.getsize(path) > 1_000_000):
            self._load_error = "模型下載不完整"
            return False, self._load_error
        return True, path

    def _ensure_extractor(self) -> bool:
        if self._ext is not None:
            return True
        if _so is None:
            self._load_error = "未安裝 sherpa-onnx"
            return False
        ok, info = self._ensure_model()
        if not ok:
            return False
        try:
            cfg = _so.SpeakerEmbeddingExtractorConfig(model=info, num_threads=1)
            self._ext = _so.SpeakerEmbeddingExtractor(cfg)
            self._dim = self._ext.dim
            self._mgr = _so.SpeakerEmbeddingManager(self._dim)
            for name, emb in self._registry.items():
                self._mgr.add(name, emb)
            return True
        except Exception as e:
            self._load_error = f"模型加載失敗：{e}"
            logger.exception("[speaker] extractor init failed")
            return False

    def is_available(self) -> Tuple[bool, str]:
        if not self._ensure_extractor():
            return False, (self._load_error or "聲紋引擎不可用")
        if pyaudio is None:
            return False, "未安裝 PyAudio，無法使用麥克風"
        return True, "ok"

    # ---- 注冊表持久化 ----

    def _load_registry(self) -> None:
        try:
            with open(_registry_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._registry = {str(k): list(v) for k, v in (data or {}).items()
                              if isinstance(v, list) and v}
        except FileNotFoundError:
            self._registry = {}
        except Exception:
            logger.exception("[speaker] registry load failed")
            self._registry = {}

    def _save_registry(self) -> None:
        try:
            os.makedirs(os.path.dirname(_registry_path()), exist_ok=True)
            with open(_registry_path(), "w", encoding="utf-8") as f:
                json.dump(self._registry, f, ensure_ascii=False)
        except Exception:
            logger.exception("[speaker] registry save failed")

    def list_speakers(self) -> List[str]:
        return sorted(self._registry.keys())

    # ---- 麥克風 ----

    def _record_mic(self, seconds: float) -> Optional["np.ndarray"]:
        if pyaudio is None or np is None:
            return None
        pa = pyaudio.PyAudio()
        frames = []
        stream = None
        try:
            stream = pa.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                             input=True, frames_per_buffer=1024)
            chunks = int(SAMPLE_RATE * seconds / 1024) + 1
            for _ in range(chunks):
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)
        except Exception:
            logger.exception("[speaker] mic record failed")
            return None
        finally:
            try:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
            except Exception:
                pass
            pa.terminate()
        if not frames:
            return None
        raw = b"".join(frames)
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        # 取整秒，避免末尾不完整幀
        n = int(SAMPLE_RATE * seconds)
        if arr.size > n:
            arr = arr[:n]
        return arr

    @staticmethod
    def _rms(arr) -> float:
        if np is None or arr is None or arr.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(arr))))

    # ---- 嵌入 / 登記 / 識別 ----

    def _embed(self, samples) -> Optional[List[float]]:
        if samples is None or len(samples) == 0:
            return None
        if not self._ensure_extractor():
            return None
        try:
            st = self._ext.create_stream()
            st.accept_waveform(SAMPLE_RATE, samples)
            emb = self._ext.compute(st)
            return list(emb) if emb is not None else None
        except Exception:
            logger.exception("[speaker] embed failed")
            return None

    def enroll(self, name: str, seconds: int = DEFAULT_ENROLL_SECONDS) -> dict:
        name = str(name or "").strip()
        if not name:
            return {"ok": False, "error": "名字不能為空"}
        ok, err = self.is_available()
        if not ok:
            return {"ok": False, "error": err}
        seconds = max(3, min(int(seconds or DEFAULT_ENROLL_SECONDS), 15))
        samples = self._record_mic(seconds)
        if samples is None:
            return {"ok": False, "error": "麥克風錄音失敗（裝置被佔用或無麥克風）"}
        if self._rms(samples) < SILENCE_RMS:
            return {"ok": False, "error": "錄音音量太低，請靠近麥克風再試"}
        emb = self._embed(samples)
        if not emb:
            return {"ok": False, "error": "聲紋提取失敗"}
        with self._lock:
            # 重複登記同名先移除再加入（更新聲紋）
            if self._mgr is not None and name in (self._mgr.all_speakers or []):
                try:
                    self._mgr.remove(name)
                except Exception:
                    pass
            self._registry[name] = emb
            if self._mgr is not None:
                self._mgr.add(name, emb)
            self._save_registry()
        return {"ok": True, "name": name, "seconds": seconds, "speakers": self.list_speakers()}

    def remove(self, name: str) -> bool:
        with self._lock:
            if name not in self._registry:
                return False
            del self._registry[name]
            if self._mgr is not None:
                try:
                    self._mgr.remove(name)
                except Exception:
                    pass
            self._save_registry()
        return True

    def identify(self, samples) -> Tuple[Optional[str], float]:
        if not self._ensure_extractor() or self._mgr is None or not self._registry:
            return None, 0.0
        emb = self._embed(samples)
        if not emb:
            return None, 0.0
        try:
            name = self._mgr.search(emb, threshold=DEFAULT_THRESHOLD)
        except Exception:
            logger.exception("[speaker] search failed")
            return None, 0.0
        if not name:
            return None, 0.0
        # sherpa 的 verify() 只回 bool，這裡用註冊向量算餘弦相似度作為置信度
        score = 0.0
        try:
            ref = self._registry.get(name)
            if ref and np is not None:
                a = np.asarray(ref, dtype=np.float32)
                b = np.asarray(emb, dtype=np.float32)
                na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
                if na > 0 and nb > 0:
                    score = float(np.dot(a, b) / (na * nb))
        except Exception:
            score = 0.0
        return str(name), score

    # ---- 即時監聽 ----

    def start_listener(self, on_change: Optional[Callable[[Optional[str]], None]] = None) -> dict:
        ok, err = self.is_available()
        if not ok:
            return {"ok": False, "error": err}
        if not self._registry:
            return {"ok": False, "error": "尚未登記任何說話人，請先登記聲紋"}
        if self.listener_running():
            return {"ok": True, "running": True, "speakers": self.list_speakers()}
        self._on_change = on_change
        self._listener_stop.clear()
        self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._listener_thread.start()
        return {"ok": True, "running": True, "speakers": self.list_speakers()}

    def stop_listener(self) -> dict:
        self._listener_stop.set()
        set_current_speaker(None, 0.0)
        return {"ok": True, "running": False}

    def listener_running(self) -> bool:
        return self._listener_thread is not None and self._listener_thread.is_alive()

    def _listener_loop(self) -> None:
        logger.info("[speaker] listener started")
        last_name = None
        while not self._listener_stop.is_set():
            try:
                samples = self._record_mic(WINDOW_SECONDS)
                if samples is None:
                    time.sleep(0.5)
                    continue
                # 靜音窗口：不識別，但如果之前有人說話，標記變成無人
                if self._rms(samples) < SILENCE_RMS:
                    if last_name is not None:
                        last_name = None
                        set_current_speaker(None, 0.0)
                        if self._on_change:
                            try:
                                self._on_change(None)
                            except Exception:
                                pass
                    continue
                name, score = self.identify(samples)
                if name:
                    # 每窗都刷新 since，避免持續說話時因 TTL 過期被誤判成「無人」
                    set_current_speaker(name, score)
                    if name != last_name:
                        last_name = name
                        logger.info(f"[speaker] detected speaker={name} score={score:.3f}")
                        if self._on_change:
                            try:
                                self._on_change(name)
                            except Exception:
                                pass
                elif not name and last_name is not None:
                    # 短暫未匹配到，不立即清空（避免抖動），由 TTL 過期處理
                    pass
            except Exception:
                logger.exception("[speaker] listener loop error")
                time.sleep(1.0)
        logger.info("[speaker] listener stopped")


def get_speaker_id() -> SpeakerId:
    return SpeakerId.get()
