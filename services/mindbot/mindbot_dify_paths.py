"""Dify streaming vs blocking reply paths for MindBot (split from callback orchestrator)."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

from clients.dify import AsyncDifyClient, DifyFile
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.core.dify_stream import (
    mindbot_consume_dify_stream_batched,
    mindbot_stream_batch_params,
)
from services.mindbot.core.redis_keys import CONV_KEY_TTL_SECONDS
from services.mindbot.mindbot_errors import MindbotErrorCode
from services.mindbot.mindbot_outbound import (
    post_session_webhook,
    reply_via_openapi,
    send_one_reply_chunk,
)
from utils.env_helpers import env_bool


async def run_streaming_dify_branch(
    *,
    cfg: OrganizationMindbotConfig,
    dify: AsyncDifyClient,
    text_in: str,
    user_id: str,
    dify_conv: Optional[str],
    files: list[DifyFile],
    body: dict[str, Any],
    session_webhook_valid: Optional[str],
    conversation_id_dt: str,
    conv_key: str,
    dify_inputs: Optional[dict[str, Any]],
    stale_cb: Optional[Callable[[], Awaitable[None]]],
    record_usage: Callable[..., Awaitable[None]],
    hdr: Callable[[MindbotErrorCode], dict[str, str]],
    redis_bind_dify_conversation: Callable[..., Awaitable[None]],
) -> tuple[int, dict[str, str]]:
    """Consume Dify SSE, send batched chunks to DingTalk, record usage."""
    min_c, flush_s, max_p = mindbot_stream_batch_params()

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        return await send_one_reply_chunk(
            cfg,
            body,
            session_webhook_valid,
            chunk,
        )

    full, new_conv, err_tok, usage_dify = await mindbot_consume_dify_stream_batched(
        dify,
        text=text_in,
        user_id=user_id,
        conversation_id=dify_conv,
        files=files,
        min_chars=min_c,
        flush_interval_s=flush_s,
        max_parts=max_p,
        on_batch=on_batch,
        inputs=dify_inputs,
        on_stale_conversation=stale_cb,
    )
    reply_text = full if isinstance(full, str) else ""
    if err_tok == "dify_error":
        await record_usage(
            MindbotErrorCode.DIFY_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.DIFY_FAILED)
    if err_tok == "dify_empty":
        await record_usage(
            MindbotErrorCode.DIFY_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.DIFY_FAILED)
    if err_tok == "token_failed":
        await record_usage(
            MindbotErrorCode.DINGTALK_TOKEN_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)
    if err_tok == "send_failed":
        await record_usage(
            MindbotErrorCode.SESSION_WEBHOOK_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.SESSION_WEBHOOK_FAILED)
    if isinstance(new_conv, str) and new_conv and conversation_id_dt:
        await redis_bind_dify_conversation(
            conv_key,
            new_conv,
            CONV_KEY_TTL_SECONDS,
        )
    await record_usage(
        MindbotErrorCode.OK,
        reply_text=reply_text,
        dify_conversation_id=new_conv,
        usage=usage_dify,
        streaming=True,
    )
    return 200, hdr(MindbotErrorCode.OK)


async def run_blocking_send_branch(
    *,
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    resp: dict[str, Any],
    usage_block: Optional[dict[str, int]],
    raw_sw: Any,
    session_webhook_valid: Optional[str],
    conversation_id_dt: str,
    conv_key: str,
    record_usage: Callable[..., Awaitable[None]],
    hdr: Callable[[MindbotErrorCode], dict[str, str]],
    redis_bind_dify_conversation: Callable[..., Awaitable[None]],
) -> tuple[int, dict[str, str]]:
    """Send blocking Dify answer to DingTalk (session webhook and/or OpenAPI)."""
    answer = (resp or {}).get("answer", "")
    if not isinstance(answer, str):
        answer = str(answer)
    new_conv = (resp or {}).get("conversation_id")
    dify_cid_block: Optional[str] = None
    if isinstance(new_conv, str) and new_conv.strip():
        dify_cid_block = new_conv.strip()
    if isinstance(new_conv, str) and new_conv and conversation_id_dt:
        await redis_bind_dify_conversation(
            conv_key,
            new_conv,
            CONV_KEY_TTL_SECONDS,
        )

    if isinstance(raw_sw, str) and raw_sw.strip():
        if not session_webhook_valid:
            openapi_ok, token_failed = await reply_via_openapi(cfg, body, answer)
            if openapi_ok:
                await record_usage(
                    MindbotErrorCode.OK,
                    reply_text=answer,
                    dify_conversation_id=dify_cid_block,
                    usage=usage_block,
                    streaming=False,
                )
                return 200, hdr(MindbotErrorCode.OK)
            if token_failed:
                await record_usage(
                    MindbotErrorCode.DINGTALK_TOKEN_FAILED,
                    reply_text=answer,
                    dify_conversation_id=dify_cid_block,
                    usage=usage_block,
                    streaming=False,
                )
                return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)
            await record_usage(
                MindbotErrorCode.SESSION_WEBHOOK_INVALID_URL,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.SESSION_WEBHOOK_INVALID_URL)

        if await post_session_webhook(session_webhook_valid, answer):
            await record_usage(
                MindbotErrorCode.OK,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.OK)
        openapi_ok, token_failed = await reply_via_openapi(cfg, body, answer)
        if openapi_ok:
            await record_usage(
                MindbotErrorCode.OK,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.OK)
        if token_failed:
            await record_usage(
                MindbotErrorCode.DINGTALK_TOKEN_FAILED,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)
        await record_usage(
            MindbotErrorCode.SESSION_WEBHOOK_FAILED,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.SESSION_WEBHOOK_FAILED)

    openapi_ok, token_failed = await reply_via_openapi(cfg, body, answer)
    if openapi_ok:
        await record_usage(
            MindbotErrorCode.OK,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.OK)

    can_fallback = (
        env_bool("MINDBOT_OPENAPI_ENABLED", True)
        and env_bool("MINDBOT_FALLBACK_OPENAPI_SEND", True)
        and bool((cfg.dingtalk_client_id or "").strip())
    )
    if not can_fallback:
        logger.warning(
            "[MindBot] Missing sessionWebhook; OpenAPI fallback not configured",
        )
        await record_usage(
            MindbotErrorCode.MISSING_SESSION_WEBHOOK,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.MISSING_SESSION_WEBHOOK)

    if token_failed:
        await record_usage(
            MindbotErrorCode.DINGTALK_TOKEN_FAILED,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)

    logger.warning("[MindBot] Missing sessionWebhook; OpenAPI fallback send failed")
    await record_usage(
        MindbotErrorCode.DINGTALK_OPENAPI_REPLY_FAILED,
        reply_text=answer,
        dify_conversation_id=dify_cid_block,
        usage=usage_block,
        streaming=False,
    )
    return 200, hdr(MindbotErrorCode.DINGTALK_OPENAPI_REPLY_FAILED)
