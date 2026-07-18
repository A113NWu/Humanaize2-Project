import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from typing import Callable, Optional

try:
    import speech_recognition as sr
except Exception:  # pragma: no cover - optional dependency
    sr = None

try:
    import pyttsx3
except Exception:  # pragma: no cover - optional dependency
    pyttsx3 = None

try:
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None

try:
    import whisper
    if not hasattr(whisper, 'load_model'):
        whisper = None
except Exception:  # pragma: no cover - optional dependency
    whisper = None

try:
    from gtts import gTTS
except Exception:  # pragma: no cover - optional dependency
    gTTS = None


def resolve_tts_config(tts_settings: Optional[dict] = None) -> dict:
    settings = tts_settings or {}
    backend = str(settings.get("backend") or os.getenv("HUMANAIZE_TTS_BACKEND") or "auto").strip().lower()
    if backend in {"openai", "openai_tts", "cloud"}:
        backend = "openai"
    elif backend in {"gtts", "google_tts", "google"}:
        backend = "gtts"
    elif backend not in {"auto", "pyttsx3", "piper", "openai", "gtts"}:
        backend = "auto"
    return {
        "backend": backend,
        "model_path": settings.get("model_path") or os.getenv("HUMANAIZE_TTS_MODEL_PATH") or "",
        "voice": settings.get("voice") or os.getenv("HUMANAIZE_TTS_VOICE") or "",
        "speed": float(settings.get("speed") or os.getenv("HUMANAIZE_TTS_SPEED") or 1.0),
        "api_key": settings.get("api_key") or os.getenv("HUMANAIZE_TTS_API_KEY") or "",
        "api_base_url": settings.get("api_base_url") or os.getenv("HUMANAIZE_TTS_API_BASE_URL") or "https://api.openai.com/v1/audio/speech",
        "api_model": settings.get("api_model") or os.getenv("HUMANAIZE_TTS_API_MODEL") or "gpt-4o-mini-tts",
        "language": settings.get("language") or os.getenv("HUMANAIZE_TTS_LANGUAGE") or "auto",
    }


