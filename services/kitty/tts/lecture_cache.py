"""One-ahead CosyVoice cache for Mind Classroom lecture slides.

Slide 0 warms in the launch modal. While slide N plays, only slide N+1
synthesizes. The next narrate plays that buffer when it matches.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import time
from collections.abc import Callable
from typing import Any, Optional

from fastapi import WebSocket

from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.desktop.kitty_voice_phase_fanout import fanout_voice_phase_from_outbound_type
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.cosyvoice_realtime import resolve_kitty_tts_enabled
from services.kitty.tts.factory import KittyTtsClient, create_kitty_tts_client, is_kitty_tts_client
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

PREFETCH_KEY = "_kitty_lecture_prefetch"
PREFETCH_READY_KEY = "_kitty_lecture_prefetch_ready"
PREFETCH_QUEUE_KEY = "_kitty_lecture_prefetch_queue"
MAX_READY_BUFFERS = 3
_PREFETCH_TOKEN_KEY = "_kitty_lecture_prefetch_token"
TTS_T0_KEY = "_kitty_lecture_tts_t0"
TTS_PCM_BYTES_KEY = "_kitty_lecture_pcm_bytes"
TTS_CHUNK_COUNT_KEY = "_kitty_lecture_pcm_chunks"
TTS_CHARS_KEY = "_kitty_lecture_chars"
LECTURE_HOLD_UNTIL_KEY = "_kitty_lecture_hold_until"
LECTURE_SAMPLE_RATE = 22050
# Cover decode + schedule jitter after the last PCM byte is sent.
LECTURE_HOLD_SLACK_SEC = 45.0
# Short miss wait when a caller must not stall (unit tests / skip probes).
PREFETCH_GRACE_SEC = 1.2
# Matching in-flight buffer is the slide we are about to speak (warmup or N+1).
PREFETCH_CURRENT_WAIT_SEC = 8.0


class LecturePrefetch:
    """One in-flight or ready next-slide PCM buffer."""

    def __init__(self, *, step_id: str, text: str, token: int) -> None:
        self.step_id = step_id
        self.text = text
        self.token = token
        self.chunks: list[tuple[str, str]] = []
        self.sample_rate = LECTURE_SAMPLE_RATE
        self.ready = asyncio.Event()
        self.failed = False
        self.task: Optional[asyncio.Task[None]] = None
        self.client: Optional[KittyTtsClient] = None
        self.notify_ws: Optional[WebSocket] = None

    def matches(self, text: str, step_id: str) -> bool:
        """True when the requested narrate is this buffered caption."""
        if self.text != text:
            return False
        if step_id and self.step_id and step_id != self.step_id:
            return False
        return True


def pcm_duration_sec(pcm_bytes: int, sample_rate: int = LECTURE_SAMPLE_RATE) -> float:
    """16-bit mono PCM duration in seconds."""
    if pcm_bytes <= 0 or sample_rate <= 0:
        return 0.0
    return (pcm_bytes / 2) / sample_rate


def pcm_duration_from_chunks(
    chunks: list[tuple[str, str]],
    sample_rate: int = LECTURE_SAMPLE_RATE,
) -> float:
    """Duration of base64 PCM chunks at ``sample_rate``."""
    total = 0
    for audio_b64, _fmt in chunks:
        try:
            total += len(base64.b64decode(audio_b64))
        except (binascii.Error, ValueError):
            continue
    return pcm_duration_sec(total, sample_rate)


def extend_lecture_idle_hold(session: dict[str, Any], *, audio_sec: float) -> None:
    """Keep the Kitty socket open while the client plays the PCM we just sent."""
    hold = time.monotonic() + max(float(audio_sec), 0.0) + LECTURE_HOLD_SLACK_SEC
    session[LECTURE_HOLD_UNTIL_KEY] = hold


def clear_lecture_idle_hold(session: dict[str, Any]) -> None:
    """Drop the client-playback idle hold (barge-in / teardown)."""
    session.pop(LECTURE_HOLD_UNTIL_KEY, None)


async def notify_lecture_prefetch_status(
    websocket: Optional[WebSocket],
    *,
    step_id: str,
    ok: bool,
) -> None:
    """Tell the launch UI that first-slide voice warmup finished."""
    if websocket is None:
        return
    payload: dict[str, Any] = {
        "type": "prefetch_ready" if ok else "prefetch_failed",
        "lecture": True,
    }
    cleaned = step_id.strip()
    if cleaned:
        payload["step_id"] = cleaned
    await safe_websocket_send(websocket, payload)


def format_tts_metric_detail(
    *,
    chars: Optional[int] = None,
    chunks: Optional[int] = None,
    audio_sec: Optional[float] = None,
    source: str = "",
) -> str:
    """``source=live chars=101 chunks=137 audio=22.04s`` fragment."""
    parts: list[str] = []
    if source:
        parts.append(f"source={source}")
    if chars is not None:
        parts.append(f"chars={chars}")
    if chunks is not None:
        parts.append(f"chunks={chunks}")
    if audio_sec is not None:
        parts.append(f"audio={audio_sec:.2f}s")
    return " ".join(parts)


def mark_lecture_tts_start(session: dict[str, Any], *, chars: int = 0) -> None:
    """Reset per-utterance clocks before live or cached play."""
    session[TTS_T0_KEY] = time.monotonic()
    session[TTS_PCM_BYTES_KEY] = 0
    session[TTS_CHUNK_COUNT_KEY] = 0
    session[TTS_CHARS_KEY] = chars


def note_lecture_pcm_chunk(session: dict[str, Any], audio_b64: str) -> None:
    """Accumulate decoded PCM bytes for audio-duration metrics."""
    try:
        raw = base64.b64decode(audio_b64)
    except (binascii.Error, ValueError):
        return
    session[TTS_PCM_BYTES_KEY] = int(session.get(TTS_PCM_BYTES_KEY) or 0) + len(raw)
    session[TTS_CHUNK_COUNT_KEY] = int(session.get(TTS_CHUNK_COUNT_KEY) or 0) + 1


def lecture_tts_elapsed(session: dict[str, Any]) -> Optional[float]:
    """Seconds since ``mark_lecture_tts_start``, or None."""
    started = session.get(TTS_T0_KEY)
    if not isinstance(started, (int, float)):
        return None
    return time.monotonic() - float(started)


# Completion / latency metrics stay on INFO (same idea as auto-complete tok/s).
# Start, skip, and miss lines are DEBUG so a lecture does not flood uvicorn.
_TTS_INFO_EVENTS = frozenset(
    {
        "first_audio",
        "synthesize_done",
        "prefetch_ready",
        "cache_play_done",
    }
)


def tts_log_level(event: str) -> int:
    """INFO for TTS metrics; DEBUG for start / skip / miss chatter."""
    return logging.INFO if event in _TTS_INFO_EVENTS else logging.DEBUG


def log_lecture_tts(
    event: str,
    *,
    voice_session_id: str,
    step_id: str = "",
    detail: str = "",
    elapsed: Optional[float] = None,
) -> None:
    """Lecture CosyVoice line. Metrics at INFO; start/skip at DEBUG."""
    step = step_id.strip() or "—"
    parts: list[str] = []
    if elapsed is not None:
        parts.append(f"elapsed={elapsed:.2f}s")
    if detail:
        parts.append(detail)
    extra = f" {' '.join(parts)}".rstrip()
    level = tts_log_level(event)
    logger.log(
        level,
        "[MindClassroom] TTS %s sid=%s step=%s asr=0%s",
        event,
        voice_session_id[:10],
        step,
        extra,
    )
    if level < logging.INFO:
        return
    kitty_wf_log(
        "lecture_tts",
        f"{event}{extra}",
        voice_session_id=voice_session_id,
        extra={"module": "tts", "step": step, "channel": "tts", "asr": 0},
    )


def record_live_lecture_audio(
    session: dict[str, Any],
    audio_b64: str,
    *,
    voice_session_id: str,
) -> None:
    """Count PCM and log first-audio latency once per live utterance."""
    note_lecture_pcm_chunk(session, audio_b64)
    if session.get("_kitty_lecture_first_audio"):
        return
    session["_kitty_lecture_first_audio"] = True
    chars = session.get(TTS_CHARS_KEY)
    char_count = int(chars) if isinstance(chars, int) else None
    log_lecture_tts(
        "first_audio",
        voice_session_id=voice_session_id,
        step_id=str(session.get("_kitty_lecture_step_id") or ""),
        elapsed=lecture_tts_elapsed(session),
        detail=format_tts_metric_detail(source="live", chars=char_count),
    )


def log_lecture_synthesize_done(
    session: dict[str, Any],
    *,
    voice_session_id: str,
    step_id: str,
    chars: int,
    sample_rate: int = LECTURE_SAMPLE_RATE,
) -> None:
    """INFO: live CosyVoice utterance finished (wall time + audio length)."""
    pcm_bytes = int(session.get(TTS_PCM_BYTES_KEY) or 0)
    chunks = int(session.get(TTS_CHUNK_COUNT_KEY) or 0)
    log_lecture_tts(
        "synthesize_done",
        voice_session_id=voice_session_id,
        step_id=step_id,
        elapsed=lecture_tts_elapsed(session),
        detail=format_tts_metric_detail(
            source="live",
            chars=chars,
            chunks=chunks,
            audio_sec=pcm_duration_sec(pcm_bytes, sample_rate),
        ),
    )


def _ready_buffers(session: dict[str, Any]) -> dict[str, LecturePrefetch]:
    raw = session.get(PREFETCH_READY_KEY)
    if isinstance(raw, dict):
        return raw
    ready: dict[str, LecturePrefetch] = {}
    session[PREFETCH_READY_KEY] = ready
    return ready


def _prefetch_queue(session: dict[str, Any]) -> list[tuple[str, str]]:
    raw = session.get(PREFETCH_QUEUE_KEY)
    if isinstance(raw, list):
        return raw
    queue: list[tuple[str, str]] = []
    session[PREFETCH_QUEUE_KEY] = queue
    return queue


def drop_unrelated_lecture_buffers(session: dict[str, Any], text: str, step_id: str) -> None:
    """Keep a matching opening buffer; drop leftover slides from a prior map."""
    session.pop(PREFETCH_QUEUE_KEY, None)
    ready = _ready_buffers(session)
    step_key = step_id.strip()
    for key in list(ready):
        parked = ready.get(key)
        if not isinstance(parked, LecturePrefetch) or not parked.matches(text, step_key):
            ready.pop(key, None)


async def cancel_lecture_prefetch(session: dict[str, Any]) -> None:
    """Drop the lookahead buffer and close its CosyVoice socket."""
    session.pop(PREFETCH_QUEUE_KEY, None)
    ready = session.pop(PREFETCH_READY_KEY, None)
    if isinstance(ready, dict):
        for entry in list(ready.values()):
            if isinstance(entry, LecturePrefetch):
                entry.token = -1
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
    if is_kitty_tts_client(client):
        try:
            await client.close()
        except LLM_PIPELINE_ERRORS as exc:
            logger.debug("Lecture prefetch close skipped: %s", exc)


def schedule_lecture_prefetch(
    voice_session_id: str,
    text: str,
    step_id: str,
    *,
    notify_ws: Optional[WebSocket] = None,
    replace: bool = True,
) -> None:
    """Start synthesizing a slide. Ready buffers stay; catch-up queues behind them."""
    cleaned = str(text or "").strip()
    if not cleaned or not resolve_kitty_tts_enabled():
        return
    session = voice_sessions.get(voice_session_id)
    if not isinstance(session, dict):
        return
    step_key = step_id.strip()
    ready = _ready_buffers(session)
    parked = ready.get(step_key)
    if isinstance(parked, LecturePrefetch) and parked.matches(cleaned, step_key):
        if notify_ws is not None:
            parked.notify_ws = notify_ws
            if parked.ready.is_set():
                asyncio.create_task(
                    notify_lecture_prefetch_status(
                        notify_ws,
                        step_id=step_key,
                        ok=not parked.failed and bool(parked.chunks),
                    )
                )
        return
    existing = session.get(PREFETCH_KEY)
    if isinstance(existing, LecturePrefetch) and existing.matches(cleaned, step_key):
        if notify_ws is not None:
            existing.notify_ws = notify_ws
            if existing.ready.is_set():
                asyncio.create_task(
                    notify_lecture_prefetch_status(
                        notify_ws,
                        step_id=step_key,
                        ok=not existing.failed and bool(existing.chunks),
                    )
                )
        return
    if isinstance(existing, LecturePrefetch) and not replace:
        queue = _prefetch_queue(session)
        item = (cleaned, step_key)
        if item not in queue:
            queue.append(item)
        return
    _start_prefetch_entry(
        session,
        voice_session_id,
        cleaned,
        step_key,
        notify_ws=notify_ws,
        replace_inflight=replace,
    )


def _start_prefetch_entry(
    session: dict[str, Any],
    voice_session_id: str,
    cleaned: str,
    step_key: str,
    *,
    notify_ws: Optional[WebSocket],
    replace_inflight: bool,
) -> None:
    existing = session.get(PREFETCH_KEY)
    if isinstance(existing, LecturePrefetch) and not replace_inflight:
        return
    token = int(session.get(_PREFETCH_TOKEN_KEY) or 0) + 1
    session[_PREFETCH_TOKEN_KEY] = token
    if isinstance(existing, LecturePrefetch):
        existing.token = -1
        stale_task = existing.task
        if isinstance(stale_task, asyncio.Task) and not stale_task.done():
            stale_task.cancel()
        stale_client = existing.client
        if is_kitty_tts_client(stale_client):
            asyncio.create_task(stale_client.close())
    entry = LecturePrefetch(step_id=step_key, text=cleaned, token=token)
    entry.notify_ws = notify_ws
    session[PREFETCH_KEY] = entry
    entry.task = asyncio.create_task(
        _run_prefetch(voice_session_id, token, cleaned, step_key),
        name=f"kitty-tts-prefetch-{voice_session_id[:8]}",
    )
    log_lecture_tts(
        "prefetch_start",
        voice_session_id=voice_session_id,
        step_id=step_key,
        detail=f"chars={len(cleaned)}",
    )


def _pump_prefetch_queue(voice_session_id: str) -> None:
    session = voice_sessions.get(voice_session_id)
    if not isinstance(session, dict):
        return
    if isinstance(session.get(PREFETCH_KEY), LecturePrefetch):
        return
    ready = _ready_buffers(session)
    if len(ready) >= MAX_READY_BUFFERS:
        return
    queue = _prefetch_queue(session)
    while queue:
        cleaned, step_key = queue.pop(0)
        parked = ready.get(step_key)
        if isinstance(parked, LecturePrefetch) and parked.matches(cleaned, step_key):
            continue
        _start_prefetch_entry(
            session,
            voice_session_id,
            cleaned,
            step_key,
            notify_ws=None,
            replace_inflight=False,
        )
        return


async def take_lecture_prefetch(
    session: dict[str, Any],
    text: str,
    step_id: str,
    *,
    voice_session_id: str,
    wait_seconds: float = PREFETCH_CURRENT_WAIT_SEC,
) -> Optional[tuple[list[tuple[str, str]], int]]:
    """Return ready PCM and sample rate, or None on miss/timeout/failure."""
    taken = _take_ready_buffer(session, text, step_id)
    if taken is not None:
        _pump_prefetch_queue(voice_session_id)
        return taken
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
    taken = _take_ready_buffer(session, text, step_id)
    if taken is not None:
        _pump_prefetch_queue(voice_session_id)
        return taken
    live = session.get(PREFETCH_KEY)
    if live is not entry or entry.failed or not entry.chunks:
        return None
    session.pop(PREFETCH_KEY, None)
    _pump_prefetch_queue(voice_session_id)
    return list(entry.chunks), int(entry.sample_rate)


def _take_ready_buffer(
    session: dict[str, Any],
    text: str,
    step_id: str,
) -> Optional[tuple[list[tuple[str, str]], int]]:
    ready = session.get(PREFETCH_READY_KEY)
    if not isinstance(ready, dict):
        return None
    parked = ready.get(step_id.strip())
    if not isinstance(parked, LecturePrefetch) or not parked.matches(text, step_id):
        return None
    if not parked.ready.is_set() or parked.failed or not parked.chunks:
        return None
    ready.pop(step_id.strip(), None)
    return list(parked.chunks), int(parked.sample_rate)


async def play_cached_lecture_pcm(
    websocket: WebSocket,
    voice_session_id: str,
    chunks: list[tuple[str, str]],
    step_id: str,
    *,
    sample_rate: int = LECTURE_SAMPLE_RATE,
    still_current: Optional[Callable[[], bool]] = None,
) -> None:
    """Push buffered PCM to the Kitty socket as if CosyVoice streamed it live."""
    started = time.monotonic()
    sent_any = False
    for audio_b64, fmt in chunks:
        if still_current is not None and not still_current():
            if sent_any:
                log_lecture_tts(
                    "cache_play_aborted",
                    voice_session_id=voice_session_id,
                    step_id=step_id,
                    elapsed=time.monotonic() - started,
                )
            return
        if not sent_any:
            log_lecture_tts(
                "first_audio",
                voice_session_id=voice_session_id,
                step_id=step_id,
                elapsed=time.monotonic() - started,
                detail="source=cache",
            )
            sent_any = True
        payload: dict[str, Any] = {
            "type": "audio_chunk",
            "audio": audio_b64,
            "format": fmt,
            "sample_rate": sample_rate,
            "lecture": True,
        }
        await safe_websocket_send(websocket, payload)
        await fanout_voice_phase_from_outbound_type(voice_session_id, "audio_chunk")
    if still_current is not None and not still_current():
        log_lecture_tts(
            "cache_play_aborted",
            voice_session_id=voice_session_id,
            step_id=step_id,
            elapsed=time.monotonic() - started,
        )
        return
    done: dict[str, Any] = {"type": "tts_done", "lecture": True}
    cleaned_step = step_id.strip()
    if cleaned_step:
        done["step_id"] = cleaned_step
    await safe_websocket_send(websocket, done)
    await fanout_voice_phase_from_outbound_type(voice_session_id, "tts_done")
    log_lecture_tts(
        "cache_play_done",
        voice_session_id=voice_session_id,
        step_id=step_id,
        elapsed=time.monotonic() - started,
        detail=format_tts_metric_detail(
            source="cache",
            chunks=len(chunks),
            audio_sec=pcm_duration_from_chunks(chunks, sample_rate),
        ),
    )


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

    client = create_kitty_tts_client(on_audio=on_audio, on_done=on_done, on_error=on_error)
    entry.client = client
    entry.sample_rate = int(client.sample_rate)
    started = time.monotonic()
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
                elapsed=time.monotonic() - started,
                detail=format_tts_metric_detail(
                    chars=len(text),
                    chunks=len(entry.chunks),
                    audio_sec=pcm_duration_from_chunks(entry.chunks, entry.sample_rate),
                ),
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
        live = voice_sessions.get(voice_session_id)
        if (
            entry.token == token
            and isinstance(live, dict)
            and live.get(PREFETCH_KEY) is entry
            and not entry.failed
            and entry.chunks
        ):
            live.pop(PREFETCH_KEY, None)
            ready = _ready_buffers(live)
            parked_id = step_id or entry.step_id or f"anon-{token}"
            ready[parked_id] = entry
            extra = len(ready) - MAX_READY_BUFFERS
            if extra > 0:
                for key in list(ready.keys()):
                    if extra <= 0:
                        break
                    if key == parked_id:
                        continue
                    ready.pop(key, None)
                    extra -= 1
            _pump_prefetch_queue(voice_session_id)
        if entry.token == token and entry.notify_ws is not None:
            await notify_lecture_prefetch_status(
                entry.notify_ws,
                step_id=step_id,
                ok=not entry.failed and bool(entry.chunks),
            )
