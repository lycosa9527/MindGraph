"""Local cache + COS durable store for generate_dingtalk preview PNGs.

MindMate / DingTalk conversation history keeps ``/api/temp_images/dingtalk_*.png``
URLs. Local files still age out after 24h; COS is the copy that hydrate uses
when a user reopens the thread later.
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
    upload_bytes,
)

logger = logging.getLogger(__name__)

DINGTALK_TEMP_PNG_RE = re.compile(r"^dingtalk_[a-f0-9]{8}_\d+\.png$", re.IGNORECASE)
LOCAL_SIGNED_TTL_SECONDS = 86400
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMP_IMAGES_DIR = _PROJECT_ROOT / "temp_images"


def temp_images_dir() -> Path:
    """Directory for local generate_dingtalk preview PNGs."""
    return _TEMP_IMAGES_DIR


def is_safe_dingtalk_temp_filename(filename: str) -> bool:
    """True when filename is a generate_dingtalk preview PNG (no path)."""
    name = (filename or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return False
    return bool(DINGTALK_TEMP_PNG_RE.match(name))


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


async def persist_dingtalk_temp_png(filename: str, data: bytes) -> Path:
    """Write the local working copy, then mirror to COS when enabled."""
    if not is_safe_dingtalk_temp_filename(filename):
        raise ValueError(f"Invalid dingtalk temp filename: {filename}")
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
        dingtalk_temp_cos_key(filename),
        log_prefix="[TempImages/COS]",
        content_type="image/png",
    )
    if uploaded:
        logger.info("[TempImages] COS put filename=%s bytes=%s", filename, len(data))
    else:
        logger.warning(
            "[TempImages] COS upload failed filename=%s (local copy kept)",
            filename,
        )
    return path


async def hydrate_dingtalk_temp_png(filename: str) -> Optional[Path]:
    """Return the local path, pulling from COS when the cache file is gone."""
    if not is_safe_dingtalk_temp_filename(filename):
        return None
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
        dingtalk_temp_cos_key(filename),
        path,
        log_prefix="[TempImages/COS]",
    )
    if downloaded and path.is_file():
        logger.info("[TempImages] COS hydrate filename=%s", filename)
        return path
    return None
