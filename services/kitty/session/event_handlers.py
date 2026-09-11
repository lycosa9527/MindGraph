"""Kitty session event consumer wiring (typed loop + memory).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict

from fastapi import WebSocket

from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.agent_loop.results import finish_pending_autocomplete, summarize_payload_for_memory
from services.kitty.context.library_refresh import bump_voice_mutation_freshness
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.events import (
    KittyEvent,
    SessionEventBus,
    get_session_event_bus,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.one_sentence_text_reply import reply_text_only_conversational
from services.kitty.session.turn_task import run_cancellable_turn
from services.kitty.session.one_sentence_turns import (
    persist_one_sentence_turn_from_voice_session,
)
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
            await run_cancellable_turn(
                runtime.voice_session_id,
                _handle_text_inbound(runtime, event.payload),
            )
        elif event.kind == "assistant_text":
            mem = get_session_memory(runtime.voice_session_id)
            chunk = event.payload.get("text")
            if isinstance(chunk, str):
                mem.append_assistant_chunk(chunk)
        elif event.kind == "assistant_done":
            get_session_memory(runtime.voice_session_id).flush_assistant_turn()
        elif event.kind == "diagram_mutated":
            bump_voice_mutation_freshness(runtime.voice_session_id)
        elif event.kind == "context_update":
            sess = voice_sessions.get(runtime.voice_session_id)
            if sess is not None:
                sess["_last_context_update_mono"] = time.monotonic()
        elif event.kind == "auto_complete_done":
            _record_auto_complete_done(runtime.voice_session_id, event.payload)

    bus.add_handler(_on_event)
    await bus.start()
    return bus


def _record_auto_complete_done(voice_session_id: str, payload: Dict[str, Any]) -> None:
    """Second generate observation when the canvas reports fill finished or failed."""
    session = voice_sessions.get(voice_session_id)
    status_raw = payload.get("status")
    status = status_raw.strip() if isinstance(status_raw, str) else "finished"
    node_raw = payload.get("node_id")
    node_id = node_raw.strip() if isinstance(node_raw, str) else None
    message_raw = payload.get("message")
    message = message_raw.strip() if isinstance(message_raw, str) else None
    observation = finish_pending_autocomplete(
        session if isinstance(session, dict) else None,
        status=status,
        node_id=node_id,
        message=message,
    )
    if observation is None:
        return
    action = str(observation.get("action") or "auto_complete")
    get_session_memory(voice_session_id).append_observation(
        summarize_payload_for_memory(observation, action=action),
        action=action,
    )


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
    """Handle keyboard or Fun-ASR committed text via the typed agent loop."""
    text = str(payload.get("text") or "").strip()
    if not text:
        return

    raw_request_id = payload.get("request_id")
    request_id = (
        str(raw_request_id).strip() if isinstance(raw_request_id, str) and str(raw_request_id).strip() else None
    )

    mem = get_session_memory(runtime.voice_session_id)
    mem.append_user_turn(text, source="text")

    session = voice_sessions.get(runtime.voice_session_id) or {}
    if request_id:
        session["_one_sentence_request_id"] = request_id
    session_context = dict(session.get("context") or {})
    ctx_phase = str(session_context.get("one_sentence_phase") or "").strip()
    user_phase = ctx_phase if ctx_phase in ("create", "edit") else "edit"
    if str(session.get("active_panel") or "") == "one_sentence":
        await persist_one_sentence_turn_from_voice_session(
            runtime.voice_session_id,
            role="user",
            content=text,
            source="ws_text",
            phase=user_phase,
            request_id=request_id,
        )

    result = await run_typed_agent_loop(
        runtime.websocket,
        runtime.voice_session_id,
        text,
        session_context,
    )
    if result.outcome == RouteOutcome.EXECUTED:
        return
    if result.outcome != RouteOutcome.CONVERSATIONAL_FALLBACK:
        return

    if str(session.get("active_panel") or "") == "one_sentence":
        ctx_phase = session_context.get("one_sentence_phase")
        if ctx_phase == "edit" or ctx_phase is None:
            return

    if await reply_text_only_conversational(
        runtime.websocket,
        runtime.voice_session_id,
        text,
        session_context,
    ):
        return

    logger.info(
        "[OneSentence] clarify fallback voice=%s request_id=%s",
        runtime.voice_session_id[:12],
        (request_id or "-")[:12],
    )
    await emit_user_ack(
        runtime.websocket,
        runtime.voice_session_id,
        "我暂时只能帮你改图或回答和这张图相关的问题，请再说具体一点。",
        reply_kind="final",
        one_sentence_outcome="clarify",
        request_id=request_id,
    )
