"""Thinking Map identity: leftover migrate, aliases, unique label, live reject."""

from __future__ import annotations

from typing import Any

from agents.inline_recommendations.context_extractors import (
    extract_bubble_map_context,
    extract_circle_map_context,
    extract_double_bubble_context,
)
from services.diagram.mindmap_identity import is_machine_node_id
from services.diagram_edit.effects import build_expected_effect
from services.diagram_edit.types import DiagramEditCommand
from services.diagram_edit.verify import verify_thinking_map_effect
from services.diagram.thinking_map_identity import (
    as_live_thinking_map_node_id,
    migrate_thinking_map_diagram_payload,
    resolve_thinking_map_identity_id,
    thinking_map_identity_aliases,
)
from services.diagram.thinking_map_patterns import is_leftover_thinking_map_id
from services.kitty.agent_loop.tools import leftover_live_key
from services.kitty.diagram.diagram_utils import child_node_live_id, session_context_child_record
from services.kitty.infra.bootstrap.kitty_native_spec import native_spec_to_pseudo_nodes
from services.mind_classroom.job_match import job_matches_live_nodes, spec_snapshot_node_ids
from services.mind_classroom.outline import extract_mindmap_outline
from services.mind_classroom.steps import collect_spec_node_ids, normalize_steps
from services.showcase.diagram_structure_outline import build_diagram_structure_outline


def _circle_payload() -> dict:
    return {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "水循环"},
            {"id": "context-0", "type": "bubble", "text": "蒸发"},
            {"id": "context-1", "type": "bubble", "text": "降水"},
        ],
        "connections": [
            {"id": "e-topic-context-0", "source": "topic", "target": "context-0"},
            {"id": "e-topic-context-1", "source": "topic", "target": "context-1"},
        ],
        "_node_styles": {"context-0": {"backgroundColor": "#eee"}},
        "children": [{"id": "context-0", "text": "蒸发", "index": 0}],
    }


def test_migrate_rewrites_leftover_edges_and_styles() -> None:
    """Hyphen leftover ids become UUIDs with rewritten edges and style keys."""
    payload = _circle_payload()
    id_map = migrate_thinking_map_diagram_payload(payload, "circle_map")
    assert id_map["context-0"]
    assert id_map["context-0"] != "context-0"
    assert not is_leftover_thinking_map_id("circle_map", id_map["context-0"])
    evap = next(node for node in payload["nodes"] if node["text"] == "蒸发")
    assert evap["id"] == id_map["context-0"]
    assert evap["data"]["circleMapLegacyId"] == "context-0"
    assert evap["data"]["circleMapUid"] == evap["id"]
    assert payload["connections"][0]["target"] == evap["id"]
    assert payload["_node_styles"][evap["id"]]["backgroundColor"] == "#eee"
    assert payload["children"][0]["id"] == evap["id"]
    aliases = thinking_map_identity_aliases("circle_map", payload["nodes"])
    assert aliases["context-0"] == evap["id"]


def test_underscore_invented_id_migrates_and_aliases() -> None:
    """Kitty ``context_0`` remints and still resolves via hyphen or underscore."""
    payload = {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "水循环"},
            {"id": "context_0", "type": "bubble", "text": "蒸发"},
        ],
        "connections": [{"id": "e0", "source": "topic", "target": "context_0"}],
    }
    id_map = migrate_thinking_map_diagram_payload(payload, "circle_map")
    live = id_map["context_0"]
    assert live != "context_0"
    aliases = thinking_map_identity_aliases("circle_map", payload["nodes"])
    assert aliases["context_0"] == live
    assert aliases["context-0"] == live
    assert as_live_thinking_map_node_id("circle_map", "context_0", aliases) == live
    assert as_live_thinking_map_node_id("circle_map", "context-0", aliases) == live


