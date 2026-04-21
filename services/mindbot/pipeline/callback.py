"""Process DingTalk HTTP robot callbacks: Dify reply (SSE streaming or blocking) + outbound."""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import time
from typing import Any, Optional

from clients.dify import AsyncDifyClient, DifyFile
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.core.conv_gate import (
    conv_gate_enabled,
    conv_gate_poll_total_ms,
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
from services.mindbot.pipeline.context import DifyReplyContext
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
from services.mindbot.telemetry.pipeline_log import format_pipeline_ctx, get_pipeline_logger
from services.mindbot.telemetry.usage import persist_mindbot_usage_event
from services.mindbot.session.webhook_url import validate_session_webhook_url
from services.mindbot.infra.redis_async import (
    redis_bind,
    redis_delete,
    redis_get,
    redis_ping,
)
from services.mindbot.pipeline.callback_validate import (
    MindbotPipelineContext,
    validate_callback_fast,
    hdr_for_cfg,
)
from services.mindbot.infra.task_registry import register as register_background_task
from utils.env_helpers import env_bool, env_float, env_int

logger = logging.getLogger(__name__)

# Per-org active-stream counters backing the dynamic per-org cap.
#
# The effective cap per org per worker is NOT static — it expands when the
# global active-stream pool has headroom and contracts to a safe base when the
# system is loaded.  This lets one school run a 20–50 teacher workshop without
# hitting a low hard limit while still preventing a single noisy school from
# starving all others during genuine overload.
#
# Env vars (streaming):
#   MINDBOT_ORG_MAX_CONCURRENT_STREAMING   base cap per org per worker (default 8)
#   MINDBOT_ORG_BURST_FREE_THRESHOLD       burst activates when ≥ this fraction of
#                                          MINDBOT_MAX_ACTIVE_STREAMING is free (default 0.5)
#   MINDBOT_ORG_BURST_SHARE                org may claim up to this fraction of free
#                                          slots in burst mode (default 0.4)
#   MINDBOT_ORG_ABSOLUTE_MAX_STREAMING     hard ceiling per org per worker, even at
#                                          100% pool free (default 40)
#
# Env vars (blocking path, same semantics):
#   MINDBOT_ORG_MAX_CONCURRENT_BLOCKING / _BURST_FREE_THRESHOLD_BLOCKING /
#   _BURST_SHARE_BLOCKING / _ABSOLUTE_MAX_BLOCKING
_org_active_streams: dict[int, int] = {}
_org_stream_lock = asyncio.Lock()

# Per-org active-blocking counters (same purpose for the blocking path).
_org_active_blocking: dict[int, int] = {}
_org_blocking_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Config readers — all @functools.cache so env parsing runs once per process.
# ---------------------------------------------------------------------------

@functools.cache
def _org_stream_warn_threshold() -> int:
    return max(1, env_int("MINDBOT_ORG_STREAM_WARN_THRESHOLD", 10))


@functools.cache
def _org_max_concurrent_streaming() -> int:
    return max(1, env_int("MINDBOT_ORG_MAX_CONCURRENT_STREAMING", 8))


@functools.cache
def _global_max_active_streaming() -> int:
    return max(1, env_int("MINDBOT_MAX_ACTIVE_STREAMING", 128))


@functools.cache
def _org_burst_free_threshold() -> float:
    return max(0.1, min(0.95, env_float("MINDBOT_ORG_BURST_FREE_THRESHOLD", 0.5)))


@functools.cache
def _org_burst_share() -> float:
    return max(0.1, min(0.9, env_float("MINDBOT_ORG_BURST_SHARE", 0.4)))


@functools.cache
def _org_absolute_max_streaming() -> int:
    return max(1, env_int("MINDBOT_ORG_ABSOLUTE_MAX_STREAMING", 40))


@functools.cache
def _org_max_concurrent_blocking() -> int:
    return max(1, env_int("MINDBOT_ORG_MAX_CONCURRENT_BLOCKING", 4))


@functools.cache
def _global_max_active_blocking() -> int:
    return max(1, env_int("MINDBOT_MAX_ACTIVE_BLOCKING", 128))


@functools.cache
def _org_burst_free_threshold_blocking() -> float:
    return max(0.1, min(0.95, env_float("MINDBOT_ORG_BURST_FREE_THRESHOLD_BLOCKING", 0.5)))


@functools.cache
def _org_burst_share_blocking() -> float:
    return max(0.1, min(0.9, env_float("MINDBOT_ORG_BURST_SHARE_BLOCKING", 0.4)))


@functools.cache
def _org_absolute_max_blocking() -> int:
    return max(1, env_int("MINDBOT_ORG_ABSOLUTE_MAX_BLOCKING", 16))


# ---------------------------------------------------------------------------
# Atomic per-org counters with dynamic cap computation.
# ---------------------------------------------------------------------------

async def _try_inc_org_stream(org_id: int) -> Optional[tuple[int, int]]:
    """Atomically compute dynamic cap and increment if under it.

    Returns ``(new_count, effective_cap)`` on success, ``None`` if rejected.

    The effective cap is computed entirely inside ``_org_stream_lock`` so the
    read-compute-write sequence is atomic within asyncio's single-threaded event
    loop (no other coroutine can interleave while we hold the lock).

    Burst mode: when ≥ MINDBOT_ORG_BURST_FREE_THRESHOLD of the global active
    pool is free the org may claim up to MINDBOT_ORG_BURST_SHARE of those free
    slots, bounded by MINDBOT_ORG_ABSOLUTE_MAX_STREAMING.  Example with defaults:
    50 idle teachers workshop → ~96% free → effective_cap = 40/worker →
    all 50 teachers served across 4 workers without throttling.
    """
    base = _org_max_concurrent_streaming()
    global_max = _global_max_active_streaming()
    threshold = _org_burst_free_threshold()
    share = _org_burst_share()
    absolute = _org_absolute_max_streaming()
    async with _org_stream_lock:
        total_active = sum(_org_active_streams.values())
        free = max(0, global_max - total_active)
        free_fraction = free / global_max
        if free_fraction >= threshold:
            burst_limit = int(free * share)
            effective_cap = max(base, min(burst_limit, absolute))
        else:
            effective_cap = base
        count = _org_active_streams.get(org_id, 0)
        if count >= effective_cap:
            return None
        count += 1
        _org_active_streams[org_id] = count
        return count, effective_cap


async def _dec_org_stream(org_id: int) -> None:
    async with _org_stream_lock:
        count = _org_active_streams.get(org_id, 1) - 1
        if count <= 0:
            _org_active_streams.pop(org_id, None)
        else:
            _org_active_streams[org_id] = count


async def _try_inc_org_blocking(org_id: int) -> Optional[tuple[int, int]]:
    """Atomically compute dynamic cap and increment if under it (blocking path).

    Same burst logic as ``_try_inc_org_stream`` using the blocking-specific
    config vars and ``_org_active_blocking`` dict.
    Returns ``(new_count, effective_cap)`` or ``None`` if rejected.
    """
    base = _org_max_concurrent_blocking()
    global_max = _global_max_active_blocking()
    threshold = _org_burst_free_threshold_blocking()
    share = _org_burst_share_blocking()
    absolute = _org_absolute_max_blocking()
    async with _org_blocking_lock:
        total_active = sum(_org_active_blocking.values())
        free = max(0, global_max - total_active)
        free_fraction = free / global_max
        if free_fraction >= threshold:
            burst_limit = int(free * share)
            effective_cap = max(base, min(burst_limit, absolute))
        else:
            effective_cap = base
        count = _org_active_blocking.get(org_id, 0)
        if count >= effective_cap:
            return None
        count += 1
        _org_active_blocking[org_id] = count
        return count, effective_cap


async def _dec_org_blocking(org_id: int) -> None:
    async with _org_blocking_lock:
        count = _org_active_blocking.get(org_id, 1) - 1
        if count <= 0:
            _org_active_blocking.pop(org_id, None)
        else:
            _org_active_blocking[org_id] = count


_STREAMING_SEMAPHORE = asyncio.Semaphore(max(1, env_int("MINDBOT_MAX_CONCURRENT_STREAMING", 64)))
# Tracks the number of streams that are **actively running** end-to-end (from first
# SSE event through to card finalization / reply send).  _STREAMING_SEMAPHORE is
# released as soon as the first SSE event arrives (to free the startup queue slot);
# _ACTIVE_STREAMS_SEMAPHORE is held for the full lifetime of the stream so total
# resource consumption (Dify connections, DingTalk API quota, Redis) remains bounded.
_ACTIVE_STREAMS_SEMAPHORE = asyncio.Semaphore(max(1, env_int("MINDBOT_MAX_ACTIVE_STREAMING", 128)))
# _BLOCKING_SEMAPHORE caps concurrent Dify blocking calls (the expensive, long-poll
# step).  _ACTIVE_BLOCKING_SEMAPHORE is held for the *full* blocking pipeline
# (Dify call + outbound send) so total in-flight blocking pipelines remain bounded,
# consistent with the two-level semaphore design used by the streaming path.
_BLOCKING_SEMAPHORE = asyncio.Semaphore(max(1, env_int("MINDBOT_MAX_CONCURRENT_BLOCKING", 64)))
_ACTIVE_BLOCKING_SEMAPHORE = asyncio.Semaphore(max(1, env_int("MINDBOT_MAX_ACTIVE_BLOCKING", 128)))


async def mindbot_concurrency_snapshot() -> dict[str, Any]:
    """
    In-process Dify↔DingTalk pipeline counts for the active uvicorn worker.

    ``active_dify_streaming`` is the number of Dify **SSE** streaming runs that
    passed the per-org cap (roughly, card stream conversations in progress).
    ``active_dify_blocking`` is the same for the **blocking** (one-shot Dify+send)
    path.  Per-worker: summed across orgs.  The admin API merges by **summing** these
    across all reporting workers.
    """
    try:
        async with _org_stream_lock:
            active_dify_streaming = int(sum(_org_active_streams.values()))
        async with _org_blocking_lock:
            active_dify_blocking = int(sum(_org_active_blocking.values()))
        return {
            "active_dify_streaming": active_dify_streaming,
            "active_dify_blocking": active_dify_blocking,
        }
    except (TypeError, ValueError, RuntimeError) as exc:
        return {"error": str(exc)}


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
    ctx: MindbotPipelineContext,
) -> tuple[int, dict[str, str]]:
    """Conv gate, Dify, outbound. Usage is persisted in its own DB session."""
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
    redis_ok = await redis_ping()
    gate_acquired = False
    if conv_gate_enabled() and redis_ok and conversation_id_dt.strip() and not dify_conv:
        gate_acquired = await redis_acquire_conv_gate_async(
            cfg.organization_id,
            conv_gate_scope,
            conv_key=conv_key,
        )
        if not gate_acquired:
            _poll_t0 = time.monotonic()
            polled = await poll_dify_conv_key_async(_redis_get_async, conv_key)
            if polled:
                dify_conv = polled
            else:
                logger.warning(
                    "[MindBot] conv_gate_poll_timeout org_id=%s scope=%s "
                    "elapsed_ms=%.0f budget_ms=%s "
                    "proceeding without existing Dify conversation (may create new session)",
                    cfg.organization_id,
                    conv_gate_scope,
                    (time.monotonic() - _poll_t0) * 1000,
                    conv_gate_poll_total_ms(),
                )

    raw_sw = msg.session_webhook
    session_webhook_valid: Optional[str] = None
    session_webhook_pinned_ip: str = ""
    if raw_sw:
        url_ok, url_reason, resolved_ip = await validate_session_webhook_url(raw_sw)
        if url_ok:
            session_webhook_valid = raw_sw
            session_webhook_pinned_ip = resolved_ip
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
    _pipeline_log = get_pipeline_logger(
        logger,
        org_id=cfg.organization_id,
        msg_id=msg_id_for_usage or "",
        robot_code=cfg.dingtalk_robot_code.strip(),
        streaming=_dify_streaming_enabled(),
    )
    _preview = text_in[:60].replace("\n", " ")
    _ellipsis = "…" if len(text_in) > 60 else ""
    _pipeline_log.info(
        "[MindBot] recv %s msgtype=%s q=%r chars=%s mode=%s sw=%s",
        pipeline_ctx,
        inbound_msg_type,
        _preview + _ellipsis,
        len(text_in),
        "streaming" if _dify_streaming_enabled() else "blocking",
        "yes" if session_webhook_valid else "no",
    )
    _pipeline_log.debug(
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
        return hdr_for_cfg(cfg, code)

    reply_ctx = DifyReplyContext(
        cfg=cfg,
        body=body,
        session_webhook_valid=session_webhook_valid,
        session_webhook_pinned_ip=session_webhook_pinned_ip,
        conversation_id_dt=conversation_id_dt,
        conv_key=conv_key,
        record_usage=_record_usage,
        hdr=_hdr,
        redis_bind_dify_conversation=_redis_bind_dify_conversation_async,
        pipeline_ctx=pipeline_ctx,
        msg_id=msg_id_for_usage or "",
    )

    cb_key = str(cfg.id)
    _streaming = _dify_streaming_enabled()

    try:
        if _streaming:
            slot_released = False

            def _release_streaming_slot() -> None:
                nonlocal slot_released
                if not slot_released:
                    slot_released = True
                    _STREAMING_SEMAPHORE.release()
                else:
                    logger.debug("[MindBot] streaming semaphore double-release prevented")

            stream_result = await _try_inc_org_stream(cfg.organization_id)
            if stream_result is None:
                logger.warning(
                    "[MindBot] org_stream_limit_exceeded org_id=%s — request rejected",
                    cfg.organization_id,
                )
                return 200, _hdr(MindbotErrorCode.ORG_CONCURRENCY_LIMIT)
            org_stream_count, effective_stream_cap = stream_result
            try:
                if effective_stream_cap > _org_max_concurrent_streaming():
                    logger.info(
                        "[MindBot] org_stream_burst_active org_id=%s active=%s "
                        "effective_cap=%s base_cap=%s",
                        cfg.organization_id,
                        org_stream_count,
                        effective_stream_cap,
                        _org_max_concurrent_streaming(),
                    )
                if org_stream_count >= _org_stream_warn_threshold():
                    logger.warning(
                        "[MindBot] org_stream_monopoly_suspected org_id=%s active_streams=%s "
                        "effective_cap=%s threshold=%s — one org may be consuming a large share "
                        "of the Dify connection pool",
                        cfg.organization_id,
                        org_stream_count,
                        effective_stream_cap,
                        _org_stream_warn_threshold(),
                    )
                await _ACTIVE_STREAMS_SEMAPHORE.acquire()
                try:
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
                            reply_ctx,
                            dify=dify,
                            text_in=text_in,
                            user_id=dify_user_id,
                            dify_conv=dify_conv,
                            files=files,
                            dify_inputs=dify_inputs,
                            stale_cb=stale_cb,
                            release_semaphore_slot=_release_streaming_slot,
                        )
                    finally:
                        _release_streaming_slot()
                finally:
                    _ACTIVE_STREAMS_SEMAPHORE.release()
            finally:
                await _dec_org_stream(cfg.organization_id)

            resp_hdr = result[1]
            if resp_hdr.get("X-MindBot-Error-Code") == MindbotErrorCode.DIFY_FAILED.value:
                await record_dify_failure(cb_key)
            else:
                await record_dify_success(cb_key)
            return result

        blocking_result = await _try_inc_org_blocking(cfg.organization_id)
        if blocking_result is None:
            logger.warning(
                "[MindBot] org_blocking_limit_exceeded org_id=%s — request rejected",
                cfg.organization_id,
            )
            return 200, _hdr(MindbotErrorCode.ORG_CONCURRENCY_LIMIT)
        org_blocking_count, effective_blocking_cap = blocking_result
        if effective_blocking_cap > _org_max_concurrent_blocking():
            logger.info(
                "[MindBot] org_blocking_burst_active org_id=%s active=%s "
                "effective_cap=%s base_cap=%s",
                cfg.organization_id,
                org_blocking_count,
                effective_blocking_cap,
                _org_max_concurrent_blocking(),
            )
        try:
            await _ACTIVE_BLOCKING_SEMAPHORE.acquire()
            try:
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
                        await record_dify_failure(cb_key)
                        await _record_usage(
                            MindbotErrorCode.DIFY_FAILED,
                            reply_text="",
                            dify_conversation_id=None,
                            usage=None,
                            streaming=False,
                        )
                        return 200, _hdr(MindbotErrorCode.DIFY_FAILED)
                    await record_dify_success(cb_key)

                    usage_block = parse_dify_usage_from_blocking_response(resp) if isinstance(resp, dict) else None

                return await run_blocking_send_branch(
                    reply_ctx,
                    resp=resp,
                    usage_block=usage_block,
                    raw_sw=raw_sw,
                )
            finally:
                _ACTIVE_BLOCKING_SEMAPHORE.release()
        finally:
            await _dec_org_blocking(cfg.organization_id)
    finally:
        if gate_acquired:
            await redis_release_conv_gate_async(
                cfg.organization_id,
                conv_gate_scope,
            )


