# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('app/resources', 'app/resources'), ('models', 'models'), ('ffmpeg.exe', '.'), ('ffprobe.exe', '.')]
datas += collect_data_files('whisper')
datas += collect_data_files('torch')


a = Analysis(
    ['app\\main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['torch', 'whisper', 'PyQt5'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook.py'],
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
    name='视频处理工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app\\resources\\images\\icon.ico'],
)