def test_as_live_rejects_unmapped_leftover() -> None:
    """Un-aliased leftover invented ids are never a live canvas id."""
    assert as_live_thinking_map_node_id("circle_map", "context-0") is None
    assert as_live_thinking_map_node_id("flow_map", "flow-step-0") is None
    assert as_live_thinking_map_node_id("circle_map", "topic") == "topic"
    aliases = {"context-0": "uid-evap"}
    assert as_live_thinking_map_node_id("circle_map", "context-0", aliases) == "uid-evap"


def test_unique_label_resolves_only_when_unique() -> None:
    """Duplicate labels do not resolve; a unique label does."""
    nodes = [
        {"id": "topic", "text": "水循环"},
        {"id": "uid-a", "text": "蒸发", "data": {"circleMapUid": "uid-a"}},
        {"id": "uid-b", "text": "降水", "data": {"circleMapUid": "uid-b"}},
    ]
    assert resolve_thinking_map_identity_id("circle_map", "蒸发", nodes) == "uid-a"
    nodes.append({"id": "uid-c", "text": "蒸发"})
    assert resolve_thinking_map_identity_id("circle_map", "蒸发", nodes) is None


def test_brace_leftover_whole_rewrites_to_reserved() -> None:
    """``brace-0-0`` becomes reserved ``brace-whole``, not a UUID."""
    payload = {
        "nodes": [
            {"id": "brace-0-0", "type": "whole", "text": "句子"},
            {"id": "brace-part-0", "type": "brace", "text": "主语"},
        ],
        "connections": [{"id": "e0", "source": "brace-0-0", "target": "brace-part-0"}],
    }
    id_map = migrate_thinking_map_diagram_payload(payload, "brace_map")
    assert id_map["brace-0-0"] == "brace-whole"
    whole = next(node for node in payload["nodes"] if node["text"] == "句子")
    assert whole["id"] == "brace-whole"
    part = next(node for node in payload["nodes"] if node["text"] == "主语")
    assert part["id"] != "brace-part-0"
    assert payload["connections"][0]["source"] == "brace-whole"
    assert payload["connections"][0]["target"] == part["id"]


def test_flow_and_bridge_leftovers_migrate() -> None:
    """Flow steps and bridge pairs remint; reserved roots stay."""
    flow: dict[str, Any] = {
        "nodes": [
            {"id": "flow-topic", "type": "topic", "text": "做饭"},
            {"id": "flow-step-0", "type": "flow", "text": "备菜"},
        ],
        "connections": [{"source": "flow-topic", "target": "flow-step-0"}],
    }
    flow_map = migrate_thinking_map_diagram_payload(flow, "flow_map")
    step = next(node for node in flow["nodes"] if node["text"] == "备菜")
    step_data = step.get("data")
    assert step["id"] == flow_map["flow-step-0"]
    assert isinstance(step_data, dict)
    assert step_data["flowMapLegacyId"] == "flow-step-0"

    bridge = {
        "nodes": [
            {"id": "dimension-label", "text": "像"},
            {"id": "pair-0-left", "text": "心脏", "data": {"pairIndex": 0, "position": "left"}},
            {"id": "pair-0-right", "text": "水泵", "data": {"pairIndex": 0, "position": "right"}},
        ],
        "connections": [],
    }
    bridge_map = migrate_thinking_map_diagram_payload(bridge, "bridge_map")
    left = next(node for node in bridge["nodes"] if node["text"] == "心脏")
    left_data = left.get("data")
    assert left["id"] == bridge_map["pair-0-left"]
    assert isinstance(left_data, dict)
    assert left_data["bridgeMapLegacyId"] == "pair-0-left"


def test_is_machine_node_id_includes_thinking_map_leftovers() -> None:
    """Spoken acks treat leftover Thinking Map ids as machine ids."""
    assert is_machine_node_id("context-0") is True
    assert is_machine_node_id("flow-step-1") is True
    assert is_machine_node_id("pair-0-left") is True
    assert is_machine_node_id("蒸发") is False
    assert is_machine_node_id("topic") is False


