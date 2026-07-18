import pyttsx3
import speech_recognition as sr


def list_microphones():
    print('=== 可用麦克风 ===')
    try:
        names = sr.Microphone.list_microphone_names()
    except Exception as exc:
        print('无法列出麦克风设备:', exc)
        return []
    for index, name in enumerate(names):
        print(f'{index}: {name}')
    return names


def test_microphone_stt(device_index=None):
    recognizer = sr.Recognizer()
    microphone = sr.Microphone(device_index=device_index)
    print('请在 5 秒内说一句中文或英文...')
    try:
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        text = recognizer.recognize_google(audio, language='zh-CN')
        print('识别结果:', text)
    except Exception as exc:
        print('识别失败:', exc)


def list_voices():
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    print('可用语音数量:', len(voices))
    for index, voice in enumerate(voices):
        voice_id = getattr(voice, 'id', '')
        voice_name = getattr(voice, 'name', '')
        languages = getattr(voice, 'languages', [])
        print(f'{index:02d}: {voice_id} | {voice_name} | {languages}')
    return voices


def pick_aize_candidate(voices):
    candidates = []
    for voice in voices:
        voice_id = (getattr(voice, 'id', '') or '').lower()
        voice_name = (getattr(voice, 'name', '') or '').lower()
        languages = [str(lang).lower() for lang in getattr(voice, 'languages', []) or []]
        score = 0
        if any(token in voice_id for token in ['cmn', 'zh', 'yue']):
            score += 5
        if any(token in voice_name for token in ['female', 'woman', 'girl', 'slt', 'young']):
            score += 3
        if any(token in languages for token in ['cmn', 'zh', 'yue']):
            score += 2
        if score > 0:
            candidates.append((score, voice))
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates else None


def test_voice_sample(voice, text='你好，我是 Aize，很高兴和你聊天。'):
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 0.95)
    try:
        engine.setProperty('voice', voice.id)
    except Exception:
        pass
    engine.say(text)
    engine.runAndWait()
    print('已用该语音试播:', voice.id, voice.name)


if __name__ == '__main__':
    print('=== 麦克风转文字测试 ===')
    list_microphones()
    test_microphone_stt()
    print('\n=== 可用语音列表 ===')
    voices = list_voices()
    candidate = pick_aize_candidate(voices)
    print('\n=== 推荐的 Aize 风格语音 ===')
    if candidate:
        print(candidate.id, candidate.name)
        test_voice_sample(candidate)
    else:
        print('没有找到明显合适的候选。')
