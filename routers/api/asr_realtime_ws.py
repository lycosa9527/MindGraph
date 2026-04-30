"""
Authenticated WebSocket bridge from the canvas to DashScope Qwen3 ASR Flash Realtime.

Browser bootstrap (first frame only):
  {"type": "start", "language": "zh", ...} — maps to upstream ``session.update``

Then use the same client events as the API doc (or short aliases):
  {"type": "input_audio_buffer.append", "event_id": "...", "audio": "<base64>"}
  (alias ``append``) — optional; relay fills ``event_id`` if missing on native type

  {"type": "session.finish", "event_id": "..."} (alias ``finish``)

Downstream: DashScope server events forwarded verbatim.

Not exposed: Manual mode (``turn_detection``: null + ``input_audio_buffer.commit``).
"""

import contextlib
import json
import logging
from typing import Any, Dict, Tuple

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from services.auth.vpn_geo_enforcement import maybe_close_websocket_for_vpn_cn_geo
from services.features.asr_realtime_bridge import bridge_error_json, run_asr_relay
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

_DEFAULT_LANG = "zh"


def _session_options_from_start(start_msg: Dict[str, Any]) -> Tuple[int, str]:
    """Parse optional sample_rate and input_audio_format per Qwen-ASR-Realtime session.update."""
    sample_rate = 16000
    raw_sr = start_msg.get("sample_rate")
    if raw_sr is not None:
        try:
            sr_int = int(raw_sr)
            if sr_int in (8000, 16000):
                sample_rate = sr_int
        except (TypeError, ValueError):
            pass
    audio_format = "pcm"
    raw_fmt = start_msg.get("input_audio_format")
    if isinstance(raw_fmt, str) and raw_fmt.strip().lower() in ("pcm", "opus"):
        audio_format = raw_fmt.strip().lower()
    return sample_rate, audio_format


@router.websocket("/ws/canvas-asr")
async def canvas_asr_websocket(websocket: WebSocket) -> None:
    # ── Auth before accept ───────────────────────────────────────────────────
    # Token is read from scope (headers/cookies) — no accept() needed.
    # Unauthenticated clients receive an HTTP 403 rejection, not a WS close,
    # which avoids burning a file descriptor on invalid requests.
    user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or user is None:
        logger.warning("[CanvasASR] Auth rejected: %s", auth_error)
        await websocket.close(code=4001, reason=auth_error or "Authentication failed")
        return

    if await maybe_close_websocket_for_vpn_cn_geo(websocket):
        logger.warning("[CanvasASR] VPN/CN policy closed connection for user_id=%s", user.id)
        return

    await websocket.accept()

    try:
        await _canvas_asr_session(websocket, user)
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("[CanvasASR] Unhandled error after accept")
        with contextlib.suppress(Exception):
            await safe_websocket_send_text(websocket, bridge_error_json("internal", "Speech session error"))
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)


async def _canvas_asr_session(websocket: WebSocket, user: Any) -> None:
    rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND)

    try:
        raw = await receive_websocket_text_frame(websocket)
    except WebSocketDisconnect:
        return

    if inbound_text_exceeds_limit(raw, DEFAULT_MAX_WS_TEXT_BYTES):
        await safe_websocket_send_text(websocket, bridge_error_json("too_large", "Message too large"))
        await websocket.close(code=1009)
        return

    try:
        start_msg = json.loads(raw)
    except json.JSONDecodeError:
        await safe_websocket_send_text(websocket, bridge_error_json("invalid_json", "Invalid JSON"))
        await websocket.close(code=4400)
        return

    if start_msg.get("type") != "start":
        await safe_websocket_send_text(websocket, bridge_error_json("bad_start", "Expected type start"))
        await websocket.close(code=4400)
        return

    if not rate_limiter.allow():
        await safe_websocket_send_text(websocket, bridge_error_json("rate_limit", "Too many messages"))
        await websocket.close(code=8429)
        return

    lang_raw = start_msg.get("language")
    language = str(lang_raw).strip() if lang_raw else _DEFAULT_LANG
    if not language:
        language = _DEFAULT_LANG

    sample_rate, input_audio_format = _session_options_from_start(start_msg)

    logger.info(
        "[CanvasASR] Relay start user_id=%s language=%s sample_rate=%s format=%s",
        user.id,
        language,
        sample_rate,
        input_audio_format,
    )

    async with ws_managed_session(
        websocket,
        user_id=user.id,
        endpoint="asr",
        max_per_user_endpoint=1,
        close_error_fn=bridge_error_json,
        language=language,
    ):
        await run_asr_relay(
            websocket,
            language,
            sample_rate=sample_rate,
            input_audio_format=input_audio_format,
            rate_limiter=rate_limiter,
        )
