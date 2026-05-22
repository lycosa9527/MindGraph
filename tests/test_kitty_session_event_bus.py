"""Tests for Kitty session event bus wiring (handlers + emit helpers)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.session.runtime_state import voice_sessions
from services.kitty.session.event_handlers import (
    KittySessionRuntime,
    setup_session_event_handlers,
    teardown_session_event_handlers,
)
from services.kitty.session.events import (
    KittyEvent,
    emit_diagram_mutated,
    get_session_event_bus,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.ops import create_voice_session


async def _drain_bus() -> None:
    """Allow the consumer task to process queued events."""
    await asyncio.sleep(0.05)


async def _make_event_runtime() -> tuple[KittySessionRuntime, str]:
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
    await teardown_session_event_handlers(voice_session_id)
    voice_sessions.pop(voice_session_id, None)


@pytest.mark.asyncio
async def test_function_call_event_routes_omni_call() -> None:
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        with patch(
            "services.kitty.session.event_handlers.route_omni_function_call",
            new=AsyncMock(),
        ) as route_mock:
            await bus.emit(
                KittyEvent(
                    kind="function_call",
                    voice_session_id=voice_session_id,
                    payload={"name": "add_node", "arguments": '{"text": "apple"}'},
                )
            )
            await _drain_bus()

        route_mock.assert_awaited_once()
        assert route_mock.await_args.args[2] == "add_node"
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_transcription_event_memory_only_no_router() -> None:
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        with (
            patch(
                "services.kitty.session.event_handlers.route_voice_command",
                new=AsyncMock(),
            ) as route_mock,
            patch(
                "services.kitty.session.event_handlers.route_omni_function_call",
                new=AsyncMock(),
            ) as fn_mock,
        ):
            await bus.emit(
                KittyEvent(
                    kind="transcription",
                    voice_session_id=voice_session_id,
                    payload={"text": "add node apple"},
                )
            )
            await _drain_bus()

        route_mock.assert_not_awaited()
        fn_mock.assert_not_awaited()
        mem = get_session_memory(voice_session_id)
        assert any(t.content == "add node apple" and t.source == "transcription" for t in mem.turns)
        history = voice_sessions[voice_session_id].get("conversation_history")
        assert isinstance(history, list)
        assert history[-1] == {"role": "user", "content": "add node apple"}
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_text_inbound_routes_with_from_voice_false() -> None:
    from services.kitty.routing.command_router import RouteOutcome

    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        with patch(
            "services.kitty.session.event_handlers.route_voice_command",
            new=AsyncMock(return_value=MagicMock(outcome=RouteOutcome.EXECUTED)),
        ) as route_mock:
            await bus.emit(
                KittyEvent(
                    kind="text_inbound",
                    voice_session_id=voice_session_id,
                    payload={"text": "open mindmate"},
                )
            )
            await _drain_bus()

        route_mock.assert_awaited_once()
        assert route_mock.await_args.kwargs["from_voice"] is False
        assert route_mock.await_args.kwargs["is_text_message"] is True
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_text_inbound_conversational_fallback_sends_omni() -> None:
    from services.kitty.routing.command_router import RouteOutcome

    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        omni = AsyncMock()
        with (
            patch(
                "services.kitty.session.event_handlers.route_voice_command",
                new=AsyncMock(return_value=MagicMock(outcome=RouteOutcome.CONVERSATIONAL_FALLBACK)),
            ),
            patch(
                "services.kitty.session.event_handlers.get_session_omni_client",
                return_value=omni,
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

        omni.send_text_message.assert_awaited_once_with("hello there")
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_diagram_mutated_schedules_single_debounced_refresh() -> None:
    _, voice_session_id = await _make_event_runtime()
    try:
        with patch(
            "services.kitty.session.event_handlers.schedule_omni_context_refresh",
            new=AsyncMock(),
        ) as schedule_mock:
            await emit_diagram_mutated(voice_session_id, action="add_node", delta="add_node applied")
            await _drain_bus()

        schedule_mock.assert_awaited_once()
        assert schedule_mock.await_args.kwargs["reason"] == "diagram_mutation"
        assert schedule_mock.await_args.kwargs["delta"] == "add_node applied"
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_context_update_schedules_refresh_once() -> None:
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        with patch(
            "services.kitty.session.event_handlers.schedule_omni_context_refresh",
            new=AsyncMock(),
        ) as schedule_mock:
            await bus.emit(
                KittyEvent(
                    kind="context_update",
                    voice_session_id=voice_session_id,
                    payload={"reason": "context_update", "diagram_type": "circle_map"},
                )
            )
            await _drain_bus()

        schedule_mock.assert_awaited_once()
        assert schedule_mock.await_args.kwargs["reason"] == "context_update"
        assert voice_sessions[voice_session_id].get("_last_context_update_mono") is not None
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_image_paragraph_event_processes_paragraph() -> None:
    _, voice_session_id = await _make_event_runtime()
    try:
        bus = get_session_event_bus(voice_session_id)
        with patch(
            "services.kitty.session.event_handlers.process_paragraph_with_qwen_plus",
            new=AsyncMock(return_value=True),
        ) as paragraph_mock:
            await bus.emit(
                KittyEvent(
                    kind="image_paragraph",
                    voice_session_id=voice_session_id,
                    payload={"text": "Describe this image in detail."},
                )
            )
            await _drain_bus()

        paragraph_mock.assert_awaited_once()
    finally:
        await _cleanup_event_runtime(voice_session_id)


@pytest.mark.asyncio
async def test_teardown_clears_bus_memory_and_pending_refresh() -> None:
    _runtime, voice_session_id = await _make_event_runtime()
    get_session_memory(voice_session_id).append_user_turn("hello", source="text")

    with (
        patch(
            "services.kitty.session.events.remove_session_event_bus",
        ) as remove_bus_mock,
        patch(
            "services.kitty.session.memory.remove_session_memory",
        ) as remove_mem_mock,
        patch(
            "services.kitty.omni.context_refresh.cancel_pending_omni_refresh",
        ) as cancel_mock,
    ):
        await teardown_session_event_handlers(voice_session_id)

    remove_bus_mock.assert_called_once_with(voice_session_id)
    remove_mem_mock.assert_called_once_with(voice_session_id)
    cancel_mock.assert_called_once_with(voice_session_id)
    voice_sessions.pop(voice_session_id, None)
