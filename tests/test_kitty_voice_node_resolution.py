"""Tests for Kitty voice node reference resolution."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.diagram.diagram_utils import (
    child_node_live_id,
    resolve_voice_node_reference,
    session_context_child_record,
)
from services.kitty.infra.bootstrap.kitty_native_spec import native_spec_to_pseudo_nodes
from services.kitty.omni.tools import omni_function_call_to_command
from services.kitty.routing.command_router import RouteOutcome, route_omni_function_call
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.typing_helpers import mock_await_args


def test_child_node_live_id_never_invents_mindmap_branch_n() -> None:
    """Mind-map voice snapshots must use the canvas UUID, never branch_N."""
    assert child_node_live_id({"id": "uid-diy", "text": "DIY"}, 0, "mindmap") == "uid-diy"
    assert child_node_live_id({"id": "branch-l-1-0", "text": "DIY"}, 0, "mindmap") is None
    assert child_node_live_id({"id": "branch_1", "text": "DIY"}, 0, "mindmap") is None
    assert child_node_live_id("DIY", 0, "mindmap") is None
    assert child_node_live_id({"text": "DIY"}, 0, "mindmap") is None
    assert child_node_live_id("Wheels", 0, "circle_map") == "context_0"
    record = session_context_child_record("Paint", 2, "mindmap")
    assert "id" not in record
    assert record["text"] == "Paint"
    circle = session_context_child_record("Wheels", 1, "circle_map")
    assert circle["id"] == "context_1"


def test_resolve_voice_mindmap_index_uses_uuid_not_invented_prefix() -> None:
    """Index resolution on a UUID canvas must not emit branch_0."""
    ctx: dict[str, object] = {
        "diagram_data": {
            "children": [{"id": "uid-diy", "text": "DIY"}],
            "nodes": [
                {"id": "topic", "text": "Cars", "type": "topic"},
                {"id": "uid-diy", "text": "DIY", "type": "branch"},
            ],
        },
    }
    out = resolve_voice_node_reference(ctx, "mindmap", node_index=0)
    assert out is not None
    assert out["node_id"] == "uid-diy"
    by_label = resolve_voice_node_reference(
        {
            "diagram_data": {
                "children": ["DIY"],
                "nodes": [{"id": "uid-diy", "text": "DIY", "type": "branch"}],
            },
        },
        "mindmap",
        node_index=0,
    )
    assert by_label is not None
    assert by_label["node_id"] == "uid-diy"
    missing = resolve_voice_node_reference(
        {"diagram_data": {"children": ["DIY"], "nodes": []}},
        "mindmap",
        node_index=0,
    )
    assert missing is None


def test_native_spec_mindmap_uses_stored_or_uuid_ids() -> None:
    """Branches-only library specs keep stored ids and never invent mm-bN."""
    nodes = native_spec_to_pseudo_nodes(
        {
            "topic": "Cars",
            "branches": [{"id": "uid-diy", "text": "DIY", "children": [{"text": "Paint"}]}],
        },
        "mindmap",
    )
    assert nodes is not None
    ids = [node["id"] for node in nodes]
    assert "topic" in ids
    assert "uid-diy" in ids
    assert all(not str(node_id).startswith("mm-b") for node_id in ids)
    paint = next(node for node in nodes if node["text"] == "Paint")
    assert paint["id"] != "mm-b0-b0"
    assert len(str(paint["id"])) >= 8


def test_native_spec_leftover_branch_n_becomes_uuid() -> None:
    """LLM ``branch_1`` / ``sub_*`` ids are not adopted as live canvas ids."""
    nodes = native_spec_to_pseudo_nodes(
        {
            "topic": "Cars",
            "children": [
                {
                    "id": "branch_1",
                    "text": "DIY",
                    "children": [{"id": "sub_1_1", "text": "Paint"}],
                }
            ],
        },
        "mindmap",
    )
    assert nodes is not None
    diy = next(node for node in nodes if node["text"] == "DIY")
    paint = next(node for node in nodes if node["text"] == "Paint")
    assert diy["id"] != "branch_1"
    assert paint["id"] != "sub_1_1"
    assert diy["data"]["mindMapLegacyId"] == "branch_1"
    assert paint["data"]["mindMapLegacyId"] == "sub_1_1"
    assert len(str(diy["id"])) >= 8
    assert len(str(paint["id"])) >= 8


def test_resolve_voice_node_by_index_uses_child_id() -> None:
    """Index resolve uses the live UUID, not a leftover invented child id."""
    ctx = {
        "diagram_data": {
            "children": [
                {"id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", "text": "Sports"},
                {"id": "ffffffff-1111-4222-8333-444444444444", "text": "Music"},
            ],
        },
        "selected_nodes": [],
    }
    out = resolve_voice_node_reference(ctx, "mindmap", node_index=0)
    assert out is not None
    assert out["node_id"] == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    assert out["node_label"] == "Sports"


def test_resolve_voice_index_rejects_leftover_child_id() -> None:
    """Stale leftover children[] ids are not adopted; unique label maps to UUID."""
    leftover_only: dict[str, object] = {
        "diagram_data": {
            "children": [{"id": "branch-l-1-0", "text": "Sports"}],
        },
    }
    assert resolve_voice_node_reference(leftover_only, "mindmap", node_index=0) is None
    ctx: dict[str, object] = {
        "diagram_data": {
            "children": [{"id": "branch-l-1-0", "text": "Sports"}],
            "nodes": [{"id": "uid-sports", "text": "Sports"}],
        },
    }
    out = resolve_voice_node_reference(ctx, "mindmap", node_index=0)
    assert out is not None
    assert out["node_id"] == "uid-sports"


def test_resolve_voice_node_by_text_match() -> None:
    """Test resolve voice node by text match."""
    ctx = {
        "diagram_data": {
            "children": [{"id": "context-0", "text": "Wheels"}],
        },
    }
    out = resolve_voice_node_reference(cast(dict[str, object], ctx), "circle_map", node_identifier="Wheel")
    assert out is not None
    assert out["node_id"] == "context-0"
    assert out["node_index"] == 0


def test_resolve_voice_node_falls_back_to_selected() -> None:
    """Test resolve voice node falls back to selected."""
    ctx = {
        "diagram_data": {
            "children": [{"id": "bubble-1", "text": "Fast"}],
            "selected_nodes": ["bubble-1"],
        },
        "selected_nodes": ["bubble-1"],
    }
    out = resolve_voice_node_reference(ctx, "bubble_map", prefer_selected=True)
    assert out is not None
    assert out["node_id"] == "bubble-1"
    assert out["node_label"] == "Fast"


def test_omni_start_inline_recommendations_tool() -> None:
    """Test omni start inline recommendations tool."""
    cmd = omni_function_call_to_command(
        "start_inline_recommendations",
        '{"node_identifier": "第一个"}',
    )
    assert cmd["action"] == "start_inline_recommendations"
    assert cmd["node_identifier"] == "第一个"


def test_omni_explain_node_without_identifier() -> None:
    """Test omni explain node without identifier."""
    cmd = omni_function_call_to_command("explain_node", "{}")
    assert cmd["action"] == "explain_node"
    assert "node_identifier" not in cmd


def test_omni_add_node_with_recommendations_tool() -> None:
    """Test omni add node with recommendations tool."""
    cmd = omni_function_call_to_command("add_node_with_recommendations", "{}")
    assert cmd["action"] == "add_node_with_recommendations"
    assert cmd.get("target") is None

    cmd2 = omni_function_call_to_command(
        "add_node_with_recommendations",
        '{"text": "placeholder"}',
    )
    assert cmd2["target"] == "placeholder"


@pytest.mark.asyncio
async def test_route_omni_add_node_with_recommendations() -> None:
    """Test route omni add node with recommendations."""
    ws = MagicMock()
    vid = create_voice_session(user_id="3", diagram_session_id="scope_test", diagram_type="bubble_map")
    voice_sessions[vid]["context"] = {"diagram_data": {"children": []}}

    send_mock = AsyncMock(return_value=True)
    omni_mock = AsyncMock()

    try:
        with (
            patch(
                "services.kitty.routing.command_router.load_kitty_live_context",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.kitty.routing.command_router.throttled_refresh_voice_context_from_library",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.kitty.routing.command_router.safe_websocket_send",
                send_mock,
            ),
            patch(
                "services.kitty.routing.command_router.get_session_omni_client",
                return_value=omni_mock,
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_omni_function_call(
                ws,
                vid,
                "add_node_with_recommendations",
                "{}",
                dict(voice_sessions[vid]["context"]),
            )
        assert result.outcome == RouteOutcome.EXECUTED
        payload = mock_await_args(send_mock)[1]
        assert payload["action"] == "add_node_with_recommendations"
        omni_mock.create_response.assert_awaited()
    finally:
        voice_sessions.pop(vid, None)


def test_omni_ask_mindmate_tool() -> None:
    """Test omni ask mindmate tool."""
    cmd = omni_function_call_to_command(
        "ask_mindmate",
        '{"message": "什么是光合作用？"}',
    )
    assert cmd["action"] == "ask_mindmate"
    assert cmd["target"] == "什么是光合作用？"
