"""Library-demo list thumbnails stored in COS under the signed-in user.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re

from services.utils.tencent_cos_client import cos_object_key, get_object_bytes, upload_bytes

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_BYTES = 2 * 1024 * 1024
_DIAGRAM_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def clean_library_demo_diagram_id(value: str) -> str | None:
    """Accept a diagram id that is safe to put in an object key and a URL."""
    cleaned = value.strip()
    if _DIAGRAM_ID.fullmatch(cleaned) is None:
        return None
    return cleaned


def library_demo_thumbnail_key(user_id: int, diagram_id: str) -> str:
    """User-scoped COS key for one list thumbnail."""
    return cos_object_key(f"library-demo/{user_id}/{diagram_id}.png")


def library_demo_thumbnail_path(diagram_id: str) -> str:
    """Same-origin URL the browser can show without COS credentials."""
    return f"/api/auth/library-demo/thumbnails/{diagram_id}"


def png_is_acceptable(payload: bytes) -> bool:
    """True for a PNG that fits the list-thumbnail size cap."""
    if len(payload) < len(_PNG_SIGNATURE) or len(payload) > _MAX_BYTES:
        return False
    return payload.startswith(_PNG_SIGNATURE)


def store_library_demo_thumbnail(user_id: int, diagram_id: str, payload: bytes) -> bool:
    """Upload one PNG. Returns false when the bytes or COS write are rejected."""
    if clean_library_demo_diagram_id(diagram_id) is None or not png_is_acceptable(payload):
        return False
    return upload_bytes(
        payload,
        library_demo_thumbnail_key(user_id, diagram_id),
        content_type="image/png",
        log_prefix="[LibraryDemo]",
    )


def read_library_demo_thumbnail(user_id: int, diagram_id: str) -> bytes | None:
    """Read a stored PNG, or None when it is missing."""
    if clean_library_demo_diagram_id(diagram_id) is None:
        return None
    return get_object_bytes(
        library_demo_thumbnail_key(user_id, diagram_id),
        max_bytes=_MAX_BYTES,
        log_prefix="[LibraryDemo]",
    )
