"""Deliver Kitty acknowledgment text to WebSocket (CosyVoice TTS in parallel)."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import WebSocket

from services.kitty.audio.session_bridge import speak_kitty_final_reply
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.desktop.kitty_voice_phase_fanout import (
    fanout_voice_phase_from_session,
)
from services.kitty.session.one_sentence_command_detail import normalize_command_detail
from services.kitty.session.one_sentence_turns import persist_one_sentence_turn_from_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.cosyvoice_realtime import resolve_kitty_tts_enabled


def _normalize_clarify_options(raw: Optional[list[Any]]) -> list[str]:
    """Keep up to three non-empty option labels for the one-sentence UI."""
    if not isinstance(raw, list):
        return []
    labels: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        if len(labels) >= 3:
            break
    return labels


def _session_request_id(voice_session_id: str) -> Optional[str]:
    session = voice_sessions.get(voice_session_id) or {}
    raw = session.get("_one_sentence_request_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


async def emit_user_ack(
    websocket: WebSocket,
    voice_session_id: str,
    text: str,
    *,
    also_omni: bool = False,
    one_sentence_action: str | None = None,
    one_sentence_outcome: str | None = None,
    one_sentence_user_text: str | None = None,
    reply_kind: str | None = None,
    clarify_question: str | None = None,
    clarify_options: list[str] | None = None,
    request_id: str | None = None,
    command_detail: dict[str, Any] | None = None,
) -> bool:
    """
    Send a user-facing ack on text_chunk and persist the one-sentence turn.

    Omni duplex is retired; ``also_omni`` is ignored (kept for call-site compat).
    Speaks via CosyVoice in parallel with the chat text (progress + final).
    ``reply_kind`` is ``progress`` for in-flight async canvas work; defaults to
    ``final`` so one-sentence chat dedupes against diagram ``user_summary``.
    Progress acks are UI-only (not durable history). Optional ``clarify_question`` /
    ``clarify_options`` drive one-sentence choice buttons.
    ``command_detail`` stores node-action / Bus proof for diagram activity tracking.
    """
    del also_omni
    message = str(text or "").strip()
    if not message:
        return False

    kind = reply_kind.strip() if isinstance(reply_kind, str) and reply_kind.strip() else "final"
    resolved_request_id = (
        request_id.strip()
        if isinstance(request_id, str) and request_id.strip()
        else _session_request_id(voice_session_id)
    )
    detail = normalize_command_detail(command_detail)

    payload: dict[str, Any] = {"type": "text_chunk", "text": message, "reply_kind": kind}
    if isinstance(one_sentence_action, str) and one_sentence_action.strip():
        payload["action"] = one_sentence_action.strip()
    if resolved_request_id:
        payload["request_id"] = resolved_request_id

    option_labels = _normalize_clarify_options(clarify_options)
    if option_labels:
        payload["clarify_options"] = option_labels
        question = clarify_question.strip() if isinstance(clarify_question, str) and clarify_question.strip() else ""
        if question:
            payload["clarify_question"] = question

    sent = await safe_websocket_send(websocket, payload)
    if sent:
        await fanout_voice_phase_from_session(voice_session_id, "speaking")

    # One durable kitty row per request — skip progress UI-only acks.
    if kind != "progress":
        await persist_one_sentence_turn_from_voice_session(
            voice_session_id,
            role="kitty",
            content=message,
            source="ack",
            phase="edit",
            action=one_sentence_action,
            outcome=one_sentence_outcome,
            user_text=one_sentence_user_text,
            request_id=resolved_request_id,
            command_detail=detail,
        )

    # Chat text and TTS start together; serial queue + barge-in handle overlap.
    session = voice_sessions.get(voice_session_id)
    tts_will_run = (
        resolve_kitty_tts_enabled() and isinstance(session, dict) and session.get("_kitty_tts_enabled") is not False
    )
    asyncio.create_task(speak_kitty_final_reply(websocket, voice_session_id, message))
    if sent and not tts_will_run:
        # Text-only / TTS off: reply is a single chunk, not a stream — return to idle.
        await fanout_voice_phase_from_session(voice_session_id, "active")

    return sent
