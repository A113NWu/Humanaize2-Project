import importlib,sys
import os

# 將 src 目錄添加到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

mods=[
    'config',
    'tools',
    'memory',
    'core.personality',
    'tools.vision',
    'core.autonomous',
    'ui.idle',
    'core.thinking_engine',
    'llm',
    'llm.llm_enhanced',
    'ui',
    'core.Agent',
]
errs=False
for m in mods:
    try:
        importlib.import_module(m)
        print('OK',m)
    except Exception as e:
        print('ERR',m,repr(e))
        errs=True
if errs:
    sys.exit(1)
else:
    print('所有匯入檢查通過')