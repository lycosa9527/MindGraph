"""Shared MIME / size gates for Kitty conversation image uploads."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

MAX_CONVERSATION_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_CONVERSATION_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def normalize_conversation_image_content_type(
    *,
    content_type: Optional[str],
    filename: Optional[str],
) -> str:
    """Normalize upload content type; infer from filename when missing."""
    raw_type = (content_type or "").strip().lower()
    if raw_type == "image/jpg":
        raw_type = "image/jpeg"
    if raw_type in ALLOWED_CONVERSATION_IMAGE_TYPES:
        return raw_type
    suffix = Path(filename or "").suffix.lower()
    by_suffix = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    return by_suffix.get(suffix, "")


def validate_conversation_image_bytes(raw: bytes) -> None:
    """Raise ValueError for empty or oversized image bodies."""
    if not raw:
        raise ValueError("Empty file")
    if len(raw) > MAX_CONVERSATION_IMAGE_BYTES:
        raise ValueError("Image too large")
