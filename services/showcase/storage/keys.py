"""Showcase object key helpers (logical keys stored in Postgres)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from config.settings import config
from services.utils.tencent_cos_client import cos_object_key

# Logical key prefix stored in PG (also used as local path under static/)
LOGICAL_PREFIX = "showcase/posts"
# Legacy on-disk layout still readable for migration / old rows
LEGACY_LOGICAL_PREFIX = "case_square"

_ROLE_SAFE = re.compile(r"^[a-z0-9_]+$")
_EXT_SAFE = re.compile(r"^\.[a-z0-9]{1,8}$", re.IGNORECASE)
# showcase/posts/{uuid}/role.ext
_POST_OBJECT_RE = re.compile(
    rf"^{re.escape(LOGICAL_PREFIX)}/"
    r"[0-9a-fA-F-]{8,36}/"
    r"[a-z0-9_]+\.[a-z0-9]{1,8}$",
    re.IGNORECASE,
)


def build_object_key(post_id: str, role: str, suffix: str) -> str:
    """
    Build logical object key stored in Postgres.

    Example: showcase/posts/{uuid}/attachment.pdf
    """
    if not _ROLE_SAFE.match(role):
        raise ValueError(f"Invalid upload role: {role}")
    ext = suffix if suffix.startswith(".") else f".{suffix}"
    if not _EXT_SAFE.match(ext):
        raise ValueError(f"Invalid file suffix: {suffix}")
    return f"{LOGICAL_PREFIX}/{post_id}/{role}{ext.lower()}"


def full_cos_key(logical_key: str) -> str:
    """Prefix logical key with COS_SHOWCASE_PREFIX for the bucket."""
    return cos_object_key(logical_key, prefix=config.COS_SHOWCASE_PREFIX)


def showcase_public_asset_url(logical_key: str) -> str:
    """App-relative asset URL only — never a durable COS host URL."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    if not (normalized.startswith(f"{LOGICAL_PREFIX}/") or normalized.startswith(f"{LEGACY_LOGICAL_PREFIX}/")):
        raise ValueError(f"Not a showcase path: {logical_key}")
    return f"/api/showcase/assets/{normalized}"


def is_showcase_logical_key(logical_key: str) -> bool:
    """True if key uses new or legacy Showcase logical prefixes."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    return normalized.startswith(f"{LOGICAL_PREFIX}/") or normalized.startswith(f"{LEGACY_LOGICAL_PREFIX}/")


def is_scoped_post_object_key(logical_key: str) -> bool:
    """True when key matches showcase/posts/{id}/role.ext (not unscoped noise)."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    return bool(_POST_OBJECT_RE.match(normalized))


def showcase_local_root() -> Path:
    """Local fallback root (dev/CI when COS off)."""
    return Path("static") / "showcase" / "posts"


def local_path_for_key(logical_key: str) -> Path:
    """Map logical key to local filesystem path under static/."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    if normalized.startswith(f"{LEGACY_LOGICAL_PREFIX}/"):
        return (Path("static") / normalized).resolve()
    if not normalized.startswith(f"{LOGICAL_PREFIX}/"):
        raise ValueError(f"Not a showcase path: {logical_key}")
    return (Path("static") / normalized).resolve()


def resolve_local_safe(logical_key: str) -> Path:
    """Resolve local path with traversal checks."""
    candidate = local_path_for_key(logical_key)
    if logical_key.lstrip("/").startswith(f"{LEGACY_LOGICAL_PREFIX}/"):
        root = (Path("static") / LEGACY_LOGICAL_PREFIX).resolve()
    else:
        root = showcase_local_root().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path traversal rejected") from exc
    return candidate


def collect_keys_from_post(
    *,
    thumbnail_path: Optional[str],
    spec: Optional[dict[str, Any]],
) -> list[str]:
    """Collect all media keys referenced by a Showcase post."""
    keys: list[str] = []
    if thumbnail_path:
        keys.append(thumbnail_path)
    if not isinstance(spec, dict):
        return keys
    for field in (
        "attachment_path",
        "source_file_path",
        "reflection_video_path",
        "classroom_video_path",
    ):
        value = spec.get(field)
        if isinstance(value, str) and value:
            keys.append(value)
    gallery = spec.get("gallery")
    if isinstance(gallery, list):
        for item in gallery:
            if isinstance(item, dict):
                path = item.get("path")
                if isinstance(path, str) and path:
                    keys.append(path)
    return keys


def logical_key_from_full_cos_key(full_key: str) -> str:
    """Strip COS_SHOWCASE_PREFIX to recover the logical key stored in PG."""
    prefix = (config.COS_SHOWCASE_PREFIX or "").strip().strip("/")
    normalized = full_key.lstrip("/").replace("\\", "/")
    if prefix:
        prefix_slash = f"{prefix}/"
        if normalized.startswith(prefix_slash):
            return normalized[len(prefix_slash) :]
    return normalized
