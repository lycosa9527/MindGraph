"""Lookahead CosyVoice cache for Mind Classroom lecture slides.

While slide N plays, synthesize slide N+1 on a second CosyVoice socket and
hold PCM in memory. The next narrate plays the buffer instead of reconnecting.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Optional

from fastapi import WebSocket

from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.desktop.kitty_voice_phase_fanout import fanout_voice_phase_from_outbound_type
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.cosyvoice_realtime import CosyVoiceRealtimeClient, resolve_kitty_tts_enabled
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

PREFETCH_KEY = "_kitty_lecture_prefetch"
_PREFETCH_TOKEN_KEY = "_kitty_lecture_prefetch_token"
# Only wait if CosyVoice is about to finish. A long wait silences the lecture.
PREFETCH_GRACE_SEC = 0.4


class LecturePrefetch:
    """One in-flight or ready next-slide PCM buffer."""

    def __init__(self, *, step_id: str, text: str, token: int) -> None:
        self.step_id = step_id
        self.text = text
        self.token = token
        self.chunks: list[tuple[str, str]] = []
        self.ready = asyncio.Event()
        self.failed = False
        self.task: Optional[asyncio.Task[None]] = None
        self.client: Optional[CosyVoiceRealtimeClient] = None

    def matches(self, text: str, step_id: str) -> bool:
        """True when the requested narrate is this buffered caption."""
        if self.text != text:
            return False
        if step_id and self.step_id and step_id != self.step_id:
            return False
        return True


def log_lecture_tts(
    event: str,
    *,
    voice_session_id: str,
    step_id: str = "",
    detail: str = "",
) -> None:
    """INFO + workflow line. Lecture uses CosyVoice TTS, not Fun-ASR."""
    step = step_id.strip() or "—"
    extra = f" {detail}".rstrip()
    logger.info(
        "[MindClassroom] TTS %s sid=%s step=%s asr=0%s",
        event,
        voice_session_id[:10],
        step,
        extra,
    )
    kitty_wf_log(
        "lecture_tts",
        f"{event}{extra}",
        voice_session_id=voice_session_id,
        extra={"module": "tts", "step": step, "channel": "tts", "asr": 0},
    )


async def cancel_lecture_prefetch(session: dict[str, Any]) -> None:
    """Drop the lookahead buffer and close its CosyVoice socket."""
    entry = session.pop(PREFETCH_KEY, None)
    if not isinstance(entry, LecturePrefetch):
        return
    entry.token = -1
    task = entry.task
    if isinstance(task, asyncio.Task) and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    client = entry.client
    entry.client = None
    if isinstance(client, CosyVoiceRealtimeClient):
        try:
            await client.close()
        except LLM_PIPELINE_ERRORS as exc:
            logger.debug("Lecture prefetch close skipped: %s", exc)


def schedule_lecture_prefetch(voice_session_id: str, text: str, step_id: str) -> None:
    """Start synthesizing the next slide while the current one is speaking."""
    cleaned = str(text or "").strip()
    if not cleaned or not resolve_kitty_tts_enabled():
        return
    session = voice_sessions.get(voice_session_id)
    if not isinstance(session, dict):
        return
    existing = session.get(PREFETCH_KEY)
    if isinstance(existing, LecturePrefetch) and existing.matches(cleaned, step_id):
        return
    token = int(session.get(_PREFETCH_TOKEN_KEY) or 0) + 1
    session[_PREFETCH_TOKEN_KEY] = token
    if isinstance(existing, LecturePrefetch):
        existing.token = -1
        stale_task = existing.task
        if isinstance(stale_task, asyncio.Task) and not stale_task.done():
            stale_task.cancel()
        stale_client = existing.client
        if isinstance(stale_client, CosyVoiceRealtimeClient):
            asyncio.create_task(stale_client.close())
    entry = LecturePrefetch(step_id=step_id.strip(), text=cleaned, token=token)
    session[PREFETCH_KEY] = entry
    entry.task = asyncio.create_task(
        _run_prefetch(voice_session_id, token, cleaned, step_id.strip()),
        name=f"kitty-tts-prefetch-{voice_session_id[:8]}",
    )
    log_lecture_tts(
        "prefetch_start",
        voice_session_id=voice_session_id,
        step_id=step_id,
        detail=f"chars={len(cleaned)}",
    )


async def take_lecture_prefetch(
    session: dict[str, Any],
    text: str,
    step_id: str,
    *,
    voice_session_id: str,
    wait_seconds: float = PREFETCH_GRACE_SEC,
) -> Optional[list[tuple[str, str]]]:
    """Return ready PCM for this caption, or None on miss/timeout/failure."""
    entry = session.get(PREFETCH_KEY)
    if not isinstance(entry, LecturePrefetch) or not entry.matches(text, step_id):
        return None
    if not entry.ready.is_set():
        grace = max(0.0, float(wait_seconds))
        if grace <= 0:
            return None
        try:
            await asyncio.wait_for(entry.ready.wait(), timeout=grace)
        except asyncio.TimeoutError:
            log_lecture_tts(
                "prefetch_miss_live",
                voice_session_id=voice_session_id,
                step_id=step_id,
                detail=f"grace={grace:.2f}s",
            )
            return None
    live = session.get(PREFETCH_KEY)
    if live is not entry or entry.failed or not entry.chunks:
        return None
    session.pop(PREFETCH_KEY, None)
    return list(entry.chunks)


async def play_cached_lecture_pcm(
    websocket: WebSocket,
    voice_session_id: str,
    chunks: list[tuple[str, str]],
    step_id: str,
    *,
    still_current: Optional[Callable[[], bool]] = None,
) -> None:
    """Push buffered PCM to the Kitty socket as if CosyVoice streamed it live."""
    sent_any = False
    for audio_b64, fmt in chunks:
        if still_current is not None and not still_current():
            if sent_any:
                log_lecture_tts(
                    "cache_play_aborted",
                    voice_session_id=voice_session_id,
                    step_id=step_id,
                )
            return
        if not sent_any:
            log_lecture_tts(
                "first_audio",
                voice_session_id=voice_session_id,
                step_id=step_id,
                detail="source=cache",
            )
            sent_any = True
        payload: dict[str, Any] = {
            "type": "audio_chunk",
            "audio": audio_b64,
            "format": fmt,
            "sample_rate": 22050,
            "lecture": True,
        }
        await safe_websocket_send(websocket, payload)
        await fanout_voice_phase_from_outbound_type(voice_session_id, "audio_chunk")
    if still_current is not None and not still_current():
        log_lecture_tts(
            "cache_play_aborted",
            voice_session_id=voice_session_id,
            step_id=step_id,
        )
        return
    done: dict[str, Any] = {"type": "tts_done", "lecture": True}
    cleaned_step = step_id.strip()
    if cleaned_step:
        done["step_id"] = cleaned_step
    await safe_websocket_send(websocket, done)
    await fanout_voice_phase_from_outbound_type(voice_session_id, "tts_done")


async def _run_prefetch(
    voice_session_id: str,
    token: int,
    text: str,
    step_id: str,
) -> None:
    session = voice_sessions.get(voice_session_id)
    if not isinstance(session, dict):
        return
    entry = session.get(PREFETCH_KEY)
    if not isinstance(entry, LecturePrefetch) or entry.token != token:
        return

    async def on_audio(audio_b64: str, fmt: str) -> None:
        if entry.token != token:
            return
        entry.chunks.append((audio_b64, fmt))

    async def on_done() -> None:
        return None

    async def on_error(err: str) -> None:
        logger.warning("[MindClassroom] TTS prefetch_error step=%s err=%s", step_id or "—", err)
        entry.failed = True

    client = CosyVoiceRealtimeClient(on_audio=on_audio, on_done=on_done, on_error=on_error)
    entry.client = client
    try:
        await client.speak(text)
        if entry.token != token:
            return
        if not entry.chunks:
            entry.failed = True
        else:
            log_lecture_tts(
                "prefetch_ready",
                voice_session_id=voice_session_id,
                step_id=step_id,
                detail=f"chunks={len(entry.chunks)}",
            )
    except LLM_PIPELINE_ERRORS as exc:
        entry.failed = True
        logger.warning("[MindClassroom] TTS prefetch_failed step=%s err=%s", step_id or "—", exc)
    finally:
        entry.client = None
        try:
            await client.close()
        except LLM_PIPELINE_ERRORS as exc:
            logger.debug("Lecture prefetch client close: %s", exc)
        entry.ready.set()
