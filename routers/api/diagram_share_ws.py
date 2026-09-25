"""
Relay a shared diagram's spec from the editor to read-only viewers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.auth.vpn_geo_enforcement import maybe_close_websocket_for_vpn_cn_geo
from services.diagram_shares.access import library_access
from services.diagram_shares.fanout import publish_share_spec
from services.diagram_shares.lease import lease_head
from services.diagram_shares.rooms import attach_share_socket, detach_share_socket
from services.utils.error_types import JSON_PARSE_ERRORS, REDIS_ERRORS
from utils.auth_ws import authenticate_websocket_user
from utils.collab_ws_origin import (
    canvas_collab_websocket_origin_is_allowed,
    load_collab_ws_allowed_origins_env,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diagram-share-ws"])

_MAX_SPEC_MESSAGE_CHARS = 1_500_000
_TAB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_DIAGRAM_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


@router.websocket("/ws/diagram-share/{diagram_id}")
async def diagram_share_socket(websocket: WebSocket, diagram_id: str) -> None:
    """Editor sends spec snapshots. Viewers receive them."""
    user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or user is None:
        await websocket.close(code=4001, reason="Authentication failed")
        return
    allowed = load_collab_ws_allowed_origins_env()
    if not canvas_collab_websocket_origin_is_allowed(websocket.headers, allowed):
        await websocket.close(code=1008, reason="Cross-origin share is not allowed")
        return
    if await maybe_close_websocket_for_vpn_cn_geo(websocket):
        return
    if not _DIAGRAM_ID_RE.fullmatch(diagram_id):
        await websocket.close(code=4000, reason="Invalid diagram id")
        return
    tab_id = (websocket.query_params.get("tab_id") or "").strip()
    if not _TAB_ID_RE.fullmatch(tab_id):
        await websocket.close(code=4000, reason="Invalid tab id")
        return
    access = await library_access(int(user.id), diagram_id)
    if access.role == "none":
        await websocket.close(code=4003, reason="Diagram not shared with this user")
        return
    await websocket.accept()
    replaced = attach_share_socket(diagram_id, tab_id, int(user.id), websocket)
    if replaced is not None:
        try:
            await replaced.close(code=4000, reason="Replaced")
        except (WebSocketDisconnect, RuntimeError, OSError) as exc:
            logger.debug("[DiagramShareWS] replaced socket close failed: %s", exc)
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw) > _MAX_SPEC_MESSAGE_CHARS:
                continue
            try:
                message = json.loads(raw)
            except JSON_PARSE_ERRORS:
                continue
            if not isinstance(message, dict) or message.get("type") != "spec":
                continue
            head = await lease_head(diagram_id)
            if head is None or head.user_id != int(user.id) or head.tab_id != tab_id:
                continue
            spec = message.get("spec")
            if not isinstance(spec, dict):
                continue
            await publish_share_spec(diagram_id, tab_id, raw)
    except WebSocketDisconnect:
        logger.debug("[DiagramShareWS] disconnect diagram=%s user=%s", diagram_id, user.id)
    except REDIS_ERRORS as exc:
        logger.warning("[DiagramShareWS] relay failed diagram=%s: %s", diagram_id, exc)
    finally:
        detach_share_socket(diagram_id, tab_id, websocket)
