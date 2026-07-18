import os
import shutil
import tempfile
import time
import wave

import speech_recognition as sr

try:
    import whisper
except Exception:  # pragma: no cover - optional dependency
    whisper = None


def transcribe_with_whisper(audio_data: bytes):
    if not shutil.which('ffmpeg') or whisper is None:
        raise RuntimeError('ffmpeg or whisper is not available')

    model = whisper.load_model('base')
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as handle:
        wav_path = handle.name
    try:
        with wave.open(wav_path, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_data)
        result = model.transcribe(wav_path, language='zh', fp16=False)
        return result.get('text', '').strip()
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass


def main():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    print('请在 3 秒内说一句中文或英文...')
    time.sleep(1)
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)

    audio_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
    try:
        text = transcribe_with_whisper(audio_data)
        if text:
            print('识别结果:', text)
            return
    except Exception as exc:
        print('Whisper 识别失败:', exc)

    try:
        text = recognizer.recognize_google(audio, language='zh-CN')
        print('识别结果:', text)
    except Exception as exc:
        print('Google 识别失败:', exc)


if __name__ == '__main__':
    main()