def test_update_and_delete_verify_by_stable_id() -> None:
    """Update/delete postconditions target the UUID, never a leftover slot."""
    update = build_expected_effect(
        DiagramEditCommand(
            tool="diagram.update_node",
            args={"node_id": "uid-evap", "new_text": "蒸腾"},
            scope="test",
            diagram_type="circle_map",
        ),
        {"nodes": [{"id": "uid-evap", "text": "蒸发"}]},
    )
    assert update.node_identifier == "uid-evap"
    report = verify_thinking_map_effect(
        update,
        {"nodes": [{"id": "uid-evap", "text": "蒸腾"}, {"id": "topic", "type": "topic", "text": "水"}]},
        before_node_count=2,
        diagram_type="circle_map",
    )
    assert report.ok is True

    delete = build_expected_effect(
        DiagramEditCommand(
            tool="diagram.delete_node",
            args={"node_id": "uid-evap"},
            scope="test",
            diagram_type="circle_map",
        ),
        {"nodes": [{"id": "uid-evap", "text": "蒸发"}, {"id": "topic", "type": "topic", "text": "水"}]},
    )
    gone = verify_thinking_map_effect(
        delete,
        {
            "nodes": [{"id": "topic", "type": "topic", "text": "水"}],
            "connections": [],
        },
        before_node_count=2,
        diagram_type="circle_map",
    )
    assert gone.ok is True
    leftover = build_expected_effect(
        DiagramEditCommand(
            tool="diagram.delete_node",
            args={"node_id": "context-0"},
            scope="test",
            diagram_type="circle_map",
        ),
        {"nodes": [{"id": "context-0", "text": "蒸发"}]},
    )
    assert leftover.node_identifier != "context-0"


def test_classroom_focus_ids_hit_after_migrate() -> None:
    """Stored leftover focus ids remap to live UUID ids."""
    spec = {
        "type": "circle_map",
        "nodes": [
            {"id": "topic", "type": "topic", "text": "水循环"},
            {"id": "context-0", "type": "bubble", "text": "蒸发"},
        ],
        "connections": [{"source": "topic", "target": "context-0"}],
    }
    migrate_thinking_map_diagram_payload(spec, "circle_map")
    known = collect_spec_node_ids(spec)
    assert "context-0" in known
    evap = next(node for node in spec["nodes"] if node["text"] == "蒸发")
    assert evap["id"] in known
    steps = normalize_steps(
        [
            {
                "kind": "branch",
                "title": "蒸发",
                "caption": "讲蒸发",
                "focus_node_ids": ["context-0"],
                "branch_node_id": "context-0",
            }
        ],
        spec=spec,
    )
    assert steps[0]["focus_node_ids"] == [evap["id"]]
    assert steps[0]["branch_node_id"] == evap["id"]
    live_ids = set(spec_snapshot_node_ids(spec))
    assert job_matches_live_nodes(["context-0"], live_ids) is True


def test_leftover_live_key_rejects_unmapped_thinking_map_id() -> None:
    """Identity-required Kitty actions reject leftover ``context-0`` without alias."""
    context = {
        "diagram_type": "circle_map",
        "diagram_data": {
            "nodes": [
                {"id": "topic", "type": "topic", "text": "水"},
                {"id": "uid-evap", "type": "bubble", "text": "蒸发"},
            ]
        },
    }
    assert leftover_live_key({"action": "update_node", "node_id": "context-0"}, context) == "context-0"
    aliased = {
        "diagram_type": "circle_map",
        "diagram_data": {
            "nodes": [
                {
                    "id": "uid-evap",
                    "type": "bubble",
                    "text": "蒸发",
                    "data": {"circleMapLegacyId": "context-0", "circleMapUid": "uid-evap"},
                }
            ]
        },
    }
    assert leftover_live_key({"action": "update_node", "node_id": "context-0"}, aliased) is None
    assert leftover_live_key({"action": "update_node", "node_id": "uid-evap"}, aliased) is None
    assert child_node_live_id({"id": "uid-evap", "text": "蒸发"}, 0, "circle_map") == "uid-evap"
    assert child_node_live_id({"id": "context-0", "text": "蒸发"}, 0, "circle_map") is None
    assert "id" not in session_context_child_record("蒸发", 0, "circle_map")
    nodes = native_spec_to_pseudo_nodes({"topic": "水", "context": ["蒸发"]}, "circle_map")
    assert nodes is not None
    child = next(node for node in nodes if node.get("text") == "蒸发")
    assert child["id"] != "context-0"
    assert child["data"]["circleMapLegacyId"] == "context-0"


