"""WebSocket ``append_image`` inbound handling for Kitty Omni multimodal.

Omni realtime **vision** path:

1. Client sends ``{"type": "append_image", "data": "<base64>", "format": "jpeg"}``.
2. Server validates size (``KITTY_WS_IMAGE_*`` in :mod:`services.kitty.ws.guards``), decodes
   base64, sends short PCM silence preamble, calls ``OmniClient.append_image``,
   ``commit_audio_buffer``, ``create_response`` with a short instruction to summarize content.
3. Session flag ``pending_kitty_image_paragraph`` routes the first non-empty transcription through
   paragraph processing when applicable.

Hub / ``kitty:live_spec`` updates follow normal ``patch_context`` / voice diagram sync.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
import binascii
import logging

from fastapi import WebSocket

from services.kitty.context.messaging import safe_websocket_send
from services.kitty.session.omni_client_access import get_session_omni_client
from services.kitty.ws.guards import (
    KITTY_WS_IMAGE_B64_MAX_CHARS,
    KITTY_WS_IMAGE_RAW_MAX_BYTES,
    pcm16_silence_base64,
)

logger = logging.getLogger(__name__)


async def kitty_ws_handle_append_image(
    websocket: WebSocket,
    voice_session_id: str,
    message: dict,
    voice_sessions: dict,
) -> None:
    """Handle ``{"type": "append_image", ...}``; mutate ``voice_sessions`` for paragraph follow-up."""
    logger.debug("User requested to append image")
    image_data = message.get("data")
    image_format = message.get("format", "jpeg")
    if not image_data:
        await safe_websocket_send(websocket, {"type": "error", "error": "Missing image data"})
        return

    if not isinstance(image_data, str) or len(image_data) > KITTY_WS_IMAGE_B64_MAX_CHARS:
        await safe_websocket_send(
            websocket,
            {"type": "error", "error": "Image payload too large"},
        )
        return
    try:
        image_bytes = base64.b64decode(image_data, validate=True)
    except (binascii.Error, TypeError, ValueError):
        await safe_websocket_send(
            websocket,
            {"type": "error", "error": "Invalid image data"},
        )
        return
    if len(image_bytes) > KITTY_WS_IMAGE_RAW_MAX_BYTES:
        await safe_websocket_send(
            websocket,
            {"type": "error", "error": "Image too large"},
        )
        return

    omni_client = get_session_omni_client(voice_session_id)
    if not omni_client:
        logger.warning(
            "Cannot append image: OmniClient not found for session %s",
            voice_session_id,
        )
        return

    try:
        await omni_client.append_audio(pcm16_silence_base64(200, 24000))
    except (RuntimeError, ConnectionError, AttributeError, ValueError) as pre_audio_err:
        logger.debug("Silence preamble before image: %s", pre_audio_err)
    await omni_client.append_image(image_bytes, image_format)
    try:
        await omni_client.commit_audio_buffer()
    except (RuntimeError, ConnectionError, AttributeError) as commit_err:
        logger.debug("commit_audio_buffer after image: %s", commit_err)
    try:
        await omni_client.create_response(
            instructions=("请用两到三句话概括图片里的文字或可入图的要点；看不清就说看不清。"),
        )
    except (RuntimeError, ConnectionError, AttributeError) as resp_err:
        logger.debug("create_response after image: %s", resp_err)
    else:
        voice_sessions[voice_session_id]["pending_kitty_image_paragraph"] = True
        voice_sessions[voice_session_id].pop("kitty_image_paragraph_empty_streak", None)
        await safe_websocket_send(
            websocket,
            {"type": "image_appended", "format": image_format},
        )
