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
from config.settings import config
from models.domain.mindbot_config import OrganizationMindbotConfig
from repositories.mindbot_repo import MindbotConfigRepository
from services.mindbot.core.conv_gate import (
    conv_gate_enabled,
    poll_dify_conv_key_async,
    redis_acquire_conv_gate_async,
    redis_release_conv_gate_async,
)
from services.mindbot.core.dify_reply import mindbot_dify_chat_blocking
from services.mindbot.dify_usage_parse import parse_dify_usage_from_blocking_response
from services.mindbot.mindbot_dify_paths import (
    run_blocking_send_branch,
    run_streaming_dify_branch,
)
from services.mindbot.education_metrics import (
    conversation_user_turn_index,
    dingtalk_chat_scope,
)
from services.mindbot.core.redis_keys import (
    CONV_KEY_PREFIX,
    MSG_DEDUP_PREFIX,
    MSG_DEDUP_TTL,
)
from services.mindbot.platforms.dingtalk import (
    extract_download_code_for_openapi,
    extract_inbound_prompt,
    fetch_message_media_bytes,
    media_filename_and_types,
    verify_dingtalk_sign,
)
from services.mindbot.dingtalk_inbound_log import (
    debug_callback_failure_logging_enabled,
    dingtalk_inbound_logging_enabled,
)
from services.mindbot.mindbot_errors import MindbotErrorCode, mindbot_error_headers
from services.mindbot.mindbot_usage import persist_mindbot_usage_event
from services.mindbot.session_webhook_url import validate_session_webhook_url
from services.redis.redis_client import RedisOperations, is_redis_available
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

_DEFAULT_SEMAPHORE = asyncio.Semaphore(int(os.getenv("MINDBOT_MAX_CONCURRENT", "64")))


