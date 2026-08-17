"""Kitty narrate is lecture TTS, not command ingress."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.kitty.audio import session_bridge as bridge
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.lecture_cache import (
    LECTURE_HOLD_UNTIL_KEY,
    PREFETCH_KEY,
    PREFETCH_QUEUE_KEY,
    PREFETCH_READY_KEY,
    LecturePrefetch,
    notify_lecture_prefetch_status,
    play_cached_lecture_pcm,
    schedule_lecture_prefetch,
    take_lecture_prefetch,
)
from services.kitty.ws.narrate import handle_kitty_narrate, handle_kitty_prefetch


def test_inbound_routes_narrate_before_text_ingress() -> None:
    """Narrate is handled before WS text ingress and does not begin_ingress."""
    source = Path("services/kitty/ws/inbound.py").read_text(encoding="utf-8")
    prefetch_at = source.index('if msg_type == "prefetch"')
    narrate_at = source.index('if msg_type == "narrate"')
    text_at = source.index('if msg_type == "text"')
    assert prefetch_at < narrate_at < text_at
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
    assert session.get("_kitty_lecture") is True
    assert session.get("_kitty_lecture_step_id") == "s1"
    assert not session["conversation_history"]


@pytest.mark.asyncio
async def test_handle_kitty_narrate_passes_next_slide_prefetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N+1 text rides with the current speak so warmup is not cancelled first."""
    spoken: list[dict] = []

    async def fake_send(_websocket, _payload) -> None:
        return None

    async def fake_speak(*_args, **kwargs) -> None:
        spoken.append(kwargs)

    monkeypatch.setattr("services.kitty.ws.narrate.safe_websocket_send", fake_send)
    monkeypatch.setattr("services.kitty.ws.narrate.speak_kitty_final_reply", fake_speak)
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
    assert spoken == [{"force": True, "prefetch_text": "Second slide", "prefetch_step_id": "s2"}]


@pytest.mark.asyncio
async def test_handle_kitty_prefetch_does_not_speak(monkeypatch: pytest.MonkeyPatch) -> None:
    """Script-ready warmup must buffer PCM without playing or emitting tts_done."""
    scheduled: list[tuple[str, str, str]] = []
    sent: list[dict] = []

    async def fake_send(_websocket, payload) -> None:
        sent.append(payload)

    async def boom(*_args, **_kwargs) -> None:
        raise AssertionError("prefetch must not enqueue playback")

    def fake_prefetch(voice_session_id: str, text: str, step_id: str, **_kwargs) -> None:
        scheduled.append((voice_session_id, text, step_id))

    monkeypatch.setattr("services.kitty.ws.narrate.safe_websocket_send", fake_send)
    monkeypatch.setattr("services.kitty.ws.narrate.speak_kitty_final_reply", boom)
    monkeypatch.setattr("services.kitty.ws.narrate.schedule_lecture_prefetch", fake_prefetch)
    monkeypatch.setattr("services.kitty.ws.narrate.voice_sessions", {"sid": {}})
    monkeypatch.setattr("services.kitty.ws.narrate.log_lecture_tts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.kitty.ws.narrate.resolve_kitty_tts_enabled", lambda: True)

    await handle_kitty_prefetch(
        MagicMock(),
        "sid",
        {"text": "First slide", "step_id": "s1"},
    )
    assert scheduled == [("sid", "First slide", "s1")]
    assert not any(item.get("type") == "tts_done" for item in sent)


