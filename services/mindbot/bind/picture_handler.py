"""Picture pre-flight: try DingTalk QR bind before Dify."""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.auth.dingtalk_bind_claim import claim_bind_token_for_staff
from services.auth.dingtalk_bind_redis import get_bind_token_consumed, get_bind_token_data
from services.mindbot.bind.messages import bind_reply_text, mindbot_code_from_claim_error
from services.mindbot.bind.qr_backend import pyzbar_backend_ready
from services.mindbot.bind.qr_decode import decode_bind_token_from_image
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.outbound.text import send_full_reply
from services.mindbot.platforms.dingtalk.inbound.parser import extract_download_code_candidates
from services.mindbot.platforms.dingtalk.media.message_files import fetch_message_media_bytes
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

RecordUsageFn = Callable[..., Coroutine[Any, Any, None]]

_INVALID_BIND_STAFF_IDS = frozenset({"", "unknown"})


def _is_valid_bind_staff_id(staff_id: str) -> bool:
    """Reject placeholder staff ids from DingTalk callbacks."""
    normalized = (staff_id or "").strip().lower()
    return bool(normalized) and normalized not in _INVALID_BIND_STAFF_IDS


def _bind_media_infra_ready(cfg: OrganizationMindbotConfig) -> bool:
    """True when OpenAPI media download and Client ID are configured for bind."""
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return False
    if not env_bool("MINDBOT_FETCH_MEDIA", True):
        return False
    return bool((cfg.dingtalk_client_id or "").strip())


async def try_handle_bind_picture(
    *,
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    inbound_msg_type: str,
    sender_staff_id: str,
    session_webhook_valid: Optional[str],
    session_webhook_pinned_ip: str,
    pipeline_ctx: str,
    record_usage: RecordUsageFn,
    hdr_for_code: Callable[[MindbotErrorCode], dict[str, str]],
) -> Optional[tuple[int, dict[str, str]]]:
    """
    Handle bind QR picture messages.

    Returns HTTP status + headers when handled (skip Dify), or None to continue pipeline.
    """
    if inbound_msg_type != "picture":
        return None

    codes = extract_download_code_candidates(body, inbound_msg_type)
    if not codes:
        return None

    staff_id = (sender_staff_id or "").strip()
    if not _is_valid_bind_staff_id(staff_id):
        logger.warning(
            "[MindBot] bind_attempt rejected invalid staff=%r org=%s %s",
            staff_id[:20] if staff_id else staff_id,
            cfg.organization_id,
            pipeline_ctx,
        )
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_INVALID_STAFF,
        )

    if not _bind_media_infra_ready(cfg):
        logger.warning(
            "[MindBot] bind_unavailable openapi_or_client_id org=%s %s",
            cfg.organization_id,
            pipeline_ctx,
        )
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_UNAVAILABLE,
        )

    if not pyzbar_backend_ready():
        logger.warning(
            "[MindBot] bind_unavailable pyzbar org=%s %s",
            cfg.organization_id,
            pipeline_ctx,
        )
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_UNAVAILABLE,
        )

    app_key = (cfg.dingtalk_client_id or "").strip()
    code = codes[0]
    alt_codes = tuple(codes[1:])

    logger.info(
        "[MindBot] bind_attempt staff=%s org=%s msgtype=picture %s",
        staff_id[:20],
        cfg.organization_id,
        pipeline_ctx,
    )

    try:
        raw = await fetch_message_media_bytes(
            cfg.organization_id,
            app_key,
            cfg.dingtalk_app_secret.strip(),
            cfg.dingtalk_robot_code.strip(),
            code,
            alternate_download_codes=alt_codes,
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[MindBot] bind media fetch failed: %s", exc)
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_IMAGE_UNREADABLE,
        )

    if not raw:
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_IMAGE_UNREADABLE,
        )

    token, bind_code, is_bind_attempt = decode_bind_token_from_image(raw)
    if not is_bind_attempt:
        return None

    if not token or not bind_code:
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_TOKEN_EXPIRED,
        )

    if await get_bind_token_consumed(token):
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_TOKEN_CONSUMED,
        )

    token_data = await get_bind_token_data(token)
    if token_data is None:
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_TOKEN_EXPIRED,
        )

    raw_org = token_data.get("organization_id")
    if isinstance(raw_org, int):
        token_org_id = raw_org
    elif isinstance(raw_org, str) and raw_org.isdigit():
        token_org_id = int(raw_org)
    else:
        token_org_id = None
    if token_org_id is not None and token_org_id != int(cfg.organization_id):
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_ORG_MISMATCH,
        )

    ok, err_code = await claim_bind_token_for_staff(
        token=token,
        bind_code=bind_code,
        organization_id=int(cfg.organization_id),
        dingtalk_staff_id=staff_id,
    )
    if ok:
        logger.info(
            "[MindBot] bind_ok staff=%s org=%s %s",
            staff_id[:20],
            cfg.organization_id,
            pipeline_ctx,
        )
        return await _finish_bind(
            cfg,
            body,
            session_webhook_valid,
            session_webhook_pinned_ip,
            pipeline_ctx,
            record_usage,
            hdr_for_code,
            MindbotErrorCode.BIND_OK,
        )

    code_enum = mindbot_code_from_claim_error(err_code)
    logger.info(
        "[MindBot] bind_fail code=%s staff=%s org=%s %s",
        code_enum.value,
        staff_id[:20],
        cfg.organization_id,
        pipeline_ctx,
    )
    return await _finish_bind(
        cfg,
        body,
        session_webhook_valid,
        session_webhook_pinned_ip,
        pipeline_ctx,
        record_usage,
        hdr_for_code,
        code_enum,
    )


async def _finish_bind(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    session_webhook_valid: Optional[str],
    session_webhook_pinned_ip: str,
    pipeline_ctx: str,
    record_usage: RecordUsageFn,
    hdr_for_code: Callable[[MindbotErrorCode], dict[str, str]],
    outcome: MindbotErrorCode,
) -> tuple[int, dict[str, str]]:
    reply = bind_reply_text(outcome)
    sent_ok, token_failed = await send_full_reply(
        cfg,
        body,
        session_webhook_valid,
        reply,
        pipeline_ctx=pipeline_ctx,
        pinned_ip=session_webhook_pinned_ip,
    )
    if not sent_ok:
        logger.warning(
            "[MindBot] bind_reply_delivery_failed code=%s token_failed=%s %s",
            outcome.value,
            token_failed,
            pipeline_ctx,
        )
    await record_usage(
        outcome,
        reply_text=reply,
        dify_conversation_id=None,
        usage=None,
        streaming=False,
    )
    return 200, hdr_for_code(outcome)
