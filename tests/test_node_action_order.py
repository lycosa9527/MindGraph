"""Tests for canonical node-action execution ordering."""

from __future__ import annotations

from services.kitty.routing.node_action_agent import _merge_tool_call_commands
from services.kitty.routing.node_action_order import order_node_action_commands
from services.kitty.routing.structural_chain import peel_chain_from_command


def test_order_puts_structure_before_autocomplete_even_if_reversed() -> None:
    """Structural edits run before any auto-complete commands."""
    ordered = order_node_action_commands(
        [
            {"action": "auto_complete", "confidence": 0.9},
            {"action": "auto_complete_branch", "target": "A"},
            {"action": "add_node", "target": "A"},
            {"action": "update_center", "target": "Topic"},
        ]
    )
    assert [cmd["action"] for cmd in ordered] == [
        "update_center",
        "add_node",
        "auto_complete_branch",
        "auto_complete",
    ]


def test_order_structural_subladder() -> None:
    """Within structural edits, center/delete/update precede add_node."""
    ordered = order_node_action_commands(
        [
            {"action": "add_node", "target": "new"},
            {"action": "update_node", "target": "x"},
            {"action": "delete_node", "target": "y"},
            {"action": "update_center", "target": "T"},
        ]
    )
    assert [cmd["action"] for cmd in ordered] == [
        "update_center",
        "delete_node",
        "update_node",
        "add_node",
    ]


def test_merge_tool_calls_uses_canonical_order() -> None:
    """Merged tool-call chains keep canonical primary + follow-up order."""
    merged = _merge_tool_call_commands(
        [
            {"action": "auto_complete_branch", "target": "跑步"},
            {"action": "add_node", "target": "跳跃"},
            {"action": "add_node", "target": "跑步"},
            {"action": "update_center", "target": "学生运动"},
        ]
    )
    assert merged is not None
    assert merged["action"] == "update_center"
    follow = merged.get("follow_up_actions")
    assert isinstance(follow, list)
    assert [item["action"] for item in follow] == [
        "add_node",
        "add_node",
        "auto_complete_branch",
    ]
    assert [item.get("target") for item in follow if item["action"] == "add_node"] == [
        "跳跃",
        "跑步",
    ]


def test_peel_reorders_structural_steps_when_primary_is_add() -> None:
    """Defense in depth: chain peel re-sorts even if primary was add_node."""
    command = {
        "action": "add_node",
        "target": "跑步",
        "follow_up_actions": [
            {"action": "update_center", "target": "学生运动"},
            {"action": "add_node", "target": "跳跃"},
            {"action": "auto_complete"},
        ],
    }
    follow = list(command["follow_up_actions"])
    steps, autocomplete, multi = peel_chain_from_command(command, follow)
    assert multi is True
    assert [step["action"] for step in steps] == [
        "update_center",
        "add_node",
        "add_node",
    ]
    assert [step.get("target") for step in steps] == ["学生运动", "跑步", "跳跃"]
    assert [item["action"] for item in autocomplete] == ["auto_complete"]
