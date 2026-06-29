"""File logging for WeChat key probe / DB read (under %TEMP%)."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOG_DIR = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))) / "mindgraph-file-reader"
_LOG_FILE = _LOG_DIR / "wechat-debug.log"
_LOCK = threading.Lock()


def debug_log_path() -> Path:
    """Path to the append-only WeChat debug log."""
    return _LOG_FILE


def debug_log_path_display() -> str:
    """Short log path for UI (TEMP alias instead of full AppData path)."""
    temp = os.environ.get("TEMP") or os.environ.get("TMP") or "TEMP"
    name = temp.rstrip("\\/").split("\\")[-1].split("/")[-1]
    if name.upper() == "TEMP":
        return f"%TEMP%\\mindgraph-file-reader\\{_LOG_FILE.name}"
    return str(_LOG_FILE)


def _stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def log_wechat(message: str, *, level: str = "INFO") -> None:
    """Append one line to the WeChat debug log."""
    line = f"[{_stamp()}] [{level}] {message}\n"
    with _LOCK:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line)


def log_wechat_section(title: str) -> None:
    """Start a visually separated log section."""
    log_wechat(f"--- {title} ---")


def clear_wechat_log() -> None:
    """Truncate the debug log (called at the start of each probe)."""
    with _LOCK:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("w", encoding="utf-8") as handle:
            handle.write(f"[{_stamp()}] [INFO] log cleared\n")
