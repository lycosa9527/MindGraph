"""Read the desktop-pet latest.json for the server's own COS prefix."""

from __future__ import annotations

import json
from typing import Any, Optional

from config.cos_env_prefix import cos_env_root
from services.utils.tencent_cos_client import generate_presigned_get_url, get_object_bytes

PLATFORMS = frozenset({"windows", "mac"})


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


def manifest_prefix() -> str:
    """COS folder for this environment's pet builds."""
    return f"{cos_env_root()}/desktop-pet"


def platform_release(manifest: dict[str, Any], platform: str) -> Optional[dict[str, Any]]:
    """One platform block from latest.json, or None when that OS has not been published."""
    block = manifest.get(platform)
    if not isinstance(block, dict):
        return None
    key = block.get("key")
    sha256 = block.get("sha256")
    if not isinstance(key, str) or not key or not isinstance(sha256, str) or not sha256:
        return None
    size = block.get("size")
    return {
        "version": str(manifest.get("version") or ""),
        "sha256": sha256,
        "size": int(size) if isinstance(size, int) else 0,
        "key": key,
    }


def load_update(platform: str) -> Optional[dict[str, Any]]:
    """Presign the current build for one OS. None when COS or the manifest is missing."""
    if platform not in PLATFORMS:
        return None
    raw = get_object_bytes(f"{manifest_prefix()}/latest.json", log_prefix="[DesktopPet]")
    if not raw:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    release = platform_release(parsed, platform)
    if release is None or not release["version"]:
        return None
    url = generate_presigned_get_url(str(release["key"]), expired=900)
    if not url:
        return None
    return {
        "version": release["version"],
        "sha256": release["sha256"],
        "size": release["size"],
        "url": url,
    }
