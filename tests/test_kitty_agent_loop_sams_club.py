"""Agent loop against the real 山姆会员商店 mindmap fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram.mindmap_location import is_leftover_mindmap_branch_id
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.agent_loop.tools import leftover_live_key
from services.kitty.infra.bootstrap.kitty_context_hydrate import diagram_data_from_saved_spec
from services.kitty.routing.command_router import RouteOutcome
from services.kitty.routing.diagram_agent_context import (
    build_diagram_agent_payload,
    resolve_diagram_node_ref,
)
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.typing_helpers import mock_await_args

FIXTURE = Path(__file__).resolve().parent / "fixtures/zhihui_sams_club_l1.json"
COMPETITOR_UID = "7b1257c0-5091-4d7b-9985-410a104d56cb"


def _raw_spec() -> Dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _unhydrated_context() -> Dict[str, Any]:
    spec = _raw_spec()
    children = [
        {"id": node["id"], "text": node.get("text")}
        for node in spec["nodes"]
        if isinstance(node, dict) and node.get("type") != "topic"
    ]
    return {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_data": {
            "center": {"text": "山姆会员商店"},
            "children": children,
            "nodes": list(spec["nodes"]),
            "connections": list(spec.get("connections") or []),
        },
    }


def _hydrated_context() -> Dict[str, Any]:
    live = diagram_data_from_saved_spec(_raw_spec(), "mindmap")
    return {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_data": live,
    }


def _tool_reply(name: str, arguments: str, call_id: str = "call_1") -> Dict[str, Any]:
    return {
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


def _applied(*, revision: int, node_id: str, op: str, text: str = "") -> DiagramCommandResult:
    op_row: Dict[str, Any] = {"op": op, "node_id": node_id}
    if text:
        op_row["text"] = text
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id=f"sams-{revision}",
            revision=revision,
            applied_ops=[op_row],
        ),
        hub_revision=revision,
    )


async def _run_loop(
    text: str,
    *,
    context: Dict[str, Any],
    chat_side_effect: Any,
    bus_side_effect: Any,
) -> tuple[Any, str, AsyncMock, AsyncMock]:
    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id="scope-sams", diagram_type="mindmap")
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock(side_effect=chat_side_effect)
    bus_mock = AsyncMock(side_effect=bus_side_effect)
    finished = False
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
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
        ):
            result = await run_typed_agent_loop(ws, vid, text, dict(context))
        finished = True
        return result, vid, chat_mock, bus_mock
    finally:
        if not finished:
            voice_sessions.pop(vid, None)


def test_sams_club_hydrate_uses_uuid_not_leftover() -> None:
    """Production hydrate remaps leftover branch-* to mindMapUid."""
    live = diagram_data_from_saved_spec(_raw_spec(), "mindmap")
    leftover_live = [
        node["id"]
        for node in live["nodes"]
        if isinstance(node, dict) and is_leftover_mindmap_branch_id(str(node.get("id") or ""))
    ]
    assert leftover_live == []
    resolved = resolve_diagram_node_ref(live, label="竞争对手")
    assert resolved is not None
    assert resolved["node_id"] == COMPETITOR_UID


def test_sams_club_unhydrated_snapshot_prefers_uid() -> None:
    """Saved-spec leftover ids must not appear as snapshot keys when uid exists."""
    ctx = _unhydrated_context()
    payload = build_diagram_agent_payload(ctx, diagram_type="mindmap")
    ids = [item.get("id") for item in payload.get("nodes") or [] if isinstance(item, dict)]
    leftover = [item for item in ids if isinstance(item, str) and is_leftover_mindmap_branch_id(item)]
    assert leftover == []
    assert COMPETITOR_UID in ids


@pytest.mark.asyncio
async def test_sams_club_delete_competitor_uses_uuid() -> None:
    """Delete 「竞争对手」 on the hydrated Sam's Club map targets the uid."""
    context = _hydrated_context()
    result, vid, _chat, bus_mock = await _run_loop(
        "删除竞争对手这个分支",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.delete_node", '{"node_identifier":"竞争对手"}'),
            {"content": "已删除"},
        ],
        bus_side_effect=[_applied(revision=3, node_id=COMPETITOR_UID, op="delete_node")],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        command = mock_await_args(bus_mock)[2]
        assert command["action"] == "delete_node"
        assert command.get("node_id") == COMPETITOR_UID
        assert not is_leftover_mindmap_branch_id(str(command.get("node_id") or ""))
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_sams_club_unhydrated_leftover_migrates_then_deletes() -> None:
    """Client leftover ids migrate in-loop so delete still hits the uid."""
    context = _unhydrated_context()
    assert leftover_live_key({"action": "delete_node", "node_id": "branch-r-1-0"}, context) is None
    result, vid, _chat, bus_mock = await _run_loop(
        "删除竞争对手这个分支",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.delete_node", '{"node_identifier":"竞争对手"}'),
            {"content": "已删除"},
        ],
        bus_side_effect=[_applied(revision=4, node_id=COMPETITOR_UID, op="delete_node")],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        command = mock_await_args(bus_mock)[2]
        assert command.get("node_id") == COMPETITOR_UID
        live_ids: List[str] = [
            str(node.get("id")) for node in context["diagram_data"]["nodes"] if isinstance(node, dict)
        ]
        assert "branch-r-1-0" not in live_ids
        assert COMPETITOR_UID in live_ids
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_sams_club_add_then_created_id_is_observed() -> None:
    """add_node on the real map returns created id in the tool transcript."""
    context = _hydrated_context()
    created = "uid-member-policy"
    result, vid, chat_mock, bus_mock = await _run_loop(
        "添加一个会员制度的分支",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.add_node", '{"text":"会员制度"}'),
            {"content": "已添加"},
        ],
        bus_side_effect=[_applied(revision=5, node_id=created, op="add_node", text="会员制度")],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        command = mock_await_args(bus_mock)[2]
        assert command["action"] == "add_node"
        assert command.get("target") == "会员制度"
        second = chat_mock.await_args_list[1].kwargs["messages"]
        tool_rows = [row for row in second if row.get("role") == "tool"]
        assert tool_rows
        assert created in tool_rows[0]["content"]
        assert "会员制度" in tool_rows[0]["content"]
    finally:
        voice_sessions.pop(vid, None)
