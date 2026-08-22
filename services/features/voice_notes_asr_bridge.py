"""Browser voice-notes WebSocket relay to Tencent realtime ASR V2.

Protocol (browser → server):
  {"type": "start", "diarization_enabled": true}
  {"type": "append", "audio": "<base64 pcm16>"}
  {"type": "stop"}

Protocol (server → browser):
  {"type": "started"}
  {"type": "snapshot", "sentences": [{"text": "...", "speaker_id": 0, "final": true}]}
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
from typing import Any, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from models.domain.auth import User
from services.features.tencent_asr_v2 import TencentAsrV2Client
from services.features.tencent_asr_v2_sentences import (
    TencentAsrSentence,
    normalize_speaker_context_id,
    parse_speaker_context_id,
    snapshot_browser_payload,
)
from services.features.tencent_asr_v2_errors import (
    TencentAsrClassifiedError,
    TencentAsrHandshakeError,
    browser_error_payload,
    format_tencent_asr_v2_log,
)
from services.features.voice_notes_usage import settle_voice_notes_usage
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.ws_limits import (
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
    receive_websocket_text_frame,
    safe_websocket_send_text,
)

logger = logging.getLogger(__name__)

ASR_CONFIG_USER_MESSAGE = "Speech service is not configured"


def voice_notes_error_json(code: str, message: str) -> str:
    """JSON error frame for the voice-notes browser client."""
    return json.dumps({"type": "error", "code": code, "message": message})


def voice_notes_diarization_enabled(start_msg: dict[str, Any]) -> bool:
    """Parse 区分说话人 from the bootstrap frame (engine is locked for the session)."""
    raw = start_msg.get("diarization_enabled")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _transcript_chars_from_sentences(sentences: list[TencentAsrSentence]) -> int:
    """Count committed (steady) sentence characters for usage settle."""
    return sum(len(item.text) for item in sentences if item.is_final)


async def run_voice_notes_asr_relay(
    client_ws: WebSocket,
    *,
    user: Optional[User] = None,
    diarization_enabled: bool = False,
    speaker_context_id: str = "",
    rate_limiter: Optional[WebsocketMessageRateLimiter] = None,
    max_inbound_text_bytes: int = DEFAULT_MAX_WS_TEXT_BYTES,
) -> None:
    """Relay authenticated browser PCM to Tencent ASR V2."""
    client: Optional[TencentAsrV2Client] = None
    stopped_emitted = False
    pcm_bytes = 0
    transcript_chars = 0
    started_at = time.monotonic()
    session_ok = True
    provider_failed = False

    async def emit(payload: dict[str, Any]) -> None:
        await safe_websocket_send_text(client_ws, json.dumps(payload))

    async def on_snapshot(sentences: list[TencentAsrSentence]) -> None:
        nonlocal transcript_chars
        transcript_chars = _transcript_chars_from_sentences(sentences)
        context_id = client.speaker_context_id if client is not None else ""
        await emit(snapshot_browser_payload(sentences, context_id))

    async def on_error(classified: TencentAsrClassifiedError) -> None:
        nonlocal session_ok, provider_failed
        session_ok = False
        provider_failed = True
        await emit(browser_error_payload(classified))

    async def emit_stopped() -> None:
        nonlocal stopped_emitted
        if stopped_emitted:
            return
        stopped_emitted = True
        await emit({"type": "stopped"})

    logger.debug("[VoiceNotesASR] Tencent relay diarization=%s", diarization_enabled)

    try:
        client = TencentAsrV2Client(
            on_snapshot=on_snapshot,
            on_error=on_error,
            speaker_diarization=diarization_enabled,
            speaker_context_id=parse_speaker_context_id({"speaker_context_id": speaker_context_id}),
        )
        await client.start()
        started: dict[str, Any] = {"type": "started"}
        started_context = normalize_speaker_context_id(client.speaker_context_id)
        if started_context:
            started["speaker_context_id"] = started_context
        await emit(started)

        while True:
            if provider_failed:
                break
            try:
                msg = await receive_websocket_text_frame(client_ws)
            except WebSocketDisconnect:
                break
            if provider_failed:
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

            if msg_type == "append":
                if provider_failed:
                    break
                audio_b64 = data.get("audio")
                if not audio_b64 or not isinstance(audio_b64, str):
                    continue
                try:
                    pcm = base64.b64decode(audio_b64, validate=False)
                except (binascii.Error, ValueError):
                    continue
                pcm_bytes += len(pcm)
                if client is not None:
                    await client.send_pcm(pcm)
                if provider_failed:
                    break
                continue

            if msg_type == "stop":
                if client is not None:
                    await client.finish()
                    client = None
                await emit_stopped()
                break

    except TencentAsrHandshakeError as exc:
        session_ok = False
        voice_id = client.voice_id if client is not None else ""
        logger.warning(
            "[VoiceNotesASR] %s",
            format_tencent_asr_v2_log(
                exc.classified,
                voice_id=voice_id,
                phase="handshake",
            ),
        )
        await emit(browser_error_payload(exc.classified))
    except RuntimeError as exc:
        session_ok = False
        logger.warning("[VoiceNotesASR] Start failed: %s", exc)
        await emit({"type": "error", "code": "asr_config", "message": ASR_CONFIG_USER_MESSAGE})
    except LLM_PIPELINE_ERRORS as exc:
        session_ok = False
        logger.warning("[VoiceNotesASR] Relay failed: %s", exc)
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
