"""
Process I/O helpers for subprocess log redirection and background launches.
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Optional


@contextmanager
def _managed_subprocess(
    *args: Any,
    **kwargs: Any,
) -> Iterator[subprocess.Popen[Any]]:
    with subprocess.Popen(*args, **kwargs) as process:
        yield process


def open_append_text(path: str | Path) -> TextIOWrapper:
    """Open a log file in append mode; caller owns lifecycle until close."""
    path_str = os.fspath(path)
    fd = os.open(path_str, os.O_CREAT | os.O_APPEND | os.O_WRONLY)
    return os.fdopen(fd, "a", encoding="utf-8", buffering=1)


def launch_background_process(
    server_state: Any,
    stack_attr: str,
    process_attr: str,
    command: list[str],
    *,
    stdout: Any = None,
    stderr: Any = None,
    **popen_kwargs: Any,
) -> subprocess.Popen[bytes]:
    """Launch a long-lived subprocess tracked on server_state via ExitStack."""
    stack = ExitStack()
    process = stack.enter_context(
        _managed_subprocess(
            command,
            stdout=stdout,
            stderr=stderr,
            **popen_kwargs,
        )
    )
    existing_stack = getattr(server_state, stack_attr, None)
    if existing_stack is not None:
        try:
            existing_stack.close()
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    setattr(server_state, stack_attr, stack)
    setattr(server_state, process_attr, process)
    return process


def close_resource_stack(server_state: Any, stack_attr: str) -> None:
    """Close an ExitStack stored on server_state, if present."""
    stack: Optional[ExitStack] = getattr(server_state, stack_attr, None)
    if stack is None:
        return
    try:
        stack.close()
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    setattr(server_state, stack_attr, None)


def subprocess_log_streams(
    log_path: str | Path,
) -> tuple[Any, Any]:
    """Return stdout/stderr streams for subprocess log redirection."""
    if sys.platform == "win32":
        return sys.stdout, sys.stderr
    log_handle = open_append_text(log_path)
    return log_handle, log_handle
