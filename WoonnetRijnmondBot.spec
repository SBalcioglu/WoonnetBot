# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['hybrid_bot.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('ttkbootstrap'),
    hiddenimports=[
        'keyring.backends.Windows.CryptUnprotect',
        'keyring.backends.SecretService',
        'keyring.backends.macOS.Keyring',
    ],
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
    [],
    a.binaries,
    a.datas,
    name='WoonnetRijnmondBot',
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
    icon=None # You can add an .ico file here, e.g., 'assets/icon.ico'
)