class VoiceService:
    def __init__(self, on_partial_text: Optional[Callable[[str], None]] = None,
                 on_final_text: Optional[Callable[[str], None]] = None,
                 on_speech_chunk: Optional[Callable[[str], None]] = None,
                 tts_settings: Optional[dict] = None):
        self.on_partial_text = on_partial_text
        self.on_final_text = on_final_text
        self.on_speech_chunk = on_speech_chunk
        self.tts_settings = tts_settings or {}
        self._recognizer = sr.Recognizer() if sr else None
        self._microphone = sr.Microphone() if sr else None
        self._engine = pyttsx3.init() if pyttsx3 else None
        self._whisper_model = None
        if whisper is not None and shutil.which('ffmpeg'):
            try:
                self._whisper_model = whisper.load_model('base')
            except Exception as exc:
                print(f"[WARN] Whisper model loading failed: {exc}")
        self._stop_event = threading.Event()
        self._thread = None
        self._queue = queue.Queue()
        self._listening = False
        self._last_partial = ""

    def start_listening(self):
        if not self._recognizer or not self._microphone:
            return False
        self._stop_event.clear()
        self._listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        return True

    def stop_listening(self):
        self._stop_event.set()
        self._listening = False

    def _listen_loop(self):
        while not self._stop_event.is_set():
            try:
                with self._microphone as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.2)
                    audio = self._recognizer.listen(source, timeout=1, phrase_time_limit=3)
                text = self._transcribe_audio(audio)
                if text:
                    if self.on_partial_text:
                        self.on_partial_text(text)
                    if self.on_final_text:
                        self.on_final_text(text)
            except Exception:
                time.sleep(0.1)

    def _transcribe_audio(self, audio) -> str:
        if not self._recognizer:
            return ""
        if self._whisper_model and shutil.which('ffmpeg'):
            try:
                audio_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
                if audio_data:
                    text = self._transcribe_with_whisper(audio_data)
                    if text:
                        return text
            except Exception as exc:
                print(f"[WARN] Whisper transcription failed: {exc}")

        try:
            return self._recognizer.recognize_google(audio, language="zh-CN")
        except Exception:
            try:
                return self._recognizer.recognize_google(audio, language="en-US")
            except Exception as exc:
                print(f"[WARN] Google STT failed: {exc}")
                return ""

    def _transcribe_with_whisper(self, audio_data: bytes) -> str:
        if not self._whisper_model:
            return ""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as handle:
            wav_path = handle.name
        try:
            with wave.open(wav_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_data)
            result = self._whisper_model.transcribe(wav_path, language='zh', fp16=False)
            return result.get('text', '').strip()
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

    def speak(self, text: str):
        config = resolve_tts_config(self.tts_settings)
        return self._speak_with_backend(text, config)

    def speak_stream(self, text: str):
        config = resolve_tts_config(self.tts_settings)
        for chunk in chunk_text_for_speech(text):
            if self._speak_with_backend(chunk, config):
                if self.on_speech_chunk:
                    self.on_speech_chunk(chunk)
        return True

    def _speak_with_backend(self, text: str, config: dict) -> bool:
        if not text:
            return False
        backend = config.get("backend") or "auto"
        if backend == "piper":
            return self._speak_with_piper(text, config)
        if backend == "gtts":
            return self._speak_with_gtts(text, config)
        if backend == "openai":
            return self._speak_with_openai(text, config)
        if self._speak_with_espeak(text, config):
            return True
        if backend == "piper":
            return self._speak_with_piper(text, config)
        if not self._engine:
            return False
        self._engine.setProperty("rate", max(80, int(180 * config.get("speed", 1.0))))
        self._select_voice_for_text(text, config)
        self._engine.say(text)
        self._engine.runAndWait()
        return True

    def _speak_with_espeak(self, text: str, config: dict) -> bool:
        espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
        if not espeak_bin:
            return False
        try:
            cmd = [espeak_bin]
            if self._contains_chinese(text):
                cmd.extend(["-v", "zh"])
            elif config.get("voice"):
                cmd.extend(["-v", str(config["voice"])])
            cmd.extend(["-s", str(int(140 * config.get("speed", 1.0)))])
            cmd.append(text)
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as exc:
            print(f"[WARN] espeak TTS failed: {exc}")
            return False

    def _select_voice_for_text(self, text: str, config: dict):
        if not self._engine:
            return
        preferred_voice = config.get("voice") or ""
        if preferred_voice:
            try:
                self._engine.setProperty("voice", preferred_voice)
                return
            except Exception:
                pass
        if not self._contains_chinese(text):
            return
        voices = self._engine.getProperty("voices") or []
        for voice in voices:
            voice_id = getattr(voice, "id", "") or ""
            languages = getattr(voice, "languages", []) or []
            language_tokens = [str(item).lower() for item in languages]
            if any(token in {"cmn", "zh", "zh-cn", "zh-tw", "yue"} for token in language_tokens) or "cmn" in voice_id.lower() or "yue" in voice_id.lower():
                try:
                    self._engine.setProperty("voice", voice.id)
                    return
                except Exception:
                    continue

    def _speak_with_gtts(self, text: str, config: dict) -> bool:
        if not gTTS:
            print("[WARN] gTTS package is not available")
            return self._speak_with_backend(text, {**config, "backend": "auto"})
        try:
            tts = gTTS(text=text, lang='zh')
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as handle:
                mp3_path = handle.name
            try:
                tts.save(mp3_path)
                self._play_mp3(mp3_path)
                return True
            finally:
                try:
                    os.remove(mp3_path)
                except OSError:
                    pass
        except Exception as exc:
            print(f"[WARN] gTTS synthesis failed: {exc}")
            return self._speak_with_backend(text, {**config, "backend": "auto"})

    def _speak_with_openai(self, text: str, config: dict) -> bool:
        if not requests:
            print("[WARN] requests package is not available for OpenAI TTS")
            return False
        api_key = str(config.get("api_key") or "").strip()
        if not api_key:
            print("[WARN] OpenAI API key is missing. Set HUMANAIZE_TTS_API_KEY or tts_api_key")
            return False

        api_base_url = str(config.get("api_base_url") or "https://api.openai.com/v1/audio/speech").strip()
        model_name = str(config.get("api_model") or "gpt-4o-mini-tts").strip()
        voice_name = str(config.get("voice") or "alloy").strip() or "alloy"
        payload = {
            "model": model_name,
            "input": text,
            "voice": voice_name,
            "response_format": "wav",
        }
        speed = float(config.get("speed") or 1.0)
        if 0.25 <= speed <= 4.0:
            payload["speed"] = speed

        try:
            response = requests.post(
                api_base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except Exception as exc:
            print(f"[WARN] OpenAI TTS request failed: {exc}")
            return False

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = handle.name
        try:
            with open(wav_path, "wb") as handle:
                handle.write(response.content)
            self._play_wav(wav_path)
            return True
        except Exception as exc:
            print(f"[WARN] OpenAI TTS playback failed: {exc}")
            return False
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        return any("\u4e00" <= ch <= "\u9fff" for ch in text)

    def _speak_with_piper(self, text: str, config: dict) -> bool:
        piper_bin = shutil.which("piper")
        if not piper_bin:
            print("[WARN] Piper executable not found. Falling back to pyttsx3")
            return self._speak_with_backend(text, {**config, "backend": "pyttsx3"})
        model_path = config.get("model_path") or ""
        if not model_path or not os.path.exists(model_path):
            print("[WARN] Piper model path missing or invalid. Falling back to pyttsx3")
            return self._speak_with_backend(text, {**config, "backend": "pyttsx3"})

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = handle.name
        try:
            cmd = [piper_bin, "--model", model_path, "--output_file", wav_path]
            if config.get("voice"):
                cmd.extend(["--voice", str(config["voice"])])
            cmd.append(text)
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._play_wav(wav_path)
            return True
        except Exception as exc:
            print(f"[WARN] Piper TTS failed: {exc}")
            return self._speak_with_backend(text, {**config, "backend": "pyttsx3"})
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

    def _play_wav(self, wav_path: str):
        ffplay_bin = shutil.which("ffplay")
        if ffplay_bin:
            subprocess.run([ffplay_bin, "-nodisp", "-autoexit", wav_path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        aplay_bin = shutil.which("aplay")
        if aplay_bin:
            subprocess.run([aplay_bin, wav_path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _play_mp3(self, mp3_path: str):
        ffplay_bin = shutil.which("ffplay")
        if ffplay_bin:
            subprocess.run([ffplay_bin, "-nodisp", "-autoexit", mp3_path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        mpg123_bin = shutil.which("mpg123")
        if mpg123_bin:
            subprocess.run([mpg123_bin, mp3_path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def chunk_text_for_speech(text: str, chunk_size: int = 8):
    if not text:
        return []

    punctuation = set('，。！？；：,.!?;:')
    words = []
    current = []

    for ch in text:
        if ch.isspace():
            if current:
                words.append(''.join(current))
                current = []
            continue

        current.append(ch)

        if ch in punctuation:
            words.append(''.join(current))
            current = []
            continue

        if len(current) >= max(4, min(chunk_size // 2, chunk_size)):
            words.append(''.join(current))
            current = []

    if current:
        words.append(''.join(current))

    return words
