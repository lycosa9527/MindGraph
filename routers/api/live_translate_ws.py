"""
Authenticated WebSocket bridge from the canvas to DashScope Qwen3 LiveTranslate Flash Realtime.

Bootstrap frame (first frame only):
  {"type": "start", "source_language": "zh", "target_language": "en", ...}

Then continuous audio:
  {"type": "input_audio_buffer.append", "event_id": "...", "audio": "<base64>"}
  (alias "append")

No session.finish — the session stays open until the client closes the socket.
All DashScope server events forwarded verbatim; key event for text-only mode: response.text.done.
"""

import contextlib
import json
import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from services.auth.vpn_geo_enforcement import maybe_close_websocket_for_vpn_cn_geo
from services.features.live_translate_bridge import run_translate_relay, translate_error_json
from utils.auth.roles import is_admin
from utils.auth_ws import authenticate_websocket_user
from utils.ws_context import ws_managed_session
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
    receive_websocket_text_frame,
    safe_websocket_send_text,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_DEFAULT_SOURCE_LANG = "en"
_DEFAULT_TARGET_LANG = "zh"


def _parse_start_options(start_msg: dict) -> tuple[str, str]:
    """Extract source_language and target_language from the start frame."""
    source = str(start_msg.get("source_language") or _DEFAULT_SOURCE_LANG).strip() or _DEFAULT_SOURCE_LANG
    target = str(start_msg.get("target_language") or _DEFAULT_TARGET_LANG).strip() or _DEFAULT_TARGET_LANG
    return source, target


@router.websocket("/ws/canvas-translate")
async def canvas_translate_websocket(websocket: WebSocket) -> None:
    # ── Auth before accept ───────────────────────────────────────────────────
    user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or user is None:
        logger.warning("[CanvasTranslate] Auth rejected: %s", auth_error)
        await websocket.close(code=4001, reason=auth_error or "Authentication failed")
        return

    if not is_admin(user):
        logger.warning("[CanvasTranslate] Non-admin access denied for user_id=%s", user.id)
        await websocket.close(code=4003, reason="Admin access required")
        return

    if await maybe_close_websocket_for_vpn_cn_geo(websocket):
        logger.warning("[CanvasTranslate] VPN/CN policy closed connection for user_id=%s", user.id)
        return

    await websocket.accept()

    try:
        await _canvas_translate_session(websocket, user)
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("[CanvasTranslate] Unhandled error after accept")
        with contextlib.suppress(Exception):
            await safe_websocket_send_text(
                websocket, translate_error_json("internal", "Translation session error")
            )
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)


async def _canvas_translate_session(websocket: WebSocket, user: object) -> None:
    rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND)

    try:
        raw = await receive_websocket_text_frame(websocket)
    except WebSocketDisconnect:
        return

    if inbound_text_exceeds_limit(raw, DEFAULT_MAX_WS_TEXT_BYTES):
        await safe_websocket_send_text(websocket, translate_error_json("too_large", "Message too large"))
        await websocket.close(code=1009)
        return

    try:
        start_msg = json.loads(raw)
    except json.JSONDecodeError:
        await safe_websocket_send_text(websocket, translate_error_json("invalid_json", "Invalid JSON"))
        await websocket.close(code=4400)
        return

    if start_msg.get("type") != "start":
        await safe_websocket_send_text(websocket, translate_error_json("bad_start", "Expected type start"))
        await websocket.close(code=4400)
        return

    if not rate_limiter.allow():
        await safe_websocket_send_text(websocket, translate_error_json("rate_limit", "Too many messages"))
        await websocket.close(code=8429)
        return

    source_lang, target_lang = _parse_start_options(start_msg)

    logger.info(
        "[CanvasTranslate] Relay start user_id=%s source=%s target=%s",
        getattr(user, "id", "?"),
        source_lang,
        target_lang,
    )

    async with ws_managed_session(
        websocket,
        user_id=getattr(user, "id", 0),
        endpoint="translate",
        max_per_user_endpoint=1,
        close_error_fn=translate_error_json,
        source_language=source_lang,
        target_language=target_lang,
    ):
        await run_translate_relay(
            websocket,
            source_lang,
            target_lang,
            rate_limiter=rate_limiter,
        )
