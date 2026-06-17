"""Tests for Kitty voice diagram intents → hub ``patch_context`` bridge."""

from __future__ import annotations

import copy
from unittest.mock import AsyncMock, patch

import pytest

from services.agent_hub.scope_lifecycle import MindGraphAgentHub
from services.kitty.diagram.hub_bridge import (
    DIAGRAM_VOICE_INTENTS,
    build_patch_context_mutation_cmd,
    preview_voice_context_after_diagram_intent,
    try_sync_voice_diagram_to_hub,
)
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions


def test_diagram_voice_intents_count() -> None:
    """Test diagram voice intents count."""
    assert len(DIAGRAM_VOICE_INTENTS) == 4


def test_build_patch_context_mutation_cmd_shape() -> None:
    """Test build patch context mutation cmd shape."""
    merged = {"diagram_data": {"center": {"text": "x"}}}
    cmd = build_patch_context_mutation_cmd(
        merged_context=merged,
        diagram_type="circle_map",
        active_panel="none",
    )
    assert cmd["op"] == "patch_context"
    assert cmd["context"] is merged
    assert cmd["diagram_type"] == "circle_map"
    assert cmd["active_panel"] == "none"


@pytest.mark.parametrize(
    "action,command,diagram_type,assert_fn",
    [
        (
            "update_center",
            {"target": "Topic"},
            "circle_map",
            lambda ctx: ctx["diagram_data"]["center"]["text"] == "Topic",
        ),
        (
            "update_node",
            {"target": "Hi", "node_index": 0},
            "circle_map",
            lambda ctx: ctx["diagram_data"]["children"][0]["text"] == "Hi",
        ),
        (
            "add_node",
            {"target": "New"},
            "circle_map",
            lambda ctx: ctx["diagram_data"]["children"][-1]["text"] == "New",
        ),
        (
            "delete_node",
            {"node_index": 0},
            "circle_map",
            lambda ctx: len(ctx["diagram_data"]["children"]) == 0,
        ),
    ],
)
def test_preview_circle_map_intents(
    action: str,
    command: dict,
    diagram_type: str,
    assert_fn,
) -> None:
    """Test preview circle map intents."""
    base = {
        "diagram_data": {
            "center": {"text": "Old"},
            "children": [{"id": "n0", "text": "A"}],
        }
    }
    before = copy.deepcopy(base)
    out = preview_voice_context_after_diagram_intent(
        action=action,
        command=command,
        session_context=base,
        diagram_type=diagram_type,
    )
    assert out is not None
    assert assert_fn(out)
    assert base == before


def test_preview_double_bubble_update_center() -> None:
    """Test preview double bubble update center."""
    base = {"diagram_data": {"left": "L0", "right": "R0"}}
    out = preview_voice_context_after_diagram_intent(
        action="update_center",
        command={"left": "L1", "right": "R1"},
        session_context=base,
        diagram_type="double_bubble_map",
    )
    assert out is not None
    assert out["diagram_data"]["left"] == "L1"
    assert out["diagram_data"]["right"] == "R1"


def test_preview_unsupported_returns_none() -> None:
    """Test preview unsupported returns none."""
    assert (
        preview_voice_context_after_diagram_intent(
            action="update_node",
            command={"target": "missing"},
            session_context={"diagram_data": {"children": []}},
            diagram_type="flow_map",
        )
        is None
    )


def test_preview_bubble_map_add_node_syncs_attributes() -> None:
    """Test preview bubble map add node syncs attributes."""
    base = {"diagram_data": {"center": {"text": "Dog"}, "children": []}}
    out = preview_voice_context_after_diagram_intent(
        action="add_node",
        command={"target": "loyal"},
        session_context=base,
        diagram_type="bubble_map",
    )
    assert out is not None
    assert out["diagram_data"]["attributes"] == [{"text": "loyal"}]


@pytest.mark.asyncio
async def test_try_sync_voice_diagram_to_hub_updates_revision() -> None:
    """Test try sync voice diagram to hub updates revision."""
    hub = MindGraphAgentHub()
    hub_sid = await hub.open_session(42, client_lane="mobile", source_module="kitty_bridge_test")
    await hub.bind_scope(hub_sid, diagram_scope="scope_z", source_module="kitty_bridge_test")

    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope_z",
        diagram_type="circle_map",
        active_panel="none",
    )
    voice_sessions[vid]["context"] = {
        "diagram_data": {"center": {"text": "hub"}, "children": []},
        "diagram_library_id": "scope_z",
    }
    voice_sessions[vid]["_hub_session_id"] = hub_sid
    voice_sessions[vid]["_hub_scope_revision"] = 0

    try:
        with (
            patch(
                "services.agent_hub.scope_lifecycle.upsert_kitty_redis_session",
                AsyncMock(return_value=123456),
            ),
            patch(
                "services.kitty.diagram.hub_bridge.get_mind_graph_agent_hub",
                return_value=hub,
            ),
            patch(
                "services.kitty.diagram.hub_bridge.apply_kitty_ws_context_patch",
                AsyncMock(return_value={"revision": 1}),
            ),
        ):
            await try_sync_voice_diagram_to_hub(vid)

        assert voice_sessions[vid].get("_hub_scope_revision") == 1
    finally:
        voice_sessions.pop(vid, None)
        await hub.close_session(hub_sid, reason="test_cleanup")
