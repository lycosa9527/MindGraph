"""Speak-only lecture narration (no command router, no one-sentence persist)."""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from services.kitty.audio.session_bridge import speak_kitty_final_reply
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.cosyvoice_realtime import resolve_kitty_tts_enabled
from services.kitty.tts.lecture_cache import log_lecture_tts, schedule_lecture_prefetch
from services.kitty.ws.guards import KITTY_WS_MAX_TEXT_CHARS


async def handle_kitty_narrate(
    websocket: WebSocket,
    voice_session_id: str,
    message: dict[str, Any],
) -> None:
    """TTS a lecture caption without treating it as user ingress."""
    text = str(message.get("text") or "").strip()
    if not text:
        return
    if len(text) > KITTY_WS_MAX_TEXT_CHARS:
        await safe_websocket_send(websocket, {"type": "error", "error": "Text too long"})
        return
    step_id = str(message.get("step_id") or "").strip()
    prefetch_text = str(message.get("prefetch_text") or "").strip()
    prefetch_step_id = str(message.get("prefetch_step_id") or "").strip()
    log_lecture_tts(
        "narrate",
        voice_session_id=voice_session_id,
        step_id=step_id,
        detail=f"chars={len(text)} channel=tts",
    )
    payload: dict[str, Any] = {"type": "text_chunk", "text": text, "reply_kind": "lecture"}
    if step_id:
        payload["step_id"] = step_id
    await safe_websocket_send(websocket, payload)
    done: dict[str, Any] = {"type": "tts_done", "lecture": True}
    if step_id:
        done["step_id"] = step_id
    session = voice_sessions.get(voice_session_id)
    if not isinstance(session, dict) or not resolve_kitty_tts_enabled():
        log_lecture_tts(
            "narrate_skip",
            voice_session_id=voice_session_id,
            step_id=step_id,
            detail="reason=no_session_or_tts_off",
        )
        await safe_websocket_send(websocket, done)
        return
    session["_kitty_lecture"] = True
    if step_id:
        session["_kitty_lecture_step_id"] = step_id
    else:
        session.pop("_kitty_lecture_step_id", None)
    try:
        await speak_kitty_final_reply(websocket, voice_session_id, text, force=True)
    finally:
        live = voice_sessions.get(voice_session_id)
        if isinstance(live, dict):
            live["_kitty_lecture"] = False
            live.pop("_kitty_lecture_step_id", None)
    if prefetch_text:
        schedule_lecture_prefetch(voice_session_id, prefetch_text, prefetch_step_id)
