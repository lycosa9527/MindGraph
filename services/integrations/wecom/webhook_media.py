"""WeCom webhook upload_media for file/voice messages (99110)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from services.integrations.wecom.config import build_webhook_upload_media_url
from services.integrations.wecom.profiles import WeComNotifyProfile
from services.integrations.wecom.webhook_constants import WEBHOOK_FILE_MAX_BYTES, WEBHOOK_VOICE_MAX_BYTES
from services.integrations.wecom.webhook_http import WECOM_HTTP_TIMEOUT_SECONDS, parse_wecom_response
from services.utils.error_types import HTTP_CLIENT_ERRORS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeComWebhookMediaUploadResult:
    """Result from webhook upload_media (99110)."""

    ok: bool
    media_id: str | None = None
    media_type: str | None = None
    errcode: int | None = None
    errmsg: str | None = None


def _media_size_limit(media_type: str) -> int:
    if media_type == "voice":
        return WEBHOOK_VOICE_MAX_BYTES
    return WEBHOOK_FILE_MAX_BYTES


async def upload_webhook_media(
    profile: WeComNotifyProfile,
    *,
    media_type: str,
    file_path: Path,
    filename: str | None = None,
) -> WeComWebhookMediaUploadResult:
    """Upload file/voice via webhook upload_media; returns media_id valid ~3 days."""
    if not profile.webhook_enabled or not profile.webhook_url:
        return WeComWebhookMediaUploadResult(ok=False, errmsg="webhook_not_configured")

    cleaned_type = media_type.strip().lower()
    if cleaned_type not in {"file", "voice"}:
        return WeComWebhookMediaUploadResult(ok=False, errmsg="invalid media_type")

    upload_url = build_webhook_upload_media_url(profile.webhook_url, cleaned_type)
    if upload_url is None:
        return WeComWebhookMediaUploadResult(ok=False, errmsg="invalid webhook url")

    data = file_path.read_bytes()
    if len(data) <= 5:
        return WeComWebhookMediaUploadResult(ok=False, errmsg="file too small (min 6 bytes per 99110)")
    if len(data) > _media_size_limit(cleaned_type):
        return WeComWebhookMediaUploadResult(ok=False, errmsg="file exceeds size limit")

    upload_name = filename.strip() if filename and filename.strip() else file_path.name
    files = {
        "media": (upload_name, data, "application/octet-stream"),
    }
    try:
        async with httpx.AsyncClient(timeout=WECOM_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(upload_url, files=files)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        logger.warning("[WeCom] upload_media HTTP error profile=%s: %s", profile.profile_id, exc)
        return WeComWebhookMediaUploadResult(ok=False, errmsg=str(exc))
    except HTTP_CLIENT_ERRORS as exc:
        logger.warning("[WeCom] upload_media failed profile=%s: %s", profile.profile_id, exc)
        return WeComWebhookMediaUploadResult(ok=False, errmsg=str(exc))

    if not isinstance(body, dict):
        return WeComWebhookMediaUploadResult(ok=False, errmsg="invalid response")

    ok, errcode, errmsg = parse_wecom_response(body)
    media_id_raw = body.get("media_id")
    media_id = media_id_raw.strip() if isinstance(media_id_raw, str) and media_id_raw.strip() else None
    type_raw = body.get("type")
    uploaded_type = str(type_raw) if type_raw is not None else cleaned_type
    return WeComWebhookMediaUploadResult(
        ok=ok and media_id is not None,
        media_id=media_id,
        media_type=uploaded_type,
        errcode=errcode,
        errmsg=errmsg,
    )
