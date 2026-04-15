"""Fast DingTalk callback validation (dedup, rate limit, circuit breaker) for MindBot."""

from __future__ import annotations

import dataclasses
import logging
import time
from typing import Any, Optional, Tuple

from config.database import AsyncSessionLocal
from config.settings import config
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.education.metrics import (
    conversation_user_turn_index,
    dingtalk_chat_scope,
)
from services.mindbot.core.redis_keys import (
    CONV_KEY_PREFIX,
    MSG_DEDUP_PREFIX,
    MSG_DEDUP_TTL,
)
from services.mindbot.platforms.dingtalk import (
    DingTalkInboundMessage,
    parse_inbound_message,
    verify_dingtalk_sign,
)
from services.mindbot.integrations.dingtalk.inbound_log import (
    debug_callback_failure_logging_enabled,
    dingtalk_inbound_logging_enabled,
)
from services.mindbot.errors import MindbotErrorCode, mindbot_error_headers
from services.mindbot.infra.circuit_breaker import check_circuit_breaker
from services.mindbot.infra.rate_limit import check_org_rate_limit
from services.mindbot.infra.redis_async import redis_setnx_ttl
from services.mindbot.telemetry.usage import persist_mindbot_usage_event

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MindbotPipelineContext:
    """Inputs for execute_mindbot_pipeline / run_pipeline_background."""

    cfg: OrganizationMindbotConfig
    body: dict[str, Any]
    timestamp_header: Optional[str]
    sign_header: Optional[str]
    debug_route_label: Optional[str]
    debug_raw_body: Optional[bytes]
    debug_request_headers: Optional[dict[str, str]]
    msg: DingTalkInboundMessage
    user_id: str
    conv_key: str


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
    from services.mindbot.integrations.dingtalk.inbound_log import (
        log_dingtalk_callback_failure_details,
    )

    log_dingtalk_callback_failure_details(
        route_label=debug_route_label or "?",
        headers=debug_request_headers or {},
        raw_body=debug_raw_body,
        parsed_body=body,
        reason=reason,
        extra=extra,
    )


def _hdr_for_cfg(
    cfg: OrganizationMindbotConfig,
    code: MindbotErrorCode,
) -> dict[str, str]:
    return mindbot_error_headers(
        code,
        organization_id=cfg.organization_id,
        robot_code=cfg.dingtalk_robot_code.strip(),
    )


