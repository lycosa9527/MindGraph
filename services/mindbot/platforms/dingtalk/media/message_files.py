"""Robot inbound file download (temporary URL + bytes)."""

from __future__ import annotations

import json
import logging
from typing import Optional

import aiohttp

from services.mindbot.infra.http_client import get_dingtalk_api_session, get_outbound_session
from services.mindbot.platforms.dingtalk.api.constants import (
    DING_API_BASE,
    MAX_DOWNLOAD_MEDIA_BYTES,
    PATH_ROBOT_MESSAGE_FILES_DOWNLOAD,
)
from services.mindbot.platforms.dingtalk.auth.oauth import get_access_token

logger = logging.getLogger(__name__)


async def get_message_file_download_url(
    access_token: str,
    robot_code: str,
    download_code: str,
) -> Optional[str]:
    """
    POST ``/v1.0/robot/messageFiles/download``.

    https://open.dingtalk.com/document/development/download-the-file-content-of-the-robot-receiving-message
    """
    if not download_code.strip() or not robot_code.strip():
        return None
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-acs-dingtalk-access-token": access_token.strip(),
    }
    payload = {"downloadCode": download_code.strip(), "robotCode": robot_code.strip()}
    timeout = aiohttp.ClientTimeout(total=60)
    try:
        session = get_dingtalk_api_session()
        async with session.post(
            f"{DING_API_BASE}{PATH_ROBOT_MESSAGE_FILES_DOWNLOAD}",
            headers=headers,
            json=payload,
            timeout=timeout,
        ) as resp:
            body_txt = await resp.text()
            if resp.status != 200:
                logger.warning(
                    "[MindBot] messageFiles/download failed: %s %s",
                    resp.status,
                    body_txt[:500],
                )
                return None
            try:
                data = json.loads(body_txt)
            except json.JSONDecodeError:
                return None
            url = data.get("downloadUrl") or ""
            if isinstance(data.get("data"), dict):
                url = url or data["data"].get("downloadUrl") or ""
            if isinstance(url, str) and url.strip():
                return url.strip()
            logger.warning(
                "[MindBot] messageFiles/download missing downloadUrl: %s",
                body_txt[:300],
            )
            return None
    except Exception as exc:
        logger.exception("[MindBot] messageFiles/download error: %s", exc)
        return None


async def download_url_bytes(url: str) -> Optional[bytes]:
    timeout = aiohttp.ClientTimeout(total=120)
    try:
        session = get_outbound_session()
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.warning("[MindBot] media GET failed: %s", resp.status)
                return None
            data = await resp.read()
            if len(data) > MAX_DOWNLOAD_MEDIA_BYTES:
                logger.warning(
                    "[MindBot] media too large: %s > %s",
                    len(data),
                    MAX_DOWNLOAD_MEDIA_BYTES,
                )
                return None
            return data
    except Exception as exc:
        logger.exception("[MindBot] media download error: %s", exc)
        return None


async def fetch_message_media_bytes(
    organization_id: int,
    app_key: str,
    app_secret: str,
    robot_code: str,
    download_code: str,
) -> Optional[bytes]:
    """Resolve OAuth token, get temporary URL, download bytes (capped)."""
    token = await get_access_token(organization_id, app_key, app_secret)
    if not token:
        return None
    dl_url = await get_message_file_download_url(token, robot_code, download_code)
    if not dl_url:
        return None
    return await download_url_bytes(dl_url)
