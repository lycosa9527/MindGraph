"""Deck bytes for a clip lesson.

``ENVIRONMENT=development`` (and ``dev``) writes ``static/clip-lessons``.
Test and production upload to COS under ``COS_CLIP_TEACHING_PREFIX`` and do
not keep a second copy on disk.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from config.settings import config
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    cos_object_key,
    delete_object,
    get_object_bytes,
    upload_bytes,
)

logger = logging.getLogger(__name__)

_KEY = re.compile(r"^clip-lessons/[0-9a-fA-F-]{36}/(deck\.pptx|preview\.pdf)$")
_VIDEO_KEY = re.compile(r"^clip-lessons/[0-9a-fA-F-]{36}/video\.(mp4|webm|mov|ogg)$")
_VIDEO_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".ogg": "video/ogg",
}
_ROOT = Path("static") / "clip-lessons"
_LOCAL_ENVIRONMENTS = frozenset({"development", "dev"})


def lesson_deck_key(lesson_id: str) -> str:
    """Logical key for the uploaded PPTX."""
    return f"clip-lessons/{lesson_id}/deck.pptx"


def lesson_preview_key(lesson_id: str) -> str:
    """Logical key for the converted PDF."""
    return f"clip-lessons/{lesson_id}/preview.pdf"


def lesson_video_key(lesson_id: str, suffix: str) -> str:
    """Logical key for a development-machine video file."""
    ext = suffix if suffix.startswith(".") else f".{suffix}"
    ext = ext.lower()
    if ext not in _VIDEO_TYPES:
        raise ValueError("Invalid clip-lesson video")
    return f"clip-lessons/{lesson_id}/video{ext}"


def video_media_type(logical_key: str) -> str:
    """Content type for a stored local video."""
    _assert_key(logical_key)
    ext = Path(logical_key).suffix.lower()
    return _VIDEO_TYPES[ext]


def uses_local_disk() -> bool:
    """True on a development machine. Test and production use COS."""
    environment = os.getenv("ENVIRONMENT", "production").strip().lower()
    return environment in _LOCAL_ENVIRONMENTS


def full_clip_cos_key(logical_key: str) -> str:
    """Bucket key under the clip-teaching prefix."""
    _assert_key(logical_key)
    return cos_object_key(logical_key, prefix=config.COS_CLIP_TEACHING_PREFIX)


def _assert_key(logical_key: str) -> None:
    if _KEY.match(logical_key) or _VIDEO_KEY.match(logical_key):
        return
    raise ValueError("Invalid clip-lesson object key")


def _local_path(logical_key: str) -> Path:
    _assert_key(logical_key)
    path = (_ROOT.parent / logical_key).resolve()
    root = _ROOT.resolve()
    if path != root and root not in path.parents:
        raise ValueError("Invalid clip-lesson object key")
    return path


def write_local_video(logical_key: str, data: bytes) -> None:
    """Write a development video. Other extensions for the same lesson are removed."""
    path = _local_path(logical_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    for sibling in path.parent.glob("video.*"):
        if sibling.is_file() and sibling.resolve() != path:
            sibling.unlink()
    path.write_bytes(data)


def local_video_file(logical_key: str) -> Path:
    """Filesystem path for a development video."""
    return _local_path(logical_key)


def put_object(logical_key: str, data: bytes, content_type: str) -> None:
    """Store bytes on local disk or COS, depending on the machine."""
    if uses_local_disk():
        path = _local_path(logical_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    if not cos_credentials_configured():
        raise OSError("Clip lesson COS credentials are not configured")
    uploaded = upload_bytes(
        data,
        full_clip_cos_key(logical_key),
        content_type=content_type,
        log_prefix="[ClipLesson]",
    )
    if not uploaded:
        raise OSError("Failed to upload clip lesson object to COS")


def read_object(logical_key: str) -> bytes | None:
    """Read bytes from the store selected for this machine."""
    if uses_local_disk():
        path = _local_path(logical_key)
        if path.is_file():
            return path.read_bytes()
        return None
    if not cos_credentials_configured():
        return None
    remote = get_object_bytes(full_clip_cos_key(logical_key), log_prefix="[ClipLesson]")
    if remote:
        return remote
    return None


def delete_object_key(logical_key: str) -> None:
    """Remove a stored deck or preview. Missing objects are ignored."""
    if uses_local_disk():
        path = _local_path(logical_key)
        if path.is_file():
            path.unlink()
        return
    if not cos_credentials_configured():
        logger.warning("Clip lesson COS delete skipped; credentials are missing key=%s", logical_key)
        return
    delete_object(full_clip_cos_key(logical_key))
