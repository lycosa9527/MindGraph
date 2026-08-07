"""ZhiHui object key helpers (logical keys stored in Postgres)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from config.settings import config
from services.utils.tencent_cos_client import cos_object_key

LOGICAL_PREFIX = "zhihui/generations"

_EXT_SAFE = re.compile(r"^\.[a-z0-9]{1,8}$", re.IGNORECASE)
_GENERATION_OBJECT_RE = re.compile(
    rf"^{re.escape(LOGICAL_PREFIX)}/"
    r"[0-9a-fA-F-]{8,36}"
    r"\.[a-z0-9]{1,8}$",
    re.IGNORECASE,
)


def build_generation_key(*, generation_id: str | None = None, suffix: str = ".jpg") -> str:
    """
    Build logical object key stored in Postgres.

    Example: zhihui/generations/{uuid}.jpg
    """
    ext = suffix if suffix.startswith(".") else f".{suffix}"
    if not _EXT_SAFE.match(ext):
        raise ValueError(f"Invalid file suffix: {suffix}")
    object_id = (generation_id or str(uuid.uuid4())).strip()
    if not object_id:
        raise ValueError("generation_id required")
    return f"{LOGICAL_PREFIX}/{object_id}{ext.lower()}"


def full_cos_key(logical_key: str) -> str:
    """Prefix logical key with COS_ZHIHUI_PREFIX for the bucket."""
    return cos_object_key(logical_key, prefix=config.COS_ZHIHUI_PREFIX)


def zhihui_public_asset_url(logical_key: str) -> str:
    """App-relative asset URL only — never a durable COS host URL."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    if not is_zhihui_logical_key(normalized):
        raise ValueError(f"Not a zhihui path: {logical_key}")
    return f"/api/zhihui/assets/{normalized}"


def is_zhihui_generation_key(logical_key: str) -> bool:
    """True if key is a user generation object."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    return bool(_GENERATION_OBJECT_RE.match(normalized))


def is_zhihui_logical_key(logical_key: str) -> bool:
    """True if key is a serveable ZhiHui generation asset."""
    return is_zhihui_generation_key(logical_key)


def zhihui_local_root() -> Path:
    """Local fallback root for generations (dev/CI when COS off)."""
    return Path("static") / "zhihui" / "generations"


def local_path_for_key(logical_key: str) -> Path:
    """Map logical key to local filesystem path under static/."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    if not is_zhihui_generation_key(normalized):
        raise ValueError(f"Not a zhihui path: {logical_key}")
    relative = normalized[len(LOGICAL_PREFIX) :].lstrip("/")
    return (zhihui_local_root() / relative).resolve()


def resolve_local_safe(logical_key: str) -> Path:
    """Resolve local path and reject traversal outside the ZhiHui root."""
    path = local_path_for_key(logical_key)
    root = zhihui_local_root().resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"Path escapes zhihui root: {logical_key}")
    return path
