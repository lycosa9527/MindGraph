"""Resolve Windows user Documents folders (Win7–11, OneDrive, localized paths)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable, List

winreg: Any = None
if sys.platform == "win32":
    import winreg as _winreg_module

    winreg = _winreg_module


def _expand_path(raw: str) -> Path:
    return Path(os.path.expandvars(raw.strip())).expanduser()


def _registry_personal_folder() -> Path | None:
    """HKCU User Shell Folders Personal — reliable on Win7–11."""
    if sys.platform != "win32" or winreg is None:
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "Personal")
    except OSError:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    path = _expand_path(value)
    return path if path.is_dir() else None


def _profile_roots() -> List[Path]:
    roots: List[Path] = []
    home = Path.home()
    roots.append(home)
    profile = os.environ.get("USERPROFILE", "").strip()
    if profile:
        roots.append(Path(profile))
    return roots


def iter_documents_directories() -> List[Path]:
    """Return existing Documents directories, deduplicated (Win7–11)."""
    if sys.platform != "win32":
        return []

    candidates: List[Path] = []
    reg_docs = _registry_personal_folder()
    if reg_docs is not None:
        candidates.append(reg_docs)

    for root in _profile_roots():
        candidates.extend(
            (
                root / "Documents",
                root / "My Documents",
                root / "OneDrive" / "Documents",
                root / "OneDrive - Personal" / "Documents",
            )
        )

    seen: set[str] = set()
    existing: List[Path] = []
    for path in candidates:
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.is_dir():
            existing.append(path)
    return existing


def dedupe_existing(paths: Iterable[Path]) -> List[Path]:
    """Keep first occurrence of each resolved directory that exists."""
    seen: set[str] = set()
    result: List[Path] = []
    for path in paths:
        if not path.is_dir():
            continue
        try:
            key = str(path.resolve()).lower()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result
