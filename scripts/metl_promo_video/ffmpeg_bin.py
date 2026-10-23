"""Locate an ffmpeg binary for the promo montage scripts."""

from __future__ import annotations

import importlib
import shutil


def ffmpeg_exe() -> str:
    """Prefer ffmpeg on PATH, then the imageio-ffmpeg bundle when that package is installed."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        module = importlib.import_module("imageio_ffmpeg")
    except ImportError as exc:
        raise RuntimeError("ffmpeg is not on PATH and imageio-ffmpeg is not installed") from exc
    getter = getattr(module, "get_ffmpeg_exe", None)
    if not callable(getter):
        raise RuntimeError("imageio-ffmpeg has no get_ffmpeg_exe")
    return str(getter())
