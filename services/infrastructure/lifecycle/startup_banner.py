"""
MindGraph launch art.

The ``python main.py`` process prints this once, before imports log.
One buffer holds those records off the console until the launch header is
printed. When logging is configured, the same records are copied to the log
file. Worker processes do not print the art again.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import atexit
import logging
import sys
from pathlib import Path

# Original launch art from the first commit. Do not delete. It must show at startup.
_MINDGRAPH_ASCII_BANNER = (
    "    ███╗   ███╗██╗███╗   ██╗██████╗ ███╗   ███╗ █████╗ ████████╗███████╗",
    "    ████╗ ████║██║████╗  ██║██╔══██╗████╗ ████║██╔══██╗╚══██╔══╝██╔════╝",
    "    ██╔████╔██║██║██╔██╗ ██║██║  ██║██╔████╔██║███████║   ██║   █████╗  ",
    "    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║╚██╔╝██║██╔══██║   ██║   ██╔══╝  ",
    "    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝██║ ╚═╝ ██║██║  ██║   ██║   ███████╗",
    "    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝",
)


class _StartupLogBuffer(logging.Handler):
    """Hold console records, then forward them to the real console handler."""

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []
        self.console: logging.Handler | None = None
        self.copied_to_file = False
        self.released = False

    def emit(self, record: logging.LogRecord) -> None:
        if self.released and self.console is not None:
            self.console.handle(record)
            return
        self.records.append(record)

    def copy_to_file(self, file_handler: logging.Handler) -> None:
        """Write records captured before the log file existed. Once only."""
        if self.copied_to_file:
            return
        for record in self.records:
            file_handler.handle(record)
        self.copied_to_file = True

    def release(self) -> None:
        """Print buffered lines. Later records go straight to the console."""
        if self.released:
            return
        self.released = True
        pending = self.records
        self.records = []
        if self.console is not None:
            for record in pending:
                self.console.handle(record)
            return
        for record in pending:
            if record.levelno >= logging.WARNING:
                sys.stderr.write(f"{record.levelname}: {record.getMessage()}\n")
        sys.stderr.flush()


class _LaunchHoldState:
    """Process-wide hold. Avoids a module-level global."""

    buffer: _StartupLogBuffer | None = None
    printed: bool = False
    atexit_registered: bool = False


def mindgraph_startup_banner_lines() -> tuple[str, ...]:
    """Launch banner lines, including the version. Do not remove."""
    version = "0.0.0"
    version_file = Path(__file__).resolve().parents[3] / "VERSION"
    try:
        text = version_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        text = ""
    if text:
        version = text
    return (
        *_MINDGRAPH_ASCII_BANNER,
        "=" * 80,
        "    AI-Powered Visual Thinking Tools for K12 Education",
        f"    Version {version} | 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)",
        "=" * 80,
    )


def print_launch_banner_and_hold_logs() -> None:
    """Print the ASCII art, then buffer log records until :func:`release_held_startup_logs`."""
    if _LaunchHoldState.printed:
        return
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)
    buffer = _StartupLogBuffer()
    root.addHandler(buffer)
    _LaunchHoldState.buffer = buffer
    _LaunchHoldState.printed = True
    if not _LaunchHoldState.atexit_registered:
        atexit.register(release_held_startup_logs)
        _LaunchHoldState.atexit_registered = True
    sys.stdout.write("\n")
    for line in mindgraph_startup_banner_lines():
        sys.stdout.write(line + "\n")
    sys.stdout.write("\n")
    sys.stdout.flush()


def bind_startup_log_handlers(
    console: logging.Handler | None,
    file_handler: logging.Handler | None,
) -> logging.Handler | None:
    """
    Return the console handler to install.

    During launch, that is the buffer: the real console stays quiet until
    :func:`release_held_startup_logs`. Other processes get ``console`` unchanged.
    """
    buffer = _LaunchHoldState.buffer
    if buffer is None:
        return console
    if file_handler is not None:
        buffer.copy_to_file(file_handler)
    if console is None:
        return None
    buffer.console = console
    return buffer


def release_held_startup_logs() -> None:
    """Send buffered startup records to the console, after the launch art and header."""
    buffer = _LaunchHoldState.buffer
    if buffer is None:
        return
    buffer.release()
