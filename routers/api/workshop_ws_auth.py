"""Authentication and workshop resolution for canvas-collab WebSocket."""

import logging
import re
from typing import Any, Optional, Tuple

from fastapi import WebSocket
from redis.exceptions import RedisError

from services.infrastructure.monitoring.ws_metrics import record_ws_auth_failure
from services.online_collab.core.online_collab_code import ONLINE_COLLAB_CODE_RE
from services.online_collab.core.online_collab_manager import (
    get_online_collab_manager,
)
from services.online_collab.participant.online_collab_ws_rate_limit import (
    check_canvas_collab_join_rate_limits,
)
from services.online_collab.participant.workshop_join_resume_tokens import (
    join_resume_claims_match_user_room,
    peek_join_resume_claims_async,
    try_consume_join_resume_token_async,
)
from services.online_collab.redis.online_collab_redis_keys import code_to_diagram_key
from services.redis.redis_async_client import get_async_redis
from utils.auth_ws import authenticate_websocket_user

logger = logging.getLogger(__name__)


def _resume_token_from_query(websocket: WebSocket) -> str:
    """Return the reconnect resume token from either supported query name."""
    resume_raw = (websocket.query_params.get("resume") or "").strip()
    if not resume_raw:
        resume_raw = (websocket.query_params.get("resume_token") or "").strip()
    return resume_raw


async def _has_verified_resume_for_rate_limit(
    websocket: WebSocket,
    user: Any,
    norm_code: str,
) -> bool:
    """
    Peek a Redis-backed resume token before join rate limiting.

    The token is not consumed here; the post-join path consumes it atomically
    only after the server has resolved the actual diagram id.
    """
    resume_raw = _resume_token_from_query(websocket)
    if not resume_raw:
        return False
    claims = await peek_join_resume_claims_async(resume_raw)
    if not claims:
        return False
    if not join_resume_claims_match_user_room(int(user.id), norm_code, claims):
        return False
    claimed_diagram_id = str(claims.get("d") or "").strip()
    if not claimed_diagram_id:
        return False
    redis = get_async_redis()
    if not redis:
        return False
    try:
        current_raw = await redis.get(code_to_diagram_key(norm_code))
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.debug(
            "[CanvasCollabWS] resume pre-check diagram lookup failed code=%s: %s",
            norm_code,
            exc,
        )
        return False
    if not current_raw:
        return False
    current_diagram_id = (
        current_raw
        if isinstance(current_raw, str)
        else current_raw.decode("utf-8", errors="replace")
    )
    return current_diagram_id == claimed_diagram_id


async def authenticate_canvas_collab_user(
    websocket: WebSocket,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Validate JWT only (no Redis workshop membership).

    Returns ``(user, None)`` on success, ``(None, error_reason)`` on failure.
    Caller must run Origin / VPN gates before ``resolve_canvas_collab_join``.
    """
    user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or user is None:
        try:
            record_ws_auth_failure()
        except Exception as exc:
            logger.debug("Failed to record auth failure metric: %s", exc)
        logger.warning("[CanvasCollabWS] Auth failed: %s", auth_error or "unknown")
        await websocket.close(code=4001, reason="Authentication failed")
        return None, auth_error or "unknown"
    logger.info("[CanvasCollabWS] authenticated user_id=%s", user.id)
    return user, None


def normalize_canvas_collab_code(raw_code: str) -> Optional[str]:
    """Return uppercased workshop code or None if format is invalid."""
    norm_code = raw_code.strip().upper()
    if not re.match(ONLINE_COLLAB_CODE_RE, norm_code):
        return None
    return norm_code


async def resolve_canvas_collab_join(
    websocket: WebSocket,
    user: Any,
    norm_code: str,
) -> Optional[Tuple[Any, str, str, Optional[int]]]:
    """
    Rate-limit, join Redis participants, optionally consume resume token.

    Call only after Origin and VPN policy gates (no workshop mutation before
    those checks).

    Returns ``(user, normalized_code, diagram_id, owner_id)``, or ``None`` if
    the socket was closed due to join failure.
    """
    has_verified_resume = await _has_verified_resume_for_rate_limit(
        websocket,
        user,
        norm_code,
    )
    rate_msg = None
    if not has_verified_resume:
        rate_msg = await check_canvas_collab_join_rate_limits(int(user.id), websocket)
    if rate_msg:
        await websocket.close(
            code=1008,
            reason="Too many join attempts; wait and retry",
        )
        logger.warning(
            "[CanvasCollabWS] Join rate limited user_id=%s",
            user.id,
        )
        return None

    workshop_info = await get_online_collab_manager().join_online_collab(
        norm_code, user.id,
    )
    if not workshop_info:
        logger.warning(
            "[CanvasCollabWS] join_online_collab returned falsy user_id=%s code=%s"
            " — session ended or invalid code",
            user.id, norm_code,
        )
        await websocket.close(
            code=1008,
            reason="Collaboration session ended or invalid code",
        )
        return None

    diagram_id = workshop_info["diagram_id"]

    resume_raw = _resume_token_from_query(websocket)

    if resume_raw:
        logger.debug(
            "[CanvasCollabWS] consuming resume token user_id=%s code=%s",
            user.id, norm_code,
        )
        consumed = await try_consume_join_resume_token_async(
            raw_query_token=resume_raw,
            user_id=int(user.id),
            workshop_code_upper=norm_code,
            diagram_id=str(diagram_id),
        )
        if not consumed:
            logger.debug(
                "[CanvasCollabWS] resume token did not match resolved join "
                "user_id=%s code=%s diagram=%s",
                user.id,
                norm_code,
                diagram_id,
            )

    owner_raw = workshop_info.get("owner_id")
    owner_id: Optional[int]
    if owner_raw is not None:
        try:
            owner_id = int(owner_raw)
        except (TypeError, ValueError):
            owner_id = None
    else:
        owner_id = None

    logger.info(
        "[CanvasCollabWS] resolved code=%s diagram_id=%s owner_id=%s user_id=%s",
        norm_code, diagram_id, owner_id, user.id,
    )

    return user, norm_code, diagram_id, owner_id


async def authenticate_and_resolve_canvas_workshop(
    websocket: WebSocket,
    code: str,
) -> Optional[Tuple[Any, str, str, Optional[int]]]:
    """
    Validate JWT and join the workshop (single-call path for tests/tools).

    Production ``workshop_ws`` uses ``authenticate_canvas_collab_user`` then
    policy gates then ``resolve_canvas_collab_join`` so Redis is not mutated
    before Origin / VPN checks.
    """
    user, err = await authenticate_canvas_collab_user(websocket)
    if err or user is None:
        return None
    norm_code = normalize_canvas_collab_code(code)
    if norm_code is None:
        await websocket.close(
            code=1008,
            reason="Invalid presentation code format",
        )
        logger.warning(
            "[CanvasCollabWS] Invalid presentation code format: %s",
            code.strip().upper(),
        )
        return None
    return await resolve_canvas_collab_join(websocket, user, norm_code)
