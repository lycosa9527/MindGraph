"""Authentication and workshop resolution for canvas-collab WebSocket."""

import logging
import re
from typing import Any, Optional, Tuple

from fastapi import WebSocket

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
from utils.auth_ws import authenticate_websocket_user

logger = logging.getLogger(__name__)


async def authenticate_and_resolve_canvas_workshop(
    websocket: WebSocket,
    code: str,
) -> Optional[Tuple[Any, str, str, Optional[int]]]:
    """
    Validate JWT and join the workshop.

    Returns ``(user, normalized_code, diagram_id, owner_id)``, or ``None`` if
    the socket was closed due to auth/join failure.
    """
    user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or user is None:
        try:
            record_ws_auth_failure()
        except Exception as exc:
            logger.debug("Failed to record auth failure metric: %s", exc)
        logger.warning("[CanvasCollabWS] Auth failed: %s", auth_error or "unknown")
        await websocket.close(code=4001, reason="Authentication failed")
        return None

    logger.info("[CanvasCollabWS] authenticated user_id=%s", user.id)

    norm_code = code.strip().upper()
    if not re.match(ONLINE_COLLAB_CODE_RE, norm_code):
        await websocket.close(
            code=1008,
            reason="Invalid presentation code format",
        )
        logger.warning(
            "[CanvasCollabWS] Invalid presentation code format: %s",
            norm_code,
        )
        return None

    resume_raw = (websocket.query_params.get("resume") or "").strip()
    if not resume_raw:
        resume_raw = (websocket.query_params.get("resume_token") or "").strip()

    plausible_resume_rate_bypass = False
    if resume_raw:
        peeked_claims = await peek_join_resume_claims_async(resume_raw)
        if peeked_claims is not None:
            plausible_resume_rate_bypass = join_resume_claims_match_user_room(
                int(user.id), norm_code, peeked_claims,
            )

    if not plausible_resume_rate_bypass:
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

    if resume_raw:
        logger.debug(
            "[CanvasCollabWS] consuming resume token user_id=%s code=%s",
            user.id, norm_code,
        )
        await try_consume_join_resume_token_async(
            raw_query_token=resume_raw,
            user_id=int(user.id),
            workshop_code_upper=norm_code,
            diagram_id=str(diagram_id),
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
        "[CanvasCollabWS] resolved code=%s diagram_id=%s owner_id=%s user_id=%s"
        " resume_bypass=%s",
        norm_code, diagram_id, owner_id, user.id, plausible_resume_rate_bypass,
    )

    return user, norm_code, diagram_id, owner_id