async def run_pipeline_background(ctx: MindbotPipelineContext) -> None:
    """Fire-and-forget pipeline; usage events use their own DB sessions."""
    try:
        _code, headers = await execute_mindbot_pipeline(ctx)
        mindbot_metrics.record_from_headers(headers)
    except Exception as exc:
        logger.exception("[MindBot] run_pipeline_background failed: %s", exc)
        mindbot_metrics.record_error_code(MindbotErrorCode.PIPELINE_INTERNAL_ERROR.value)


async def process_dingtalk_callback(
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
            logger.error("[MindBot] validate_callback_fast returned ok=False with None early — invariant violated")
            return 500, mindbot_error_headers(MindbotErrorCode.PIPELINE_INTERNAL_ERROR)
        return early[0], early[1]
    if ctx is None:
        logger.error("[MindBot] validate_callback_fast returned ok=True with ctx=None — invariant violated")
        return 500, mindbot_error_headers(MindbotErrorCode.PIPELINE_INTERNAL_ERROR)
    return await execute_mindbot_pipeline(ctx)


def schedule_dingtalk_pipeline_background(ctx: MindbotPipelineContext) -> None:
    """Spawn background task and register for shutdown drain."""
    org_id = ctx.cfg.organization_id
    task = asyncio.create_task(
        run_pipeline_background(ctx),
        name=f"mindbot_pipeline:org_{org_id}",
    )
    register_background_task(task)
