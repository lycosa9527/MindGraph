"""
Cross-worker Kitty / voice coordination via Redis pub/sub.

When multiple Uvicorn workers run, ``voice_sessions`` and ``active_websockets``
are process-local. Publishing a close-scope event lets every worker drop local
state for that diagram session scope if it matches the authenticated user.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import socket
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import WebSocket
from redis.exceptions import RedisError

from config.settings import config
from services.infrastructure.monitoring.ws_metrics import (
    record_kitty_control_cleanup_applied,
    record_kitty_control_cleanup_not_configured,
    record_kitty_control_message_ignored,
    record_kitty_control_publish_failure,
    record_kitty_control_publish_success,
    record_kitty_control_received,
    record_kitty_control_voice_cleanup_failed,
)
from services.kitty.infra.control.kitty_control_secret import get_kitty_control_shared_secret
from services.kitty.infra.control.kitty_observability import kitty_extra
from services.kitty.infra.redis.kitty_session_redis import kitty_sessionmeta_active_for_user
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

KITTY_CONTROL_PAYLOAD_VERSION = 1
KITTY_CONTROL_ACTION_CLOSE_SCOPE = "close_scope"
KITTY_CONTROL_REASON_HTTP_CLEANUP = "http_cleanup"
KITTY_CONTROL_REASON_HANDSHAKE_PREEMPT = "handshake_preempt"
KITTY_CONTROL_REASON_IDLE_TIMEOUT = "idle_timeout"
KITTY_CONTROL_REASON_MAX_LEN = 256


def kitty_control_channel() -> str:
    """Redis pub/sub channel for Kitty control messages (override via env)."""
    return os.getenv("KITTY_CONTROL_CHANNEL", "mg:kitty:control").strip() or "mg:kitty:control"


def get_kitty_control_instance_id() -> str:
    """
    Per-process instance tag used to skip local subscriber handling for
    handshake preemption (same worker already runs the in-process lock path).
    """
    explicit = os.getenv("KITTY_CONTROL_INSTANCE_ID", "").strip()
    if explicit:
        return explicit[:128]
    hn = socket.gethostname()
    return f"{hn}:{os.getpid()}"[:128]


def verify_kitty_control_shared_secret(envelope: Dict[str, Any]) -> bool:
    """HMAC gate for control payloads (Redis-backed secret or env override)."""
    secret = get_kitty_control_shared_secret()
    if not secret:
        if not getattr(config, "DEBUG", True):
            logger.warning(
                "[KittyControl] control shared secret unavailable while DEBUG=False; rejecting control messages",
                extra=kitty_extra("control_secret_missing_subscriber"),
            )
            return False
        return True
    token = envelope.get("auth")
    if not isinstance(token, str) or not token:
        return False
    scope = str(envelope.get("scope") or "")
    uid = envelope.get("user_id")
    reason = str(envelope.get("reason") or "")
    if len(reason) > KITTY_CONTROL_REASON_MAX_LEN:
        return False
    msg = f"{scope}:{uid}:{reason}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(token, expected)


async def publish_kitty_close_scope_async(
    scope: str,
    user_id: int,
    reason: str,
) -> None:
    """Notify all workers to drop local Kitty state for ``scope`` if owned by ``user_id``."""
    if len(reason) > KITTY_CONTROL_REASON_MAX_LEN:
        record_kitty_control_publish_failure()
        logger.warning(
            "[KittyControl] publish skipped: reason too long",
            extra=kitty_extra(
                "publish_reason_too_long",
                user_id=int(user_id),
                reason=reason[:KITTY_CONTROL_REASON_MAX_LEN],
            ),
        )
        return

    scope_norm = normalize_kitty_diagram_session_id(scope)
    if scope_norm is None:
        record_kitty_control_publish_failure()
        logger.warning(
            "[KittyControl] publish skipped: invalid scope",
            extra=kitty_extra("publish_invalid_scope", user_id=int(user_id), reason=reason),
        )
        return

    secret = get_kitty_control_shared_secret()
    if not secret and not getattr(config, "DEBUG", True):
        record_kitty_control_publish_failure()
        logger.warning(
            "[KittyControl] publish skipped: control shared secret unavailable while DEBUG=False",
            extra=kitty_extra(
                "publish_secret_missing_production",
                scope=scope_norm,
                user_id=int(user_id),
                reason=reason,
            ),
        )
        return

    redis = get_async_redis()
    if redis is None:
        record_kitty_control_publish_failure()
        logger.warning(
            "[KittyControl] publish skipped: no async Redis client",
            extra=kitty_extra("publish_no_redis", scope=scope_norm, user_id=int(user_id), reason=reason),
        )
        return

    body: Dict[str, Any] = {
        "v": KITTY_CONTROL_PAYLOAD_VERSION,
        "action": KITTY_CONTROL_ACTION_CLOSE_SCOPE,
        "scope": scope_norm,
        "user_id": int(user_id),
        "reason": reason,
        "origin": get_kitty_control_instance_id(),
    }
    if secret:
        msg = f"{scope_norm}:{user_id}:{reason}".encode("utf-8")
        body["auth"] = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    try:
        await redis.publish(kitty_control_channel(), json.dumps(body, ensure_ascii=False))
        record_kitty_control_publish_success()
    except (RedisError, TypeError, ValueError) as exc:
        record_kitty_control_publish_failure()
        logger.warning(
            "[KittyControl] publish failed: %s",
            exc,
            extra=kitty_extra(
                "publish_redis_error",
                scope=scope_norm,
                user_id=int(user_id),
                reason=reason,
                error_type=type(exc).__name__,
            ),
        )


def parse_kitty_control_envelope(raw: str) -> Optional[Dict[str, Any]]:
    """Parse and validate top-level envelope; returns dict or None."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("[KittyControl] invalid JSON")
        return None
    if not isinstance(data, dict):
        return None
    if data.get("v") != KITTY_CONTROL_PAYLOAD_VERSION:
        return None
    if data.get("action") != KITTY_CONTROL_ACTION_CLOSE_SCOPE:
        return None
    scope = data.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        return None
    raw_uid = data.get("user_id")
    if isinstance(raw_uid, bool):
        return None
    if isinstance(raw_uid, int):
        uid = raw_uid
    elif isinstance(raw_uid, str):
        if not raw_uid.strip():
            return None
        try:
            uid = int(raw_uid, 10)
        except ValueError:
            return None
    else:
        return None
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason:
        return None
    if len(reason) > KITTY_CONTROL_REASON_MAX_LEN:
        logger.debug("[KittyControl] rejected envelope: reason too long")
        return None
    scope_norm = normalize_kitty_diagram_session_id(scope)
    if scope_norm is None:
        logger.debug("[KittyControl] rejected envelope: scope failed normalization")
        return None
    data["_parsed_scope"] = scope_norm
    data["_parsed_user_id"] = uid
    data["_parsed_reason"] = reason
    return data


