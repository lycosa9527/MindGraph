"""Kitty narrate is lecture TTS, not command ingress."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.kitty.audio import session_bridge as bridge
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.lecture_cache import (
    PREFETCH_KEY,
    LecturePrefetch,
    play_cached_lecture_pcm,
    take_lecture_prefetch,
)
from services.kitty.ws.narrate import handle_kitty_narrate


def test_inbound_routes_narrate_before_text_ingress() -> None:
    """Narrate is handled before WS text ingress and does not begin_ingress."""
    source = Path("services/kitty/ws/inbound.py").read_text(encoding="utf-8")
    narrate_at = source.index('if msg_type == "narrate"')
    text_at = source.index('if msg_type == "text"')
    assert narrate_at < text_at
    narrate_src = Path("services/kitty/ws/narrate.py").read_text(encoding="utf-8")
    assert "begin_ingress" not in narrate_src
    assert "conversation_history" not in narrate_src


@pytest.mark.asyncio
async def test_handle_kitty_narrate_speaks_without_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lecture TTS must not append the caption to conversation history."""
    sent: list[dict] = []
    session: dict = {"conversation_history": []}

    async def fake_send(_websocket, payload):
        """Capture the lecture text_chunk frame."""
        sent.append(payload)

    async def speak(*_args, **_kwargs) -> None:
        """Assert lecture metadata is still set while enqueueing TTS."""
        assert session.get("_kitty_lecture") is True
        assert session.get("_kitty_lecture_step_id") == "s1"

    speak_mock = AsyncMock(side_effect=speak)
    monkeypatch.setattr("services.kitty.ws.narrate.safe_websocket_send", fake_send)
    monkeypatch.setattr("services.kitty.ws.narrate.speak_kitty_final_reply", speak_mock)
    monkeypatch.setattr("services.kitty.ws.narrate.voice_sessions", {"sid": session})

    await handle_kitty_narrate(MagicMock(), "sid", {"text": "Hello class", "step_id": "s1"})

    assert sent[0]["reply_kind"] == "lecture"
    speak_mock.assert_awaited_once()
    called = speak_mock.await_args
    assert called is not None
    assert called.kwargs.get("force") is True
    assert session.get("_kitty_lecture") is False
    assert "_kitty_lecture_step_id" not in session
    assert not session["conversation_history"]


@pytest.mark.asyncio
async def test_handle_kitty_narrate_schedules_next_slide_prefetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Current caption enqueues TTS; next caption starts the CosyVoice lookahead."""
    scheduled: list[tuple[str, str, str]] = []

    async def fake_send(_websocket, _payload) -> None:
        return None

    async def fake_speak(*_args, **_kwargs) -> None:
        return None

    def fake_prefetch(voice_session_id: str, text: str, step_id: str) -> None:
        scheduled.append((voice_session_id, text, step_id))

    monkeypatch.setattr("services.kitty.ws.narrate.safe_websocket_send", fake_send)
    monkeypatch.setattr("services.kitty.ws.narrate.speak_kitty_final_reply", fake_speak)
    monkeypatch.setattr("services.kitty.ws.narrate.schedule_lecture_prefetch", fake_prefetch)
    monkeypatch.setattr("services.kitty.ws.narrate.voice_sessions", {"sid": {}})
    monkeypatch.setattr("services.kitty.ws.narrate.log_lecture_tts", lambda *_args, **_kwargs: None)

    await handle_kitty_narrate(
        MagicMock(),
        "sid",
        {
            "text": "First slide",
            "step_id": "s1",
            "prefetch_text": "Second slide",
            "prefetch_step_id": "s2",
        },
    )
    assert scheduled == [("sid", "Second slide", "s2")]


@pytest.mark.asyncio
async def test_take_lecture_prefetch_returns_ready_chunks() -> None:
    """A ready lookahead buffer is consumed once."""
    entry = LecturePrefetch(step_id="s2", text="Next slide", token=1)
    entry.chunks = [("YmFzZQ==", "pcm")]
    entry.ready.set()
    session = {PREFETCH_KEY: entry}
    chunks = await take_lecture_prefetch(
        session,
        "Next slide",
        "s2",
        voice_session_id="sid",
    )
    assert chunks == [("YmFzZQ==", "pcm")]
    assert PREFETCH_KEY not in session


@pytest.mark.asyncio
async def test_take_lecture_prefetch_unready_does_not_block() -> None:
    """An unfinished lookahead must not stall the speaking worker."""
    entry = LecturePrefetch(step_id="s2", text="Next slide", token=1)
    session = {PREFETCH_KEY: entry}
    chunks = await take_lecture_prefetch(
        session,
        "Next slide",
        "s2",
        voice_session_id="sid",
        wait_seconds=0,
    )
    assert chunks is None
    assert session[PREFETCH_KEY] is entry


@pytest.mark.asyncio
async def test_play_cached_lecture_pcm_aborts_when_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skip mid-dump must not send leftover PCM or a late tts_done."""
    sent: list[dict] = []

    async def fake_send(_websocket, payload) -> None:
        sent.append(payload)

    async def fake_fanout(_sid, _kind) -> None:
        return None

    monkeypatch.setattr("services.kitty.tts.lecture_cache.safe_websocket_send", fake_send)
    monkeypatch.setattr(
        "services.kitty.tts.lecture_cache.fanout_voice_phase_from_outbound_type",
        fake_fanout,
    )
    await play_cached_lecture_pcm(
        MagicMock(),
        "sid",
        [("YQ==", "pcm"), ("Yg==", "pcm")],
        "s2",
        still_current=lambda: False,
    )
    assert not any(item.get("type") == "tts_done" for item in sent)
    assert not any(item.get("type") == "audio_chunk" for item in sent)


