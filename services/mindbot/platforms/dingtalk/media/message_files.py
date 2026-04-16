"""Robot inbound file download (temporary URL + bytes)."""

from __future__ import annotations

import json
import logging
import re
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

_SENSITIVE_FIELDS_RE = re.compile(
    r'(?i)("(?:accessToken|access_token|downloadUrl|download_url|appSecret|'
    r'appKey|token|secret|password|credential)")\s*:\s*"[^"]{4,}"',
)


def _sanitize_media_snippet(text: str, max_len: int = 400) -> str:
    """Redact token/URL fields from DingTalk API response bodies before logging."""
    snippet = text[:max_len]
    return _SENSITIVE_FIELDS_RE.sub(r'\1: "***"', snippet)


async def get_message_file_download_url(
    access_token: str,
    robot_code: str,
    download_code: str,
) -> Optional[str]:
    """
    POST ``/v1.0/robot/messageFiles/download``.

    https://open.dingtalk.com/document/development/download-the-file-content-of-the-robot-receiving-message
    """
    dl_code = (download_code or "").strip()
    r_code = (robot_code or "").strip()
    if not dl_code or not r_code:
        logger.debug(
            "[MindBot] messageFiles/download skipped: empty download_code=%r robot_code=%r",
            not dl_code,
            not r_code,
        )
        return None
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-acs-dingtalk-access-token": (access_token or "").strip(),
    }
    payload = {"downloadCode": dl_code, "robotCode": r_code}
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
                    _sanitize_media_snippet(body_txt),
                )
                return None
            try:
                data = json.loads(body_txt)
            except json.JSONDecodeError:
                logger.warning(
                    "[MindBot] messageFiles/download json_decode_error body_len=%s",
                    len(body_txt),
                )
                return None
            url = data.get("downloadUrl") or ""
            if isinstance(data.get("data"), dict):
                url = url or data["data"].get("downloadUrl") or ""
            if isinstance(url, str) and url.strip():
                return url.strip()
            logger.warning(
                "[MindBot] messageFiles/download missing downloadUrl: %s",
                _sanitize_media_snippet(body_txt),
            )
            return None
    except Exception as exc:
        logger.exception("[MindBot] messageFiles/download error: %s", exc)
        return None


async def download_url_bytes(url: str) -> Optional[bytes]:
    timeout = aiohttp.ClientTimeout(total=120)
    try:
        session = get_outbound_session()
        async with session.get(url, timeout=timeout, allow_redirects=False) as resp:
            if resp.status != 200:
                logger.warning("[MindBot] media GET failed: %s", resp.status)
                return None
            content_length_raw = resp.headers.get("Content-Length")
            if content_length_raw is not None:
                try:
                    content_length = int(content_length_raw)
                    if content_length > MAX_DOWNLOAD_MEDIA_BYTES:
                        logger.warning(
                            "[MindBot] media Content-Length too large: %s > %s",
                            content_length,
                            MAX_DOWNLOAD_MEDIA_BYTES,
                        )
                        return None
                except (ValueError, TypeError):
                    logger.debug(
                        "[MindBot] media Content-Length unparseable: %r (body size check still applies)",
                        content_length_raw,
                    )
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
