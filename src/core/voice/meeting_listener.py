# -*- coding: utf-8 -*-
"""
會議旁聽器（騰訊會議等任意會議軟件通用）

鏈路：
  音頻捕獲（WASAPI loopback 優先，麥克風兜底）
  → Google 語音識別（網絡，無需本地模型）
  → 滾動逐字稿（內存 deque + 落盤文件）
  → 定期/手動調 LLM 生成會議摘要
  → 摘要推送到 Live2D 聊天中樞（web UI 可見）

外部入口：get_meeting_listener() 單例；API 路由 /api/meeting/*。
"""
from __future__ import annotations

import os
import threading
import time
import traceback
from collections import deque
from datetime import datetime

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import pyaudiowpatch as paw
except Exception:
    paw = None


def _data_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "Humanaize2", "data", "meeting")
    os.makedirs(d, exist_ok=True)
    return d


class MeetingListener:
    """持續旁聽會議音頻，轉寫並定期總結"""

    CHUNK_SECONDS = 4          # 每段送識別的音頻長度
    SUMMARY_INTERVAL = 300     # 自動摘要間隔（秒）
    SUMMARY_MIN_CHARS = 200    # 觸發自動摘要的最少新字數

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._running = False
        self._source = ""        # loopback / microphone
        self._error = ""
        self._transcript = deque(maxlen=3000)   # (HH:MM:SS, text)
        self._new_chars = 0
        self._last_summary_ts = 0.0
        self._summary = ""
        self._summarizing = False

    # ------------------------------------------------------------------
    # 對外接口
    # ------------------------------------------------------------------
    def start(self) -> dict:
        with self._lock:
            if self._running:
                return {"ok": True, "already": True, "source": self._source}
            self._stop.clear()
            self._error = ""
            self._thread = threading.Thread(target=self._loop, daemon=True, name="MeetingListener")
            self._thread.start()
            self._running = True
        return {"ok": True}

    def stop(self) -> dict:
        with self._lock:
            self._stop.set()
            self._running = False
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=5)
        return {"ok": True}

    def status(self) -> dict:
        with self._lock:
            last = self._transcript[-1] if self._transcript else None
            return {
                "running": self._running,
                "source": self._source,
                "error": self._error,
                "lines": len(self._transcript),
                "summary": self._summary,
                "summarizing": self._summarizing,
                "last": {"time": last[0], "text": last[1]} if last else None,
                "transcript_file": os.path.join(_data_dir(), "transcript.txt"),
            }

    def transcript(self, limit: int = 500) -> dict:
        with self._lock:
            lines = list(self._transcript)[-limit:]
        return {"lines": [{"time": t, "text": x} for t, x in lines]}

    def summarize_now(self) -> dict:
        if self._summarizing:
            return {"ok": False, "error": "summarizing"}
        threading.Thread(target=self._do_summary, kwargs={"force": True}, daemon=True).start()
        return {"ok": True}

    # ------------------------------------------------------------------
    # 捕獲主循環
    # ------------------------------------------------------------------
    def _loop(self):
        try:
            if paw is not None:
                self._source = "loopback"
                self._loop_loopback()
            elif sr is not None:
                self._source = "microphone"
                self._loop_mic()
            else:
                self._error = "無可用音頻後端（缺 pyaudiowpatch / speech_recognition）"
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        finally:
            with self._lock:
                self._running = False

    def _loop_loopback(self):
        """WASAPI loopback：捕獲揚聲器輸出（會議聲音），不需要虛擬聲卡"""
        p = paw.PyAudio()
        try:
            dev = p.get_default_wasapi_loopback()
            rate = int(dev["defaultSampleRate"])
            channels = int(dev["maxInputChannels"]) or 2
            frames_per = rate * self.CHUNK_SECONDS
            stream = p.open(format=paw.paInt16, channels=channels, rate=rate,
                            input=True, input_device_index=dev["index"],
                            frames_per_buffer=rate)  # 1s buffer
            try:
                while not self._stop.is_set():
                    frames = stream.read(frames_per, exception_on_overflow=False)
                    pcm = self._to_mono(frames, channels)
                    self._recognize_chunk(pcm, rate)
            finally:
                try:
                    stream.stop_stream(); stream.close()
                except Exception:
                    pass
        finally:
            p.terminate()

    def _loop_mic(self):
        """麥克風兜底：會議外放時可用"""
        r = sr.Recognizer()
        with sr.Microphone(sample_rate=16000) as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            while not self._stop.is_set():
                try:
                    audio = r.listen(source, timeout=1, phrase_time_limit=self.CHUNK_SECONDS)
                except sr.WaitTimeoutError:
                    continue
                self._recognize_audio(audio)

    @staticmethod
    def _to_mono(frames: bytes, channels: int) -> bytes:
        """純標準庫立體聲→單聲道（audioop 已在 3.13 移除）"""
        if channels <= 1:
            return frames
        import array
        a = array.array("h")
        a.frombytes(frames)
        n = len(a) // channels
        mono = array.array("h", bytes(0))
        if channels == 2:
            mono = array.array("h", ((a[i] + a[i + 1]) // 2 for i in range(0, n * 2, 2)))
        else:
            mono = array.array("h", (sum(a[i:i + channels]) // channels
                                       for i in range(0, n * channels, channels)))
        return mono.tobytes()

    # ------------------------------------------------------------------
    # 識別與記錄
    # ------------------------------------------------------------------
    def _recognize_chunk(self, pcm: bytes, rate: int):
        if sr is None:
            return
        audio = sr.AudioData(pcm, rate, 2)
        self._recognize_audio(audio)

    def _recognize_audio(self, audio):
        r = sr.Recognizer()
        text = ""
        try:
            text = r.recognize_google(audio, language="zh-CN") or ""
        except sr.UnknownValueError:
            pass
        except Exception as e:
            # 網絡故障等：記一次錯誤但繼續跑
            self._error = f"stt: {type(e).__name__}: {e}"
            time.sleep(2)
            return
        if not text:
            return
        # 英文補識別（中文識別結果太短且音頻較長時）
        if len(text) < 4:
            try:
                en = r.recognize_google(audio, language="en-US") or ""
                if len(en) > len(text):
                    text = en
            except Exception:
                pass
        self._append(text.strip())

    def _append(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._transcript.append((ts, text))
            self._new_chars += len(text)
            new_chars = self._new_chars
            due = (time.time() - self._last_summary_ts) > self.SUMMARY_INTERVAL
        # 落盤
        try:
            with open(os.path.join(_data_dir(), "transcript.txt"), "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {text}\n")
        except OSError:
            pass
        # 自動摘要
        if due and new_chars >= self.SUMMARY_MIN_CHARS and not self._summarizing:
            threading.Thread(target=self._do_summary, daemon=True).start()

    # ------------------------------------------------------------------
    # 摘要
    # ------------------------------------------------------------------
    def _do_summary(self, force: bool = False):
        with self._lock:
            if self._summarizing:
                return
            self._summarizing = True
            lines = list(self._transcript)[-200:]
        try:
            if not lines:
                return
            text = "\n".join(f"[{t}] {x}" for t, x in lines)
            from llm import chat
            prompt = (
                "以下是線上會議的語音轉寫片段（可能含識別錯誤）。"
                "請用繁體中文輸出 3~6 條會議重點，標註關鍵人名/結論/待辦；"
                "若片段無實質內容，只回「（無實質內容）」。不要寒暄。\n\n" + text
            )
            summary = (chat(prompt, max_tokens=800, timeout=60, max_retries=1) or "").strip()
            if summary and "無實質內容" not in summary:
                with self._lock:
                    self._summary = summary
                    self._last_summary_ts = time.time()
                    self._new_chars = 0
                self._push_summary(summary)
        except Exception as e:
            self._error = f"summary: {type(e).__name__}: {e}"
        finally:
            with self._lock:
                self._summarizing = False

    def _push_summary(self, summary: str):
        """摘要推送到 Live2D 聊天中樞，web UI 聊天區可見"""
        try:
            from tools.live2d_hub import get_live2d_hub
            get_live2d_hub().ingest_chat(
                source="meeting", user="會議摘要",
                text=f"📋 會議摘要（{datetime.now().strftime('%H:%M')}）\n{summary}")
        except Exception:
            pass


_listener = MeetingListener()


def get_meeting_listener() -> MeetingListener:
    return _listener
