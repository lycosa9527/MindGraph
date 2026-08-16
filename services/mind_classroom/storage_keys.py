"""Logical COS keys for classroom slides and lecture transcripts."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from config.settings import config
from services.utils.tencent_cos_client import cos_object_key

LOGICAL_ROOT = "mind_classroom"
LOGICAL_PREFIX = f"{LOGICAL_ROOT}/generations"
TRANSCRIPT_PREFIX = f"{LOGICAL_ROOT}/transcripts"

_EXT_SAFE = re.compile(r"^\.[a-z0-9]{1,8}$", re.IGNORECASE)
_ID_RE = re.compile(r"^[0-9a-fA-F-]{8,36}$")
_SLIDE_RE = re.compile(
    rf"^{re.escape(LOGICAL_PREFIX)}/"
    r"[0-9a-fA-F-]{8,36}"
    r"\.[a-z0-9]{1,8}$",
    re.IGNORECASE,
)
_TRANSCRIPT_RE = re.compile(
    rf"^{re.escape(TRANSCRIPT_PREFIX)}/"
    r"([0-9a-fA-F-]{8,36})"
    r"\.md$",
    re.IGNORECASE,
)


def build_slide_key(*, slide_id: str | None = None, suffix: str = ".png") -> str:
    """Build logical object key stored in Postgres."""
    ext = suffix if suffix.startswith(".") else f".{suffix}"
    if not _EXT_SAFE.match(ext):
        raise ValueError(f"Invalid file suffix: {suffix}")
    object_id = (slide_id or str(uuid.uuid4())).strip()
    if not object_id:
        raise ValueError("slide_id required")
    return f"{LOGICAL_PREFIX}/{object_id}{ext.lower()}"


def build_transcript_key(job_id: str) -> str:
    """Logical key for one job's lecture markdown."""
    cleaned = (job_id or "").strip()
    if not _ID_RE.match(cleaned):
        raise ValueError(f"Invalid job_id: {job_id}")
    return f"{TRANSCRIPT_PREFIX}/{cleaned}.md"


def job_id_from_transcript_key(logical_key: str) -> Optional[str]:
    """Return job id when the key is a classroom transcript."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    match = _TRANSCRIPT_RE.match(normalized)
    return match.group(1) if match else None


def is_classroom_logical_key(logical_key: str) -> bool:
    """True if key is a serveable classroom slide or transcript."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    return bool(_SLIDE_RE.match(normalized) or _TRANSCRIPT_RE.match(normalized))


def classroom_public_asset_url(logical_key: str) -> str:
    """App-relative asset URL."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    if not is_classroom_logical_key(normalized):
        raise ValueError(f"Not a classroom path: {logical_key}")
    return f"/api/mind-classroom/assets/{normalized}"


def full_cos_key(logical_key: str) -> str:
    """Prefix logical key with COS_ZHIHUI_PREFIX for the shared bucket."""
    return cos_object_key(logical_key, prefix=config.COS_ZHIHUI_PREFIX)


def classroom_local_root() -> Path:
    """Local fallback root for classroom objects."""
    return Path("static") / LOGICAL_ROOT


def resolve_local_safe(logical_key: str) -> Path:
    """Resolve local path and reject traversal outside the classroom root."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    if not is_classroom_logical_key(normalized):
        raise ValueError(f"Not a classroom path: {logical_key}")
    relative = normalized[len(LOGICAL_ROOT) :].lstrip("/")
    path = (classroom_local_root() / relative).resolve()
    root = classroom_local_root().resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"Path escapes classroom root: {logical_key}")
    return path
