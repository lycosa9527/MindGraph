"""Picture pre-flight: try DingTalk QR bind before Dify."""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.auth.dingtalk_bind_claim import claim_bind_token_for_staff
from services.auth.dingtalk_bind_redis import get_bind_token_consumed, get_bind_token_data
from services.mindbot.bind.messages import bind_reply_text
from services.mindbot.bind.qr_decode import decode_bind_token_from_image
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.outbound.text import send_full_reply
from services.mindbot.platforms.dingtalk import (
    extract_download_code_for_openapi,
    fetch_message_media_bytes,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

RecordUsageFn = Callable[..., Coroutine[Any, Any, None]]


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

    if not env_bool("MINDBOT_OPENAPI_ENABLED", True) or not env_bool("MINDBOT_FETCH_MEDIA", True):
        return None

    app_key = (cfg.dingtalk_client_id or "").strip()
    if not app_key:
        return None

    code = extract_download_code_for_openapi(body, inbound_msg_type)
    if not code:
        return None

    staff_id = (sender_staff_id or "").strip()
    if not staff_id:
        return None

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

    code_enum = MindbotErrorCode.BIND_INTERNAL
    if err_code == "MINDBOT_BIND_ORG_MISMATCH":
        code_enum = MindbotErrorCode.BIND_ORG_MISMATCH
    elif err_code == "MINDBOT_BIND_TOKEN_EXPIRED":
        code_enum = MindbotErrorCode.BIND_TOKEN_EXPIRED
    elif err_code == "MINDBOT_BIND_TOKEN_CONSUMED":
        code_enum = MindbotErrorCode.BIND_TOKEN_CONSUMED
    elif err_code == "MINDBOT_BIND_STAFF_TAKEN":
        code_enum = MindbotErrorCode.BIND_STAFF_TAKEN
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
    await send_full_reply(
        cfg,
        body,
        session_webhook_valid,
        reply,
        pipeline_ctx=pipeline_ctx,
        pinned_ip=session_webhook_pinned_ip,
    )
    await record_usage(
        outcome,
        reply_text=reply,
        dify_conversation_id=None,
        usage=None,
        streaming=False,
    )
    return 200, hdr_for_code(outcome)
