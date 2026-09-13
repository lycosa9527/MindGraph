"""Replay 思维讲堂 one-ahead CosyVoice using the same lecture cache as Kitty."""

from __future__ import annotations

import asyncio
import base64
import binascii
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.lecture_cache import (
    PREFETCH_KEY,
    PREFETCH_READY_KEY,
    LecturePrefetch,
    schedule_lecture_prefetch,
    take_lecture_prefetch,
)
from services.utils.error_types import FILE_IO_ERRORS

PREFETCH_WAIT_S = 180.0
WALK_VOICE_SESSION = "audit-lecture-prefetch"
MAX_PLAYS = 3


@dataclass(frozen=True)
class LectureCaption:
    """One spoken lecture step."""

    id: str
    kind: str
    title: str
    caption: str


@dataclass(frozen=True)
class WalkBeat:
    """One played slide and the lookahead that started with it."""

    index: int
    step_id: str
    kind: str
    title: str
    played_from: str
    prefetch_step_id: str
    prefetch_ready: bool
    chunk_count: int
    audio_path: str


def spoken_lecture_steps(raw: list[dict[str, Any]]) -> list[LectureCaption]:
    """Keep steps the frontend would send to Kitty (non-empty caption)."""
    spoken: list[LectureCaption] = []
    for index, item in enumerate(raw):
        caption = str(item.get("caption") or "").strip()
        if not caption:
            continue
        kind = str(item.get("kind") or "branch")
        if kind not in {"overview", "branch", "closing"}:
            kind = "branch"
        step_id = str(item.get("id") or f"step-{index}").strip() or f"step-{index}"
        title = str(item.get("title") or caption).strip() or step_id
        spoken.append(LectureCaption(id=step_id, kind=kind, title=title, caption=caption))
    return spoken


def next_lookahead_step(
    steps: list[LectureCaption],
    index: int,
) -> Optional[LectureCaption]:
    """Same rule as afterStepReady: prefetch steps[index + 1] when it has text."""
    if index < 0 or index + 1 >= len(steps):
        return None
    upcoming = steps[index + 1]
    if not upcoming.caption.strip():
        return None
    return upcoming


def planned_prefetch_ids(steps: list[LectureCaption]) -> list[str]:
    """Expected N+1 step ids while playing each caption."""
    planned: list[str] = []
    for index, _step in enumerate(steps):
        upcoming = next_lookahead_step(steps, index)
        planned.append(upcoming.id if upcoming else "")
    return planned


def write_prefetch_wav(path: Path, chunks: list[tuple[str, str]], sample_rate: int) -> str:
    """Decode lecture PCM chunks into a WAV file."""
    pcm = bytearray()
    for audio_b64, _fmt in chunks:
        try:
            pcm.extend(base64.b64decode(audio_b64))
        except (binascii.Error, ValueError):
            continue
    data = bytes(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(data),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        len(data),
    )
    path.write_bytes(header + data)
    return str(path)


async def wait_prefetch_ready(
    session: dict[str, Any],
    step_id: str,
    text: str,
    *,
    timeout_s: float = PREFETCH_WAIT_S,
) -> bool:
    """Wait until the lookahead buffer for this caption is parked and ready."""
    deadline = time.monotonic() + max(timeout_s, 0.0)
    step_key = step_id.strip()
    while time.monotonic() < deadline:
        ready = session.get(PREFETCH_READY_KEY)
        if isinstance(ready, dict):
            parked = ready.get(step_key)
            if (
                isinstance(parked, LecturePrefetch)
                and parked.matches(text, step_key)
                and parked.ready.is_set()
                and parked.chunks
                and not parked.failed
            ):
                return True
        live = session.get(PREFETCH_KEY)
        if isinstance(live, LecturePrefetch) and live.matches(text, step_key):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            try:
                await asyncio.wait_for(live.ready.wait(), timeout=remaining)
            except TimeoutError:
                return False
            continue
        await asyncio.sleep(0.05)
    return False


