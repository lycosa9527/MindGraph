"""Admin helpers for per-organization MindMate agent branding."""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Optional, cast

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from models.domain.auth import MINDMATE_AGENT_NAME_MAX_LENGTH, Organization
from models.domain.messages import Language, Messages
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

ORG_MINDMATE_AVATARS_DIR = Path("static/org_mindmate_avatars")
ORG_MINDMATE_AVATAR_URL_PREFIX = "/static/org_mindmate_avatars/"
ORG_AVATAR_PNG_FILENAME = "avatar.png"
ORG_AVATAR_GIF_FILENAME = "avatar.gif"
ALLOWED_PIL_FORMATS = frozenset({"PNG", "JPEG", "GIF", "WEBP"})
MAX_AVATAR_BYTES = 1024 * 1024
MINDMATE_AVATAR_OUTPUT_PX = 256
MIN_AVATAR_INPUT_PX = 64
MAX_AVATAR_DECODE_PX = 4096
MAX_GIF_FRAMES = 120
DEFAULT_GIF_FRAME_MS = 100
CANONICAL_AVATAR_RELATIVE_RE = re.compile(r"^(?P<org_id>\d+)/(avatar\.(?:png|gif))$")


def mindmate_org_avatar_dir(org_id: int) -> Path:
    """Filesystem directory for one school's MindMate avatar."""
    return ORG_MINDMATE_AVATARS_DIR / str(org_id)


def mindmate_org_avatar_public_url(org_id: int, *, animated: bool = False) -> str:
    """Public URL for a school's canonical MindMate avatar file."""
    filename = ORG_AVATAR_GIF_FILENAME if animated else ORG_AVATAR_PNG_FILENAME
    return f"{ORG_MINDMATE_AVATAR_URL_PREFIX}{org_id}/{filename}"


def mindmate_branding_list_fields(org: Organization) -> dict[str, Any]:
    """Serialized MindMate branding fields for admin organization list."""
    agent_name = (cast(Optional[str], getattr(org, "mindmate_agent_name", None)) or "").strip()
    avatar_url = (cast(Optional[str], getattr(org, "mindmate_agent_avatar_url", None)) or "").strip()
    return {
        "mindmate_agent_name": agent_name or None,
        "mindmate_agent_avatar_url": avatar_url or None,
    }


def _resolved_avatars_root() -> Path:
    """Resolved avatars root."""
    return ORG_MINDMATE_AVATARS_DIR.resolve()


def _avatar_url_path_part(avatar_url: str) -> str:
    """Strip cache-buster query string from a stored avatar URL."""
    return avatar_url.split("?", 1)[0]


def _canonical_avatar_relative_path(path_part: str) -> Optional[str]:
    """Return org avatar relative path when URL maps to a canonical avatar file."""
    if not path_part.startswith(ORG_MINDMATE_AVATAR_URL_PREFIX):
        return None
    relative = path_part[len(ORG_MINDMATE_AVATAR_URL_PREFIX) :].lstrip("/")
    if not relative or ".." in relative.replace("\\", "/"):
        return None
    if CANONICAL_AVATAR_RELATIVE_RE.fullmatch(relative.replace("\\", "/")) is None:
        return None
    return relative.replace("\\", "/")


def local_mindmate_avatar_path(avatar_url: Optional[str]) -> Optional[Path]:
    """Map a stored public URL to a filesystem path when it is a local org avatar."""
    if not avatar_url or not avatar_url.startswith(ORG_MINDMATE_AVATAR_URL_PREFIX):
        return None
    relative = _canonical_avatar_relative_path(_avatar_url_path_part(avatar_url))
    if relative is None:
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


def _unlink_if_exists(filepath: Path) -> None:
    """Unlink if exists."""
    if not filepath.is_file():
        return
    try:
        filepath.unlink()
    except OSError as exc:
        logger.warning("Failed to delete MindMate avatar %s: %s", filepath, exc)