@pytest.mark.asyncio
async def test_handle_kitty_narrate_tts_off_still_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabled CosyVoice must emit tts_done so the lecture does not hang."""
    sent: list[dict] = []

    async def fake_send(_websocket, payload) -> None:
        sent.append(payload)

    monkeypatch.setattr("services.kitty.ws.narrate.safe_websocket_send", fake_send)
    monkeypatch.setattr("services.kitty.ws.narrate.resolve_kitty_tts_enabled", lambda: False)
    monkeypatch.setattr("services.kitty.ws.narrate.voice_sessions", {"sid": {}})
    monkeypatch.setattr("services.kitty.ws.narrate.log_lecture_tts", lambda *_args, **_kwargs: None)

    await handle_kitty_narrate(MagicMock(), "sid", {"text": "Hello class", "step_id": "s1"})

    assert sent[0]["reply_kind"] == "lecture"
    assert sent[1]["type"] == "tts_done"
    assert sent[1]["lecture"] is True
    assert sent[1]["step_id"] == "s1"


@pytest.mark.asyncio
async def test_tts_worker_plays_prefetch_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Slide 2 should play cached PCM instead of opening a new CosyVoice task."""
    vid = "voice-lecture-cache"
    entry = LecturePrefetch(step_id="s2", text="Next slide", token=1)
    entry.chunks = [("YmFzZQ==", "pcm")]
    entry.ready.set()
    voice_sessions[vid] = {
        "_kitty_tts_enabled": True,
        "_kitty_lecture": True,
        "_kitty_lecture_step_id": "s2",
        PREFETCH_KEY: entry,
    }
    played: list[tuple[list[tuple[str, str]], str]] = []

    async def fake_play(_ws, _sid, chunks, step_id, **_kwargs) -> None:
        """Capture cache playback without requiring CosyVoice."""
        played.append((chunks, step_id))

    async def boom(*_args, **_kwargs):
        raise AssertionError("live CosyVoice should not run on cache hit")

    monkeypatch.setattr(bridge, "play_cached_lecture_pcm", fake_play)
    monkeypatch.setattr(bridge, "_get_or_create_cosyvoice_client", boom)
    monkeypatch.setattr(bridge, "resolve_kitty_tts_enabled", lambda: True)
    try:
        await bridge.speak_kitty_final_reply(MagicMock(), vid, "Next slide", force=True)
        for _ in range(40):
            if played:
                break
            await asyncio.sleep(0.02)
        assert played == [([("YmFzZQ==", "pcm")], "s2")]
    finally:
        await bridge.teardown_session_audio(vid)
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_tts_worker_drops_cache_after_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prefetch that finishes after skip must not start playing."""
    vid = "voice-lecture-stale-cache"
    voice_sessions[vid] = {
        "_kitty_tts_enabled": True,
        "_kitty_lecture": True,
        "_kitty_lecture_step_id": "s2",
    }
    played: list[bool] = []

    async def fake_take(*_args, **_kwargs):
        await bridge.interrupt_kitty_tts(vid)
        return [("YmFzZQ==", "pcm")]

    async def fake_play(*_args, **_kwargs) -> None:
        """Record an unexpected cache play after interrupt."""
        played.append(True)

    monkeypatch.setattr(bridge, "take_lecture_prefetch", fake_take)
    monkeypatch.setattr(bridge, "play_cached_lecture_pcm", fake_play)
    monkeypatch.setattr(bridge, "resolve_kitty_tts_enabled", lambda: True)
    try:
        await bridge.speak_kitty_final_reply(MagicMock(), vid, "Next slide", force=True)
        await asyncio.sleep(0.08)
        assert not played
    finally:
        await bridge.teardown_session_audio(vid)
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_interrupt_cancels_lecture_prefetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip/pause must drop the lookahead so a stale next slide is not kept."""
    vid = "voice-lecture-interrupt-prefetch"
    cancelled: list[bool] = []

    async def fake_cancel(_session) -> None:
        cancelled.append(True)

    monkeypatch.setattr(bridge, "cancel_lecture_prefetch", fake_cancel)
    voice_sessions[vid] = {"_kitty_tts_enabled": True}
    try:
        await bridge.interrupt_kitty_tts(vid)
        assert cancelled == [True]
    finally:
        voice_sessions.pop(vid, None)
