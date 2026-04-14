"""Legacy ``oapi.dingtalk.com/media/upload`` (multipart)."""

from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import quote

import aiohttp

from services.mindbot.http_client import get_outbound_session
from services.mindbot.platforms.dingtalk.constants import (
    OAPI_MAX_FILE_BYTES,
    OAPI_MAX_IMAGE_BYTES,
    OAPI_MAX_VIDEO_BYTES,
    OAPI_MAX_VOICE_BYTES,
    OAPI_MEDIA_UPLOAD,
)

logger = logging.getLogger(__name__)


def oapi_max_bytes_for_type(dingtalk_media_type: str) -> int:
    return {
        "image": OAPI_MAX_IMAGE_BYTES,
        "voice": OAPI_MAX_VOICE_BYTES,
        "video": OAPI_MAX_VIDEO_BYTES,
        "file": OAPI_MAX_FILE_BYTES,
    }.get(dingtalk_media_type.strip().lower(), 0)


async def upload_media_oapi(
    access_token: str,
    dingtalk_media_type: str,
    file_bytes: bytes,
    filename: str,
) -> Optional[str]:
    """
    POST ``https://oapi.dingtalk.com/media/upload?access_token=...&type=...``

    Form field ``media``. Returns ``media_id``.

    https://open.dingtalk.com/document/orgapp/upload-media-files
    """
    dmt = dingtalk_media_type.strip().lower()
    max_b = oapi_max_bytes_for_type(dmt)
    if max_b == 0:
        logger.warning("[MindBot] oapi media/upload invalid type: %s", dingtalk_media_type)
        return None
    if len(file_bytes) > max_b:
        logger.warning(
            "[MindBot] oapi media too large for type=%s: %s > %s",
            dmt,
            len(file_bytes),
            max_b,
        )
        return None

    tok = quote(access_token.strip(), safe="")
    typ = quote(dmt, safe="")
    url = f"{OAPI_MEDIA_UPLOAD}?access_token={tok}&type={typ}"
    data = aiohttp.FormData()
    data.add_field(
        "media",
        file_bytes,
        filename=filename or "upload.bin",
        content_type="application/octet-stream",
    )
    timeout = aiohttp.ClientTimeout(total=120)
    try:
        session = get_outbound_session()
        async with session.post(url, data=data, timeout=timeout) as resp:
                body_txt = await resp.text()
                if resp.status != 200:
                    logger.warning(
                        "[MindBot] oapi media/upload failed: %s %s",
                        resp.status,
                        body_txt[:500],
                    )
                    return None
                try:
                    payload = json.loads(body_txt)
                except json.JSONDecodeError:
                    logger.warning("[MindBot] oapi media/upload invalid JSON")
                    return None
                err = payload.get("errcode")
                if err is not None and err != 0:
                    logger.warning("[MindBot] oapi media/upload err: %s", body_txt[:500])
                    return None
                mid = payload.get("media_id")
                if isinstance(mid, str) and mid.strip():
                    return mid.strip()
                return None
    except Exception as exc:
        logger.exception("[MindBot] oapi media/upload error: %s", exc)
        return None
