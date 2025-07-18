# WoonnetRijnmondBot.spec

# Before running `pyinstaller WoonnetRijnmondBot.spec`, you must:
# 1. Download the correct `chromedriver.exe` for your target Chrome version.
# 2. Place `chromedriver.exe` in the root directory of this project.

a = Analysis(
    ['hybrid_bot.py'],
    pathex=[],
    binaries=[],
    datas=[
        # This is the crucial line. It finds 'chromedriver.exe' in your project
        # folder and bundles it into the final .exe at the root level.
        ('chromedriver.exe', '.')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WoonnetRijnmondBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # This creates a windowed (GUI) app, not a console app.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' # Optional: Add an icon file in an `assets` folder
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WoonnetRijnmondBot',
)