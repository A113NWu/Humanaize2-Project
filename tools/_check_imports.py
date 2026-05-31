import importlib,sys
mods=['config','tools','memory','personality','vision','autonomous','idle','thinking_engine','llm','llm_enhanced','ui']
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
    print('All imports OK')
