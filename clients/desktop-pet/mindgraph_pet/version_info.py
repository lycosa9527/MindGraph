"""Installed version and numeric comparison."""

from __future__ import annotations

import sys
from pathlib import Path


def version_tuple(text: str) -> tuple[int, ...]:
    """Split a version into numbers. Non-numeric tails are ignored."""
    parts: list[int] = []
    for piece in text.strip().split("."):
        digits = ""
        for char in piece:
            if char.isdigit():
                digits += char
            else:
                break
        parts.append(int(digits or "0"))
    return tuple(parts)


def is_newer(remote: str, local: str) -> bool:
    """True when the remote version should replace the installed copy."""
    return version_tuple(remote) > version_tuple(local)


def installed_version() -> str:
    """Read VERSION beside the source tree, or next to a frozen executable."""
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().parent / "VERSION"
    else:
        candidate = Path(__file__).resolve().parents[1] / "VERSION"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8").strip() or "0.0.0"
    return "0.0.0"
