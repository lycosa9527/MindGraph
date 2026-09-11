"""Speak the office line before the canvas apply; fail replaces speech."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions


def _edit_context() -> dict:
    return {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_type": "mind_map",
        "diagram_data": {
            "center": {"text": "Cars"},
            "children": [{"id": "uid-hist", "text": "历史"}],
            "nodes": [
                {"id": "topic", "text": "Cars"},
                {"id": "uid-hist", "text": "历史"},
            ],
        },
    }


def _applied_result() -> DiagramCommandResult:
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id="mut-1",
            revision=2,
            applied_ops=[{"op": "update_center", "text": "光合作用"}],
        ),
        hub_revision=2,
    )


def _failed_result() -> DiagramCommandResult:
    return DiagramCommandResult(
        tool_result=ToolResult(status="failed", mutation_id="", revision=1, applied_ops=[]),
        hub_revision=1,
    )


async def _run_center_turn(
    *,
    bus_result: DiagramCommandResult,
    order: list[str],
) -> RouteOutcome:
    context = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-speak-apply",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"

    async def emit_ack(*_args, **_kwargs):
        order.append("ack")
        return True

    async def apply_cmd(*_args, **_kwargs):
        order.append("apply")
        return bus_result

    async def interrupt(*_args, **_kwargs):
        order.append("interrupt")

    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=AsyncMock()),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", apply_cmd),
            patch("services.kitty.agent_loop.tools.emit_user_ack", emit_ack),
            patch("services.kitty.agent_loop.tools.interrupt_kitty_tts", interrupt),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                new=AsyncMock(return_value=False),
            ),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
            patch("services.kitty.agent_loop.loop.fanout_voice_phase_from_session", new=AsyncMock()),
        ):
            result = await run_typed_agent_loop(ws, vid, "主题改成光合作用", dict(context))
        return result.outcome
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_speak_then_apply_success_one_ack() -> None:
    """Commit line is spoken before apply; success does not speak again."""
    order: list[str] = []
    outcome = await _run_center_turn(bus_result=_applied_result(), order=order)
    assert outcome == RouteOutcome.EXECUTED
    assert order == ["ack", "apply"]


@pytest.mark.asyncio
async def test_speak_then_apply_fail_interrupts() -> None:
    """Failed apply cuts the commit line and speaks a fail ack."""
    order: list[str] = []
    outcome = await _run_center_turn(bus_result=_failed_result(), order=order)
    assert outcome == RouteOutcome.FAILED
    assert order == ["ack", "apply", "interrupt", "ack"]
