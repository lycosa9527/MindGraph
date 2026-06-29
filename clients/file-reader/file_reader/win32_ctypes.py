"""Access Windows ``ctypes.windll`` with Linux-safe static typing."""

from __future__ import annotations

import ctypes
from typing import Any


def require_windll() -> Any:
    """Return ``ctypes.windll`` or raise when the platform has no windll."""
    windll_obj = getattr(ctypes, "windll", None)
    if windll_obj is None:
        raise OSError("ctypes.windll is unavailable on this platform")
    return windll_obj


def windll_module(name: str) -> Any:
    """Return one submodule from ``ctypes.windll`` (for example ``kernel32``)."""
    return getattr(require_windll(), name)