class _ControlDispatchState:
    """Injected process-local registries for subscriber dispatch."""

    kitty_scope_cleanup: Optional[Callable[[str], Awaitable[bool]]] = None
    active_websockets: Optional[Dict[str, List[WebSocket]]] = None
    voice_sessions: Optional[Dict[str, Any]] = None


def configure_kitty_control_dispatch(
    *,
    kitty_scope_cleanup: Optional[Callable[[str], Awaitable[bool]]] = None,
    active_websockets: Optional[Dict[str, List[WebSocket]]] = None,
    voice_sessions: Optional[Dict[str, Any]] = None,
) -> None:
    """Wire scope lifecycle registries used by Redis control subscriber dispatch."""
    if kitty_scope_cleanup is not None:
        _ControlDispatchState.kitty_scope_cleanup = kitty_scope_cleanup
    if active_websockets is not None:
        _ControlDispatchState.active_websockets = active_websockets
    if voice_sessions is not None:
        _ControlDispatchState.voice_sessions = voice_sessions


async def _run_scope_cleanup(
    cleanup: Callable[[str], Awaitable[bool]],
    scope: str,
) -> bool:
    """Invoke configured scope cleanup callback."""
    return await cleanup(scope)


async def _local_scope_matches_user(scope: str, user_id: int) -> bool:
    """Local scope matches user."""
    if _ControlDispatchState.voice_sessions is None or _ControlDispatchState.active_websockets is None:
        return False
    matching_sessions = [
        session
        for session in _ControlDispatchState.voice_sessions.values()
        if session.get("diagram_session_id") == scope
    ]
    if matching_sessions:
        return all(str(session.get("user_id")) == str(user_id) for session in matching_sessions)
    active_websockets = _ControlDispatchState.active_websockets
    if active_websockets is not None and scope in dict(active_websockets):
        return await kitty_sessionmeta_active_for_user(scope, user_id)
    return False


