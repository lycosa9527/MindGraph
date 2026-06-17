"""Kitty session event consumer wiring (command router + memory + omni refresh)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict

from fastapi import WebSocket

from services.kitty.content.paragraph import process_paragraph_with_qwen_plus
from services.kitty.context.library_refresh import bump_voice_mutation_freshness
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.omni.context_refresh import schedule_omni_context_refresh
from services.kitty.routing.command_router import RouteOutcome, route_omni_function_call, route_voice_command
from services.kitty.session.events import (
    KittyEvent,
    SessionEventBus,
    get_session_event_bus,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.omni_client_access import get_session_omni_client
from services.kitty.session.runtime_state import voice_sessions

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class KittySessionRuntime:
    """KittySessionRuntime helper."""
    websocket: WebSocket
    voice_session_id: str


async def setup_session_event_handlers(runtime: KittySessionRuntime) -> SessionEventBus:
    """Setup session event handlers."""
    bus = get_session_event_bus(runtime.voice_session_id)

    async def _on_event(event: KittyEvent) -> None:
        if event.kind == "transcription":
            await _handle_transcription(runtime, event.payload)
        elif event.kind == "text_inbound":
            await _handle_text_inbound(runtime, event.payload)
        elif event.kind == "assistant_text":
            mem = get_session_memory(runtime.voice_session_id)
            chunk = event.payload.get("text")
            if isinstance(chunk, str):
                mem.append_assistant_chunk(chunk)
        elif event.kind == "assistant_done":
            get_session_memory(runtime.voice_session_id).flush_assistant_turn()
        elif event.kind == "function_call":
            await _handle_function_call(runtime, event.payload)
        elif event.kind == "diagram_mutated":
            bump_voice_mutation_freshness(runtime.voice_session_id)
            delta = event.payload.get("delta")
            await schedule_omni_context_refresh(
                runtime.voice_session_id,
                reason="diagram_mutation",
                delta=str(delta) if delta else None,
            )
        elif event.kind == "context_update":
            sess = voice_sessions.get(runtime.voice_session_id)
            if sess is not None:
                sess["_last_context_update_mono"] = time.monotonic()
            reason = str(event.payload.get("reason") or "context_update")
            await schedule_omni_context_refresh(runtime.voice_session_id, reason=reason)
        elif event.kind == "image_paragraph":
            await _handle_image_paragraph(runtime, event.payload)

    bus.add_handler(_on_event)
    await bus.start()
    return bus


async def _handle_transcription(runtime: KittySessionRuntime, payload: Dict[str, Any]) -> None:
    """Handle transcription."""
    text = str(payload.get("text") or "").strip()
    if not text:
        return

    kitty_wf_log(
        "user_turn",
        text,
        voice_session_id=runtime.voice_session_id,
    )

    mem = get_session_memory(runtime.voice_session_id)
    mem.append_user_turn(text, source="transcription")

    session = voice_sessions.get(runtime.voice_session_id)
    if session is not None:
        history = session.get("conversation_history")
        if isinstance(history, list):
            history.append({"role": "user", "content": text})


async def _handle_text_inbound(runtime: KittySessionRuntime, payload: Dict[str, Any]) -> None:
    """Handle text inbound."""
    text = str(payload.get("text") or "").strip()
    if not text:
        return

    mem = get_session_memory(runtime.voice_session_id)
    mem.append_user_turn(text, source="text")

    session = voice_sessions.get(runtime.voice_session_id) or {}
    session_context = dict(session.get("context") or {})
    result = await route_voice_command(
        runtime.websocket,
        runtime.voice_session_id,
        text,
        session_context,
        is_text_message=True,
        from_voice=False,
    )
    if result.outcome == RouteOutcome.EXECUTED:
        return
    if result.outcome != RouteOutcome.CONVERSATIONAL_FALLBACK:
        return

    try:
        logger.debug("Text message is conversational, sending to Omni")
        omni_client = get_session_omni_client(runtime.voice_session_id)
        if omni_client:
            await omni_client.send_text_message(text)
            return
        logger.warning(
            "Cannot send text: OmniClient not found for session %s",
            runtime.voice_session_id,
        )
        await safe_websocket_send(
            runtime.websocket,
            {"type": "error", "error": "Voice session not initialized"},
        )
    except (RuntimeError, ConnectionError, AttributeError) as text_error:
        logger.error("Text message processing error: %s", text_error, exc_info=True)
        await safe_websocket_send(
            runtime.websocket,
            {"type": "error", "error": str(text_error)},
        )


async def _handle_function_call(runtime: KittySessionRuntime, payload: Dict[str, Any]) -> None:
    """Handle function call."""
    name = payload.get("name")
    args = payload.get("arguments") or "{}"
    if not isinstance(name, str):
        return
    kitty_wf_log(
        "omni_tool",
        str(args)[:160],
        voice_session_id=runtime.voice_session_id,
        action=name,
    )
    session = voice_sessions.get(runtime.voice_session_id) or {}
    session_context = dict(session.get("context") or {})
    await route_omni_function_call(
        runtime.websocket,
        runtime.voice_session_id,
        name,
        str(args),
        session_context,
    )


async def _handle_image_paragraph(runtime: KittySessionRuntime, payload: Dict[str, Any]) -> None:
    """Handle image paragraph."""
    text = str(payload.get("text") or "").strip()
    if not text:
        return
    session = voice_sessions.get(runtime.voice_session_id) or {}
    session_context = dict(session.get("context") or {})
    try:
        await process_paragraph_with_qwen_plus(
            runtime.websocket,
            runtime.voice_session_id,
            text,
            session_context,
        )
    except (ValueError, KeyError, RuntimeError, AttributeError) as voice_error:
        logger.error("Image paragraph processing error: %s", voice_error, exc_info=True)
        await safe_websocket_send(
            runtime.websocket,
            {"type": "error", "error": "Image paragraph processing failed"},
        )
