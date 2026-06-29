# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

here = Path(SPECPATH)
tools_ffmpeg = here / "tools" / "ffmpeg.exe"
tools_wxkey = here / "tools" / "wx_key.dll"
datas = [("assets/icon.png", "assets")]
if tools_ffmpeg.is_file():
    datas.append(("tools/ffmpeg.exe", "tools"))
if tools_wxkey.is_file():
    datas.append(("tools/wx_key.dll", "tools"))

a = Analysis(
    ['file_reader\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['webview', 'requests', 'Crypto.Cipher.AES', 'zstandard'],
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
    name='mindgraph-file-reader',
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
)