async def walk_lecture_lookahead(
    steps: list[LectureCaption],
    out_dir: Path,
    *,
    max_plays: int = MAX_PLAYS,
    wait_s: float = PREFETCH_WAIT_S,
) -> list[WalkBeat]:
    """
    Warm slide 0, then play N and start N+1 — the same order as Kitty narrate.

    Writes WAV for each played buffer under ``out_dir``.
    """
    spoken = [step for step in steps if step.caption.strip()]
    if len(spoken) < 2:
        raise RuntimeError("Need at least two spoken lecture steps for lookahead")
    plays = spoken[: max(2, max_plays)]
    session: dict[str, Any] = {}
    voice_sessions[WALK_VOICE_SESSION] = session
    beats: list[WalkBeat] = []
    try:
        first = plays[0]
        schedule_lecture_prefetch(
            WALK_VOICE_SESSION,
            first.caption,
            first.id,
            replace=True,
        )
        warmed = await wait_prefetch_ready(session, first.id, first.caption, timeout_s=wait_s)
        if not warmed:
            raise RuntimeError(f"Opening warmup failed step={first.id}")
        for index, step in enumerate(plays):
            taken = await take_lecture_prefetch(
                session,
                step.caption,
                step.id,
                voice_session_id=WALK_VOICE_SESSION,
            )
            upcoming = next_lookahead_step(spoken, index)
            if upcoming is not None:
                schedule_lecture_prefetch(
                    WALK_VOICE_SESSION,
                    upcoming.caption,
                    upcoming.id,
                    replace=False,
                )
            audio_path = ""
            chunk_count = 0
            if taken is not None:
                chunks, sample_rate = taken
                chunk_count = len(chunks)
                slug = f"{index:02d}_{step.id}"
                try:
                    audio_path = write_prefetch_wav(
                        out_dir / f"{slug}.wav",
                        chunks,
                        sample_rate,
                    )
                except FILE_IO_ERRORS as exc:
                    raise RuntimeError(f"Could not write {slug}.wav: {exc}") from exc
            prefetch_ready = False
            if upcoming is not None:
                prefetch_ready = await wait_prefetch_ready(
                    session,
                    upcoming.id,
                    upcoming.caption,
                    timeout_s=wait_s,
                )
            beats.append(
                WalkBeat(
                    index=index,
                    step_id=step.id,
                    kind=step.kind,
                    title=step.title,
                    played_from="cache" if taken is not None else "miss",
                    prefetch_step_id=upcoming.id if upcoming is not None else "",
                    prefetch_ready=prefetch_ready,
                    chunk_count=chunk_count,
                    audio_path=audio_path,
                )
            )
        return beats
    finally:
        voice_sessions.pop(WALK_VOICE_SESSION, None)


def prefetch_walk_checks(
    steps: list[LectureCaption],
    beats: list[WalkBeat],
) -> dict[str, bool]:
    """Branch 1 must start the next slide; that next slide must play from cache."""
    spoken = [step for step in steps if step.caption.strip()]
    branch_indexes = [index for index, step in enumerate(spoken) if step.kind == "branch"]
    first_branch = branch_indexes[0] if branch_indexes else -1
    next_after_branch = first_branch + 1
    branch_beat = beats[first_branch] if 0 <= first_branch < len(beats) else None
    next_beat = beats[next_after_branch] if 0 <= next_after_branch < len(beats) else None
    expected_next = spoken[next_after_branch].id if 0 <= next_after_branch < len(spoken) else ""
    return {
        "has_overview": bool(spoken) and spoken[0].kind == "overview",
        "has_first_branch": first_branch == 1,
        "has_next_after_branch": bool(expected_next),
        "branch_one_prefetches_next": bool(
            branch_beat and expected_next and branch_beat.prefetch_step_id == expected_next
        ),
        "branch_one_prefetch_ready": bool(branch_beat and branch_beat.prefetch_ready),
        "next_slide_played_from_cache": bool(next_beat and next_beat.played_from == "cache"),
        "opening_played_from_cache": bool(beats and beats[0].played_from == "cache"),
    }
