"""Omni SDK event loop for Kitty voice — emit-only to session bus + client forward.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
import random
from typing import Any, AsyncIterator

from fastapi import WebSocket

from services.infrastructure.http.error_handler import UserDailyTokenCapExceededError
from services.kitty.context.messaging import (
    build_greeting_message,
    resolve_voice_interaction_language,
    safe_websocket_send,
)
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.desktop.kitty_voice_phase_fanout import (
    fanout_voice_phase_from_outbound_type,
)
from services.kitty.session.events import KittyEvent, SessionEventBus, emit_kitty_session_event
from services.kitty.session.omni_client_access import get_session_omni_client
from services.kitty.session.runtime_state import logger, voice_sessions
from utils.auth.user_daily_token_quota import daily_token_limit_message


async def run_kitty_omni_event_loop(
    websocket: WebSocket,
    voice_session_id: str,
    omni_generator: AsyncIterator[dict[str, Any]],
    event_bus: SessionEventBus,
) -> None:
    """Forward Omni transport events to the client and session event bus."""
    greeting_sent = False
    try:
        async for event in omni_generator:
            event_type = event.get("type")

            if not greeting_sent and event_type == "session_ready":
                session = voice_sessions.get(voice_session_id)
                if session is None:
                    return
                diagram_type = session.get("diagram_type", "unknown")
                sess_ctx = session.get("context", {})
                greeting_lang = resolve_voice_interaction_language(sess_ctx if isinstance(sess_ctx, dict) else {})
                greeting = build_greeting_message(diagram_type, language=greeting_lang)

                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.create_greeting(greeting_text=greeting)
                else:
                    logger.debug(
                        "Cannot create greeting: OmniClient not found for session %s",
                        voice_session_id,
                    )
                greeting_sent = True
                logger.debug("Greeting sent: %s...", greeting[:50])

            if event_type == "transcription":
                await _handle_transcription_event(
                    websocket,
                    voice_session_id,
                    event,
                    event_bus,
                )
                continue

            if event_type == "function_call":
                fn_name = event.get("name", "")
                fn_args = event.get("arguments", "{}")
                await emit_kitty_session_event(
                    voice_session_id,
                    "function_call",
                    {"name": str(fn_name), "arguments": str(fn_args)},
                )
                continue

            if event_type == "text_chunk":
                text_chunk = event.get("text", "")
                logger.debug("Omni text chunk (%d chars)", len(text_chunk))
                await event_bus.emit(
                    KittyEvent(
                        kind="assistant_text",
                        voice_session_id=voice_session_id,
                        payload={"text": text_chunk},
                    )
                )
                await safe_websocket_send(websocket, {"type": "text_chunk", "text": text_chunk})
                await fanout_voice_phase_from_outbound_type(voice_session_id, "text_chunk")
                continue

            if event_type == "audio_chunk":
                await _forward_audio_chunk(websocket, event)
                await fanout_voice_phase_from_outbound_type(voice_session_id, "audio_chunk")
                continue

            if event_type == "speech_started":
                logger.debug("VAD: Speech started at %sms", event.get("audio_start_ms"))
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "speech_started",
                        "audio_start_ms": event.get("audio_start_ms"),
                    },
                )
                continue

            if event_type == "speech_stopped":
                logger.debug("VAD: Speech stopped at %sms", event.get("audio_end_ms"))
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "speech_stopped",
                        "audio_end_ms": event.get("audio_end_ms"),
                    },
                )
                continue

            if event_type == "response_done":
                logger.debug("Omni response complete")
                await event_bus.emit(
                    KittyEvent(
                        kind="assistant_done",
                        voice_session_id=voice_session_id,
                        payload={},
                    )
                )
                await safe_websocket_send(websocket, {"type": "response_done"})
                await fanout_voice_phase_from_outbound_type(voice_session_id, "response_done")
                continue

            if event_type == "error":
                await safe_websocket_send(
                    websocket,
                    {"type": "error", "error": str(event.get("error"))},
                )
                continue

            if event_type is not None:
                forwarded = await _forward_informational_event(websocket, event_type, event)
                if forwarded:
                    continue

    except UserDailyTokenCapExceededError as cap_exc:
        session = voice_sessions.get(voice_session_id)
        sess_ctx = session.get("context", {}) if session else {}
        greeting_lang = resolve_voice_interaction_language(sess_ctx if isinstance(sess_ctx, dict) else {})
        await safe_websocket_send(
            websocket,
            {
                "type": "error",
                "error": daily_token_limit_message(greeting_lang, cap_exc.cap),
                "error_type": "daily_token_cap",
            },
        )
    except (RuntimeError, ConnectionError, AttributeError, ValueError) as exc:
        logger.error("Omni event error: %s", exc, exc_info=True)
        await safe_websocket_send(websocket, {"type": "error", "error": str(exc)})


async def _handle_transcription_event(
    websocket: WebSocket,
    voice_session_id: str,
    event: dict[str, Any],
    event_bus: SessionEventBus,
) -> None:
    """Handle transcription event."""
    transcription_text = event.get("text", "")
    session_mut = voice_sessions.get(voice_session_id)
    if session_mut is None:
        return

    kitty_wf_log(
        "transcription",
        str(transcription_text),
        voice_session_id=voice_session_id,
    )

    await safe_websocket_send(
        websocket,
        {"type": "transcription", "text": transcription_text},
    )

    await event_bus.emit(
        KittyEvent(
            kind="transcription",
            voice_session_id=voice_session_id,
            payload={"text": transcription_text},
        )
    )

    if not session_mut.get("pending_kitty_image_paragraph"):
        return

    if not transcription_text.strip():
        streak = session_mut.get("kitty_image_paragraph_empty_streak", 0) + 1
        session_mut["kitty_image_paragraph_empty_streak"] = streak
        if streak >= 15:
            session_mut["pending_kitty_image_paragraph"] = False
            session_mut.pop("kitty_image_paragraph_empty_streak", None)
        return

    session_mut["pending_kitty_image_paragraph"] = False
    session_mut.pop("kitty_image_paragraph_empty_streak", None)
    await emit_kitty_session_event(
        voice_session_id,
        "image_paragraph",
        {"text": transcription_text},
    )


async def _forward_audio_chunk(websocket: WebSocket, event: dict[str, Any]) -> None:
    """Forward audio chunk."""
    audio_bytes = event.get("audio")
    if audio_bytes is None:
        logger.warning("Received audio_chunk event without audio data")
        return
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

    if random.random() < 0.2:
        logger.debug(
            "Omni audio chunk: %d bytes -> %d base64",
            len(audio_bytes),
            len(audio_b64),
        )

    await safe_websocket_send(websocket, {"type": "audio_chunk", "audio": audio_b64})


async def _forward_informational_event(
    websocket: WebSocket,
    event_type: str,
    event: dict[str, Any],
) -> bool:
    """Forward informational event."""
    payload_map = {
        "session_created": ("session_created", {"session": event.get("session", {})}),
        "session_updated": ("session_updated", {"session": event.get("session", {})}),
        "response_created": ("response_created", {"response": event.get("response", {})}),
        "audio_buffer_committed": (
            "audio_buffer_committed",
            {"item_id": event.get("item_id")},
        ),
        "audio_buffer_cleared": ("audio_buffer_cleared", {}),
        "item_created": ("item_created", {"item": event.get("item", {})}),
        "response_text_done": (
            "response_text_done",
            {"text": event.get("text", "")},
        ),
        "response_audio_done": ("response_audio_done", {}),
        "response_audio_transcript_done": (
            "response_audio_transcript_done",
            {"transcript": event.get("transcript", "")},
        ),
        "output_item_added": (
            "output_item_added",
            {"item": event.get("item", {})},
        ),
        "output_item_done": ("output_item_done", {"item": event.get("item", {})}),
        "content_part_added": (
            "content_part_added",
            {"part": event.get("part", {})},
        ),
        "content_part_done": (
            "content_part_done",
            {"part": event.get("part", {})},
        ),
    }
    mapped = payload_map.get(event_type)
    if mapped is None:
        return False
    msg_type, extra = mapped
    await safe_websocket_send(websocket, {"type": msg_type, **extra})
    return True