async def validate_callback_fast(
    *,
    timestamp_header: Optional[str],
    sign_header: Optional[str],
    body: dict[str, Any],
    resolved_config: Optional[OrganizationMindbotConfig] = None,
    debug_route_label: Optional[str] = None,
    debug_raw_body: Optional[bytes] = None,
    debug_request_headers: Optional[dict[str, str]] = None,
) -> Tuple[bool, Optional[Tuple[int, dict[str, str]]], Optional[MindbotPipelineContext]]:
    """
    Fast validation: config, signature, dedup, parse, rate limit, circuit breaker.

    Returns (False, (status, headers), None) on early exit, else (True, None, ctx).
    """
    if not config.FEATURE_MINDBOT:
        return False, (404, mindbot_error_headers(MindbotErrorCode.FEATURE_DISABLED)), None

    ts_missing = not (timestamp_header or "").strip()
    sg_missing = not (sign_header or "").strip()
    if resolved_config is None and body == {} and ts_missing and sg_missing:
        logger.debug("[MindBot] shared_callback probe empty_body no_signature")
        return False, (200, mindbot_error_headers(MindbotErrorCode.OK)), None

    cfg = resolved_config
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
            "[MindBot] Path-based callback URL required (use /dingtalk/callback/t/<token> "
            "or /dingtalk/orgs/<organization_id>/callback); message delivery is not routed "
            "via the shared /dingtalk/callback URL.%s",
            _hint,
        )
        _log_callback_debug_failure(
            debug_route_label=debug_route_label,
            debug_raw_body=debug_raw_body,
            debug_request_headers=debug_request_headers,
            body=body,
            reason="path_callback_required",
            extra={},
        )
        return False, (404, mindbot_error_headers(MindbotErrorCode.PATH_CALLBACK_REQUIRED)), None
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
        return False, (
            404,
            mindbot_error_headers(
                MindbotErrorCode.CONFIG_NOT_FOUND,
                organization_id=cfg.organization_id,
                robot_code=cfg.dingtalk_robot_code.strip(),
            ),
        ), None

    if resolved_config is not None:
        rc_in_body = body.get("robotCode") or body.get("robot_code")
        if isinstance(rc_in_body, str) and rc_in_body.strip():
            if rc_in_body.strip() != cfg.dingtalk_robot_code.strip():
                logger.debug(
                    "[MindBot] body robotCode=%r differs from stored dingtalk_robot_code=%r "
                    "(ignored; inbound routing is path-based)",
                    rc_in_body.strip(),
                    cfg.dingtalk_robot_code.strip(),
                )
        if body == {} and ts_missing and sg_missing:
            logger.debug(
                "[MindBot] path_callback probe org_id=%s robot=%s",
                cfg.organization_id,
                cfg.dingtalk_robot_code.strip(),
            )
            return False, (200, _hdr_for_cfg(cfg, MindbotErrorCode.OK)), None

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
        return False, (401, _hdr_for_cfg(cfg, MindbotErrorCode.INVALID_SIGNATURE)), None

    msg_id = body.get("msgId") or body.get("msg_id")
    if msg_id and isinstance(msg_id, str):
        dedup_key = f"{MSG_DEDUP_PREFIX}{cfg.organization_id}:{msg_id}"
        first = await redis_setnx_ttl(dedup_key, "1", MSG_DEDUP_TTL)
        if first is False:
            return False, (200, _hdr_for_cfg(cfg, MindbotErrorCode.DUPLICATE_MESSAGE)), None

    msg = parse_inbound_message(body)
    text_in = msg.text_in
    inbound_msg_type = msg.inbound_msg_type
    logger.debug(
        "[MindBot] inbound msgtype=%s normalized=%s len=%s",
        body.get("msgtype"),
        inbound_msg_type,
        len(text_in),
    )
    if not text_in:
        return False, (200, _hdr_for_cfg(cfg, MindbotErrorCode.EMPTY_USER_MESSAGE)), None

    sender_staff = msg.sender_staff_id
    conversation_id_dt = msg.conversation_id

    user_id = f"mindbot_{cfg.organization_id}_{sender_staff}"
    conv_key = f"{CONV_KEY_PREFIX}{cfg.organization_id}:{conversation_id_dt}"

    if not await check_org_rate_limit(cfg.organization_id):
        return False, (200, _hdr_for_cfg(cfg, MindbotErrorCode.DUPLICATE_MESSAGE)), None

    cb_key = str(cfg.organization_id)
    if not check_circuit_breaker(cb_key):
        usage_started = time.monotonic()
        async with AsyncSessionLocal() as session:
            turn = await conversation_user_turn_index(cfg.organization_id, conversation_id_dt)
            await persist_mindbot_usage_event(
                session,
                cfg=cfg,
                body=body,
                text_in=text_in,
                conversation_id_dt=conversation_id_dt,
                user_id=user_id,
                streaming=False,
                error_code=MindbotErrorCode.DIFY_FAILED,
                reply_text="",
                dify_conversation_id=None,
                started_mono=usage_started,
                msg_id=msg.msg_id,
                usage=None,
                dingtalk_chat_scope=dingtalk_chat_scope(body),
                inbound_msg_type=inbound_msg_type,
                conversation_user_turn=turn,
            )
        return False, (200, _hdr_for_cfg(cfg, MindbotErrorCode.DIFY_FAILED)), None

    ctx = MindbotPipelineContext(
        cfg=cfg,
        body=body,
        timestamp_header=timestamp_header,
        sign_header=sign_header,
        debug_route_label=debug_route_label,
        debug_raw_body=debug_raw_body,
        debug_request_headers=debug_request_headers,
        msg=msg,
        user_id=user_id,
        conv_key=conv_key,
    )
    return True, None, ctx
