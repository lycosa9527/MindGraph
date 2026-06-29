# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import playwright
import webview

here = Path(SPECPATH)
tools_ffmpeg = here / "tools" / "ffmpeg.exe"
tools_wxkey = here / "tools" / "wx_key.dll"
icon_ico = here / "assets" / "icon.ico"
datas = [("assets/icon.png", "assets")]
if tools_ffmpeg.is_file():
    datas.append(("tools/ffmpeg.exe", "tools"))
if tools_wxkey.is_file():
    datas.append(("tools/wx_key.dll", "tools"))

playwright_root = Path(playwright.__file__).resolve().parent
playwright_driver = playwright_root / "driver"
if playwright_driver.is_dir():
    for driver_file in playwright_driver.rglob("*"):
        if driver_file.is_file():
            rel_parent = driver_file.parent.relative_to(playwright_root)
            datas.append((str(driver_file), str(Path("playwright") / rel_parent)))

webview_root = Path(webview.__file__).resolve().parent
webview_lib = webview_root / "lib"
if webview_lib.is_dir():
    for dll_path in webview_lib.rglob("*.dll"):
        bundle_dir = dll_path.parent.relative_to(webview_root).as_posix()
        datas.append((str(dll_path), bundle_dir))

a = Analysis(
    ['file_reader\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'webview',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'pythonnet',
        'clr_loader',
        'tkwebview2',
        'tkwebview2.tkwebview2',
        'playwright',
        'playwright.sync_api',
        'playwright._impl',
        'yt_dlp',
        'requests',
        'Crypto.Cipher.AES',
        'zstandard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(here / "rthook_playwright.py")],
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
    upx_exclude=[
        'chrome.exe',
        'chrome.dll',
        'chrome_elf.dll',
        'libEGL.dll',
        'libGLESv2.dll',
        'vk_swiftshader.dll',
        'vulkan-1.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(icon_ico)] if icon_ico.is_file() else None,
)
