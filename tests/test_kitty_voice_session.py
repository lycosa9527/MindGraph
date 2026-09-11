"""Kitty voice phase, listen modes, turn cancel, and hello aliases."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.session.listen_modes import (
    LISTEN_AUTO,
    LISTEN_MANUAL,
    asr_commit_mode,
    normalize_listen_mode,
    set_session_listen_mode,
)
from services.kitty.session.memory import get_session_memory, remove_session_memory
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.session.turn_task import cancel_active_turn, run_cancellable_turn
from services.kitty.session.voice_phase import is_legal_transition, normalize_voice_phase
from services.kitty.ws.inbound import dispatch_kitty_ws_inbound_message
from services.kitty.ws.inbound_types import KittyWsInboundContext


def _make_session() -> str:
    sid = create_voice_session(
        user_id="9",
        diagram_session_id="scope-voice",
        diagram_type="mind_map",
    )
    voice_sessions[sid]["conversation_history"] = []
    return sid


def test_normalize_listen_mode_defaults_manual() -> None:
    """Unknown values stay PTT."""
    assert normalize_listen_mode("auto") == LISTEN_AUTO
    assert normalize_listen_mode("manual") == LISTEN_MANUAL
    assert normalize_listen_mode("") == LISTEN_MANUAL
    assert normalize_listen_mode("always-on") == LISTEN_MANUAL


def test_asr_commit_mode_follows_listen_mode() -> None:
    """Auto commits on Fun-ASR final; manual waits for release."""
    sid = _make_session()
    try:
        assert asr_commit_mode(sid) == "release_only"
        set_session_listen_mode(sid, "auto")
        assert asr_commit_mode(sid) == "final_or_stopped"
    finally:
        voice_sessions.pop(sid, None)


def test_voice_phase_legal_transitions() -> None:
    """Barge-in speaking → listening is legal; idle is not a server phase."""
    assert is_legal_transition("speaking", "listening")
    assert is_legal_transition("thinking", "speaking")
    assert not is_legal_transition("listening", "idle")
    assert normalize_voice_phase("THINKING") == "thinking"
    assert normalize_voice_phase("idle") is None


@pytest.mark.asyncio
async def test_abort_cancels_turn_and_writes_observation() -> None:
    """Abort cancels the turn Task and records one interrupted line."""
    sid = _make_session()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _slow() -> None:
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    try:
        runner = asyncio.create_task(run_cancellable_turn(sid, _slow()))
        await started.wait()
        cancelled_ok = await cancel_active_turn(sid, reason="user_ptt")
        await runner
        assert cancelled_ok
        assert cancelled.is_set()
        mem = get_session_memory(sid)
        abort_turns = [t for t in mem.turns if t.action_taken == "abort"]
        assert len(abort_turns) == 1
        assert "interrupted:user_ptt" in abort_turns[0].content
    finally:
        remove_session_memory(sid)
        voice_sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_hello_and_listen_aliases() -> None:
    """hello registers listen_mode; listen stop aliases asr_stop."""
    sid = _make_session()
    ctx = KittyWsInboundContext(
        websocket=MagicMock(),
        current_user=MagicMock(id=9),
        diagram_session_id="scope-voice",
        voice_session_id=sid,
        hub_session_id="hub",
        hub=None,
        agent_session_id="agent",
        user_id="9",
    )
    try:
        redis = AsyncMock()
        pipe = MagicMock()
        redis.pipeline = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock()
        with (
            patch(
                "services.kitty.session.device_hello.get_async_redis",
                return_value=redis,
            ),
            patch(
                "services.kitty.ws.inbound_hello.safe_websocket_send",
                new_callable=AsyncMock,
            ) as hello_send,
        ):
            flow = await dispatch_kitty_ws_inbound_message(
                ctx,
                {
                    "type": "hello",
                    "listen_mode": "auto",
                    "firmware": "1.85c",
                    "device_id": "aa:bb:cc",
                },
            )
            assert flow == "continue"
            hello_send.assert_awaited()
            called = hello_send.await_args
            assert called is not None
            ack = called.args[1]
            assert ack["listen_mode"] == "auto"
            assert ack["asr_commit_mode"] == "final_or_stopped"
            assert ack["asr_audio_formats"] == ["pcm", "opus"]

        with patch(
            "services.kitty.ws.inbound._handle_asr_stop",
            new_callable=AsyncMock,
            return_value="continue",
        ) as stop:
            await dispatch_kitty_ws_inbound_message(ctx, {"type": "listen", "state": "stop"})
            stop.assert_awaited_once()
    finally:
        voice_sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_asr_start_forwards_opus_format() -> None:
    """asr_start format=opus reaches Fun-ASR; omitted format stays PCM."""
    sid = _make_session()
    ctx = KittyWsInboundContext(
        websocket=MagicMock(),
        current_user=MagicMock(id=9),
        diagram_session_id="scope-voice",
        voice_session_id=sid,
        hub_session_id="hub",
        hub=None,
        agent_session_id="agent",
        user_id="9",
    )
    try:
        with patch(
            "services.kitty.ws.inbound.start_session_asr",
            new_callable=AsyncMock,
        ) as start:
            await dispatch_kitty_ws_inbound_message(
                ctx,
                {"type": "asr_start", "format": "opus", "utterance_id": "w1"},
            )
            start.assert_awaited_once()
            assert start.await_args is not None
            assert start.await_args.kwargs["audio_format"] == "opus"
            start.reset_mock()
            await dispatch_kitty_ws_inbound_message(ctx, {"type": "asr_start"})
            assert start.await_args is not None
            assert start.await_args.kwargs["audio_format"] == "pcm"
    finally:
        voice_sessions.pop(sid, None)
