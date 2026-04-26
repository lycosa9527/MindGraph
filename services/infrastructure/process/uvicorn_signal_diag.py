"""
Diagnostics for Uvicorn multiprocess mode (SIGHUP-driven worker reloads).

Linux does not expose the sending PID for signals to Python handlers. When
SIGHUP triggers a reload, we log parent cmdline, session id, and cgroup so
operators can correlate with systemd scope, SSH session, or deploy scripts.
"""

from __future__ import annotations

import logging
import os
import signal
from types import FrameType
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)

_SignalHandler = Union[Callable[[int, Optional[FrameType]], Any], int, signal.Handlers]

_signal_patch_installed: list[bool] = [False]


def _signal_diag_env_enabled() -> bool:
    env_raw = os.environ.get("MINDGRAPH_UVICORN_SIGNAL_DIAG", "1").lower()
    return env_raw not in ("0", "false", "no", "off")


def _read_proc_cmdline(pid: int, max_bytes: int = 400) -> str:
    """Best-effort /proc cmdline for pid (truncated)."""
    path = f"/proc/{pid}/cmdline"
    try:
        with open(path, "rb") as proc_file:
            raw = proc_file.read(max_bytes)
    except OSError:
        return f"<unreadable:{pid}>"
    text = raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    return text or f"<empty:{pid}>"


def _read_session_id() -> str:
    try:
        with open("/proc/self/sessionid", "r", encoding="utf-8") as sess_file:
            return sess_file.read().strip()
    except OSError:
        return "?"


def _read_cgroup_hint() -> str:
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8") as cg_file:
            lines = [ln.strip() for ln in cg_file if ln.strip()]
    except OSError:
        return "?"
    if not lines:
        return "?"
    tail = lines[-1]
    return tail[-160:] if len(tail) > 160 else tail


def log_uvicorn_supervisor_boot(worker_count: int) -> None:
    """Log one line of supervisor context when Uvicorn uses multiple workers."""
    if not _signal_diag_env_enabled():
        return
    ppid = os.getppid()
    logger.info(
        "[SRVR] mindgraph_supervisor_boot pid=%s ppid=%s sessionid=%s workers=%s parent_cmd=%s cgroup=%s",
        os.getpid(),
        ppid,
        _read_session_id(),
        worker_count,
        _read_proc_cmdline(ppid),
        _read_cgroup_hint(),
    )


def patch_signal_for_uvicorn_sighup_trace() -> None:
    """
    Wrap signal.signal so the next registration of SIGHUP chains our logger.

    Uvicorn's multiprocess supervisor registers SIGHUP after this runs; the
    wrapper runs first and logs context, then delegates to Uvicorn's handler.

    Production servers use Linux (paths under /proc); on other OSes the readers
    degrade to placeholders if /proc is absent.
    """
    if _signal_patch_installed[0]:
        return

    if not _signal_diag_env_enabled():
        return

    original_signal = signal.signal

    def patched(sig: int, handler: _SignalHandler) -> Any:
        sighup = getattr(signal, "SIGHUP", None)
        if sighup is not None and sig == sighup and callable(handler):

            def wrapped(signum: int, frame: Optional[FrameType]) -> Any:
                ppid = os.getppid()
                logger.warning(
                    "[SRVR] mindgraph_sighup_received pid=%s ppid=%s sessionid=%s "
                    "parent_cmd=%s cgroup=%s (Uvicorn will reload workers next)",
                    os.getpid(),
                    ppid,
                    _read_session_id(),
                    _read_proc_cmdline(ppid),
                    _read_cgroup_hint(),
                )
                return handler(signum, frame)

            return original_signal(sig, wrapped)
        return original_signal(sig, handler)

    signal.signal = patched  # type: ignore[assignment]
    _signal_patch_installed[0] = True
