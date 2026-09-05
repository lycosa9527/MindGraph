"""Training COS object key helpers (logical keys stored in Postgres)."""

from __future__ import annotations

import re
from pathlib import Path

from config.settings import config
from services.utils.tencent_cos_client import cos_object_key

LOGICAL_PREFIX = "courses"
ASSET_ROLES = frozenset({"cover", "slide", "video", "media", "thumb"})
ROLE_FOLDERS = {
    "cover": "",
    "slide": "slides",
    "video": "videos",
    "media": "media",
    "thumb": "thumbs",
}

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_EXT_SAFE = re.compile(r"^\.[a-z0-9]{1,8}$", re.IGNORECASE)
_UUID_PATH = r"[0-9a-fA-F-]{36}"
_COURSE_OBJECT_RE = re.compile(
    rf"^{re.escape(LOGICAL_PREFIX)}/"
    rf"{_UUID_PATH}/"
    rf"(?:cover|slides/{_UUID_PATH}|videos/{_UUID_PATH}|media/{_UUID_PATH}|thumbs/{_UUID_PATH})"
    r"\.[a-z0-9]{1,8}$",
    re.IGNORECASE,
)


def normalize_ext(suffix: str) -> str:
    """Return a dotted lowercase suffix or raise."""
    ext = suffix if suffix.startswith(".") else f".{suffix}"
    if not _EXT_SAFE.match(ext):
        raise ValueError(f"Invalid file suffix: {suffix}")
    return ext.lower()


def require_course_id(course_id: str) -> str:
    """Validate a course UUID string."""
    if not _UUID_RE.match(course_id):
        raise ValueError(f"Invalid course id: {course_id}")
    return course_id


def course_folder(course_id: str) -> str:
    """Logical folder for one course (no trailing slash)."""
    return f"{LOGICAL_PREFIX}/{require_course_id(course_id)}"


def build_object_key(course_id: str, role: str, asset_id: str, suffix: str) -> str:
    """
    Build logical object key stored in Postgres.

    Examples:
      courses/{uuid}/cover.png
      courses/{uuid}/slides/{asset_id}.png
    """
    if role not in ASSET_ROLES:
        raise ValueError(f"Invalid upload role: {role}")
    ext = normalize_ext(suffix)
    folder = course_folder(course_id)
    if role == "cover":
        return f"{folder}/cover{ext}"
    if not _UUID_RE.match(asset_id):
        raise ValueError(f"Invalid asset id: {asset_id}")
    return f"{folder}/{ROLE_FOLDERS[role]}/{asset_id}{ext}"


def full_cos_key(logical_key: str) -> str:
    """Prefix logical key with COS_TRAINING_PREFIX for the bucket."""
    return cos_object_key(logical_key, prefix=config.COS_TRAINING_PREFIX)


def training_public_asset_url(logical_key: str) -> str:
    """App-relative asset URL only — never a durable COS host URL."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    if not is_training_logical_key(normalized):
        raise ValueError(f"Not a training path: {logical_key}")
    return f"/api/training/assets/{normalized}"


def is_training_logical_key(logical_key: str) -> bool:
    """True if key uses the training courses prefix."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    return normalized.startswith(f"{LOGICAL_PREFIX}/")


def is_scoped_course_object_key(logical_key: str) -> bool:
    """True when key matches courses/{id}/cover|slides|videos|media|thumbs."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    return bool(_COURSE_OBJECT_RE.match(normalized))


def course_id_from_key(logical_key: str) -> str | None:
    """Extract course UUID from a logical key."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    parts = normalized.split("/")
    if len(parts) < 2 or parts[0] != LOGICAL_PREFIX:
        return None
    if not _UUID_RE.match(parts[1]):
        return None
    return parts[1]


def training_local_root() -> Path:
    """Local fallback root (dev/CI when COS off)."""
    return Path("static") / "training" / LOGICAL_PREFIX


def local_path_for_key(logical_key: str) -> Path:
    """Map logical key to local filesystem path under static/training/."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    if not normalized.startswith(f"{LOGICAL_PREFIX}/"):
        raise ValueError(f"Not a training path: {logical_key}")
    return (Path("static") / "training" / normalized).resolve()


def resolve_local_safe(logical_key: str) -> Path:
    """Resolve local path with traversal checks."""
    candidate = local_path_for_key(logical_key)
    root = training_local_root().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path traversal rejected") from exc
    return candidate
