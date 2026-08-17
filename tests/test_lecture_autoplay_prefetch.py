"""Auto-play is one slide ahead; manual jump TTS the landed caption."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.lecture_cache import (
    PREFETCH_KEY,
    PREFETCH_READY_KEY,
    LecturePrefetch,
    schedule_lecture_prefetch,
    take_lecture_prefetch,
)

# Captions from a real 思维讲堂 canvas-tour family (overview + two trunks).
REAL_TOUR = (
    ("overview-0", "同学们好，我们先从这张图的中心看起，把整张图的主线讲清楚。"),
    ("branch-1", "第一条主线讲的是概念本身，我们沿着主干把关键节点串起来。"),
    ("branch-2", "第二条主线转到应用，看看这些节点在实际问题里怎么落地。"),
)


@pytest.mark.asyncio
async def test_autoplay_prefetches_only_the_next_real_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Modal warms slide 0; playing N starts only N+1, using real branch copy."""
    started: list[str] = []
    sid = "voice-autoplay-real-tour"
    session: dict[str, Any] = {}
    voice_sessions[sid] = session

    async def fake_run(
        voice_session_id: str,
        _token: int,
        _text: str,
        step_id: str,
    ) -> None:
        started.append(step_id)
        live = voice_sessions[voice_session_id]
        entry = live.get(PREFETCH_KEY)
        if not isinstance(entry, LecturePrefetch):
            return
        entry.chunks = [("YmFzZQ==", "pcm")]
        entry.ready.set()
        live.pop(PREFETCH_KEY, None)
        ready = live.setdefault(PREFETCH_READY_KEY, {})
        ready[step_id] = entry

    monkeypatch.setattr("services.kitty.tts.lecture_cache.voice_sessions", voice_sessions)
    monkeypatch.setattr("services.kitty.tts.lecture_cache.resolve_kitty_tts_enabled", lambda: True)
    monkeypatch.setattr("services.kitty.tts.lecture_cache._run_prefetch", fake_run)
    try:
        overview_id, overview_text = REAL_TOUR[0]
        branch_id, branch_text = REAL_TOUR[1]
        next_id, next_text = REAL_TOUR[2]
        schedule_lecture_prefetch(sid, overview_text, overview_id, replace=True)
        await asyncio.sleep(0)
        assert started == [overview_id]

        taken = await take_lecture_prefetch(session, overview_text, overview_id, voice_session_id=sid)
        assert taken is not None
        schedule_lecture_prefetch(sid, branch_text, branch_id, replace=False)
        await asyncio.sleep(0)
        assert started == [overview_id, branch_id]

        taken_next = await take_lecture_prefetch(session, branch_text, branch_id, voice_session_id=sid)
        assert taken_next is not None
        schedule_lecture_prefetch(sid, next_text, next_id, replace=False)
        await asyncio.sleep(0)
        assert started == [overview_id, branch_id, next_id]
    finally:
        voice_sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_manual_jump_misses_unrelated_prefetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Jumping to a later branch must not play the one-ahead buffer."""
    sid = "voice-manual-jump"
    session: dict[str, Any] = {}
    voice_sessions[sid] = session
    monkeypatch.setattr("services.kitty.tts.lecture_cache.voice_sessions", voice_sessions)
    monkeypatch.setattr("services.kitty.tts.lecture_cache.resolve_kitty_tts_enabled", lambda: True)
    parked = LecturePrefetch(step_id="branch-1", text=REAL_TOUR[1][1], token=1)
    parked.chunks = [("YmFzZQ==", "pcm")]
    parked.ready.set()
    session[PREFETCH_READY_KEY] = {"branch-1": parked}
    try:
        jumped = await take_lecture_prefetch(session, REAL_TOUR[2][1], REAL_TOUR[2][0], voice_session_id=sid)
        assert jumped is None
        assert session[PREFETCH_READY_KEY]["branch-1"] is parked
    finally:
        voice_sessions.pop(sid, None)
