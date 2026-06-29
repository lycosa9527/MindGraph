"""Default export folder paths for chat history."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from file_reader.api_client import UserProfile


def _safe_slug(name: str) -> str:
    cleaned = re.sub(r"[^\w\-]", "_", name.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:32] or "user"


def default_chat_export_dir(profile: UserProfile | None = None) -> Path:
    """Desktop folder ``{user}_chathistory_{dd}`` for today's exports."""
    if profile is not None:
        display = profile.name.strip() or profile.phone.strip()
    else:
        display = "user"
    slug = _safe_slug(display)
    day = datetime.now().strftime("%d")
    folder = Path.home() / "Desktop" / f"{slug}_chathistory_{day}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def unique_export_path(export_dir: Path, title: str) -> Path:
    """Return a non-colliding ``.md`` path under ``export_dir``."""
    slug = _safe_slug(title) or "chat"
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    candidate = export_dir / f"{slug}_{stamp}.md"
    counter = 0
    while candidate.exists():
        counter += 1
        candidate = export_dir / f"{slug}_{stamp}_{counter}.txt"
    return candidate
