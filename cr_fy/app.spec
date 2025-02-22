# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app/main.py'],  # 主程序入口
    pathex=[],
    binaries=[],
    datas=[
        ('app/resources/config', 'app/resources/config'),  # 配置文件目录
        ('app/resources/images', 'app/resources/images'),  # 图片资源目录
    ],
    hiddenimports=[
        'PyQt5',
        'requests',
        'sqlmodel',
        'cpuinfo',
        'whisper',
        'torch',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='视频处理工具',
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
    icon='app/resources/images/icon.ico'  # 应用程序图标
) 