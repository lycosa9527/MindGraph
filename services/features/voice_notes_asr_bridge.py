"""Browser voice-notes WebSocket relay to DashScope Fun-ASR realtime.

Protocol (browser → server):
  {"type": "start", "language_hints": ["zh"]}
  {"type": "append", "audio": "<base64 pcm16>"}
  {"type": "stop"}

Protocol (server → browser):
  {"type": "started"}
  {"type": "partial", "text": "...", "final": false}
  {"type": "final", "text": "..."}
  {"type": "stopped"}
  {"type": "error", "code": "...", "message": "..."}

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import time
from typing import Any, List, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from models.domain.auth import User
from services.features.voice_notes_usage import settle_voice_notes_usage
from services.kitty.asr.fun_asr_realtime import FunAsrRealtimeClient
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.ws_limits import (
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
    receive_websocket_text_frame,
    safe_websocket_send_text,
)

logger = logging.getLogger(__name__)


def voice_notes_error_json(code: str, message: str) -> str:
    """JSON error frame for the voice-notes browser client."""
    return json.dumps({"type": "error", "code": code, "message": message})


async def run_voice_notes_asr_relay(
    client_ws: WebSocket,
    *,
    user: Optional[User] = None,
    language_hints: Optional[List[str]] = None,
    rate_limiter: Optional[WebsocketMessageRateLimiter] = None,
    max_inbound_text_bytes: int = DEFAULT_MAX_WS_TEXT_BYTES,
) -> None:
    """Relay authenticated browser PCM to Fun-ASR with meeting punctuation."""
    client: Optional[FunAsrRealtimeClient] = None
    stopped_emitted = False
    pcm_bytes = 0
    transcript_chars = 0
    started_at = time.monotonic()
    session_ok = True

    async def emit(payload: dict[str, Any]) -> None:
        await safe_websocket_send_text(client_ws, json.dumps(payload))

    async def on_partial(text: str, sentence_end: bool) -> None:
        nonlocal transcript_chars
        if sentence_end:
            transcript_chars += len(str(text or "").strip())
            await emit({"type": "final", "text": text})
        else:
            await emit({"type": "partial", "text": text, "final": False})

    async def on_error(message: str) -> None:
        nonlocal session_ok
        session_ok = False
        await emit({"type": "error", "code": "upstream", "message": message})

    async def emit_stopped() -> None:
        nonlocal stopped_emitted
        if stopped_emitted:
            return
        stopped_emitted = True
        await emit({"type": "stopped"})

    try:
        client = FunAsrRealtimeClient(
            on_partial=on_partial,
            on_error=on_error,
            language_hints=language_hints,
            semantic_punctuation_enabled=True,
        )
        await client.start()
        await emit({"type": "started"})

        while True:
            try:
                msg = await receive_websocket_text_frame(client_ws)
            except WebSocketDisconnect:
                break

            if inbound_text_exceeds_limit(msg, max_inbound_text_bytes):
                session_ok = False
                await emit({"type": "error", "code": "too_large", "message": "Message too large"})
                break

            if rate_limiter is not None and not rate_limiter.allow():
                session_ok = False
                await emit({"type": "error", "code": "rate_limit", "message": "Too many messages"})
                break

            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue

            if not isinstance(data, dict):
                continue

            msg_type = data.get("type")
            if msg_type == "start":
                continue

            if msg_type in ("append", "input_audio_buffer.append"):
                audio_b64 = data.get("audio") or data.get("data")
                if not audio_b64 or not isinstance(audio_b64, str):
                    continue
                try:
                    pcm = base64.b64decode(audio_b64, validate=False)
                except (binascii.Error, ValueError):
                    continue
                pcm_bytes += len(pcm)
                if client is not None:
                    await client.send_pcm(pcm)
                continue

            if msg_type in ("stop", "finish", "session.finish"):
                if client is not None:
                    await client.finish()
                    client = None
                await emit_stopped()
                break

    except RuntimeError as exc:
        session_ok = False
        logger.warning("[VoiceNotesASR] Start failed: %s", exc)
        await emit({"type": "error", "code": "asr_config", "message": str(exc)})
    except LLM_PIPELINE_ERRORS as exc:
        session_ok = False
        logger.exception("[VoiceNotesASR] Relay failed: %s", exc)
        await emit({"type": "error", "code": "relay", "message": "Speech relay error"})
    finally:
        if client is not None:
            try:
                await client.finish()
            except LLM_PIPELINE_ERRORS:
                pass
            client = None
        try:
            await emit_stopped()
        except LLM_PIPELINE_ERRORS:
            pass
        if user is not None:
            try:
                await settle_voice_notes_usage(
                    user=user,
                    pcm_bytes=pcm_bytes,
                    transcript_chars=transcript_chars,
                    started_at=started_at,
                    success=session_ok,
                )
            except LLM_PIPELINE_ERRORS as exc:
                logger.debug("[VoiceNotesASR] settle skipped: %s", exc)
