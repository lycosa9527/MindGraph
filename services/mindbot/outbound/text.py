"""DingTalk outbound helpers for MindBot (OpenAPI send, session webhook POST)."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import aiohttp

from services.mindbot.http_client import get_outbound_session
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.telemetry.pipeline_log import session_webhook_host
from utils.env_helpers import env_bool

from services.mindbot.platforms.dingtalk import (
    build_session_webhook_payload,
    get_access_token,
    openapi_robot_msg_param_for_answer,
    openapi_robot_msg_param_stream_chunk,
    send_group_robot_message,
    send_oto_robot_message,
)

logger = logging.getLogger(__name__)


def is_group_conversation(body: dict[str, Any]) -> bool:
    ct = body.get("conversationType") or body.get("conversation_type")
    if ct is None:
        return False
    s = str(ct).strip().lower()
    return s in ("2", "group")


async def reply_via_openapi(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    answer: str,
    *,
    stream_chunk: bool = False,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """
    Try OpenAPI send. Returns (success, token_failed).

    ``token_failed`` is True only when token acquisition failed (vs send failure).
    """
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return False, False
    if not env_bool("MINDBOT_FALLBACK_OPENAPI_SEND", True):
        return False, False
    app_key = (cfg.dingtalk_client_id or "").strip()
    if not app_key:
        return False, False
    token = await get_access_token(
        cfg.organization_id,
        app_key,
        cfg.dingtalk_app_secret.strip(),
    )
    if not token:
        logger.warning("[MindBot] OpenAPI fallback: no access token")
        return False, True
    robot_code = cfg.dingtalk_robot_code.strip()
    sender = body.get("senderStaffId") or body.get("sender_staff_id")
    sender_s = sender.strip() if isinstance(sender, str) else ""
    conv_id = body.get("conversationId") or body.get("conversation_id")
    conv_s = conv_id.strip() if isinstance(conv_id, str) else ""
    if stream_chunk:
        msg_key, msg_param = openapi_robot_msg_param_stream_chunk(answer)
    else:
        msg_key, msg_param = openapi_robot_msg_param_for_answer(answer)
    if is_group_conversation(body):
        if not conv_s:
            logger.warning("[MindBot] OpenAPI group fallback: missing conversationId")
            return (False, False)
        res = await send_group_robot_message(
            token,
            robot_code,
            conv_s,
            msg_key,
            msg_param,
        )
        ok = res is not None
        if ok:
            log_fn = logger.debug if stream_chunk else logger.info
            log_fn(
                "[MindBot] outbound_openapi %s chat=group chunk=%s answer_chars=%s",
                pipeline_ctx,
                stream_chunk,
                len(answer),
            )
        else:
            logger.warning(
                "[MindBot] outbound_openapi_failed %s chat=group",
                pipeline_ctx,
            )
        return (ok, False)
    if not sender_s:
        logger.warning("[MindBot] OpenAPI private fallback: missing senderStaffId")
        return False, False
    res = await send_oto_robot_message(
        token,
        robot_code,
        [sender_s],
        msg_key,
        msg_param,
    )
    ok = res is not None
    if ok:
        log_fn = logger.debug if stream_chunk else logger.info
        log_fn(
            "[MindBot] outbound_openapi %s chat=oto chunk=%s answer_chars=%s",
            pipeline_ctx,
            stream_chunk,
            len(answer),
        )
    else:
        logger.warning(
            "[MindBot] outbound_openapi_failed %s chat=oto",
            pipeline_ctx,
        )
    return (ok, False)


async def post_session_webhook(
    session_webhook: str,
    answer: str,
    *,
    stream_chunk: bool = False,
    pipeline_ctx: str = "",
) -> bool:
    out_payload = build_session_webhook_payload(answer, stream_chunk=stream_chunk)
    host = session_webhook_host(session_webhook)
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        http = get_outbound_session()
        async with http.post(
            session_webhook.strip(),
            data=json.dumps(out_payload),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=timeout,
        ) as r:
                if r.status >= 400:
                    body_txt = await r.text()
                    logger.warning(
                        "[MindBot] outbound_session_webhook_http %s host=%s status=%s body=%s",
                        pipeline_ctx,
                        host,
                        r.status,
                        body_txt[:500],
                    )
                    return False
    except Exception as exc:
        logger.exception(
            "[MindBot] outbound_session_webhook_error %s host=%s: %s",
            pipeline_ctx,
            host,
            exc,
        )
        return False
    payload_chars = len(json.dumps(out_payload, ensure_ascii=False))
    log_ok = logger.debug if stream_chunk else logger.info
    log_ok(
        "[MindBot] outbound_session_webhook_ok %s host=%s chunk=%s payload_chars=%s",
        pipeline_ctx,
        host,
        stream_chunk,
        payload_chars,
    )
    return True


async def send_one_reply_chunk(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    session_webhook_valid: Optional[str],
    chunk: str,
    *,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """Send one streaming segment: session webhook (text) then OpenAPI ``sampleText`` fallback."""
    logger.debug(
        "[MindBot] outbound_text_chunk %s chars=%s route=%s",
        pipeline_ctx,
        len(chunk),
        "session_webhook" if session_webhook_valid else "openapi_only",
    )
    if session_webhook_valid:
        if await post_session_webhook(
            session_webhook_valid,
            chunk,
            stream_chunk=True,
            pipeline_ctx=pipeline_ctx,
        ):
            return True, False
        return await reply_via_openapi(cfg, body, chunk, stream_chunk=True, pipeline_ctx=pipeline_ctx)
    return await reply_via_openapi(cfg, body, chunk, stream_chunk=True, pipeline_ctx=pipeline_ctx)
