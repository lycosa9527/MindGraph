"""DingTalk outbound helpers for MindBot (OpenAPI send, session webhook POST)."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import aiohttp

from models.domain.mindbot_config import OrganizationMindbotConfig
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
        return (res is not None, False)
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
    return (res is not None, False)


async def post_session_webhook(
    session_webhook: str,
    answer: str,
    *,
    stream_chunk: bool = False,
) -> bool:
    out_payload = build_session_webhook_payload(answer, stream_chunk=stream_chunk)
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.post(
                session_webhook.strip(),
                data=json.dumps(out_payload),
                headers={"Content-Type": "application/json; charset=utf-8"},
            ) as r:
                if r.status >= 400:
                    body_txt = await r.text()
                    logger.warning(
                        "[MindBot] sessionWebhook POST failed: %s %s",
                        r.status,
                        body_txt[:500],
                    )
                    return False
    except Exception as exc:
        logger.exception("[MindBot] sessionWebhook request error: %s", exc)
        return False
    return True


async def send_one_reply_chunk(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    session_webhook_valid: Optional[str],
    chunk: str,
) -> tuple[bool, bool]:
    """Send one streaming segment: session webhook (text) then OpenAPI ``sampleText`` fallback."""
    if session_webhook_valid:
        if await post_session_webhook(session_webhook_valid, chunk, stream_chunk=True):
            return True, False
        return await reply_via_openapi(cfg, body, chunk, stream_chunk=True)
    return await reply_via_openapi(cfg, body, chunk, stream_chunk=True)
