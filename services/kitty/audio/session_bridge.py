"""Per-session Fun-ASR / CosyVoice helpers attached to Kitty voice sessions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Optional

from fastapi import WebSocket
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from services.kitty.asr.fun_asr_realtime import FunAsrRealtimeClient
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.desktop.kitty_voice_phase_fanout import (
    fanout_voice_phase_from_outbound_type,
    fanout_voice_phase_from_session,
)
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.cosyvoice_realtime import CosyVoiceRealtimeClient, resolve_kitty_tts_enabled
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

# Session keys for serial TTS (industry: one utterance at a time; barge-in clears queue).
_TTS_QUEUE_KEY = "_kitty_tts_queue"
_TTS_WORKER_KEY = "_kitty_tts_worker"
_TTS_GENERATION_KEY = "_kitty_tts_generation"
_TTS_SPEAKING_KEY = "_kitty_tts_speaking"
_COSYVOICE_KEY = "_cosyvoice_client"


def _tts_generation(session: dict[str, Any]) -> int:
    raw = session.get(_TTS_GENERATION_KEY)
    return int(raw) if isinstance(raw, int) else 0


def _bump_tts_generation(session: dict[str, Any]) -> int:
    nxt = _tts_generation(session) + 1
    session[_TTS_GENERATION_KEY] = nxt
    return nxt


def _drain_tts_queue(session: dict[str, Any]) -> None:
    queue = session.get(_TTS_QUEUE_KEY)
    if not isinstance(queue, asyncio.Queue):
        return
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break


async def interrupt_kitty_tts(voice_session_id: str) -> None:
    """Barge-in: cancel in-flight CosyVoice, drain pending utterances, notify client."""
    session = voice_sessions.get(voice_session_id)
    if not session:
        return
    _bump_tts_generation(session)
    _drain_tts_queue(session)
    session[_TTS_SPEAKING_KEY] = False
    client = session.get(_COSYVOICE_KEY)
    if isinstance(client, CosyVoiceRealtimeClient):
        try:
            await client.interrupt()
        except LLM_PIPELINE_ERRORS as exc:
            logger.debug("CosyVoice interrupt skipped: %s", exc)
        try:
            await client.close()
        except LLM_PIPELINE_ERRORS as exc:
            logger.debug("CosyVoice close after interrupt skipped: %s", exc)
        session[_COSYVOICE_KEY] = None
    await fanout_voice_phase_from_outbound_type(voice_session_id, "tts_interrupted")


async def _get_or_create_cosyvoice_client(
    websocket: WebSocket,
    voice_session_id: str,
    session: dict[str, Any],
) -> CosyVoiceRealtimeClient:
    """Reuse CosyVoice client across serial utterances (do not tear down mid-speak)."""

    existing = session.get(_COSYVOICE_KEY)
    if isinstance(existing, CosyVoiceRealtimeClient):
        return existing

    async def on_audio(audio_b64: str, fmt: str) -> None:
        await safe_websocket_send(
            websocket,
            {"type": "audio_chunk", "audio": audio_b64, "format": fmt},
        )
        await fanout_voice_phase_from_outbound_type(voice_session_id, "audio_chunk")

    async def on_done() -> None:
        await safe_websocket_send(websocket, {"type": "tts_done"})
        await fanout_voice_phase_from_outbound_type(voice_session_id, "tts_done")

    async def on_error(err: str) -> None:
        logger.warning("CosyVoice error session=%s: %s", voice_session_id, err)

    client = CosyVoiceRealtimeClient(on_audio=on_audio, on_done=on_done, on_error=on_error)
    session[_COSYVOICE_KEY] = client
    return client


async def _tts_worker_loop(voice_session_id: str) -> None:
    """Serialize TTS: finish one utterance before starting the next."""
    while True:
        session = voice_sessions.get(voice_session_id)
        if not isinstance(session, dict):
            return
        queue = session.get(_TTS_QUEUE_KEY)
        if not isinstance(queue, asyncio.Queue):
            return
        item = await queue.get()
        if item is None:
            return
        websocket, text, generation = item
        live = voice_sessions.get(voice_session_id)
        if not isinstance(live, dict):
            return
        if generation != _tts_generation(live):
            continue
        if live.get("_kitty_tts_enabled") is False:
            continue
        if not resolve_kitty_tts_enabled():
            continue
        live[_TTS_SPEAKING_KEY] = True
        try:
            client = await _get_or_create_cosyvoice_client(websocket, voice_session_id, live)
            await client.speak(text)
        except LLM_PIPELINE_ERRORS as exc:
            logger.warning("CosyVoice speak failed: %s", exc)
            live[_COSYVOICE_KEY] = None
            await safe_websocket_send(
                websocket,
                {"type": "error", "error": f"TTS failed: {exc}"},
            )
        finally:
            cur = voice_sessions.get(voice_session_id)
            if isinstance(cur, dict):
                cur[_TTS_SPEAKING_KEY] = False


def _ensure_tts_worker(voice_session_id: str, session: dict[str, Any]) -> asyncio.Queue:
    queue = session.get(_TTS_QUEUE_KEY)
    if not isinstance(queue, asyncio.Queue):
        queue = asyncio.Queue()
        session[_TTS_QUEUE_KEY] = queue
    worker = session.get(_TTS_WORKER_KEY)
    if not isinstance(worker, asyncio.Task) or worker.done():
        session[_TTS_WORKER_KEY] = asyncio.create_task(
            _tts_worker_loop(voice_session_id),
            name=f"kitty-tts-{voice_session_id[:12]}",
        )
    return queue


async def speak_kitty_final_reply(
    websocket: WebSocket,
    voice_session_id: str,
    text: str,
) -> None:
    """
    Enqueue a Kitty reply for CosyVoice (serial per session).

    Concurrent fire-and-forget speaks are rejected by design: overlapping
    synthesis tears down the prior stream mid-utterance. Industry pattern is
    a single playback queue; barge-in clears it via ``interrupt_kitty_tts``.
    """
    if not resolve_kitty_tts_enabled():
        return
    message = str(text or "").strip()
    if not message:
        return
    session = voice_sessions.get(voice_session_id)
    if not session:
        return
    if session.get("_kitty_tts_enabled") is False:
        return

    queue = _ensure_tts_worker(voice_session_id, session)
    await queue.put((websocket, message, _tts_generation(session)))


async def start_session_asr(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    language_hints: Optional[list[str]] = None,
) -> None:
    """Start Fun-ASR for this Kitty session (one task per mic session)."""
    await interrupt_kitty_tts(voice_session_id)
    await safe_websocket_send(websocket, {"type": "tts_interrupted"})
    session = voice_sessions.get(voice_session_id)
    if not session:
        return
    existing = session.get("_fun_asr_client")
    session["_fun_asr_client"] = None
    if isinstance(existing, FunAsrRealtimeClient):
        # Do not await DashScope teardown on the Kitty WS loop (can hang ~10s).
        asyncio.create_task(_finish_asr_client_background(existing))

    async def on_partial(text: str, sentence_end: bool) -> None:
        msg_type = "asr_final" if sentence_end else "asr_partial"
        await safe_websocket_send(websocket, {"type": msg_type, "text": text})

    async def on_error(err: str) -> None:
        await safe_websocket_send(websocket, {"type": "error", "error": f"ASR failed: {err}"})

    client = FunAsrRealtimeClient(
        on_partial=on_partial,
        on_error=on_error,
        language_hints=language_hints,
    )
    session["_fun_asr_client"] = client
    try:
        await client.start()
        await safe_websocket_send(websocket, {"type": "asr_started"})
        await fanout_voice_phase_from_session(voice_session_id, "listening")
    except LLM_PIPELINE_ERRORS as exc:
        session["_fun_asr_client"] = None
        logger.warning("Fun-ASR start failed: %s", exc)
        await safe_websocket_send(websocket, {"type": "error", "error": f"ASR start failed: {exc}"})


async def feed_session_asr_audio(voice_session_id: str, audio_b64: str) -> None:
    """Decode base64 PCM and forward to Fun-ASR."""
    session = voice_sessions.get(voice_session_id)
    if not session:
        return
    client = session.get("_fun_asr_client")
    if not isinstance(client, FunAsrRealtimeClient):
        return
    try:
        pcm = base64.b64decode(audio_b64)
    except (ValueError, TypeError):
        return
    await client.send_pcm(pcm)


async def _finish_asr_client_background(client: FunAsrRealtimeClient) -> None:
    """Best-effort Fun-ASR finish/close off the Kitty inbound loop."""
    try:
        await client.finish()
    except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK, OSError) as exc:
        logger.debug("Fun-ASR background finish: %s", exc)
    except LLM_PIPELINE_ERRORS as exc:
        logger.debug("Fun-ASR background finish pipeline error: %s", exc)


async def stop_session_asr(voice_session_id: str) -> None:
    """Finish Fun-ASR and flush ``asr_final`` before returning (bounded).

    Awaiting DashScope forever would block later Kitty frames, so finish is
    capped. We still wait long enough for the final transcript — fire-and-forget
    teardown was dropping ``asr_final`` on PTT release.
    """
    session = voice_sessions.get(voice_session_id)
    if not session:
        return
    client = session.get("_fun_asr_client")
    session["_fun_asr_client"] = None
    if not isinstance(client, FunAsrRealtimeClient):
        return
    try:
        await asyncio.wait_for(client.finish(), timeout=3.0)
    except asyncio.TimeoutError:
        logger.warning("Fun-ASR finish timed out for session %s", voice_session_id[:12])
        asyncio.create_task(_finish_asr_client_background(client))
    except LLM_PIPELINE_ERRORS as exc:
        logger.debug("Fun-ASR stop pipeline error: %s", exc)
        asyncio.create_task(_finish_asr_client_background(client))


async def teardown_session_audio(voice_session_id: str) -> None:
    """Close ASR + TTS clients on Kitty disconnect."""
    session = voice_sessions.get(voice_session_id)
    if not session:
        return
    _bump_tts_generation(session)
    _drain_tts_queue(session)
    queue = session.get(_TTS_QUEUE_KEY)
    if isinstance(queue, asyncio.Queue):
        await queue.put(None)
    worker = session.pop(_TTS_WORKER_KEY, None)
    if isinstance(worker, asyncio.Task) and not worker.done():
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
    session.pop(_TTS_QUEUE_KEY, None)
    asr = session.pop("_fun_asr_client", None)
    if isinstance(asr, FunAsrRealtimeClient):
        await asr.close()
    tts = session.pop(_COSYVOICE_KEY, None)
    if isinstance(tts, CosyVoiceRealtimeClient):
        await tts.close()
