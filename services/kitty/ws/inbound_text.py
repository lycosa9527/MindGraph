"""Ingest Kitty user text (typed or Fun-ASR) onto the session bus.

Watch / phone PTT used to echo the transcript after ``asr_stopped``. Short
holds often never sent that echo, so ASR finished and Kitty sat idle. The
server now ingests the Fun-ASR transcript on stop; a later client ``text``
with the same ``utterance_id`` is ignored.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.session.events import KittyEvent, get_session_event_bus
from services.kitty.session.manager import get_kitty_session_manager
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.session.turn_task import cancel_active_turn
from services.kitty.ws.guards import KITTY_WS_MAX_TEXT_CHARS
from services.kitty.ws.inbound_types import KittyInboundFlow, KittyWsInboundContext

logger = logging.getLogger(__name__)

ASR_COMMITTED_UTTERANCE_KEY = "_asr_committed_utterance_id"
INGRESS_SOURCES = frozenset({"asr", "text", "clarify_choice", "ui_create"})


def asr_utterance_already_ingested(voice_session_id: str, utterance_id: Optional[str]) -> bool:
    """True when ``asr_stop`` already pushed this utterance onto the bus."""
    utt = (utterance_id or "").strip()
    if not utt:
        return False
    session = voice_sessions.get(voice_session_id)
    if not isinstance(session, dict):
        return False
    stored = session.get(ASR_COMMITTED_UTTERANCE_KEY)
    return isinstance(stored, str) and stored == utt


def mark_asr_utterance_ingested(voice_session_id: str, utterance_id: Optional[str]) -> None:
    """Remember the Fun-ASR utterance so a client echo cannot start a second turn."""
    utt = (utterance_id or "").strip()
    if not utt:
        return
    session = voice_sessions.get(voice_session_id)
    if isinstance(session, dict):
        session[ASR_COMMITTED_UTTERANCE_KEY] = utt


@dataclass(frozen=True, slots=True)
class KittyTextIngest:
    """Optional fields for :func:`ingest_kitty_user_text`."""

    utterance_id: Optional[str] = None
    ingress_source: str = "text"
    request_id: str = ""
    cancel_prior: bool = True


def _resolve_ingress_source(raw: object) -> str:
    if isinstance(raw, str) and raw.strip() in INGRESS_SOURCES:
        return raw.strip()
    return "text"


async def ingest_kitty_user_text(
    ctx: KittyWsInboundContext,
    text: str,
    ingest: KittyTextIngest | None = None,
) -> KittyInboundFlow:
    """Validate, gate, and emit ``text_inbound`` for one user turn."""
    fields = ingest if ingest is not None else KittyTextIngest()
    if fields.cancel_prior:
        await cancel_active_turn(ctx.voice_session_id, reason="text_input")
    cleaned = text.strip()
    if len(cleaned) > KITTY_WS_MAX_TEXT_CHARS:
        await safe_websocket_send(
            ctx.websocket,
            {"type": "error", "error": "Text too long"},
        )
        return "continue"
    if not cleaned:
        return "continue"
    session = voice_sessions.get(ctx.voice_session_id)
    if not isinstance(session, dict):
        return "continue"
    logger.debug("Received text message (%d chars)", len(cleaned))
    kitty_wf_log(
        "text_inbound",
        cleaned[:120],
        voice_session_id=ctx.voice_session_id,
    )
    history = session.get("conversation_history")
    if isinstance(history, list):
        history.append({"role": "user", "content": cleaned})
    resolved_request = fields.request_id.strip() if fields.request_id.strip() else str(uuid.uuid4())
    session["_one_sentence_request_id"] = resolved_request
    source = _resolve_ingress_source(fields.ingress_source)
    raw_utt = fields.utterance_id
    utt = raw_utt.strip() if isinstance(raw_utt, str) and raw_utt.strip() else None
    if utt:
        session["_one_sentence_utterance_id"] = utt
    lane_raw = session.get("_kitty_client_lane")
    lane = lane_raw.strip() if isinstance(lane_raw, str) and lane_raw.strip() else None
    if lane != "mobile":
        gate = await get_kitty_session_manager().require_desktop_ingress_allowed(
            int(ctx.current_user.id),
            ctx.diagram_session_id,
            voice_session_id=ctx.voice_session_id,
            request_id=resolved_request,
        )
        if not gate.ok:
            await safe_websocket_send(
                ctx.websocket,
                {
                    "type": "error",
                    "error": gate.error_code or "mobile_owns_ingress",
                    "message": gate.message or "Mobile Kitty owns edit input for this diagram",
                    "request_id": resolved_request,
                },
            )
            return "continue"
    await get_kitty_session_manager().begin_ingress(
        user_id=int(ctx.current_user.id),
        scope=ctx.diagram_session_id,
        request_id=resolved_request,
        source=source,
        text=cleaned,
        lane=lane,
        voice_session_id=ctx.voice_session_id,
        utterance_id=utt,
    )
    inbound_payload: Dict[str, Any] = {
        "text": cleaned,
        "request_id": resolved_request,
        "ingress_source": source,
    }
    if utt:
        inbound_payload["utterance_id"] = utt
    await get_session_event_bus(ctx.voice_session_id).emit(
        KittyEvent(
            kind="text_inbound",
            voice_session_id=ctx.voice_session_id,
            payload=inbound_payload,
        )
    )
    return "continue"
