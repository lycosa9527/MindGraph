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
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
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
_ASR_AUDIO_FRAMES_KEY = "_fun_asr_audio_frames"
_ASR_AUDIO_BYTES_KEY = "_fun_asr_audio_bytes"
_ASR_FIRST_AUDIO_LOGGED_KEY = "_fun_asr_first_audio_logged"
_ASR_DROPPED_BEFORE_START_KEY = "_fun_asr_dropped_before_start"
_ASR_UTTERANCE_ID_KEY = "_fun_asr_utterance_id"
_ASR_LAST_TEXT_KEY = "_fun_asr_last_text"


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
            {
                "type": "audio_chunk",
                "audio": audio_b64,
                "format": fmt,
                "sample_rate": 22050,
            },
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


def _reset_asr_audio_counters(session: dict[str, Any]) -> None:
    """Clear per-hold PCM counters used for PTT debug logs."""
    session[_ASR_AUDIO_FRAMES_KEY] = 0
    session[_ASR_AUDIO_BYTES_KEY] = 0
    session[_ASR_FIRST_AUDIO_LOGGED_KEY] = False
    session[_ASR_DROPPED_BEFORE_START_KEY] = 0
    session[_ASR_LAST_TEXT_KEY] = ""
    session[_ASR_UTTERANCE_ID_KEY] = None


def _session_client_lane(session: dict[str, Any]) -> str:
    """Session client lane."""
    lane = session.get("_kitty_client_lane")
    return lane if isinstance(lane, str) and lane.strip() else "—"


async def start_session_asr(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    language_hints: Optional[list[str]] = None,
    utterance_id: Optional[str] = None,
) -> None:
    """Start Fun-ASR for this Kitty session (one task per mic session)."""
    await interrupt_kitty_tts(voice_session_id)
    await safe_websocket_send(websocket, {"type": "tts_interrupted"})
    session = voice_sessions.get(voice_session_id)
    if not session:
        logger.warning(
            "Fun-ASR start ignored — no voice session %s",
            voice_session_id[:12],
        )
        kitty_wf_log(
            "asr_start_rejected",
            "no_session",
            voice_session_id=voice_session_id,
        )
        return
    lane = _session_client_lane(session)
    _reset_asr_audio_counters(session)
    session[_ASR_UTTERANCE_ID_KEY] = utterance_id
    existing = session.get("_fun_asr_client")
    session["_fun_asr_client"] = None
    if isinstance(existing, FunAsrRealtimeClient):
        # Do not await DashScope teardown on the Kitty WS loop (can hang ~10s).
        asyncio.create_task(_finish_asr_client_background(existing))

    async def on_partial(text: str, sentence_end: bool) -> None:
        # Provider sentence_end is still a partial hold update — FE submits on stop.
        msg_type = "asr_final" if sentence_end else "asr_partial"
        session[_ASR_LAST_TEXT_KEY] = text
        if sentence_end:
            kitty_wf_log(
                "asr_final",
                text[:120],
                voice_session_id=voice_session_id,
            )
            logger.info(
                "Fun-ASR final sid=%s lane=%s text=%s",
                voice_session_id[:12],
                lane,
                text[:80],
            )
        payload: dict[str, object] = {"type": msg_type, "text": text}
        active_utt = session.get(_ASR_UTTERANCE_ID_KEY)
        if isinstance(active_utt, str) and active_utt.strip():
            payload["utterance_id"] = active_utt
        await safe_websocket_send(websocket, payload)

    async def on_error(err: str) -> None:
        logger.warning(
            "Fun-ASR runtime error sid=%s lane=%s: %s",
            voice_session_id[:12],
            lane,
            err,
        )
        kitty_wf_log(
            "asr_error",
            err,
            voice_session_id=voice_session_id,
        )
        err_payload: dict[str, object] = {"type": "error", "error": f"ASR failed: {err}"}
        active_utt = session.get(_ASR_UTTERANCE_ID_KEY)
        if isinstance(active_utt, str) and active_utt.strip():
            err_payload["utterance_id"] = active_utt
        await safe_websocket_send(websocket, err_payload)

    client = FunAsrRealtimeClient(
        on_partial=on_partial,
        on_error=on_error,
        language_hints=language_hints,
    )
    session["_fun_asr_client"] = client
    try:
        await client.start()
        started_payload: dict[str, object] = {"type": "asr_started"}
        if utterance_id:
            started_payload["utterance_id"] = utterance_id
        await safe_websocket_send(websocket, started_payload)
        await fanout_voice_phase_from_session(voice_session_id, "listening")
        hints = language_hints or ["zh"]
        logger.info(
            "Fun-ASR started sid=%s lane=%s hints=%s utt=%s",
            voice_session_id[:12],
            lane,
            hints,
            (utterance_id or "—")[:16],
        )
        kitty_wf_log(
            "asr_started",
            f"lane={lane} hints={hints} utt={utterance_id or '—'}",
            voice_session_id=voice_session_id,
        )
    except LLM_PIPELINE_ERRORS as exc:
        session["_fun_asr_client"] = None
        logger.warning(
            "Fun-ASR start failed sid=%s lane=%s: %s",
            voice_session_id[:12],
            lane,
            exc,
        )
        kitty_wf_log(
            "asr_start_failed",
            str(exc),
            voice_session_id=voice_session_id,
        )
        fail_payload: dict[str, object] = {
            "type": "error",
            "error": f"ASR start failed: {exc}",
        }
        if utterance_id:
            fail_payload["utterance_id"] = utterance_id
        await safe_websocket_send(websocket, fail_payload)


