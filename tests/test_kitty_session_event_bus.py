"""Tests for Kitty session event bus wiring (handlers + emit helpers)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.agent_loop.results import PENDING_AUTOCOMPLETE_KEY, arm_pending_autocomplete
from services.kitty.routing.command_router import RouteOutcome
from services.kitty.session.event_handlers import (
    KittySessionRuntime,
    setup_session_event_handlers,
)
from services.kitty.session.events import (
    KittyEvent,
    emit_diagram_mutated,
    get_session_event_bus,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.session.session_teardown import teardown_session_event_handlers
from tests.typing_helpers import mock_await_args


async def _drain_bus() -> None:
    """Allow the consumer task to process queued events."""
    await asyncio.sleep(0.05)


async def _make_event_runtime() -> tuple[KittySessionRuntime, str]:
    """Make event runtime."""
    ws = MagicMock()
    voice_session_id = create_voice_session(
        user_id="1",
        diagram_session_id="event_bus_test",
        diagram_type="circle_map",
    )
    voice_sessions[voice_session_id]["context"] = {
        "diagram_data": {"children": [], "center": {"text": ""}},
    }
    voice_sessions[voice_session_id]["conversation_history"] = []
    runtime = KittySessionRuntime(websocket=ws, voice_session_id=voice_session_id)
    await setup_session_event_handlers(runtime)
    return runtime, voice_session_id


async def _cleanup_event_runtime(voice_session_id: str) -> None:
    """Cleanup event runtime."""
    await teardown_session_event_handlers(voice_session_id)
    voice_sessions.pop(voice_session_id, None)


@pytest.mark.asyncio
async def test_auto_complete_done_records_observation() -> None:
    """Canvas generate-done is a second tool observation, not an Omni call."""
    _, voice_session_id = await _make_event_runtime()
    try:
        session = voice_sessions[voice_session_id]
        arm_pending_autocomplete(session, action="auto_complete_branch", node_id="n1")
        bus = get_session_event_bus(voice_session_id)
        await bus.emit(
            KittyEvent(
                kind="auto_complete_done",
                voice_session_id=voice_session_id,
                payload={"status": "finished", "node_id": "n1"},
            )
        )
        await _drain_bus()

        mem = get_session_memory(voice_session_id)
        assert any(turn.source == "tool" and "finished" in turn.content for turn in mem.turns)
        assert PENDING_AUTOCOMPLETE_KEY not in session
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_transcription_event_memory_only_no_router() -> None:
    """Test transcription event memory only no router."""
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        with patch(
            "services.kitty.session.event_handlers.route_voice_command",
            new=AsyncMock(),
        ) as route_mock:
            await bus.emit(
                KittyEvent(
                    kind="transcription",
                    voice_session_id=voice_session_id,
                    payload={"text": "add node apple"},
                )
            )
            await _drain_bus()

        route_mock.assert_not_awaited()
        mem = get_session_memory(voice_session_id)
        assert any(t.content == "add node apple" and t.source == "transcription" for t in mem.turns)
        history = voice_sessions[voice_session_id].get("conversation_history")
        assert isinstance(history, list)
        assert history[-1] == {"role": "user", "content": "add node apple"}
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_text_inbound_routes_typed_agent_loop() -> None:
    """Keyboard typed text uses the agent loop, not the one-shot router."""
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        with (
            patch(
                "services.kitty.session.event_handlers.run_typed_agent_loop",
                new=AsyncMock(return_value=MagicMock(outcome=RouteOutcome.EXECUTED)),
            ) as loop_mock,
            patch(
                "services.kitty.session.event_handlers.route_voice_command",
                new=AsyncMock(),
            ) as route_mock,
        ):
            await bus.emit(
                KittyEvent(
                    kind="text_inbound",
                    voice_session_id=voice_session_id,
                    payload={"text": "open mindmate"},
                )
            )
            await _drain_bus()

        loop_mock.assert_awaited_once()
        route_mock.assert_not_awaited()
        assert mock_await_args(loop_mock)[2] == "open mindmate"
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_text_inbound_asr_uses_same_agent_loop() -> None:
    """Fun-ASR ingress uses the same typed loop as keyboard."""
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        with (
            patch(
                "services.kitty.session.event_handlers.run_typed_agent_loop",
                new=AsyncMock(return_value=MagicMock(outcome=RouteOutcome.EXECUTED)),
            ) as loop_mock,
            patch(
                "services.kitty.session.event_handlers.route_voice_command",
                new=AsyncMock(),
            ) as route_mock,
        ):
            await bus.emit(
                KittyEvent(
                    kind="text_inbound",
                    voice_session_id=voice_session_id,
                    payload={"text": "删除历史", "ingress_source": "asr"},
                )
            )
            await _drain_bus()

        loop_mock.assert_awaited_once()
        route_mock.assert_not_awaited()
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_text_inbound_conversational_fallback_uses_text_reply() -> None:
    """General typed chat fallback stays on the text reply path."""
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        reply_mock = AsyncMock(return_value=True)
        with (
            patch(
                "services.kitty.session.event_handlers.run_typed_agent_loop",
                new=AsyncMock(return_value=MagicMock(outcome=RouteOutcome.CONVERSATIONAL_FALLBACK)),
            ),
            patch(
                "services.kitty.session.event_handlers.reply_text_only_conversational",
                reply_mock,
            ),
        ):
            await bus.emit(
                KittyEvent(
                    kind="text_inbound",
                    voice_session_id=voice_session_id,
                    payload={"text": "hello there"},
                )
            )
            await _drain_bus()

        reply_mock.assert_awaited_once()
        assert mock_await_args(reply_mock)[2] == "hello there"
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_diagram_mutated_bumps_freshness() -> None:
    """Diagram mutations refresh voice freshness, not an Omni session."""
    _, voice_session_id = await _make_event_runtime()
    try:
        with patch(
            "services.kitty.session.event_handlers.bump_voice_mutation_freshness",
        ) as bump_mock:
            await emit_diagram_mutated(voice_session_id, action="add_node", delta="add_node applied")
            await _drain_bus()

        bump_mock.assert_called_once_with(voice_session_id)
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_context_update_records_timestamp() -> None:
    """Context updates stamp the session clock for later loop snapshots."""
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        await bus.emit(
            KittyEvent(
                kind="context_update",
                voice_session_id=voice_session_id,
                payload={"reason": "context_update", "diagram_type": "circle_map"},
            )
        )
        await _drain_bus()

        assert voice_sessions[voice_session_id].get("_last_context_update_mono") is not None
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_teardown_clears_bus_and_memory() -> None:
    """Teardown drops the session bus and memory."""
    _runtime, voice_session_id = await _make_event_runtime()
    get_session_memory(voice_session_id).append_user_turn("hello", source="text")

    with (
        patch(
            "services.kitty.session.session_teardown.remove_session_event_bus",
        ) as remove_bus_mock,
        patch(
            "services.kitty.session.session_teardown.remove_session_memory",
        ) as remove_mem_mock,
    ):
        await teardown_session_event_handlers(voice_session_id)

    remove_bus_mock.assert_called_once_with(voice_session_id)
    remove_mem_mock.assert_called_once_with(voice_session_id)
    voice_sessions.pop(voice_session_id, None)