def test_inline_rec_extractors_use_stamps_not_leftover_ids() -> None:
    """UUID Thinking Map nodes still yield rec context after leftover migrate."""
    circle = extract_circle_map_context(
        [
            {"id": "topic", "type": "topic", "text": "水"},
            {
                "id": "uid-evap",
                "type": "bubble",
                "text": "蒸发",
                "data": {"circleMapUid": "uid-evap", "circleMapLegacyId": "context-0"},
            },
        ]
    )
    assert circle["context_texts"] == ["蒸发"]
    bubble = extract_bubble_map_context(
        [
            {"id": "topic", "type": "topic", "text": "苹果"},
            {
                "id": "uid-red",
                "type": "bubble",
                "text": "红",
                "data": {"bubbleMapUid": "uid-red", "bubbleMapLegacyId": "bubble-0"},
            },
        ]
    )
    assert bubble["attribute_texts"] == ["红"]
    double = extract_double_bubble_context(
        [
            {"id": "left-topic", "text": "猫"},
            {"id": "right-topic", "text": "狗"},
            {
                "id": "uid-sim",
                "text": "宠物",
                "data": {"doubleBubbleRole": "similarity", "groupIndex": 0},
            },
            {
                "id": "uid-ld",
                "text": "喵",
                "data": {"doubleBubbleRole": "leftDiff", "groupIndex": 0},
            },
            {
                "id": "uid-rd",
                "text": "汪",
                "data": {"doubleBubbleRole": "rightDiff", "groupIndex": 0},
            },
        ],
        current_node_id="uid-ld",
    )
    assert double["similarity_texts"] == ["宠物"]
    assert double["difference_texts"] == ["喵 | 汪"]
    assert double["mode"] == "differences"


def test_showcase_outline_splits_uuid_double_bubble_diffs() -> None:
    """UUID diffs use stamped role, not leftover ``left-diff-`` prefixes."""
    outline = build_diagram_structure_outline(
        {
            "type": "double_bubble_map",
            "nodes": [
                {"id": "left-topic", "type": "topic", "text": "猫"},
                {"id": "right-topic", "type": "topic", "text": "狗"},
                {
                    "id": "uid-ld",
                    "type": "bubble",
                    "text": "喵",
                    "data": {"doubleBubbleRole": "leftDiff"},
                },
                {
                    "id": "uid-rd",
                    "type": "bubble",
                    "text": "汪",
                    "data": {"doubleBubbleRole": "rightDiff"},
                },
            ],
            "connections": [],
        },
        "double_bubble_map",
    )
    assert "左侧不同点" in outline
    assert "喵" in outline
    assert "汪" in outline


def test_classroom_hierarchical_leftover_id_is_not_live() -> None:
    """Leftover thinking-map slot ids never become outline branch ids."""
    outline = extract_mindmap_outline(
        {
            "type": "circle_map",
            "topic": "水循环",
            "children": [{"id": "context-0", "text": "蒸发"}],
        },
        diagram_type="circle_map",
    )
    assert outline.branches[0].text == "蒸发"
    assert outline.branches[0].id is None
