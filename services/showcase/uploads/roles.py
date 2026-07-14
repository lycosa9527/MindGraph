"""
Showcase upload role allowlists (init/complete).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from routers.features.community.helpers import THUMBNAIL_MAX_BYTES
from routers.features.showcase.helpers import (
    ALLOWED_DOC_SUFFIXES,
    ALLOWED_SOURCE_SUFFIXES,
    ALLOWED_VIDEO_SUFFIXES,
    ATTACHMENT_MAX_BYTES,
    GALLERY_IMAGE_SUFFIXES,
    GALLERY_MAX_ITEMS,
    VIDEO_MAX_BYTES,
)

_GALLERY_ROLE = re.compile(r"^gallery_([0-9]|1[0-1])$")

CONTENT_TYPES: dict[str, frozenset[str]] = {
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".gif": frozenset({"image/gif"}),
    ".webp": frozenset({"image/webp"}),
    ".pdf": frozenset({"application/pdf"}),
    ".doc": frozenset({"application/msword"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    ),
    ".mp4": frozenset({"video/mp4"}),
    ".m4v": frozenset({"video/mp4", "video/x-m4v"}),
    ".mov": frozenset({"video/quicktime"}),
    ".webm": frozenset({"video/webm"}),
    ".mg": frozenset({"application/json", "application/octet-stream", "text/plain"}),
    ".json": frozenset({"application/json"}),
}


@dataclass(frozen=True)
class UploadRoleSpec:
    """Role → suffix allowlist and size cap."""

    role: str
    allowed_suffixes: frozenset[str]
    max_bytes: int
    spec_field: Optional[str] = None  # key in post.spec dict
    is_thumbnail: bool = False
    is_gallery: bool = False
    gallery_slot: Optional[int] = None


def resolve_upload_role(role: str) -> UploadRoleSpec:
    """Map role name to allowlist + size limits."""
    if role == "thumbnail":
        return UploadRoleSpec(
            role=role,
            allowed_suffixes=frozenset({".png"}),
            max_bytes=THUMBNAIL_MAX_BYTES,
            is_thumbnail=True,
        )
    if role == "attachment":
        return UploadRoleSpec(
            role=role,
            allowed_suffixes=ALLOWED_DOC_SUFFIXES,
            max_bytes=ATTACHMENT_MAX_BYTES,
            spec_field="attachment_path",
        )
    if role == "source":
        return UploadRoleSpec(
            role=role,
            allowed_suffixes=ALLOWED_SOURCE_SUFFIXES,
            max_bytes=ATTACHMENT_MAX_BYTES,
            spec_field="source_file_path",
        )
    if role == "reflection":
        return UploadRoleSpec(
            role=role,
            allowed_suffixes=ALLOWED_VIDEO_SUFFIXES,
            max_bytes=VIDEO_MAX_BYTES,
            spec_field="reflection_video_path",
        )
    if role == "classroom":
        return UploadRoleSpec(
            role=role,
            allowed_suffixes=ALLOWED_VIDEO_SUFFIXES,
            max_bytes=VIDEO_MAX_BYTES,
            spec_field="classroom_video_path",
        )
    if role == "spec":
        # Spec JSON is stored in Postgres; do not mint COS uploads for it.
        raise ValueError("Spec is stored in Postgres; use the post create/update JSON body")
    match = _GALLERY_ROLE.match(role)
    if match:
        slot = int(match.group(1))
        if slot >= GALLERY_MAX_ITEMS:
            raise ValueError(f"Invalid gallery slot: {slot}")
        return UploadRoleSpec(
            role=role,
            allowed_suffixes=GALLERY_IMAGE_SUFFIXES,
            max_bytes=ATTACHMENT_MAX_BYTES,
            is_gallery=True,
            gallery_slot=slot,
        )
    raise ValueError(f"Invalid upload role: {role}")


def suffix_from_filename(filename: str, allowed: frozenset[str]) -> str:
    """Extract and validate suffix from filename."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in allowed:
        raise ValueError(f"Invalid file type. Allowed: {sorted(allowed)}")
    return suffix


def assert_content_type_allowed(suffix: str, content_type: str) -> None:
    """Reject Content-Type values outside the allowlist for the suffix."""
    allowed = CONTENT_TYPES.get(suffix)
    if not allowed:
        return
    normalized = (content_type or "").split(";")[0].strip().lower()
    if normalized and normalized not in allowed:
        raise ValueError(f"Content-Type {content_type} not allowed for {suffix}")
