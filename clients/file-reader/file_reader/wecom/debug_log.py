"""Append-only debug log for WeCom key probe and DB read."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

_LOG_PATH = Path(tempfile.gettempdir()) / "mindgraph-file-reader" / "wecom-debug.log"


def debug_log_path_display() -> str:
    """Return the WeCom debug log path for UI display."""
    return str(_LOG_PATH)


def log_wecom(message: str, *, level: str = "INFO") -> None:
    """Append one line to the WeCom debug log."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] [{level}] {message}\n"
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def clear_wecom_log() -> None:
    """Remove the WeCom debug log file when present."""
    try:
        if _LOG_PATH.is_file():
            _LOG_PATH.unlink()
    except OSError:
        pass


def log_wecom_section(title: str) -> None:
    """Write a section header to the WeCom debug log."""
    log_wecom(f"--- {title} ---")
