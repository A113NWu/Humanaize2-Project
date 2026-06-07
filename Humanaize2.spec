# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\core\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('src/ui/ascii.txt', 'src/ui/'), ('src/config/*.py', 'src/config/'), ('src/core/*.py', 'src/core/'), ('src/ui/*.py', 'src/ui/'), ('src/llm/*.py', 'src/llm/'), ('src/memory/*.py', 'src/memory/'), ('src/tools/*.py', 'src/tools/'), ('src/utils/*.py', 'src/utils/'), ('skills/*', 'skills/'), ('version.json', '. '), ('requirements.txt', '. ')],
    hiddenimports=['customtkinter', 'requests', 'nltk', 'transformers', 'torch'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Humanaize2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