def finalize_mindmate_avatar_upload(
    org_id: int,
    old_avatar_url: Optional[str],
    new_avatar_url: str,
) -> None:
    """Remove superseded avatar files after the DB URL has been committed."""
    org_dir = mindmate_org_avatar_dir(org_id)
    new_path = local_mindmate_avatar_path(new_avatar_url)
    old_path = local_mindmate_avatar_path(old_avatar_url)

    if new_path is not None:
        other_name = ORG_AVATAR_PNG_FILENAME if new_path.name == ORG_AVATAR_GIF_FILENAME else ORG_AVATAR_GIF_FILENAME
        _unlink_if_exists(org_dir / other_name)

    if old_path is not None and new_path is not None and old_path.resolve() != new_path.resolve():
        _unlink_if_exists(old_path)


def revert_mindmate_avatar_upload(
    old_avatar_url: Optional[str],
    new_avatar_url: str,
) -> None:
    """Remove a newly written avatar file when the DB commit fails."""
    new_path = local_mindmate_avatar_path(new_avatar_url)
    old_path = local_mindmate_avatar_path(old_avatar_url)
    if new_path is None or not new_path.is_file():
        return
    if old_path is not None and new_path.resolve() == old_path.resolve():
        return
    _unlink_if_exists(new_path)


def _cleanup_stale_upload_temps(org_dir: Path) -> None:
    """Remove abandoned temp files from interrupted uploads."""
    if not org_dir.is_dir():
        return
    for temp_path in org_dir.glob(".upload-*"):
        if temp_path.is_file():
            _unlink_if_exists(temp_path)


def purge_legacy_flat_org_avatars(org_id: int) -> None:
    """Remove pre-subfolder uploads: org_mindmate_avatars/org_{id}_* at repo root."""
    if not ORG_MINDMATE_AVATARS_DIR.is_dir():
        return
    for pattern in (f"org_{org_id}_*.png", f"org_{org_id}_*.gif"):
        for filepath in ORG_MINDMATE_AVATARS_DIR.glob(pattern):
            if not filepath.is_file():
                continue
            try:
                filepath.unlink()
            except OSError as exc:
                logger.warning("Failed to delete legacy MindMate avatar %s: %s", filepath, exc)


def purge_org_mindmate_avatar_storage(org_id: int) -> None:
    """Delete all on-disk MindMate avatar files for one organization."""
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
            if stripped and _canonical_avatar_relative_path(_avatar_url_path_part(stripped)) is None:
                error_msg = Messages.error("mindmate_agent_avatar_url_invalid", lang)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )
            setattr(org, "mindmate_agent_avatar_url", stripped if stripped else None)


