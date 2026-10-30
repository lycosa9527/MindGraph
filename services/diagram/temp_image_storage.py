"""Local cache + COS durable store for preview PNGs.

MindMate / DingTalk conversation history keeps ``/api/temp_images/dingtalk_*.png``
URLs. Seminar canvas shares use ``diagram_{uuid}.png``. Local files still age
out after 24h; COS is the copy that hydrate uses when a user reopens later.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

import aiofiles

from config.settings import config
from services.utils.error_types import FILE_IO_ERRORS
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    cos_object_key,
    download_file,
    object_exists,
    upload_bytes,
)

logger = logging.getLogger(__name__)

DINGTALK_TEMP_PNG_RE = re.compile(r"^dingtalk_[a-f0-9]{8}_\d+\.png$", re.IGNORECASE)
DIAGRAM_PREVIEW_PNG_RE = re.compile(r"^diagram_[a-f0-9]{32}\.png$", re.IGNORECASE)
LOCAL_SIGNED_TTL_SECONDS = 86400
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMP_IMAGES_DIR = _PROJECT_ROOT / "temp_images"


def temp_images_dir() -> Path:
    """Directory for local generate_dingtalk preview PNGs."""
    return _TEMP_IMAGES_DIR


def _is_bare_filename(filename: str) -> bool:
    name = (filename or "").strip()
    return bool(name) and "/" not in name and "\\" not in name and ".." not in name


def is_safe_dingtalk_temp_filename(filename: str) -> bool:
    """True when filename is a generate_dingtalk preview PNG (no path)."""
    return _is_bare_filename(filename) and bool(DINGTALK_TEMP_PNG_RE.match(filename.strip()))


def is_safe_diagram_preview_filename(filename: str) -> bool:
    """True when filename is a seminar canvas-share preview PNG (no path)."""
    return _is_bare_filename(filename) and bool(DIAGRAM_PREVIEW_PNG_RE.match(filename.strip()))


def cos_temp_images_enabled() -> bool:
    """True when COS credentials are configured (same bucket as ZhiHui/Showcase)."""
    return cos_credentials_configured()


def temp_images_signed_ttl() -> int:
    """Signed URL lifetime: long-lived when COS is on, 24h when local-only."""
    if not cos_temp_images_enabled():
        return LOCAL_SIGNED_TTL_SECONDS
    return int(config.COS_TEMP_IMAGES_URL_TTL_SECONDS)


def dingtalk_temp_cos_key(filename: str) -> str:
    """Full COS object key for a dingtalk preview PNG."""
    return cos_object_key(
        f"dingtalk/{filename}",
        prefix=config.COS_TEMP_IMAGES_PREFIX,
    )


def diagram_preview_cos_key(filename: str) -> str:
    """Full COS object key for a seminar canvas-share preview PNG."""
    return cos_object_key(
        f"diagram/{filename}",
        prefix=config.COS_TEMP_IMAGES_PREFIX,
    )


async def _persist_preview_png(
    filename: str,
    data: bytes,
    object_key: str,
    *,
    require_cos: bool = False,
) -> Path:
    """Write the local working copy, then mirror to COS when enabled."""
    dest = temp_images_dir()
    dest.mkdir(exist_ok=True)
    path = dest / filename
    async with aiofiles.open(path, "wb") as handle:
        await handle.write(data)
    if not cos_temp_images_enabled():
        return path
    uploaded = await asyncio.to_thread(
        upload_bytes,
        data,
        object_key,
        log_prefix="[TempImages/COS]",
        content_type="image/png",
    )
    if uploaded:
        logger.info("[TempImages] COS put filename=%s bytes=%s", filename, len(data))
        return path
    if require_cos:
        raise ValueError("upload_failed")
    logger.warning(
        "[TempImages] COS upload failed filename=%s (local copy kept)",
        filename,
    )
    return path


async def _hydrate_preview_png(filename: str, object_key: str) -> Optional[Path]:
    """Return the local path, pulling from COS when the cache file is gone."""
    dest = temp_images_dir()
    path = dest / filename
    try:
        if path.is_file():
            return path
    except FILE_IO_ERRORS:
        return None
    if not cos_temp_images_enabled():
        return None
    dest.mkdir(exist_ok=True)
    downloaded = await asyncio.to_thread(
        download_file,
        object_key,
        path,
        log_prefix="[TempImages/COS]",
    )
    if downloaded and path.is_file():
        logger.info("[TempImages] COS hydrate filename=%s", filename)
        return path
    return None


async def persist_dingtalk_temp_png(filename: str, data: bytes) -> Path:
    """Write the local working copy, then require the COS mirror when COS is on."""
    if not is_safe_dingtalk_temp_filename(filename):
        raise ValueError(f"Invalid dingtalk temp filename: {filename}")
    return await _persist_preview_png(
        filename,
        data,
        dingtalk_temp_cos_key(filename),
        require_cos=True,
    )


async def hydrate_dingtalk_temp_png(filename: str) -> Optional[Path]:
    """Return the local path, pulling from COS when the cache file is gone."""
    if not is_safe_dingtalk_temp_filename(filename):
        return None
    return await _hydrate_preview_png(filename, dingtalk_temp_cos_key(filename))


async def persist_diagram_preview_png(filename: str, data: bytes) -> Path:
    """Write a seminar canvas preview PNG locally and mirror it to COS."""
    if not is_safe_diagram_preview_filename(filename):
        raise ValueError(f"Invalid diagram preview filename: {filename}")
    return await _persist_preview_png(
        filename,
        data,
        diagram_preview_cos_key(filename),
        require_cos=True,
    )


def preview_png_safe_to_drop(filename: str, path: Path) -> bool:
    """True when a local preview PNG may be deleted.

    With COS off, the local file is the only copy and still ages out. With COS
    on, the file stays until the bucket holds it, so a seminar bubble can
    hydrate the image after this disk is gone.
    """
    if not cos_temp_images_enabled():
        return True
    if is_safe_dingtalk_temp_filename(filename):
        object_key = dingtalk_temp_cos_key(filename)
    elif is_safe_diagram_preview_filename(filename):
        object_key = diagram_preview_cos_key(filename)
    else:
        return True
    if object_exists(object_key):
        return True
    try:
        data = path.read_bytes()
    except OSError:
        return False
    uploaded = upload_bytes(
        data,
        object_key,
        log_prefix="[TempImages/COS]",
        content_type="image/png",
    )
    if uploaded:
        logger.info("[TempImages] COS mirror before cleanup filename=%s", filename)
        return True
    logger.warning("[TempImages] keeping %s; COS mirror failed", filename)
    return False


async def hydrate_diagram_preview_png(filename: str) -> Optional[Path]:
    """Return a seminar canvas preview PNG, pulling from COS when the cache is gone."""
    if not is_safe_diagram_preview_filename(filename):
        return None
    return await _hydrate_preview_png(filename, diagram_preview_cos_key(filename))
