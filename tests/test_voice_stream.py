from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'src/core/voice/voice_service.py'

assert MODULE.exists(), 'voice service module should exist'

spec = importlib.util.spec_from_file_location('voice_service', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

chunks = list(module.chunk_text_for_speech('你好，世界！这是一个测试。', chunk_size=6))
assert chunks == ['你好，', '世界！', '这是一个', '测试。'], chunks

config = module.resolve_tts_config({
    'backend': 'piper',
    'model_path': '/tmp/custom_voice.onnx',
    'voice': 'zh_CN',
})
assert config['backend'] == 'piper'
assert config['model_path'] == '/tmp/custom_voice.onnx'
assert config['voice'] == 'zh_CN'

auto_config = module.resolve_tts_config({'backend': 'auto'})
assert auto_config['backend'] == 'auto'

cloud_config = module.resolve_tts_config({
    'backend': 'openai',
    'api_key': 'demo-key',
    'api_model': 'gpt-4o-mini-tts',
    'voice': 'nova',
})
assert cloud_config['backend'] == 'openai'
assert cloud_config['api_key'] == 'demo-key'
assert cloud_config['api_model'] == 'gpt-4o-mini-tts'
assert cloud_config['voice'] == 'nova'

print('voice stream test passed')
