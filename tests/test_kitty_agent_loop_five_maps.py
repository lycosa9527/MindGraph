"""All library node actions on five real mindmaps (mocked LLM, real identity)."""

from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram.mindmap_location import is_leftover_mindmap_branch_id
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.routing.command_router import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.kitty_agent_loop_catalog import (
    NODE_ACTIONS,
    STRUCTURAL_ACTIONS,
    load_all_real_mindmaps,
    mock_tool_for,
    utterance_for,
)
from tests.typing_helpers import mock_await_args

_MAPS = load_all_real_mindmaps()
_CASES = [(mmap.slug, action) for mmap in _MAPS for action in NODE_ACTIONS]
_MAP_BY_SLUG = {mmap.slug: mmap for mmap in _MAPS}


def _tool_reply(name: str, arguments: str) -> Dict[str, Any]:
    return {
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


def _applied(action: str, node_id: str | None) -> DiagramCommandResult:
    applied_ops = [{"op": action, "node_id": node_id}] if node_id else [{"op": action}]
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id="five-maps",
            revision=2,
            applied_ops=applied_ops,
        ),
        hub_revision=2,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("slug", "action"), _CASES, ids=[f"{s}-{a}" for s, a in _CASES])
async def test_five_maps_all_node_actions(slug: str, action: str) -> None:
    """Each real map dispatches every library action through identity + Bus/UI."""
    mmap = _MAP_BY_SLUG[slug]
    utterance = utterance_for(mmap, action)
    tool_name, tool_args = mock_tool_for(mmap, action)
    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id=f"scope-{slug}", diagram_type="mindmap")
    voice_sessions[vid]["context"] = mmap.context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    bus_mock = AsyncMock(return_value=_applied(action, mmap.branch_id))
    branch_mock = AsyncMock(return_value=True)
    start_ac_mock = AsyncMock(return_value=True)
    ws_mock = AsyncMock(return_value=True)
    chat_mock = AsyncMock(side_effect=[_tool_reply(tool_name, tool_args), {"content": "好的"}])
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.tools.emit_auto_complete_branch", branch_mock),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                start_ac_mock,
            ),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
        ):
            result = await run_typed_agent_loop(ws, vid, utterance, dict(mmap.context))

        assert result.outcome == RouteOutcome.EXECUTED, result
        assert result.reason != "heuristic", result
        if action in STRUCTURAL_ACTIONS:
            bus_mock.assert_awaited()
            command = mock_await_args(bus_mock)[2]
            assert command.get("action") == action, command
            if action in {"update_node", "delete_node"}:
                assert command.get("node_id") == mmap.branch_id, command
                assert not is_leftover_mindmap_branch_id(str(command.get("node_id") or ""))
            if action == "add_node":
                assert command.get("target") == "扩展阅读", command
                start_ac_mock.assert_awaited()
                assert start_ac_mock.await_args is not None
                assert start_ac_mock.await_args.kwargs.get("node_id") == mmap.branch_id
                assert result.reason == "await_canvas"
            if action == "update_center":
                assert "导学" in str(command.get("target") or ""), command
        elif action == "auto_complete_branch":
            branch_mock.assert_awaited()
            kwargs = branch_mock.await_args.kwargs if branch_mock.await_args else {}
            assert kwargs.get("node_id") == mmap.branch_id
        elif action == "auto_complete":
            ws_mock.assert_awaited()
            payload = mock_await_args(ws_mock)[2]
            assert payload.get("action") == "auto_complete"
        elif action == "clarify_options":
            assert result.action == "clarify_options"
            pending = voice_sessions[vid].get("pending_clarify_options")
            assert isinstance(pending, dict)
            assert len(pending.get("option_commands") or []) >= 2
    finally:
        voice_sessions.pop(vid, None)


def test_five_real_mindmaps_loaded() -> None:
    """Catalog exposes five distinct hydrated maps with UUID branches."""
    slugs = [mmap.slug for mmap in _MAPS]
    assert slugs == [
        "sams_club",
        "photosynthesis",
        "new_energy_vehicles",
        "chinese_tea",
        "beijing_trip",
    ]
    topics = {mmap.topic for mmap in _MAPS}
    assert len(topics) == 5
    for mmap in _MAPS:
        assert mmap.branch_label
        assert mmap.branch_id
        assert mmap.branch_id != "topic"
        assert not is_leftover_mindmap_branch_id(mmap.branch_id)
        assert json.dumps(mmap.context["diagram_data"], ensure_ascii=False)
