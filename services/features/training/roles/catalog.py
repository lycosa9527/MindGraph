"""Allowlisted packed role clip ids and repo/COS key mapping."""

from __future__ import annotations

import re
from pathlib import Path

ROLE_LOGICAL_PREFIX = "roles"
ROLE_CONTENT_TYPE = "image/webp"
_ROLE_ID_RE = re.compile(r"^[0-9]{2}-[a-z0-9-]+$")

TRAINING_ROLE_IDS: tuple[str, ...] = (
    "01-look-here",
    "02-listen",
    "03-raise-hand",
    "04-secret",
    "05-open-book",
    "06-eureka",
    "07-build-blocks",
    "08-zoom",
    "09-orbit",
    "10-erase",
    "11-clap",
    "12-cheer",
    "13-pat-head",
    "14-take-notes",
    "15-countdown",
    "16-pace-think",
    "17-telescope",
    "18-magic-light",
    "19-drink-ink",
    "20-dismiss",
)

_ROLE_ID_SET = frozenset(TRAINING_ROLE_IDS)
_REPO_ROOT = Path(__file__).resolve().parents[4]


def is_training_role_id(role_id: str) -> bool:
    """True when id is one of the shipped mascot clips."""
    return role_id in _ROLE_ID_SET and bool(_ROLE_ID_RE.match(role_id))


def packed_role_filename(role_id: str, *, thumb: bool = False) -> str:
    """Safe filename under the packed roles folder."""
    if not is_training_role_id(role_id):
        raise ValueError(f"Unknown training role: {role_id}")
    suffix = "-thumb.webp" if thumb else ".webp"
    return f"{role_id}{suffix}"


def packed_role_key(role_id: str, *, thumb: bool = False) -> str:
    """Logical COS/API key. Never a durable bucket host."""
    return f"{ROLE_LOGICAL_PREFIX}/{packed_role_filename(role_id, thumb=thumb)}"


def packed_role_public_url(role_id: str, *, thumb: bool = False) -> str:
    """App-relative playback URL that 302s to COS when training COS is on."""
    return f"/api/training/assets/{packed_role_key(role_id, thumb=thumb)}"


def parse_packed_role_key(logical_key: str) -> tuple[str, bool] | None:
    """Return (role_id, is_thumb) when key is a packed role object."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    prefix = f"{ROLE_LOGICAL_PREFIX}/"
    if not normalized.startswith(prefix) or normalized.count("/") != 1:
        return None
    filename = normalized[len(prefix) :]
    thumb = filename.endswith("-thumb.webp")
    stem = filename[: -len("-thumb.webp")] if thumb else filename[: -len(".webp")]
    if not filename.endswith(".webp") or not is_training_role_id(stem):
        return None
    if not thumb and filename != f"{stem}.webp":
        return None
    return stem, thumb


def is_packed_role_key(logical_key: str) -> bool:
    """True for roles/{id}.webp or roles/{id}-thumb.webp."""
    return parse_packed_role_key(logical_key) is not None


def packed_role_repo_dirs() -> tuple[Path, ...]:
    """Repo public folder first, then built frontend copy."""
    return (
        _REPO_ROOT / "frontend" / "public" / "training" / "roles",
        _REPO_ROOT / "frontend" / "dist" / "training" / "roles",
    )


def packed_role_file(role_id: str, *, thumb: bool = False) -> Path | None:
    """Absolute path to a shipped WebP, if present on disk."""
    name = packed_role_filename(role_id, thumb=thumb)
    for folder in packed_role_repo_dirs():
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def packed_role_filenames() -> tuple[str, ...]:
    """All shipped anim + thumb filenames."""
    names: list[str] = []
    for role_id in TRAINING_ROLE_IDS:
        names.append(packed_role_filename(role_id, thumb=False))
        names.append(packed_role_filename(role_id, thumb=True))
    return tuple(names)