def _raise_invalid_image(exc: Exception) -> None:
    """Raise invalid image."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="mindmate_avatar_invalid_image",
    ) from exc


def _validate_pil_format(pil_format: Optional[str]) -> None:
    """Validate pil format."""
    normalized = (pil_format or "").upper()
    if normalized not in ALLOWED_PIL_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_unsupported_type",
        )


def _validate_decoded_dimensions(width: int, height: int) -> None:
    """Validate decoded dimensions."""
    if width < 1 or height < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_invalid_image",
        )
    if width > MAX_AVATAR_DECODE_PX or height > MAX_AVATAR_DECODE_PX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_invalid_image",
        )


def _is_animated_gif(opened: Image.Image) -> bool:
    """Is animated gif."""
    return (
        (opened.format or "").upper() == "GIF"
        and getattr(opened, "is_animated", False)
        and getattr(opened, "n_frames", 1) > 1
    )


def _square_crop_resize(image: Image.Image, *, enforce_min_size: bool) -> Image.Image:
    """Square crop resize."""
    width, height = image.size
    _validate_decoded_dimensions(width, height)
    if enforce_min_size and min(width, height) < MIN_AVATAR_INPUT_PX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_too_small",
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


def _process_static_avatar_image(opened: Image.Image) -> Image.Image:
    """Decode, EXIF-correct, center-crop square, and resize static avatar for MindMate UI."""
    try:
        image = ImageOps.exif_transpose(opened).convert("RGBA")
    except (OSError, ValueError) as exc:
        _raise_invalid_image(exc)
        raise AssertionError("invalid image") from exc
    return _square_crop_resize(image, enforce_min_size=True)


def _process_animated_gif_avatar(
    opened: Image.Image,
) -> tuple[list[Image.Image], list[int]]:
    """Center-crop and resize each GIF frame to the MindMate avatar square."""
    frame_count = getattr(opened, "n_frames", 1)
    if frame_count > MAX_GIF_FRAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmate_avatar_gif_too_many_frames",
        )

    frames: list[Image.Image] = []
    durations: list[int] = []
    for frame_index in range(frame_count):
        opened.seek(frame_index)
        frame = opened.convert("RGBA")
        frames.append(_square_crop_resize(frame, enforce_min_size=frame_index == 0))
        raw_duration = opened.info.get("duration", DEFAULT_GIF_FRAME_MS)
        duration_ms = int(raw_duration) if raw_duration else DEFAULT_GIF_FRAME_MS
        if duration_ms < 1:
            duration_ms = DEFAULT_GIF_FRAME_MS
        durations.append(duration_ms)
    return frames, durations


def _write_avatar_atomically(
    org_dir: Path,
    *,
    animated: bool,
    static_image: Optional[Image.Image],
    gif_frames: Optional[list[Image.Image]],
    gif_durations: Optional[list[int]],
) -> Path:
    """Write avatar atomically."""
    org_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_stale_upload_temps(org_dir)
    final_name = ORG_AVATAR_GIF_FILENAME if animated else ORG_AVATAR_PNG_FILENAME
    final_path = org_dir / final_name
    temp_path = org_dir / f".upload-{uuid.uuid4().hex}.{final_name}"

    try:
        if animated:
            if not gif_frames:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="mindmate_avatar_invalid_image",
                )
            append_images = gif_frames[1:] if len(gif_frames) > 1 else []
            gif_frames[0].save(
                temp_path,
                save_all=True,
                append_images=append_images,
                loop=0,
                duration=gif_durations or DEFAULT_GIF_FRAME_MS,
                optimize=True,
            )
        else:
            if static_image is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="mindmate_avatar_invalid_image",
                )
            static_image.save(temp_path, "PNG", optimize=True)
        os.replace(temp_path, final_path)
    except HTTPException:
        _unlink_if_exists(temp_path)
        raise
    except BACKGROUND_INFRA_ERRORS:
        _unlink_if_exists(temp_path)
        raise

    if animated and gif_frames:
        for frame in gif_frames[1:]:
            frame.close()
        gif_frames[0].close()

    return final_path


async def save_mindmate_agent_avatar(org: Organization, file: UploadFile) -> str:
    """Validate, process, persist avatar file, and return its public URL path."""
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

    animated = False
    static_image = None
    gif_frames = None
    gif_durations = None

    try:
        with Image.open(BytesIO(contents)) as opened:
            _validate_pil_format(opened.format)
            _validate_decoded_dimensions(opened.size[0], opened.size[1])
            animated = _is_animated_gif(opened)
            if animated:
                gif_frames, gif_durations = _process_animated_gif_avatar(opened)
                static_image = None
            else:
                static_image = _process_static_avatar_image(opened)
                gif_frames = None
                gif_durations = None
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        _raise_invalid_image(exc)

    org_id = cast(int, getattr(org, "id", 0))
    org_dir = mindmate_org_avatar_dir(org_id)
    _write_avatar_atomically(
        org_dir,
        animated=animated,
        static_image=static_image,
        gif_frames=gif_frames,
        gif_durations=gif_durations,
    )
    purge_legacy_flat_org_avatars(org_id)

    canonical = mindmate_org_avatar_public_url(org_id, animated=animated)
    return f"{canonical}?v={int(time.time())}"
