"""End-to-end Kitty path for mind-map identity invert (no live LLM)."""

from __future__ import annotations

from services.diagram.mindmap_location import is_positional_mindmap_branch_id
from services.diagram_edit.effects import build_expected_effect
from services.diagram_edit.types import DiagramEditCommand
from services.diagram_edit.verify import extract_created_node_id, verify_mindmap_effect
from services.kitty.diagram.diagram_utils import resolve_voice_node_reference
from services.kitty.infra.bootstrap.kitty_context_hydrate import diagram_data_from_saved_spec
from services.kitty.routing.diagram_agent_context import (
    build_diagram_agent_payload,
    enrich_node_action_command,
    resolve_diagram_node_ref,
)


def _positional_library_spec() -> dict:
    return {
        "type": "mindmap",
        "nodes": [
            {"id": "topic", "type": "topic", "text": "Cars"},
            {
                "id": "branch-r-1-0",
                "type": "branch",
                "text": "DIY",
                "data": {"mindMapUid": "uid-diy", "mindMapSide": "right", "mindMapDepth": 1},
            },
            {
                "id": "branch-r-1-1",
                "type": "branch",
                "text": "Engine",
                "data": {"mindMapUid": "uid-engine", "mindMapSide": "right", "mindMapDepth": 1},
            },
        ],
        "connections": [
            {"id": "e0", "source": "topic", "target": "branch-r-1-0", "sourceHandle": "mindmap-right"},
            {"id": "e1", "source": "topic", "target": "branch-r-1-1", "sourceHandle": "mindmap-right"},
        ],
        "_node_styles": {"branch-r-1-0": {"fontSize": 18}},
    }


def test_kitty_hydrate_and_agent_compact_use_uuid() -> None:
    """Library hydrate remaps positional ids; compact snapshot is id+path+type."""
    live = diagram_data_from_saved_spec(_positional_library_spec(), "mindmap")
    diy = next(node for node in live["nodes"] if node.get("text") == "DIY")
    engine = next(node for node in live["nodes"] if node.get("text") == "Engine")
    assert diy["id"] == "uid-diy"
    assert engine["id"] == "uid-engine"
    assert not is_positional_mindmap_branch_id(diy["id"])
    child_ids = {item["id"] for item in live["children"] if isinstance(item, dict)}
    assert "uid-diy" in child_ids
    assert "branch-r-1-0" not in child_ids
    assert live["_node_styles"]["uid-diy"]["fontSize"] == 18

    payload = build_diagram_agent_payload({"diagram_data": live}, diagram_type="mindmap")
    compact = next(item for item in payload["nodes"] if item.get("text") == "DIY")
    assert compact == {"id": "uid-diy", "text": "DIY", "type": "branch", "path": "r/0"}


def test_kitty_resolve_leftover_positional_and_voice() -> None:
    """Old clients sending branch-r-1-0 still hit the live UUID."""
    live = diagram_data_from_saved_spec(_positional_library_spec(), "mindmap")
    leftover = resolve_diagram_node_ref(live, node_id="branch-r-1-0")
    assert leftover is not None
    assert leftover["node_id"] == "uid-diy"
    voice = resolve_voice_node_reference({"diagram_data": live}, "mindmap", node_id="branch-r-1-0")
    assert voice is not None
    assert voice["node_id"] == "uid-diy"
    assert voice["node_label"] == "DIY"


def test_kitty_delete_does_not_recycle_survivor_id() -> None:
    """Delete DIY; Engine keeps uid-engine (the original Kitty targeting bug)."""
    live = diagram_data_from_saved_spec(_positional_library_spec(), "mindmap")
    cmd = enrich_node_action_command(
        {"action": "delete_node", "target": "DIY"},
        {"diagram_data": live},
    )
    assert cmd["node_id"] == "uid-diy"

    effect = build_expected_effect(
        DiagramEditCommand(
            tool="diagram.delete_node",
            args={"node_id": cmd["node_id"]},
            scope="kitty-e2e",
            diagram_type="mindmap",
        ),
        live,
    )
    survivors = [node for node in live["nodes"] if node.get("id") != "uid-diy"]
    survivor_conns = [
        conn for conn in live["connections"] if conn.get("source") != "uid-diy" and conn.get("target") != "uid-diy"
    ]
    after = {"nodes": survivors, "connections": survivor_conns}
    report = verify_mindmap_effect(effect, after, before_node_count=3)
    assert report.ok is True
    engine = next(node for node in after["nodes"] if node.get("text") == "Engine")
    assert engine["id"] == "uid-engine"


def test_kitty_created_node_ids_chain_uuid() -> None:
    """Next tool call (auto-complete) can target the canvas-minted UUID."""
    live = diagram_data_from_saved_spec(_positional_library_spec(), "mindmap")
    created = "3f2a9c0e-1111-4111-8111-aaaaaaaaaaaa"
    live["nodes"].append(
        {
            "id": created,
            "type": "branch",
            "text": "Paint",
            "data": {"mindMapUid": created, "mindMapSide": "right", "mindMapDepth": 1},
        }
    )
    live["connections"].append({"source": "topic", "target": created})
    effect = build_expected_effect(
        DiagramEditCommand(
            tool="diagram.add_node",
            args={"text": "Paint", "parent_id": "topic"},
            scope="kitty-e2e",
            diagram_type="mindmap",
        ),
        live,
    )
    assert extract_created_node_id(effect, live, created_node_ids=[created]) == created
    follow = enrich_node_action_command(
        {"action": "auto_complete_branch", "node_id": created},
        {"diagram_data": live},
    )
    assert follow["node_id"] == created