async def handle_kitty_control_dispatch(raw: str, local_instance: str) -> None:
    """Redis subscriber entry: validate envelope, match local state, run cleanup."""
    record_kitty_control_received()
    envelope = parse_kitty_control_envelope(raw)
    if envelope is None:
        record_kitty_control_message_ignored()
        return
    if not verify_kitty_control_shared_secret(envelope):
        env_uid: Optional[int] = None
        raw_uid = envelope.get("user_id")
        if isinstance(raw_uid, int) and not isinstance(raw_uid, bool):
            env_uid = raw_uid
        elif isinstance(raw_uid, str) and raw_uid.strip():
            try:
                env_uid = int(raw_uid.strip(), 10)
            except ValueError:
                env_uid = None
        raw_scope = envelope.get("scope")
        env_scope = normalize_kitty_diagram_session_id(raw_scope) if isinstance(raw_scope, str) else None
        logger.warning(
            "[KittyControl] rejected control message (auth verification failed)",
            extra=kitty_extra("control_auth_rejected", scope=env_scope, user_id=env_uid),
        )
        record_kitty_control_message_ignored()
        return

    scope = str(envelope["_parsed_scope"])
    user_id = int(envelope["_parsed_user_id"])
    reason = str(envelope["_parsed_reason"])
    origin = envelope.get("origin")
    origin_str = origin if isinstance(origin, str) else ""

    if reason == KITTY_CONTROL_REASON_HANDSHAKE_PREEMPT and origin_str == local_instance:
        record_kitty_control_message_ignored()
        return

    if not await _local_scope_matches_user(scope, user_id):
        record_kitty_control_message_ignored()
        return

    scope_cleanup = _ControlDispatchState.kitty_scope_cleanup
    if scope_cleanup is None:
        record_kitty_control_cleanup_not_configured()
        logger.warning(
            "[KittyControl] cleanup not configured; ignoring scope=%s",
            scope,
            extra=kitty_extra(
                "cleanup_not_configured",
                scope=scope,
                user_id=user_id,
                reason=reason,
                origin=origin_str or None,
            ),
        )
        return

    assert callable(scope_cleanup)
    try:
        cleaned = await _run_scope_cleanup(scope_cleanup, scope)
    except BACKGROUND_INFRA_ERRORS as exc:
        record_kitty_control_voice_cleanup_failed()
        logger.warning(
            "[KittyControl] voice cleanup failed scope=%s user_id=%s reason=%s: %s",
            scope,
            user_id,
            reason,
            exc,
            exc_info=True,
            extra=kitty_extra(
                "voice_cleanup_failed",
                scope=scope,
                user_id=user_id,
                reason=reason,
                origin=origin_str or None,
                error_type=type(exc).__name__,
            ),
        )
        return
    if cleaned:
        record_kitty_control_cleanup_applied()
        logger.info(
            "[KittyControl] cross-worker cleanup scope=%s user_id=%s reason=%s",
            scope,
            user_id,
            reason,
            extra=kitty_extra(
                "control_cleanup_applied",
                scope=scope,
                user_id=user_id,
                reason=reason,
                origin=origin_str or None,
            ),
        )


async def handle_kitty_control_message(raw: str, local_instance: str) -> None:
    """Dispatch pub/sub payload to the configured scope cleanup handler."""
    await handle_kitty_control_dispatch(raw, local_instance)
