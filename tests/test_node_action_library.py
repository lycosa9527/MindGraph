"""Tests for node-action library tools and command mapping."""

from __future__ import annotations

import json

from services.kitty.routing.node_action_library import (
    NODE_ACTION_ROWS,
    build_node_action_tools,
    command_from_tool_call,
    extract_branch_labels,
    extract_mindmap_topic,
    node_action_tool_names,
    render_diagram_snapshot_block,
    render_library_prompt,
)


def test_build_node_action_tools_includes_ui_actions() -> None:
    """Library tools extend structural diagram.* with branch fill and clarify."""
    names = {t["function"]["name"] for t in build_node_action_tools()}
    assert "diagram.add_node" in names
    assert "node_action.auto_complete_branch" in names
    assert "node_action.auto_complete" in names
    assert "node_action.clarify_options" in names


def test_command_from_tool_call_auto_complete_branch() -> None:
    """Branch auto-complete maps to legacy auto_complete_branch."""
    cmd = command_from_tool_call(
        "node_action.auto_complete_branch",
        json.dumps({"target": "中国"}),
    )
    assert cmd["action"] == "auto_complete_branch"
    assert cmd["target"] == "中国"


def test_command_from_tool_call_clarify_options() -> None:
    """Clarify tool maps labels and nested option commands."""
    args = {
        "question": "你是想：",
        "options": [
            {"label": "补全已有「中国」分支", "action": "auto_complete_branch", "target": "中国"},
            {"label": "新增「中国」分支", "action": "add_node", "target": "中国"},
        ],
    }
    cmd = command_from_tool_call("node_action.clarify_options", json.dumps(args))
    assert cmd["action"] == "clarify_options"
    assert len(cmd["options"]) == 2
    assert len(cmd["option_commands"]) == 2
    assert cmd["option_commands"][0]["action"] == "auto_complete_branch"


def test_command_from_tool_call_structural_delegates() -> None:
    """diagram.* tools reuse diagram_edit mapping."""
    cmd = command_from_tool_call(
        "diagram.add_node",
        json.dumps({"text": "饮品分析"}),
    )
    assert cmd["action"] == "add_node"
    assert cmd["target"] == "饮品分析"


def test_render_library_prompt_zh() -> None:
    """Library prompt lists OpenAI tool names, not legacy action keys."""
    text = render_library_prompt("zh")
    assert "node_action.auto_complete_branch" in text
    assert "node_action.clarify_options" in text
    assert "diagram.add_node" in text


def test_catalog_rows_map_to_registered_tools() -> None:
    """Every catalog row tool_name exists in build_node_action_tools()."""
    registered = node_action_tool_names()
    for row in NODE_ACTION_ROWS:
        assert row["tool_name"] in registered, row["tool_name"]


def test_diagram_snapshot_uses_branch_labels() -> None:
    """Snapshot JSON includes existing branches for agent matching."""
    ctx = {
        "diagram_data": {
            "center": {"text": "茶叶"},
            "children": [
                {"text": "中国", "id": "n1"},
                {"text": "日本", "id": "n2"},
            ],
        },
    }
    block = render_diagram_snapshot_block(ctx, diagram_type="mindmap", lang="zh")
    assert "茶叶" in block
    assert "中国" in block
    assert "日本" in block
    assert extract_mindmap_topic(ctx["diagram_data"]) == "茶叶"
    assert extract_branch_labels(ctx["diagram_data"]) == ["中国", "日本"]
