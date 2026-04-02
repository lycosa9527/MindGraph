"""Authentication and workshop resolution for canvas-collab WebSocket."""

import logging
import re
from typing import Any, Optional, Tuple

from fastapi import WebSocket

from services.infrastructure.monitoring.ws_metrics import record_ws_auth_failure
from services.workshop.workshop_service import workshop_service
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
        reason = auth_error or "Authentication failed"
        await websocket.close(code=4001, reason=reason)
        logger.warning("[CanvasCollabWS] Auth failed: %s", reason)
        return None

    logger.info("[CanvasCollabWS] connection accepted user_id=%s", user.id)

    norm_code = code.strip()
    if not re.match(r"^\d{3}-\d{3}$", norm_code):
        await websocket.close(
            code=1008,
            reason="Invalid presentation code format",
        )
        logger.warning(
            "[CanvasCollabWS] Invalid presentation code format: %s",
            norm_code,
        )
        return None

    workshop_info = await workshop_service.join_workshop(norm_code, user.id)
    if not workshop_info:
        await websocket.close(
            code=1008,
            reason="Collaboration session ended or invalid code",
        )
        return None

    diagram_id = workshop_info["diagram_id"]
    owner_raw = workshop_info.get("owner_id")
    owner_id: Optional[int]
    if owner_raw is not None:
        try:
            owner_id = int(owner_raw)
        except (TypeError, ValueError):
            owner_id = None
    else:
        owner_id = None

    return user, norm_code, diagram_id, owner_id
