"""Process DingTalk HTTP robot callbacks: Dify reply (SSE streaming or blocking) + outbound."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from clients.dify import AsyncDifyClient, DifyFile
from config.database import AsyncSessionLocal
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.core.conv_gate import (
    conv_gate_enabled,
    normalize_dify_conversation_id_from_redis,
    poll_dify_conv_key_async,
    redis_acquire_conv_gate_async,
    redis_release_conv_gate_async,
)
from services.mindbot.core.dify_reply import mindbot_dify_chat_blocking
from services.mindbot.infra.circuit_breaker import (
    record_dify_failure,
    record_dify_success,
)
from services.mindbot.dify.usage_parse import parse_dify_usage_from_blocking_response
from services.mindbot.education.metrics import (
    conversation_user_turn_index,
    dingtalk_chat_scope,
)
from services.mindbot.pipeline.dify_paths import (
    run_blocking_send_branch,
    run_streaming_dify_branch,
)
from services.mindbot.platforms.dingtalk import (
    extract_download_code_for_openapi,
    fetch_message_media_bytes,
    media_filename_and_types,
)
from services.mindbot.errors import MindbotErrorCode, mindbot_error_headers
from services.mindbot.telemetry.metrics import mindbot_metrics
from services.mindbot.telemetry.pipeline_log import format_pipeline_ctx
from services.mindbot.telemetry.usage import persist_mindbot_usage_event
from services.mindbot.session.webhook_url import validate_session_webhook_url
from services.mindbot.infra.redis_async import (
    redis_bind,
    redis_delete,
    redis_get,
)
from services.mindbot.pipeline.callback_validate import (
    MindbotPipelineContext,
    validate_callback_fast,
    _hdr_for_cfg,
)
from services.mindbot.infra.task_registry import register as register_background_task
from services.redis.redis_client import is_redis_available
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

_STREAMING_SEMAPHORE = asyncio.Semaphore(
    int(os.getenv("MINDBOT_MAX_CONCURRENT_STREAMING", "64"))
)
_BLOCKING_SEMAPHORE = asyncio.Semaphore(
    int(os.getenv("MINDBOT_MAX_CONCURRENT_BLOCKING", "64"))
)


def mindbot_accept_ack_headers(cfg: OrganizationMindbotConfig) -> dict[str, str]:
    """Headers returned immediately when the pipeline is accepted for background processing."""
    return mindbot_error_headers(
        MindbotErrorCode.ACCEPTED,
        organization_id=cfg.organization_id,
        robot_code=cfg.dingtalk_robot_code.strip(),
    )


def _parse_dify_inputs_from_config(
    cfg: OrganizationMindbotConfig,
) -> Optional[dict[str, Any]]:
    """Parse optional JSON object of Dify app ``inputs`` from org config."""
    raw = getattr(cfg, "dify_inputs_json", None)
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[MindBot] dify_inputs_json invalid JSON; ignoring")
        return None
    if not isinstance(parsed, dict):
        logger.warning("[MindBot] dify_inputs_json must be a JSON object; ignoring")
        return None
    return parsed


def _dify_streaming_enabled() -> bool:
    return env_bool("MINDBOT_DIFY_STREAMING", True)


async def _redis_get_async(key: str) -> Optional[str]:
    return await redis_get(key)


async def _redis_delete_async(key: str) -> None:
    await redis_delete(key)


async def _redis_bind_dify_conversation_async(key: str, value: str, ttl: int) -> None:
    """
    First successful writer wins: SET NX EX. If the key already exists, refresh TTL only.

    Uses a single Redis pipeline (SET NX + EXPIRE) — 1 RTT regardless of
    whether the key is new or existing.  Avoids races where parallel callbacks
    overwrite each other's Dify ``conversation_id``.
    """
    await redis_bind(key, value, ttl)


async def _maybe_dify_files_for_media(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    inbound_msg_type: str,
    dify_user_id: str,
    dify: AsyncDifyClient,
) -> list[DifyFile]:
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return []
    if not env_bool("MINDBOT_FETCH_MEDIA", True):
        return []
    if inbound_msg_type not in ("picture", "video", "audio", "file"):
        return []
    app_key = (cfg.dingtalk_client_id or "").strip()
    if not app_key:
        return []
    code = extract_download_code_for_openapi(body, inbound_msg_type)
    if not code:
        return []
    robot_code = cfg.dingtalk_robot_code.strip()
    try:
        raw = await fetch_message_media_bytes(
            cfg.organization_id,
            app_key,
            cfg.dingtalk_app_secret.strip(),
            robot_code,
            code,
        )
    except Exception as exc:
        logger.warning("[MindBot] OpenAPI media fetch failed: %s", exc)
        return []
    if not raw:
        logger.warning("[MindBot] OpenAPI media fetch returned empty bytes")
        return []
    fname, mime, dify_type = media_filename_and_types(inbound_msg_type, body)
    try:
        up = await dify.upload_file(
            dify_user_id,
            file_bytes=raw,
            filename=fname,
            content_type=mime,
        )
    except Exception as exc:
        logger.warning("[MindBot] Dify upload_file failed: %s", exc)
        return []
    file_id = up.get("id") if isinstance(up, dict) else None
    if not isinstance(file_id, str) or not file_id.strip():
        logger.warning("[MindBot] Dify upload missing file id")
        return []
    return [
        DifyFile(
            type=dify_type,
            transfer_method="local_file",
            upload_file_id=file_id.strip(),
        ),
    ]


async def execute_mindbot_pipeline(
    session: AsyncSession,
    ctx: MindbotPipelineContext,
) -> tuple[int, dict[str, str]]:
    """Conv gate, Dify, outbound. Caller supplies the async DB session."""
    cfg = ctx.cfg
    body = ctx.body
    msg = ctx.msg
    text_in = msg.text_in
    inbound_msg_type = msg.inbound_msg_type
    sender_staff = msg.sender_staff_id
    conversation_id_dt = msg.conversation_id
    dify_user_id = ctx.dify_user_id
    conv_key = ctx.conv_key
    conv_gate_scope = ctx.conv_gate_scope

    dify_conv: Optional[str] = normalize_dify_conversation_id_from_redis(
        await _redis_get_async(conv_key),
    )
    redis_ok = is_redis_available()
    gate_acquired = False
    if (
        conv_gate_enabled()
        and redis_ok
        and conversation_id_dt.strip()
        and not dify_conv
    ):
        gate_acquired = await redis_acquire_conv_gate_async(
            cfg.organization_id,
            conv_gate_scope,
            conv_key=conv_key,
        )
        if not gate_acquired:
            polled = await poll_dify_conv_key_async(_redis_get_async, conv_key)
            if polled:
                dify_conv = polled

    raw_sw = msg.session_webhook
    session_webhook_valid: Optional[str] = None
    if raw_sw:
        url_ok, url_reason = await validate_session_webhook_url(raw_sw)
        if url_ok:
            session_webhook_valid = raw_sw
        else:
            logger.warning(
                "[MindBot] sessionWebhook URL rejected: %s (%s)",
                url_reason,
                raw_sw[:120],
            )

    dify = AsyncDifyClient(
        api_key=cfg.dify_api_key.strip(),
        api_url=cfg.dify_api_base_url.strip(),
        timeout=max(5, min(600, cfg.dify_timeout_seconds)),
    )

    usage_started = time.monotonic()
    msg_id_for_usage = msg.msg_id
    sender_nick = msg.sender_nick or ""
    chat_type = msg.chat_type
    pipeline_ctx = format_pipeline_ctx(
        cfg.organization_id,
        cfg.dingtalk_robot_code.strip(),
        msg_id=msg_id_for_usage or "",
        staff_id=sender_staff,
        nick=sender_nick,
        chat_type=chat_type,
        conv_dingtalk=conversation_id_dt,
        dify_conv=dify_conv or "",
    )
    _preview = text_in[:60].replace("\n", " ")
    _ellipsis = "…" if len(text_in) > 60 else ""
    logger.info(
        "[MindBot] recv %s msgtype=%s q=%r chars=%s mode=%s sw=%s",
        pipeline_ctx,
        inbound_msg_type,
        _preview + _ellipsis,
        len(text_in),
        "streaming" if _dify_streaming_enabled() else "blocking",
        "yes" if session_webhook_valid else "no",
    )
    logger.debug(
        "[MindBot] pipeline_detail %s gate_acquired=%s redis_dify_conv=%s",
        pipeline_ctx,
        gate_acquired,
        bool(dify_conv),
    )

    async def _record_usage(
        outcome: MindbotErrorCode,
        *,
        reply_text: str,
        dify_conversation_id: Optional[str],
        usage: Optional[dict[str, int]],
        streaming: bool,
    ) -> None:
        turn = await conversation_user_turn_index(
            cfg.organization_id,
            conversation_id_dt,
        )
        await persist_mindbot_usage_event(
            session,
            cfg=cfg,
            body=body,
            text_in=text_in,
            conversation_id_dt=conversation_id_dt,
            user_id=dify_user_id,
            streaming=streaming,
            error_code=outcome,
            reply_text=reply_text,
            dify_conversation_id=dify_conversation_id,
            started_mono=usage_started,
            msg_id=msg_id_for_usage,
            usage=usage,
            dingtalk_chat_scope=dingtalk_chat_scope(body),
            inbound_msg_type=inbound_msg_type,
            conversation_user_turn=turn,
        )

    async def _on_stale_dify_conversation() -> None:
        await _redis_delete_async(conv_key)

    stale_cb = _on_stale_dify_conversation if redis_ok else None
    dify_inputs = _parse_dify_inputs_from_config(cfg)

    def _hdr(code: MindbotErrorCode) -> dict[str, str]:
        return _hdr_for_cfg(cfg, code)

    cb_key = str(cfg.organization_id)
    _streaming = _dify_streaming_enabled()

    try:
        if _streaming:
            slot_released = False

            def _release_streaming_slot() -> None:
                nonlocal slot_released
                if not slot_released:
                    slot_released = True
                    _STREAMING_SEMAPHORE.release()

            await _STREAMING_SEMAPHORE.acquire()
            try:
                files = await _maybe_dify_files_for_media(
                    cfg,
                    body,
                    inbound_msg_type,
                    dify_user_id,
                    dify,
                )
                result = await run_streaming_dify_branch(
                    cfg=cfg,
                    dify=dify,
                    text_in=text_in,
                    user_id=dify_user_id,
                    dify_conv=dify_conv,
                    files=files,
                    body=body,
                    session_webhook_valid=session_webhook_valid,
                    conversation_id_dt=conversation_id_dt,
                    conv_key=conv_key,
                    dify_inputs=dify_inputs,
                    stale_cb=stale_cb,
                    record_usage=_record_usage,
                    hdr=_hdr,
                    redis_bind_dify_conversation=_redis_bind_dify_conversation_async,
                    pipeline_ctx=pipeline_ctx,
                    release_semaphore_slot=_release_streaming_slot,
                )
            finally:
                _release_streaming_slot()

            resp_hdr = result[1]
            if resp_hdr.get("X-MindBot-Error-Code") == MindbotErrorCode.DIFY_FAILED.value:
                record_dify_failure(cb_key)
            else:
                record_dify_success(cb_key)
            return result

        async with _BLOCKING_SEMAPHORE:
            files = await _maybe_dify_files_for_media(
                cfg,
                body,
                inbound_msg_type,
                dify_user_id,
                dify,
            )
            resp = await mindbot_dify_chat_blocking(
                dify,
                text=text_in,
                user_id=dify_user_id,
                conversation_id=dify_conv,
                files=files,
                inputs=dify_inputs,
                on_stale_conversation=stale_cb,
                pipeline_ctx=pipeline_ctx,
            )
            if resp is None:
                record_dify_failure(cb_key)
                await _record_usage(
                    MindbotErrorCode.DIFY_FAILED,
                    reply_text="",
                    dify_conversation_id=None,
                    usage=None,
                    streaming=False,
                )
                return 200, _hdr(MindbotErrorCode.DIFY_FAILED)
            record_dify_success(cb_key)

            usage_block = (
                parse_dify_usage_from_blocking_response(resp)
                if isinstance(resp, dict)
                else None
            )

        return await run_blocking_send_branch(
            cfg=cfg,
            body=body,
            resp=resp,
            usage_block=usage_block,
            raw_sw=raw_sw,
            session_webhook_valid=session_webhook_valid,
            conversation_id_dt=conversation_id_dt,
            conv_key=conv_key,
            record_usage=_record_usage,
            hdr=_hdr,
            redis_bind_dify_conversation=_redis_bind_dify_conversation_async,
            pipeline_ctx=pipeline_ctx,
        )
    finally:
        if gate_acquired:
            await redis_release_conv_gate_async(
                cfg.organization_id,
                conv_gate_scope,
            )


async def run_pipeline_background(ctx: MindbotPipelineContext) -> None:
    """Fire-and-forget pipeline with its own DB session; records final metrics."""
    try:
        async with AsyncSessionLocal() as session:
            _code, headers = await execute_mindbot_pipeline(session, ctx)
        mindbot_metrics.record_from_headers(headers)
    except Exception as exc:
        logger.exception("[MindBot] run_pipeline_background failed: %s", exc)
        mindbot_metrics.record_error_code(MindbotErrorCode.PIPELINE_INTERNAL_ERROR.value)


async def process_dingtalk_callback(
    session: AsyncSession,
    *,
    timestamp_header: Optional[str],
    sign_header: Optional[str],
    body: dict[str, Any],
    resolved_config: Optional[OrganizationMindbotConfig] = None,
    debug_route_label: Optional[str] = None,
    debug_raw_body: Optional[bytes] = None,
    debug_request_headers: Optional[dict[str, str]] = None,
) -> tuple[int, dict[str, str]]:
    """
    Handle one DingTalk callback (full request scope: shared URL / tests).

    Returns (http_status, response_headers including X-MindBot-Error-Code).
    """
    ok, early, ctx = await validate_callback_fast(
        timestamp_header=timestamp_header,
        sign_header=sign_header,
        body=body,
        resolved_config=resolved_config,
        debug_route_label=debug_route_label,
        debug_raw_body=debug_raw_body,
        debug_request_headers=debug_request_headers,
    )
    if not ok:
        if early is None:
            return 500, mindbot_error_headers(MindbotErrorCode.DIFY_FAILED)
        return early[0], early[1]
    if ctx is None:
        return 500, mindbot_error_headers(MindbotErrorCode.DIFY_FAILED)
    return await execute_mindbot_pipeline(session, ctx)


def schedule_dingtalk_pipeline_background(ctx: MindbotPipelineContext) -> None:
    """Spawn background task and register for shutdown drain."""
    org_id = ctx.cfg.organization_id
    task = asyncio.create_task(
        run_pipeline_background(ctx),
        name=f"mindbot_pipeline:org_{org_id}",
    )
    register_background_task(task)
