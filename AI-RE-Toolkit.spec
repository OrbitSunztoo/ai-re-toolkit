# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/main.py'],
    pathex=[r'E:\项目\ai-re-toolkit'],
    binaries=[],
    datas=['--add-data=config;config', '--add-data=src/ai/prompts;src/ai/prompts', '--add-data=src/tools/definitions;src/tools/definitions', '--add-data=resources;resources', '--add-data=tools;tools'],
    hiddenimports=['src.core.file_analyzer', 'src.core.binary_reader', 'src.ai.providers.ollama_provider', 'src.ai.providers.openai_provider', 'src.tools.registry', 'src.tools.executor', 'src.utils.logger', 'requests'],
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
    name='AI-RE-Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    
)