def _log_callback_debug_failure(
    *,
    debug_route_label: Optional[str],
    debug_raw_body: Optional[bytes],
    debug_request_headers: Optional[dict[str, str]],
    body: dict[str, Any],
    reason: str,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Full request dump when MINDBOT_LOG_CALLBACK_DEBUG is on (default) and router passed raw bytes."""
    if debug_raw_body is None:
        return
    from services.mindbot.dingtalk_inbound_log import log_dingtalk_callback_failure_details

    log_dingtalk_callback_failure_details(
        route_label=debug_route_label or "?",
        headers=debug_request_headers or {},
        raw_body=debug_raw_body,
        parsed_body=body,
        reason=reason,
        extra=extra,
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


def _redis_get(key: str) -> Optional[str]:
    if not is_redis_available():
        return None
    return RedisOperations.get(key)


def _redis_set_ttl(key: str, value: str, ttl: int) -> bool:
    if not is_redis_available():
        return False
    return RedisOperations.set_with_ttl(key, value, ttl)


async def _redis_get_async(key: str) -> Optional[str]:
    return await asyncio.to_thread(_redis_get, key)


async def _redis_set_ttl_async(key: str, value: str, ttl: int) -> bool:
    return await asyncio.to_thread(_redis_set_ttl, key, value, ttl)


def _redis_delete(key: str) -> None:
    if not is_redis_available():
        return
    RedisOperations.delete(key)


async def _redis_delete_async(key: str) -> None:
    await asyncio.to_thread(_redis_delete, key)


async def _redis_bind_dify_conversation_async(key: str, value: str, ttl: int) -> None:
    """
    First successful writer wins: SET NX EX. If the key already exists, refresh TTL only.

    Avoids races where parallel callbacks overwrite each other's Dify ``conversation_id``.
    """
    if not is_redis_available():
        return
    created = await asyncio.to_thread(
        RedisOperations.set_with_ttl_if_not_exists,
        key,
        value,
        ttl,
    )
    if not created:
        await asyncio.to_thread(RedisOperations.set_ttl, key, ttl)


async def _maybe_dify_files_for_media(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    inbound_msg_type: str,
    user_id: str,
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
            user_id=user_id,
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


async def process_dingtalk_callback(
    session: AsyncSession,
    *,
    timestamp_header: Optional[str],
    sign_header: Optional[str],
    body: dict[str, Any],
    resolved_config: Optional[OrganizationMindbotConfig] = None,
    robot_code_override: Optional[str] = None,
    debug_route_label: Optional[str] = None,
    debug_raw_body: Optional[bytes] = None,
    debug_request_headers: Optional[dict[str, str]] = None,
) -> tuple[int, dict[str, str]]:
    """
    Handle one DingTalk callback.

    Returns (http_status, response_headers including X-MindBot-Error-Code).

    DingTalk may retry non-2xx; business failures after a valid receive often
    still use 200 to acknowledge delivery (see internal error code header).
    """
    if not config.FEATURE_MINDBOT:
        return 404, mindbot_error_headers(MindbotErrorCode.FEATURE_DISABLED)

    repo = MindbotConfigRepository(session)
    ts_missing = not (timestamp_header or "").strip()
    sg_missing = not (sign_header or "").strip()
    if resolved_config is None and body == {} and ts_missing and sg_missing:
        logger.info("[MindBot] shared callback URL connectivity probe (empty body, no signature)")
        return 200, mindbot_error_headers(MindbotErrorCode.OK)

    attempted_robot_code: Optional[str] = None
    cfg = resolved_config
    if cfg is None:
        rc = robot_code_override or body.get("robotCode") or body.get("robot_code")
        if not rc or not isinstance(rc, str):
            logger.warning("[MindBot] Missing robotCode in payload")
            _log_callback_debug_failure(
                debug_route_label=debug_route_label,
                debug_raw_body=debug_raw_body,
                debug_request_headers=debug_request_headers,
                body=body,
                reason="missing_robot_code",
                extra={"robot_code_override": robot_code_override},
            )
            return 400, mindbot_error_headers(MindbotErrorCode.MISSING_ROBOT_CODE)
        attempted_robot_code = rc.strip()
        cfg = await repo.get_by_robot_code(attempted_robot_code)
    if cfg is None:
        _hint = ""
        if not dingtalk_inbound_logging_enabled():
            _hint = (
                " MindBot callback logging is off (set MINDBOT_LOG_CALLBACK_INBOUND or "
                "INBOUND_FULL, or MINDBOT_LOG_CALLBACK_DEBUG; DEBUG defaults on unless "
                "MINDBOT_LOG_CALLBACK_DEBUG=0)."
            )
        elif not debug_callback_failure_logging_enabled():
            _hint = (
                " Failure dumps need MINDBOT_LOG_CALLBACK_DEBUG=1 (default on unless DEBUG=0)."
            )
        logger.warning(
            "[MindBot] No enabled MindBot config for robot_code=%r "
            "(no DB row with this dingtalk_robot_code and is_enabled=true, or code mismatch).%s",
            attempted_robot_code,
            _hint,
        )
        _log_callback_debug_failure(
            debug_route_label=debug_route_label,
            debug_raw_body=debug_raw_body,
            debug_request_headers=debug_request_headers,
            body=body,
            reason="config_not_found",
            extra={"attempted_robot_code": attempted_robot_code},
        )
        return 404, mindbot_error_headers(MindbotErrorCode.CONFIG_NOT_FOUND)
    if not cfg.is_enabled:
        logger.warning(
            "[MindBot] MindBot config is disabled organization_id=%s robot_code=%s",
            cfg.organization_id,
            cfg.dingtalk_robot_code.strip(),
        )
        _log_callback_debug_failure(
            debug_route_label=debug_route_label,
            debug_raw_body=debug_raw_body,
            debug_request_headers=debug_request_headers,
            body=body,
            reason="config_disabled",
            extra={
                "organization_id": cfg.organization_id,
                "robot_code": cfg.dingtalk_robot_code.strip(),
            },
        )
        return 404, mindbot_error_headers(
            MindbotErrorCode.CONFIG_NOT_FOUND,
            organization_id=cfg.organization_id,
            robot_code=cfg.dingtalk_robot_code.strip(),
        )

    def _hdr(code: MindbotErrorCode) -> dict[str, str]:
        return mindbot_error_headers(
            code,
            organization_id=cfg.organization_id,
            robot_code=cfg.dingtalk_robot_code.strip(),
        )

    if resolved_config is not None:
        rc_in_body = body.get("robotCode") or body.get("robot_code")
        if isinstance(rc_in_body, str) and rc_in_body.strip():
            if rc_in_body.strip() != cfg.dingtalk_robot_code.strip():
                logger.warning("[MindBot] robotCode does not match org-scoped callback config")
                _log_callback_debug_failure(
                    debug_route_label=debug_route_label,
                    debug_raw_body=debug_raw_body,
                    debug_request_headers=debug_request_headers,
                    body=body,
                    reason="robot_code_mismatch",
                    extra={
                        "organization_id": cfg.organization_id,
                        "expected_robot_code": cfg.dingtalk_robot_code.strip(),
                        "body_robot_code": rc_in_body.strip(),
                    },
                )
                return 400, _hdr(MindbotErrorCode.ROBOT_CODE_MISMATCH)

    if resolved_config is not None:
        if body == {} and ts_missing and sg_missing:
            logger.info(
                "[MindBot] callback connectivity probe org_id=%s robot=%s",
                cfg.organization_id,
                cfg.dingtalk_robot_code.strip(),
            )
            return 200, _hdr(MindbotErrorCode.OK)

    if not verify_dingtalk_sign(timestamp_header, sign_header, cfg.dingtalk_app_secret.strip()):
        logger.warning("[MindBot] Invalid DingTalk signature")
        _log_callback_debug_failure(
            debug_route_label=debug_route_label,
            debug_raw_body=debug_raw_body,
            debug_request_headers=debug_request_headers,
            body=body,
            reason="invalid_signature",
            extra={
                "organization_id": cfg.organization_id,
                "timestamp_header_present": bool((timestamp_header or "").strip()),
                "sign_header_present": bool((sign_header or "").strip()),
            },
        )
        return 401, _hdr(MindbotErrorCode.INVALID_SIGNATURE)

    msg_id = body.get("msgId") or body.get("msg_id")
    if msg_id and isinstance(msg_id, str):
        dedup_key = f"{MSG_DEDUP_PREFIX}{cfg.organization_id}:{msg_id}"
        if is_redis_available():
            first = await asyncio.to_thread(
                RedisOperations.set_with_ttl_if_not_exists,
                dedup_key,
                "1",
                MSG_DEDUP_TTL,
            )
            if not first:
                return 200, _hdr(MindbotErrorCode.DUPLICATE_MESSAGE)
        elif env_bool("MINDBOT_DEDUP_REQUIRE_REDIS", False):
            return 503, _hdr(MindbotErrorCode.REDIS_UNAVAILABLE_FOR_DEDUP)

    text_in, inbound_msg_type = extract_inbound_prompt(body)
    logger.debug(
        "[MindBot] inbound msgtype=%s normalized=%s len=%s",
        body.get("msgtype"),
        inbound_msg_type,
        len(text_in),
    )
    if not text_in:
        return 200, _hdr(MindbotErrorCode.EMPTY_USER_MESSAGE)

    logger.info(
        "[MindBot] callback org_id=%s robot=%s inbound_len=%s",
        cfg.organization_id,
        cfg.dingtalk_robot_code.strip(),
        len(text_in),
    )

    sender_staff = body.get("senderStaffId") or body.get("sender_staff_id") or "unknown"
    if not isinstance(sender_staff, str):
        sender_staff = str(sender_staff)
    conversation_id_dt = body.get("conversationId") or body.get("conversation_id") or ""
    if not isinstance(conversation_id_dt, str):
        conversation_id_dt = str(conversation_id_dt)

    user_id = f"mindbot_{cfg.organization_id}_{sender_staff}"
    conv_key = f"{CONV_KEY_PREFIX}{cfg.organization_id}:{conversation_id_dt}"
    dify_conv: Optional[str] = await _redis_get_async(conv_key)
    gate_acquired = False
    if (
        conv_gate_enabled()
        and is_redis_available()
        and conversation_id_dt.strip()
        and not dify_conv
    ):
        gate_acquired = await redis_acquire_conv_gate_async(
            cfg.organization_id,
            conversation_id_dt,
        )
        if not gate_acquired:
            polled = await poll_dify_conv_key_async(_redis_get_async, conv_key)
            if polled:
                dify_conv = polled

    raw_sw = body.get("sessionWebhook") or body.get("session_webhook")
    session_webhook_valid: Optional[str] = None
    if isinstance(raw_sw, str) and raw_sw.strip():
        url_ok, url_reason = await validate_session_webhook_url(raw_sw)
        if url_ok:
            session_webhook_valid = raw_sw.strip()
        else:
            logger.warning(
                "[MindBot] sessionWebhook URL rejected: %s (%s)",
                url_reason,
                raw_sw.strip()[:120],
            )

    dify = AsyncDifyClient(
        api_key=cfg.dify_api_key.strip(),
        api_url=cfg.dify_api_base_url.strip(),
        timeout=max(5, min(120, cfg.dify_timeout_seconds)),
    )

    usage_started = time.monotonic()
    mid_raw = body.get("msgId") or body.get("msg_id")
    msg_id_for_usage: Optional[str] = None
    if isinstance(mid_raw, str) and mid_raw.strip():
        msg_id_for_usage = mid_raw.strip()

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
            user_id=user_id,
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

    stale_cb = _on_stale_dify_conversation if is_redis_available() else None
    dify_inputs = _parse_dify_inputs_from_config(cfg)

    try:
        async with _DEFAULT_SEMAPHORE:
            files = await _maybe_dify_files_for_media(
                cfg,
                body,
                inbound_msg_type,
                user_id,
                dify,
            )
            if _dify_streaming_enabled():
                return await run_streaming_dify_branch(
                    cfg=cfg,
                    dify=dify,
                    text_in=text_in,
                    user_id=user_id,
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
                )

            resp = await mindbot_dify_chat_blocking(
                dify,
                text=text_in,
                user_id=user_id,
                conversation_id=dify_conv,
                files=files,
                inputs=dify_inputs,
                on_stale_conversation=stale_cb,
            )
            if resp is None:
                await _record_usage(
                    MindbotErrorCode.DIFY_FAILED,
                    reply_text="",
                    dify_conversation_id=None,
                    usage=None,
                    streaming=False,
                )
                return 200, _hdr(MindbotErrorCode.DIFY_FAILED)

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
        )
    finally:
        if gate_acquired:
            await redis_release_conv_gate_async(
                cfg.organization_id,
                conversation_id_dt,
            )
