#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频识别技能执行模块
"""

import os
import sys
import base64
import subprocess
import tempfile
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# 惰性导入：只在函数内部首次使用时加载，避免 PyInstaller 静态分析时触发 heavy deps 崩溃
_speech_recognition = None
_pydub_AudioSegment = None
_llm_chat = None
_whisper = None

def _lazy_imports():
    global _speech_recognition, _pydub_AudioSegment, _llm_chat, _whisper
    if _speech_recognition is None:
        try:
            import speech_recognition as sr
            _speech_recognition = sr
        except ImportError:
            _speech_recognition = False
    if _pydub_AudioSegment is None:
        try:
            from pydub import AudioSegment
            _pydub_AudioSegment = AudioSegment
        except ImportError:
            _pydub_AudioSegment = False
    if _llm_chat is None:
        try:
            from src.core.llm.llm import chat
            _llm_chat = chat
        except ImportError:
            _llm_chat = False
    if _whisper is None:
        try:
            import whisper
            _whisper = whisper if hasattr(whisper, 'load_model') else False
        except ImportError:
            _whisper = False

def _has_sr():
    _lazy_imports()
    return _speech_recognition is not False

def _has_pydub():
    _lazy_imports()
    return _pydub_AudioSegment is not False

def _has_llm():
    _lazy_imports()
    return _llm_chat is not False

def _has_whisper():
    _lazy_imports()
    return _whisper is not False

WHISPER_MODEL = "base"


def _silk_to_wav(silk_path: str, wav_path: str) -> bool:
    """将silk格式转换为wav格式"""
    try:
        silk_v3_decoder_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "silk-v3-decoder",
            "decoder"
        )
        
        if not os.path.exists(silk_v3_decoder_path):
            silk_v3_decoder_path = "/usr/bin/silk-v3-decoder"
        
        if os.path.exists(silk_v3_decoder_path):
            result = subprocess.run(
                [silk_v3_decoder_path, silk_path, wav_path],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        else:
            try:
                from silk2wav import decode
                decode(silk_path, wav_path)
                return True
            except ImportError:
                pass
        
        return False
    except Exception as e:
        print(f"Silk conversion failed: {e}")
        return False


def _convert_to_wav(audio_path: str) -> Optional[str]:
    """将音频转换为wav格式"""
    if audio_path.lower().endswith('.wav'):
        return audio_path
    
    temp_wav = os.path.join(tempfile.gettempdir(), f"temp_audio_{os.urandom(4).hex()}.wav")
    
    if audio_path.lower().endswith('.silk'):
        if _silk_to_wav(audio_path, temp_wav):
            return temp_wav
        return None
    
    if _has_pydub():
        try:
            audio = _pydub_AudioSegment.from_file(audio_path)
            audio.export(temp_wav, format='wav')
            return temp_wav
        except Exception as e:
            print(f"Failed to convert audio with pydub: {e}")
    
    return None


def _load_audio_base64(audio_base64: str) -> Optional[str]:
    """从base64加载音频文件"""
    try:
        audio_data = base64.b64decode(audio_base64)
        temp_file = os.path.join(tempfile.gettempdir(), f"temp_audio_{os.urandom(4).hex()}.tmp")
        
        with open(temp_file, 'wb') as f:
            f.write(audio_data)
        
        wav_path = _convert_to_wav(temp_file)
        os.unlink(temp_file)
        
        return wav_path
    except Exception as e:
        print(f"Failed to load audio from base64: {e}")
        return None


def transcribe_audio(audio_path: str = None, audio_base64: str = None) -> Dict:
    """语音转文字"""
    wav_path = None
    
    try:
        if audio_path and os.path.exists(audio_path):
            wav_path = _convert_to_wav(audio_path)
        elif audio_base64:
            wav_path = _load_audio_base64(audio_base64)
        
        if not wav_path:
            return {"status": "error", "message": "Failed to load or convert audio"}
        
        if _has_whisper():
            model = _whisper.load_model(WHISPER_MODEL)
            result = model.transcribe(wav_path, language='zh')
            return {
                "status": "success",
                "text": result.get("text", "").strip(),
                "language": result.get("language", "zh"),
                "segments": result.get("segments", []),
                "confidence": "high" if len(result.get("text", "").strip()) > 0 else "low"
            }
        elif _has_sr():
            recognizer = _speech_recognition.Recognizer()
            with _speech_recognition.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            
            try:
                text = recognizer.recognize_google(audio_data, language='zh-CN')
                return {
                    "status": "success",
                    "text": text.strip(),
                    "language": "zh",
                    "segments": [],
                    "confidence": "medium"
                }
            except _speech_recognition.UnknownValueError:
                return {"status": "success", "text": "", "language": "zh", "segments": [], "confidence": "low"}
            except _speech_recognition.RequestError:
                return {"status": "error", "message": "Google Speech Recognition service unavailable"}
        else:
            return {"status": "error", "message": "No speech recognition library available"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)


def analyze_audio(audio_path: str = None, audio_base64: str = None) -> Dict:
    """分析音频内容"""
    transcribe_result = transcribe_audio(audio_path, audio_base64)
    
    if transcribe_result["status"] != "success":
        return transcribe_result
    
    result = {
        "status": "success",
        "transcription": transcribe_result["text"],
        "language": transcribe_result.get("language", "zh")
    }
    
    if _has_llm():
        try:
            prompt = f"""请分析以下语音识别结果：

