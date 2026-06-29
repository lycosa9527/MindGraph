"""Optional wx_key.dll backend for WeChat 4.x database keys.

See https://github.com/ycccccccy/wx_key and docs/dll_usage.md
"""

from __future__ import annotations

import ctypes
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from file_reader.wechat.debug_log import log_wechat

_DLL_NAMES = ("wx_key.dll",)
_DEFAULT_HOOK_TIMEOUT_SEC = 45.0


@dataclass(frozen=True)
class WxKeyResult:
    """Outcome of a wx_key.dll hook attempt."""

    material: Optional[bytes]
    dll_path: Optional[Path]
    error: Optional[str]
    status_lines: tuple[str, ...]


def _dll_search_paths() -> List[Path]:
    roots: List[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str):
        roots.append(Path(meipass) / "tools")
    file_root = Path(__file__).resolve().parent.parent
    roots.extend(
        [
            file_root / "tools",
            file_root,
            Path.cwd(),
            Path.cwd() / "tools",
        ]
    )
    return roots


def find_wx_key_dll() -> Optional[Path]:
    """Locate wx_key.dll if the user bundled it."""
    for root in _dll_search_paths():
        for name in _DLL_NAMES:
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


def is_process_admin() -> bool:
    """True when the current process is elevated on Windows."""
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


class WxKeyDll:
    """Thin ctypes wrapper around wx_key hook DLL."""

    def __init__(self, dll_path: Path) -> None:
        self._lib = ctypes.CDLL(str(dll_path))
        self._lib.InitializeHook.argtypes = [ctypes.c_uint32]
        self._lib.InitializeHook.restype = ctypes.c_bool
        self._lib.PollKeyData.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self._lib.PollKeyData.restype = ctypes.c_bool
        self._lib.CleanupHook.argtypes = []
        self._lib.CleanupHook.restype = ctypes.c_bool
        self._lib.GetLastErrorMsg.restype = ctypes.c_char_p
        self._has_status = hasattr(self._lib, "GetStatusMessage")
        if self._has_status:
            self._lib.GetStatusMessage.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            self._lib.GetStatusMessage.restype = ctypes.c_bool
        self._active = False

    def initialize(self, pid: int) -> None:
        """Attach wx_key hook to the WeChat process."""
        if not self._lib.InitializeHook(pid):
            err = self._last_error()
            raise RuntimeError(err or "InitializeHook failed")
        self._active = True

    def poll_key_hex(self) -> Optional[str]:
        """Return the latest 64-char hex key from the hook, if any."""
        buffer = ctypes.create_string_buffer(128)
        if not self._lib.PollKeyData(buffer, len(buffer)):
            return None
        text = buffer.value.decode("ascii", errors="ignore").strip()
        return text or None

    def drain_status_messages(self) -> list[str]:
        """Return and clear pending wx_key.dll status log lines."""
        if not self._has_status:
            return []
        lines: list[str] = []
        buffer = ctypes.create_string_buffer(512)
        level = ctypes.c_int()
        while self._lib.GetStatusMessage(buffer, len(buffer), ctypes.byref(level)):
            text = buffer.value.decode("utf-8", errors="replace").strip()
            if text:
                lines.append(text)
        return lines

    def wait_for_key_hex(
        self,
        *,
        timeout_sec: float = _DEFAULT_HOOK_TIMEOUT_SEC,
        interval_sec: float = 0.1,
    ) -> tuple[Optional[str], tuple[str, ...]]:
        """Poll until a key appears or timeout elapses."""
        deadline = time.monotonic() + timeout_sec
        status_lines: list[str] = []
        while time.monotonic() < deadline:
            key = self.poll_key_hex()
            for line in self.drain_status_messages():
                status_lines.append(line)
                log_wechat(f"wx_key: {line}")
            if key:
                return key, tuple(status_lines)
            time.sleep(interval_sec)
        for line in self.drain_status_messages():
            status_lines.append(line)
            log_wechat(f"wx_key: {line}")
        return None, tuple(status_lines)

    def cleanup(self) -> None:
        """Remove the hook from the target process."""
        if self._active:
            self._lib.CleanupHook()
            self._active = False

    def last_error(self) -> str:
        """Return the DLL's last error message."""
        return self._last_error()

    def _last_error(self) -> str:
        ptr = self._lib.GetLastErrorMsg()
        if not ptr:
            return ""
        return ptr.decode("utf-8", errors="replace")


def try_wx_key_passphrase(
    pid: int,
    *,
    timeout_sec: float = _DEFAULT_HOOK_TIMEOUT_SEC,
) -> WxKeyResult:
    """Hook Weixin and return the 32-byte WCDB passphrase when captured."""
    dll_path = find_wx_key_dll()
    if dll_path is None:
        return WxKeyResult(None, None, "wx_key.dll not found", ())

    log_wechat(f"wx_key.dll path={dll_path} pid={pid} admin={is_process_admin()}")
    backend = WxKeyDll(dll_path)
    status_lines: list[str] = []
    try:
        backend.initialize(pid)
        log_wechat("wx_key InitializeHook ok — log out and log back in to Weixin")
        hex_key, polled = backend.wait_for_key_hex(timeout_sec=timeout_sec)
        status_lines.extend(polled)
        if not hex_key or len(hex_key) != 64:
            err = backend.last_error() or "no key captured before timeout"
            log_wechat(f"wx_key timeout/error pid={pid} detail={err}", level="WARN")
            return WxKeyResult(None, dll_path, err, tuple(status_lines))
        return WxKeyResult(bytes.fromhex(hex_key), dll_path, None, tuple(status_lines))
    except (OSError, RuntimeError, ValueError) as exc:
        err = str(exc) or backend.last_error()
        log_wechat(f"wx_key failed pid={pid} error={err}", level="ERROR")
        return WxKeyResult(None, dll_path, err, tuple(status_lines))
    finally:
        backend.cleanup()
