"""Detect WeChat / Weixin client version and map to crypto variant."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal, Optional, Tuple

winreg: Any = None
if sys.platform == "win32":
    import winreg as _winreg_module

    winreg = _winreg_module

WeChatCryptoVariant = Literal["v3", "v4", "v4.1"]
LayoutVariant = Literal["v3", "v4"]

_V4_1_MIN = (4, 1, 0, 0)
# Weixin 4.1.10.31+ no longer keeps passphrase plaintext on heap (chatlog-keeper / wx_key).
_V4_1_PASSIVE_MAX = (4, 1, 10, 30)
_V3_PROCESS = "WeChat.exe"
_V4_PROCESS = "Weixin.exe"


class _VsFixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("signature", wt.DWORD),
        ("struc_version", wt.DWORD),
        ("file_version_ms", wt.DWORD),
        ("file_version_ls", wt.DWORD),
        ("product_version_ms", wt.DWORD),
        ("product_version_ls", wt.DWORD),
        ("file_flags_mask", wt.DWORD),
        ("file_flags", wt.DWORD),
        ("file_os", wt.DWORD),
        ("file_type", wt.DWORD),
        ("file_subtype", wt.DWORD),
        ("file_date_ms", wt.DWORD),
        ("file_date_ls", wt.DWORD),
    ]


def _registry_install_path(key_path: str, value_name: str) -> Optional[Path]:
    if sys.platform != "win32" or winreg is None:
        return None

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value.strip())
    if path.is_file():
        return path
    candidate = path / "Weixin.exe"
    if candidate.is_file():
        return candidate
    candidate = path / "WeChat.exe"
    return candidate if candidate.is_file() else None


def _weixin_install_exe() -> Optional[Path]:
    for key_path, value_name in (
        (r"Software\Tencent\Weixin", "InstallPath"),
        (r"Software\Tencent\WeChat", "InstallPath"),
    ):
        path = _registry_install_path(key_path, value_name)
        if path is not None and path.name.lower() == "weixin.exe":
            return path
    for candidate in (
        Path(r"C:\Program Files\Tencent\Weixin\Weixin.exe"),
        Path(r"C:\Program Files (x86)\Tencent\Weixin\Weixin.exe"),
    ):
        if candidate.is_file():
            return candidate
    return None


def _wechat_install_exe() -> Optional[Path]:
    for key_path, value_name in (
        (r"Software\Tencent\WeChat", "InstallPath"),
        (r"Software\Tencent\Weixin", "InstallPath"),
    ):
        path = _registry_install_path(key_path, value_name)
        if path is not None and path.name.lower() == "wechat.exe":
            return path
    for candidate in (
        Path(r"C:\Program Files\Tencent\WeChat\WeChat.exe"),
        Path(r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe"),
    ):
        if candidate.is_file():
            return candidate
    return None


def _tasklist_pid(image_name: str) -> Optional[int]:
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip('"').split('","')
        if len(parts) >= 2 and parts[0].lower() == image_name.lower():
            try:
                return int(parts[1])
            except ValueError:
                continue
    return None


def _process_image_path(pid: int) -> Optional[Path]:
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.windll.kernel32
    access = 0x1000
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        return None
    try:
        size = wt.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)) == 0:
            return None
        path = Path(buffer.value)
        return path if path.is_file() else None
    finally:
        kernel32.CloseHandle(handle)


def running_process_image(image_name: str) -> Optional[Path]:
    """Return the on-disk path of a running process image, if found."""
    pid = _tasklist_pid(image_name)
    if pid is None:
        return None
    return _process_image_path(pid)


def detect_running_process() -> Optional[str]:
    """Return Weixin.exe or WeChat.exe when that client is running."""
    if sys.platform != "win32":
        return None
    if _tasklist_pid(_V4_PROCESS) is not None:
        return _V4_PROCESS
    if _tasklist_pid(_V3_PROCESS) is not None:
        return _V3_PROCESS
    return None


def read_pe_file_version(exe_path: Path) -> Optional[Tuple[int, int, int, int]]:
    """Return (major, minor, build, revision) from a Windows PE version resource."""
    if sys.platform != "win32" or not exe_path.is_file():
        return None
    ver = ctypes.windll.version
    path_w = str(exe_path.resolve())
    size = ver.GetFileVersionInfoSizeW(path_w, None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(path_w, 0, size, buffer):
        return None
    value_ptr = ctypes.c_void_p()
    value_len = wt.UINT()
    if not ver.VerQueryValueW(buffer, r"\\", ctypes.byref(value_ptr), ctypes.byref(value_len)):
        return None
    info = ctypes.cast(value_ptr, ctypes.POINTER(_VsFixedFileInfo)).contents
    major = (info.file_version_ms >> 16) & 0xFFFF
    minor = info.file_version_ms & 0xFFFF
    build = (info.file_version_ls >> 16) & 0xFFFF
    revision = info.file_version_ls & 0xFFFF
    return major, minor, build, revision


def format_client_version(version: Optional[Tuple[int, int, int, int]]) -> str:
    """Human-readable client version label."""
    if version is None:
        return "unknown"
    major, minor, build, revision = version
    if revision:
        return f"{major}.{minor}.{build}.{revision}"
    return f"{major}.{minor}.{build}"


def format_weixin_version(version: Optional[Tuple[int, int, int, int]]) -> str:
    """Alias kept for callers that still refer to Weixin version formatting."""
    return format_client_version(version)


def cached_weixin_version_matches(saved_version: str, current_version: str) -> bool:
    """True when a cached unlock record matches the installed/running client version."""
    saved = saved_version.strip()
    current = current_version.strip()
    if not saved or not current:
        return True
    if saved in {"unknown", "?"} or current in {"unknown", "?"}:
        return True
    return saved == current


def detect_client_exe_version(*, layout: LayoutVariant) -> Optional[Tuple[int, int, int, int]]:
    """Resolve client PE version: running process first, then install path."""
    if layout == "v3":
        running = running_process_image(_V3_PROCESS)
        if running is not None:
            version = read_pe_file_version(running)
            if version is not None:
                return version
        install = _wechat_install_exe()
        if install is not None:
            return read_pe_file_version(install)
        return None

    running = running_process_image(_V4_PROCESS)
    if running is not None:
        version = read_pe_file_version(running)
        if version is not None:
            return version
    install = _weixin_install_exe()
    if install is not None:
        return read_pe_file_version(install)
    return None


def get_weixin_version() -> Optional[Tuple[int, int, int, int]]:
    """Return installed or running Weixin.exe version tuple, if detectable."""
    return detect_client_exe_version(layout="v4")


def is_weixin_v41_or_newer(version: Optional[Tuple[int, int, int, int]]) -> bool:
    """True when Weixin is 4.1.0 or newer."""
    if version is None:
        return False
    return version >= _V4_1_MIN


def supports_passive_passphrase_scan(
    version: Optional[Tuple[int, int, int, int]],
) -> bool:
    """True when chatlog-style passive RAM scan may still find the WCDB passphrase."""
    if version is None:
        return True
    if version < _V4_1_MIN:
        return False
    return version <= _V4_1_PASSIVE_MAX


def requires_wx_key_hook(version: Optional[Tuple[int, int, int, int]]) -> bool:
    """True when Weixin 4.1.10.31+ needs wx_key.dll hook (passive scan is obsolete)."""
    if version is None:
        return False
    return version > _V4_1_PASSIVE_MAX


def resolve_crypto_variant(
    layout_variant: Optional[str],
    *,
    weixin_version: Optional[Tuple[int, int, int, int]] = None,
) -> WeChatCryptoVariant:
    """Map filesystem layout + optional exe version to v3 / v4 / v4.1."""
    if layout_variant == "v3":
        return "v3"
    if layout_variant == "v4.1":
        return "v4.1"
    version = weixin_version
    if version is None and layout_variant in {None, "v4"}:
        version = detect_client_exe_version(layout="v4")
    if is_weixin_v41_or_newer(version):
        return "v4.1"
    return "v4"


def infer_layout_variant(account_dir: Path) -> LayoutVariant:
    """Return v3 or v4 filesystem layout for an account directory."""
    if (account_dir / "db_storage").is_dir():
        return "v4"
    return "v3"


def key_extraction_plan(
    crypto: WeChatCryptoVariant,
    *,
    weixin_version: Optional[Tuple[int, int, int, int]] = None,
) -> tuple[str, ...]:
    """Ordered key extraction methods for a crypto variant."""
    if crypto == "v3":
        return ("v3_wechatwin", "v3_wx_key_dll")
    if crypto == "v4":
        return ("v4_xhex", "v4_wx_key_dll")
    if requires_wx_key_hook(weixin_version):
        return ("v4.1_wx_key_dll",)
    return ("v4.1_passphrase", "v4.1_wx_key_dll")


def primary_key_method(
    crypto: WeChatCryptoVariant,
    *,
    weixin_version: Optional[Tuple[int, int, int, int]] = None,
) -> str:
    """First key extraction method that will be attempted."""
    return key_extraction_plan(crypto, weixin_version=weixin_version)[0]
