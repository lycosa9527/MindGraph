"""Deliver Kitty acknowledgment text to WebSocket and optional Omni voice."""

from __future__ import annotations

import logging

from fastapi import WebSocket

from services.kitty.context.messaging import safe_websocket_send
from services.kitty.session.omni_client_access import get_session_omni_client
from services.kitty.session.one_sentence_turns import persist_one_sentence_turn_from_voice_session

_ack_logger = logging.getLogger(__name__)


async def emit_user_ack(
    websocket: WebSocket,
    voice_session_id: str,
    text: str,
    *,
    also_omni: bool = True,
    one_sentence_action: str | None = None,
    one_sentence_outcome: str | None = None,
    one_sentence_user_text: str | None = None,
) -> bool:
    """
    Send a user-facing ack on text_chunk (always) and Omni create_response (optional).

    Text clients and the one-sentence chat panel rely on text_chunk; voice may use Omni TTS.
    """
    message = str(text or "").strip()
    if not message:
        return False

    sent = await safe_websocket_send(websocket, {"type": "text_chunk", "text": message})

    await persist_one_sentence_turn_from_voice_session(
        voice_session_id,
        role="kitty",
        content=message,
        source="ack",
        phase="edit",
        action=one_sentence_action,
        outcome=one_sentence_outcome,
        user_text=one_sentence_user_text,
    )

    if also_omni:
        omni_client = get_session_omni_client(voice_session_id)
        if omni_client:
            try:
                await omni_client.create_response(instructions=message)
            except (RuntimeError, ConnectionError, AttributeError) as exc:
                _ack_logger.debug("Omni ack skipped: %s", exc)

    return sent
