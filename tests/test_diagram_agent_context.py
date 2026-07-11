"""Tests for full diagram JSON serialization in NodeActionAgent prompts."""

from __future__ import annotations

import json

from services.kitty.routing.diagram_agent_context import (
    build_diagram_agent_payload,
    enrich_node_action_command,
    serialize_diagram_for_node_action,
)
from services.kitty.routing.node_action_library import (
    command_from_tool_call,
    render_diagram_snapshot_block,
)


def test_payload_includes_all_pinia_nodes() -> None:
    """nodes[] from the canvas is included with id and text."""
    ctx = {
        "diagram_data": {
            "center": {"text": "茶叶"},
            "children": [{"id": "branch-r-1-0", "text": "中国"}],
            "nodes": [
                {"id": "topic", "text": "茶叶", "type": "topic"},
                {"id": "branch-r-1-0", "text": "中国", "type": "branch"},
                {"id": "branch-r-1-0-child-0", "text": "绿茶", "type": "child"},
            ],
        },
        "selected_nodes": ["branch-r-1-0"],
    }
    payload = build_diagram_agent_payload(ctx, diagram_type="mindmap")
    assert payload["topic"] == "茶叶"
    assert len(payload["nodes"]) == 3
    assert any(n.get("text") == "绿茶" for n in payload["nodes"])
    assert payload["selected"][0]["node_id"] == "branch-r-1-0"
    assert payload["selected"][0]["node_label"] == "中国"


def test_snapshot_block_is_json_with_header() -> None:
    """render_diagram_snapshot_block emits full JSON, not a 4-line summary."""
    ctx = {
        "diagram_data": {
            "center": {"text": "茶叶"},
            "children": [{"text": "中国", "id": "n1"}, {"text": "日本", "id": "n2"}],
        },
    }
    block = render_diagram_snapshot_block(ctx, diagram_type="mindmap", lang="zh")
    assert "当前导图（JSON" in block
    assert "茶叶" in block
    assert "中国" in block
    assert "日本" in block
    json_part = block.split("\n", 1)[1]
    parsed = json.loads(json_part.split("\n…[")[0])
    assert parsed["diagram_type"] == "mindmap"
    assert parsed["topic"] == "茶叶"


def test_nested_children_in_payload() -> None:
    """Server-side nested children[] is preserved in the tree."""
    ctx = {
        "diagram_data": {
            "center": {"text": "茶叶"},
            "children": [
                {
                    "id": "b1",
                    "text": "中国",
                    "children": [{"id": "c1", "text": "绿茶"}],
                },
            ],
        },
    }
    payload = build_diagram_agent_payload(ctx, diagram_type="mindmap")
    children = payload["children"]
    assert isinstance(children, list)
    assert children[0]["text"] == "中国"
    assert children[0]["children"][0]["text"] == "绿茶"


def test_serialize_truncates_large_payload() -> None:
    """Very large diagrams are capped with a truncation marker."""
    many_nodes = [{"id": f"n{i}", "text": f"节点{i}" * 20, "type": "branch"} for i in range(200)]
    ctx = {"diagram_data": {"center": {"text": "大"}, "nodes": many_nodes}}
    block, truncated = serialize_diagram_for_node_action(
        ctx,
        diagram_type="mindmap",
        max_chars=500,
    )
    assert truncated is True
    assert "truncated" in block


def test_enrich_add_node_does_not_invent_node_id() -> None:
    """add_node must not echo target text as node_id when the node does not exist yet."""
    ctx = {
        "diagram_data": {
            "nodes": [
                {"id": "topic", "text": "鼠标", "type": "topic"},
                {"id": "branch-r-1-0", "text": "品牌", "type": "branch"},
            ],
        },
    }
    cmd = enrich_node_action_command(
        {
            "action": "add_node",
            "target": "使用场景",
            "node_id": "使用场景",
            "confidence": 0.95,
        },
        ctx,
    )
    assert "node_id" not in cmd
    assert cmd["target"] == "使用场景"


def test_enrich_auto_complete_branch_adds_node_id() -> None:
    """Post-parse enrichment attaches stable node_id from diagram snapshot."""
    ctx = {
        "diagram_data": {
            "nodes": [
                {"id": "branch-r-1-0", "text": "中国", "type": "branch"},
            ],
        },
    }
    cmd = enrich_node_action_command(
        {"action": "auto_complete_branch", "target": "中国", "confidence": 0.95},
        ctx,
    )
    assert cmd["node_id"] == "branch-r-1-0"
    assert cmd["target"] == "中国"


def test_enrich_uses_node_id_when_label_changed() -> None:
    """node_id still resolves after the visible label changes on canvas."""
    ctx = {
        "diagram_data": {
            "nodes": [
                {"id": "branch-r-1-0", "text": "中华茶文化", "type": "branch"},
            ],
        },
    }
    cmd = enrich_node_action_command(
        {"action": "delete_node", "node_id": "branch-r-1-0", "confidence": 0.95},
        ctx,
    )
    assert cmd["node_id"] == "branch-r-1-0"
    assert cmd.get("target") == "中华茶文化"


def test_command_from_tool_call_auto_complete_branch_with_node_id() -> None:
    """Tool call may pass node_id directly from the LLM."""
    cmd = command_from_tool_call(
        "node_action.auto_complete_branch",
        json.dumps({"node_id": "branch-r-1-0", "target": "中国"}),
    )
    assert cmd["action"] == "auto_complete_branch"
    assert cmd["node_id"] == "branch-r-1-0"
    assert cmd["target"] == "中国"
