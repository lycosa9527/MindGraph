"""Admin helpers for per-organization MindMate agent branding."""

from __future__ import annotations

import logging
import shutil
from io import BytesIO
from pathlib import Path
from typing import Any, Optional, cast

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from models.domain.auth import MINDMATE_AGENT_NAME_MAX_LENGTH, Organization
from models.domain.messages import Language, Messages

logger = logging.getLogger(__name__)

ORG_MINDMATE_AVATARS_DIR = Path("static/org_mindmate_avatars")
ORG_MINDMATE_AVATAR_URL_PREFIX = "/static/org_mindmate_avatars/"
ORG_AVATAR_FILENAME = "avatar.png"
ALLOWED_AVATAR_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
)
MAX_AVATAR_BYTES = 1024 * 1024
MINDMATE_AVATAR_OUTPUT_PX = 256


def mindmate_org_avatar_dir(org_id: int) -> Path:
    """Filesystem directory for one school's MindMate avatar."""
    return ORG_MINDMATE_AVATARS_DIR / str(org_id)


def mindmate_org_avatar_public_url(org_id: int) -> str:
    """Public URL for a school's canonical MindMate avatar file."""
    return f"{ORG_MINDMATE_AVATAR_URL_PREFIX}{org_id}/{ORG_AVATAR_FILENAME}"


def mindmate_branding_list_fields(org: Organization) -> dict[str, Any]:
    """Serialized MindMate branding fields for admin organization list."""
    agent_name = (cast(Optional[str], getattr(org, "mindmate_agent_name", None)) or "").strip()
    avatar_url = (
        cast(Optional[str], getattr(org, "mindmate_agent_avatar_url", None)) or ""
    ).strip()
    return {
        "mindmate_agent_name": agent_name or None,
        "mindmate_agent_avatar_url": avatar_url or None,
    }


def _resolved_avatars_root() -> Path:
    return ORG_MINDMATE_AVATARS_DIR.resolve()


def local_mindmate_avatar_path(avatar_url: Optional[str]) -> Optional[Path]:
    """Map a stored public URL to a filesystem path when it is a local org avatar."""
    if not avatar_url or not avatar_url.startswith(ORG_MINDMATE_AVATAR_URL_PREFIX):
        return None
    relative = avatar_url[len(ORG_MINDMATE_AVATAR_URL_PREFIX) :].lstrip("/")
    if not relative or ".." in relative.replace("\\", "/"):
        return None
    candidate = (ORG_MINDMATE_AVATARS_DIR / relative).resolve()
    try:
        candidate.relative_to(_resolved_avatars_root())
    except ValueError:
        return None
    return candidate


def delete_local_mindmate_avatar(avatar_url: Optional[str]) -> None:
    """Remove one stored org avatar file referenced by URL."""
    filepath = local_mindmate_avatar_path(avatar_url)
    if filepath is None or not filepath.is_file():
        return
    try:
        filepath.unlink()
    except OSError as exc:
        logger.warning("Failed to delete MindMate avatar %s: %s", filepath, exc)


def purge_legacy_flat_org_avatars(org_id: int) -> None:
    """Remove pre-subfolder uploads: org_mindmate_avatars/org_{id}_*.png at repo root."""
    if not ORG_MINDMATE_AVATARS_DIR.is_dir():
        return
    pattern = f"org_{org_id}_*.png"
    for filepath in ORG_MINDMATE_AVATARS_DIR.glob(pattern):
        if not filepath.is_file():
            continue
        try:
            filepath.unlink()
        except OSError as exc:
            logger.warning("Failed to delete legacy MindMate avatar %s: %s", filepath, exc)


def purge_org_mindmate_avatar_storage(org_id: int) -> None:
    """Delete all on-disk MindMate avatar files for one organization."""
    delete_local_mindmate_avatar(mindmate_org_avatar_public_url(org_id))
    org_dir = mindmate_org_avatar_dir(org_id)
    if org_dir.is_dir():
        try:
            shutil.rmtree(org_dir)
        except OSError as exc:
            logger.warning("Failed to remove MindMate avatar dir %s: %s", org_dir, exc)
    purge_legacy_flat_org_avatars(org_id)


def apply_mindmate_branding_on_update(
    org: Organization,
    request: dict,
    lang: Language,
) -> None:
    """Apply MindMate agent name / avatar URL on organization update."""
    if "mindmate_agent_name" in request:
        raw_name = request.get("mindmate_agent_name")
        if raw_name is None:
            setattr(org, "mindmate_agent_name", None)
        else:
            stripped = (raw_name or "").strip()
            if stripped and len(stripped) > MINDMATE_AGENT_NAME_MAX_LENGTH:
                error_msg = Messages.error("mindmate_agent_name_too_long", lang)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )
            setattr(org, "mindmate_agent_name", stripped if stripped else None)

    if "mindmate_agent_avatar_url" in request:
        raw_url = request.get("mindmate_agent_avatar_url")
        if raw_url is None:
            old_url = cast(
                Optional[str],
                getattr(org, "mindmate_agent_avatar_url", None),
            )
            delete_local_mindmate_avatar(old_url)
            org_id = cast(int, getattr(org, "id", 0))
            purge_org_mindmate_avatar_storage(org_id)
            setattr(org, "mindmate_agent_avatar_url", None)
        else:
            stripped = (raw_url or "").strip()
            if stripped and len(stripped) > 512:
                error_msg = Messages.error("mindmate_agent_avatar_url_too_long", lang)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )
            if stripped and not stripped.startswith(ORG_MINDMATE_AVATAR_URL_PREFIX):
                error_msg = Messages.error("mindmate_agent_avatar_url_invalid", lang)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )
            setattr(org, "mindmate_agent_avatar_url", stripped if stripped else None)


def _process_avatar_image(contents: bytes) -> Image.Image:
    """Decode, center-crop square, and resize avatar for MindMate UI."""
    try:
        with Image.open(BytesIO(contents)) as opened:
            image = opened.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_invalid_image",
        ) from exc

    width, height = image.size
    if width < 1 or height < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_invalid_image",
        )

    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    cropped = image.crop((left, top, left + side, top + side))
    if side != MINDMATE_AVATAR_OUTPUT_PX:
        cropped = cropped.resize(
            (MINDMATE_AVATAR_OUTPUT_PX, MINDMATE_AVATAR_OUTPUT_PX),
            Image.Resampling.LANCZOS,
        )
    return cropped


async def save_mindmate_agent_avatar(org: Organization, file: UploadFile) -> str:
    """Validate, process, persist avatar file, and return its public URL path."""
    content_type = (file.content_type or "").strip().lower()
    if content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_unsupported_type",
        )

    contents = await file.read()
    if len(contents) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_too_large",
        )

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_invalid_image",
        )

    processed = _process_avatar_image(contents)

    org_id = cast(int, getattr(org, "id", 0))
    old_url = cast(Optional[str], getattr(org, "mindmate_agent_avatar_url", None))

    org_dir = mindmate_org_avatar_dir(org_id)
    org_dir.mkdir(parents=True, exist_ok=True)
    filepath = org_dir / ORG_AVATAR_FILENAME
    processed.save(filepath, "PNG", optimize=True)

    if old_url:
        delete_local_mindmate_avatar(old_url)
    purge_legacy_flat_org_avatars(org_id)

    return mindmate_org_avatar_public_url(org_id)
