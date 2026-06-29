"""Persist per-platform download folder preferences."""

from __future__ import annotations

import json
from pathlib import Path

from file_reader.platform_browser.sites import PlatformSite, default_download_dir
from file_reader.settings import SETTINGS_DIR

_PREFS_PATH = SETTINGS_DIR / "platform_download_folders.json"


def _read_folders() -> dict[str, str]:
    if not _PREFS_PATH.is_file():
        return {}
    try:
        raw = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    folders: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, str) and value.strip():
            folders[key] = value.strip()
    return folders


def saved_download_dir(site_id: str) -> Path | None:
    """Return a saved download folder for a platform, if any."""
    path_text = _read_folders().get(site_id, "")
    if not path_text:
        return None
    return Path(path_text)


def remember_download_dir(site_id: str, folder: Path) -> None:
    """Persist the chosen download folder for a platform."""
    data = _read_folders()
    data[site_id] = str(folder.resolve())
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    _PREFS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_download_dir(site: PlatformSite) -> Path:
    """Return the download folder for a platform (saved preference or default)."""
    saved = saved_download_dir(site.site_id)
    if saved is not None:
        saved.mkdir(parents=True, exist_ok=True)
        return saved
    return default_download_dir(site)