async def feed_session_asr_audio(
    voice_session_id: str,
    audio_b64: str,
    *,
    utterance_id: Optional[str] = None,
) -> None:
    """Decode base64 PCM and forward to Fun-ASR."""
    session = voice_sessions.get(voice_session_id)
    if not session:
        return
    active_utt = session.get(_ASR_UTTERANCE_ID_KEY)
    if utterance_id and isinstance(active_utt, str) and active_utt.strip() and utterance_id != active_utt:
        return
    client = session.get("_fun_asr_client")
    if not isinstance(client, FunAsrRealtimeClient):
        dropped = int(session.get(_ASR_DROPPED_BEFORE_START_KEY) or 0) + 1
        session[_ASR_DROPPED_BEFORE_START_KEY] = dropped
        if dropped == 1:
            lane = _session_client_lane(session)
            logger.info(
                "Fun-ASR audio before ready sid=%s lane=%s (client will keep sending)",
                voice_session_id[:12],
                lane,
            )
            kitty_wf_log(
                "asr_audio_dropped",
                f"lane={lane} before_asr_ready",
                voice_session_id=voice_session_id,
            )
        return
    try:
        pcm = base64.b64decode(audio_b64)
    except (ValueError, TypeError):
        logger.debug("Fun-ASR invalid base64 audio sid=%s", voice_session_id[:12])
        return
    frames = int(session.get(_ASR_AUDIO_FRAMES_KEY) or 0) + 1
    nbytes = int(session.get(_ASR_AUDIO_BYTES_KEY) or 0) + len(pcm)
    session[_ASR_AUDIO_FRAMES_KEY] = frames
    session[_ASR_AUDIO_BYTES_KEY] = nbytes
    if not session.get(_ASR_FIRST_AUDIO_LOGGED_KEY):
        session[_ASR_FIRST_AUDIO_LOGGED_KEY] = True
        lane = _session_client_lane(session)
        logger.info(
            "Fun-ASR first audio frame sid=%s lane=%s bytes=%d",
            voice_session_id[:12],
            lane,
            len(pcm),
        )
        kitty_wf_log(
            "asr_audio_first",
            f"lane={lane} bytes={len(pcm)}",
            voice_session_id=voice_session_id,
        )
    await client.send_pcm(pcm)


async def _finish_asr_client_background(client: FunAsrRealtimeClient) -> None:
    """Best-effort Fun-ASR finish/close off the Kitty inbound loop."""
    try:
        await client.finish()
    except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK, OSError) as exc:
        logger.debug("Fun-ASR background finish: %s", exc)
    except LLM_PIPELINE_ERRORS as exc:
        logger.debug("Fun-ASR background finish pipeline error: %s", exc)


async def stop_session_asr(
    voice_session_id: str,
    *,
    utterance_id: Optional[str] = None,
) -> str:
    """Finish Fun-ASR and flush ``asr_final`` before returning (bounded).

    Awaiting DashScope forever would block later Kitty frames, so finish is
    capped. We still wait long enough for the final transcript — fire-and-forget
    teardown was dropping ``asr_final`` on PTT release.

    Returns the last transcript text for this utterance (may be empty).
    """
    session = voice_sessions.get(voice_session_id)
    if not session:
        return ""
    active_utt = session.get(_ASR_UTTERANCE_ID_KEY)
    if utterance_id and isinstance(active_utt, str) and active_utt.strip() and utterance_id != active_utt:
        return ""
    client = session.get("_fun_asr_client")
    session["_fun_asr_client"] = None
    frames = int(session.get(_ASR_AUDIO_FRAMES_KEY) or 0)
    nbytes = int(session.get(_ASR_AUDIO_BYTES_KEY) or 0)
    dropped = int(session.get(_ASR_DROPPED_BEFORE_START_KEY) or 0)
    lane = _session_client_lane(session)
    logger.info(
        "Fun-ASR stop sid=%s lane=%s frames=%d bytes=%d dropped_before_ready=%d has_client=%s",
        voice_session_id[:12],
        lane,
        frames,
        nbytes,
        dropped,
        isinstance(client, FunAsrRealtimeClient),
    )
    kitty_wf_log(
        "asr_stop_summary",
        f"lane={lane} frames={frames} bytes={nbytes} dropped={dropped}",
        voice_session_id=voice_session_id,
    )
    if not isinstance(client, FunAsrRealtimeClient):
        last = session.get(_ASR_LAST_TEXT_KEY)
        return last if isinstance(last, str) else ""
    try:
        await asyncio.wait_for(client.finish(), timeout=3.0)
    except asyncio.TimeoutError:
        logger.warning("Fun-ASR finish timed out for session %s", voice_session_id[:12])
        asyncio.create_task(_finish_asr_client_background(client))
    except LLM_PIPELINE_ERRORS as exc:
        logger.debug("Fun-ASR stop pipeline error: %s", exc)
        asyncio.create_task(_finish_asr_client_background(client))
    last = session.get(_ASR_LAST_TEXT_KEY)
    return last if isinstance(last, str) else ""


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
