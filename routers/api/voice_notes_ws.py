"""
Authenticated WebSocket bridge for Voice Notes → DashScope Fun-ASR realtime.

Browser bootstrap (first frame):
  {"type": "start", "language_hints": ["zh"]}

Then:
  {"type": "append", "audio": "<base64 pcm16>"}
  {"type": "stop"}

Downstream: started / partial / final / stopped / error.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any, List, Optional

from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketState
from starlette.websockets import WebSocketDisconnect

from models.domain.messages import Language, get_request_language
from services.auth.vpn_geo_enforcement import maybe_close_websocket_for_vpn_cn_geo
from services.features.voice_notes_asr_bridge import run_voice_notes_asr_relay, voice_notes_error_json
from services.features.voice_notes_usage import (
    assert_voice_notes_usage_budget,
    schedule_voice_notes_session_activity,
    voice_notes_budget_error_payload,
)
from services.infrastructure.http.error_handler import (
    ThinkingCoinInsufficientError,
    UserDailyTokenCapExceededError,
)
from services.infrastructure.monitoring.ws_metrics import record_ws_auth_failure
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth_ws import authenticate_websocket_user
from utils.collab_ws_origin import (
    canvas_collab_websocket_origin_is_allowed,
    load_collab_ws_allowed_origins_env,
)
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

_WS_CLOSE_REASON_MAX = 120


async def _reject_voice_notes_websocket(websocket: WebSocket, code: int, reason: str) -> None:
    """Accept first, then close — avoid HTTP 403 that hides the real close code."""
    clipped = (reason or "rejected")[:_WS_CLOSE_REASON_MAX]
    try:
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[VoiceNotesASR] accept-before-reject skipped: %s", exc)
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=code, reason=clipped)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[VoiceNotesASR] reject close skipped: %s", exc)


def _language_hints_from_start(start_msg: dict[str, Any]) -> Optional[List[str]]:
    """Parse optional language_hints / language from the bootstrap frame."""
    raw = start_msg.get("language_hints")
    if isinstance(raw, list):
        hints = [str(item).strip() for item in raw if str(item).strip()]
        return hints or None
    language = start_msg.get("language")
    if isinstance(language, str) and language.strip():
        return [language.strip()]
    return None


def _ws_ui_language(websocket: WebSocket) -> Language:
    """Best-effort UI language for budget error messages."""
    return get_request_language(
        websocket.headers.get("X-Language"),
        websocket.headers.get("Accept-Language"),
    )


@router.websocket("/ws/voice-notes")
async def voice_notes_websocket(websocket: WebSocket) -> None:
    """Voice notes Fun-ASR websocket."""
    user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or user is None:
        logger.warning("[VoiceNotesASR] Auth rejected: %s", auth_error)
        record_ws_auth_failure()
        await _reject_voice_notes_websocket(
            websocket,
            4001,
            auth_error or "Authentication failed",
        )
        return

    allowed = load_collab_ws_allowed_origins_env()
    if not canvas_collab_websocket_origin_is_allowed(websocket.headers, allowed):
        logger.warning("[VoiceNotesASR] WebSocket origin rejected (CSWSH guard)")
        await _reject_voice_notes_websocket(
            websocket,
            1008,
            "Cross-origin connection is not allowed",
        )
        return

    # Accept before VPN/geo close so the browser sees WS close codes, not HTTP 403.
    if websocket.client_state == WebSocketState.CONNECTING:
        await websocket.accept()

    if await maybe_close_websocket_for_vpn_cn_geo(websocket):
        logger.warning("[VoiceNotesASR] VPN/CN policy closed connection for user_id=%s", user.id)
        return

    try:
        await _voice_notes_session(websocket, user)
    except WebSocketDisconnect:
        return
    except BACKGROUND_INFRA_ERRORS:
        logger.exception("[VoiceNotesASR] Unhandled error after accept")
        with contextlib.suppress(Exception):
            await safe_websocket_send_text(
                websocket,
                voice_notes_error_json("internal", "Speech session error"),
            )
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)


async def _voice_notes_session(websocket: WebSocket, user: Any) -> None:
    """Handle bootstrap start frame then relay PCM to Fun-ASR."""
    rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND)

    try:
        raw = await receive_websocket_text_frame(websocket)
    except WebSocketDisconnect:
        return

    if inbound_text_exceeds_limit(raw, DEFAULT_MAX_WS_TEXT_BYTES):
        await safe_websocket_send_text(
            websocket,
            voice_notes_error_json("too_large", "Message too large"),
        )
        await websocket.close(code=1009)
        return

    try:
        start_msg = json.loads(raw)
    except json.JSONDecodeError:
        await safe_websocket_send_text(
            websocket,
            voice_notes_error_json("invalid_json", "Invalid JSON"),
        )
        await websocket.close(code=4400)
        return

    if not isinstance(start_msg, dict) or start_msg.get("type") != "start":
        await safe_websocket_send_text(
            websocket,
            voice_notes_error_json("bad_start", "Expected type start"),
        )
        await websocket.close(code=4400)
        return

    if not rate_limiter.allow():
        await safe_websocket_send_text(
            websocket,
            voice_notes_error_json("rate_limit", "Too many messages"),
        )
        await websocket.close(code=8429)
        return

    lang = _ws_ui_language(websocket)
    try:
        await assert_voice_notes_usage_budget(user, lang=lang)
    except (ThinkingCoinInsufficientError, UserDailyTokenCapExceededError) as exc:
        code, message = voice_notes_budget_error_payload(exc)
        await safe_websocket_send_text(websocket, voice_notes_error_json(code, message))
        await websocket.close(code=4403, reason=message[:_WS_CLOSE_REASON_MAX])
        return

    language_hints = _language_hints_from_start(start_msg)
    logger.info(
        "[VoiceNotesASR] Relay start user_id=%s language_hints=%s",
        user.id,
        language_hints,
    )

    async with ws_managed_session(
        websocket,
        user_id=user.id,
        endpoint="voice_notes_asr",
        max_per_user_endpoint=1,
        close_error_fn=voice_notes_error_json,
    ):
        schedule_voice_notes_session_activity(user, websocket)
        await run_voice_notes_asr_relay(
            websocket,
            user=user,
            language_hints=language_hints,
            rate_limiter=rate_limiter,
        )