@pytest.mark.asyncio
async def test_notify_lecture_prefetch_status_signals_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Launch UI needs prefetch_ready so Start can leave Loading voice."""
    sent: list[dict] = []

    async def fake_send(_websocket, payload) -> None:
        sent.append(payload)

    monkeypatch.setattr("services.kitty.tts.lecture_cache.safe_websocket_send", fake_send)
    await notify_lecture_prefetch_status(MagicMock(), step_id="s1", ok=True)
    assert sent == [{"type": "prefetch_ready", "lecture": True, "step_id": "s1"}]


@pytest.mark.asyncio
async def test_take_lecture_prefetch_returns_ready_chunks() -> None:
    """A ready lookahead buffer is consumed once."""
    entry = LecturePrefetch(step_id="s2", text="Next slide", token=1)
    entry.chunks = [("YmFzZQ==", "pcm")]
    entry.sample_rate = 24000
    entry.ready.set()
    session = {PREFETCH_KEY: entry}
    taken = await take_lecture_prefetch(
        session,
        "Next slide",
        "s2",
        voice_session_id="sid",
    )
    assert taken == ([("YmFzZQ==", "pcm")], 24000)
    assert PREFETCH_KEY not in session


@pytest.mark.asyncio
async def test_catchup_prefetch_does_not_drop_ready_first_slide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Later families queue behind the opening-slide buffer instead of replacing it."""
    first = LecturePrefetch(step_id="s1", text="Open", token=1)
    first.chunks = [("YmFzZQ==", "pcm")]
    first.ready.set()
    session: dict[str, Any] = {PREFETCH_KEY: first}
    monkeypatch.setattr("services.kitty.tts.lecture_cache.voice_sessions", {"sid": session})
    monkeypatch.setattr("services.kitty.tts.lecture_cache.resolve_kitty_tts_enabled", lambda: True)
    schedule_lecture_prefetch("sid", "Second", "s2", replace=False)
    assert session[PREFETCH_KEY] is first
    assert session[PREFETCH_QUEUE_KEY] == [("Second", "s2")]
    session[PREFETCH_READY_KEY] = {"s1": first}
    session.pop(PREFETCH_KEY, None)
    taken = await take_lecture_prefetch(session, "Open", "s1", voice_session_id="sid")
    assert taken == ([("YmFzZQ==", "pcm")], first.sample_rate)
    assert "s1" not in session.get(PREFETCH_READY_KEY, {})


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
async def test_play_cached_lecture_pcm_uses_prefetch_sample_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qwen-TTS prefetch is 24000 Hz; cache play must not hardcode CosyVoice 22050."""
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
        [("YQ==", "pcm")],
        "s2",
        sample_rate=24000,
    )
    chunk = next(item for item in sent if item.get("type") == "audio_chunk")
    assert chunk["sample_rate"] == 24000


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
async def test_tts_worker_takes_warmup_before_next_prefetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slide-1 warmup must be consumed before slide-2 lookahead starts."""
    vid = "voice-lecture-warmup-then-next"
    entry = LecturePrefetch(step_id="s1", text="First slide", token=1)
    entry.chunks = [("YmFzZQ==", "pcm")]
    entry.ready.set()
    voice_sessions[vid] = {
        "_kitty_tts_enabled": True,
        "_kitty_lecture": True,
        "_kitty_lecture_step_id": "s1",
        PREFETCH_KEY: entry,
    }
    order: list[str] = []

    async def fake_play(*_args, **_kwargs) -> None:
        order.append("play")

    def fake_schedule(_sid: str, text: str, step_id: str) -> None:
        order.append(f"prefetch:{text}:{step_id}")

    monkeypatch.setattr(bridge, "play_cached_lecture_pcm", fake_play)
    monkeypatch.setattr(bridge, "schedule_lecture_prefetch", fake_schedule)
    monkeypatch.setattr(bridge, "resolve_kitty_tts_enabled", lambda: True)
    try:
        await bridge.speak_kitty_final_reply(
            MagicMock(),
            vid,
            "First slide",
            force=True,
            prefetch_text="Second slide",
            prefetch_step_id="s2",
        )
        for _ in range(40):
            if "play" in order and any(item.startswith("prefetch:") for item in order):
                break
            await asyncio.sleep(0.02)
        assert order[0] == "prefetch:Second slide:s2"
        assert order[1] == "play"
        assert PREFETCH_KEY not in voice_sessions[vid]
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
async def test_interrupt_keeps_lecture_prefetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip/pause must not drop the N+1 buffer — the next slide may need it."""
    vid = "voice-lecture-interrupt-prefetch"
    cancelled: list[bool] = []

    async def fake_cancel(_session) -> None:
        cancelled.append(True)

    monkeypatch.setattr(bridge, "cancel_lecture_prefetch", fake_cancel)
    voice_sessions[vid] = {"_kitty_tts_enabled": True}
    try:
        await bridge.interrupt_kitty_tts(vid)
        assert not cancelled
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_teardown_cancels_lecture_prefetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disconnect / stop lecture still drops the lookahead buffer."""
    vid = "voice-lecture-teardown-prefetch"
    cancelled: list[bool] = []

    async def fake_cancel(_session) -> None:
        cancelled.append(True)

    monkeypatch.setattr(bridge, "cancel_lecture_prefetch", fake_cancel)
    voice_sessions[vid] = {"_kitty_tts_enabled": True}
    try:
        await bridge.teardown_session_audio(vid)
        assert cancelled == [True]
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_interrupt_clears_lecture_idle_hold() -> None:
    """Skip/pause must drop the client-playback hold so idle can fire later."""
    vid = "voice-lecture-interrupt-hold"
    voice_sessions[vid] = {
        "_kitty_tts_enabled": True,
        "_kitty_lecture": True,
        LECTURE_HOLD_UNTIL_KEY: 9_999_999.0,
    }
    try:
        await bridge.interrupt_kitty_tts(vid)
        live = voice_sessions[vid]
        assert live.get("_kitty_lecture") is False
        assert LECTURE_HOLD_UNTIL_KEY not in live
    finally:
        voice_sessions.pop(vid, None)