识别文本：{transcribe_result["text"]}
语言：{transcribe_result.get("language", "未知")}

请分析：
1. 说话者的意图和目的
2. 语音内容的主题
3. 重要信息点
4. 是否有需要特别关注的内容

请用中文回答。"""
            
            response = _llm_chat(prompt)
            result["analysis"] = response
        except Exception as e:
            result["analysis"] = None
            result["analysis_error"] = str(e)
    
    return result


def detect_speech(audio_path: str = None, audio_base64: str = None) -> Dict:
    """检测语音片段"""
    transcribe_result = transcribe_audio(audio_path, audio_base64)
    
    if transcribe_result["status"] != "success":
        return transcribe_result
    
    text = transcribe_result.get("text", "")
    has_speech = len(text.strip()) > 0
    
    return {
        "status": "success",
        "has_speech": has_speech,
        "speech_text": text if has_speech else None,
        "confidence": "high" if has_speech else "low"
    }


def convert_audio_format(audio_path: str = None, audio_base64: str = None, target_format: str = "mp3") -> Dict:
    """转换音频格式"""
    if not _has_pydub():
        return {"status": "error", "message": "pydub not available"}
    
    try:
        if audio_path and os.path.exists(audio_path):
            audio = _pydub_AudioSegment.from_file(audio_path)
        elif audio_base64:
            audio_data = base64.b64decode(audio_base64)
            from io import BytesIO
            audio = _pydub_AudioSegment.from_file(BytesIO(audio_data))
        else:
            return {"status": "error", "message": "No audio provided"}
        
        target_format = target_format.lower()
        temp_output = os.path.join(tempfile.gettempdir(), f"temp_audio_{os.urandom(4).hex()}.{target_format}")
        
        audio.export(temp_output, format=target_format)
        
        with open(temp_output, 'rb') as f:
            output_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        os.unlink(temp_output)
        
        return {
            "status": "success",
            "format": target_format,
            "audio_base64": output_base64
        }
    
    except Exception as e:
        return {"status": "error", "message": str(e)}


def execute(input_data: dict) -> dict:
    """执行音频识别技能"""
    action = input_data.get('action', '')
    params = input_data.get('params', {})
    
    audio_path = params.get('audio_path', '')
    audio_base64 = params.get('audio_base64', '')
    target_format = params.get('target_format', 'mp3')
    
    if action == 'transcribe':
        return transcribe_audio(audio_path, audio_base64)
    
    elif action == 'analyze':
        return analyze_audio(audio_path, audio_base64)
    
    elif action == 'detect_speech':
        return detect_speech(audio_path, audio_base64)
    
    elif action == 'convert_format':
        return convert_audio_format(audio_path, audio_base64, target_format)
    
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}
