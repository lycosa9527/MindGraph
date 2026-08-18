"""Mind-map identity invert: location helpers, migrate, resolve, verify."""

from __future__ import annotations

from typing import Any

from services.diagram.mindmap_identity import (
    as_live_mindmap_node_id,
    identity_aliases,
    is_machine_node_id,
    migrate_mindmap_diagram_payload,
    migrate_mindmap_identity_ids,
    remap_focus_payload,
)
from services.diagram.mindmap_location import (
    is_mindmap_l1,
    is_positional_mindmap_branch_id,
    mindmap_location_path_key,
    mindmap_node_depth,
    mindmap_node_side,
)
from services.diagram_edit.effects import build_expected_effect
from services.diagram_edit.types import DiagramEditCommand
from services.diagram_edit.verify import extract_created_node_id, verify_mindmap_effect
from services.kitty.routing.diagram_agent_context import (
    build_diagram_agent_payload,
    resolve_diagram_node_ref,
)
from services.mind_classroom.job_match import job_matches_live_nodes, spec_snapshot_node_ids
from services.mind_classroom.steps import collect_spec_node_ids, normalize_steps


def _positional_tree() -> tuple[list[dict], list[dict]]:
    nodes = [
        {"id": "topic", "type": "topic", "text": "Cars"},
        {
            "id": "branch-r-1-0",
            "type": "branch",
            "text": "DIY",
            "data": {"mindMapUid": "uid-diy", "mindMapSide": "right", "mindMapDepth": 1},
        },
        {
            "id": "branch-r-2-0",
            "type": "branch",
            "text": "Paint",
            "data": {"mindMapUid": "uid-paint", "mindMapSide": "right", "mindMapDepth": 2},
        },
        {
            "id": "branch-l-1-0",
            "type": "branch",
            "text": "Engine",
            "data": {"mindMapUid": "uid-engine", "mindMapSide": "left", "mindMapDepth": 1},
        },
    ]
    connections = [
        {"id": "e1", "source": "topic", "target": "branch-r-1-0", "sourceHandle": "mindmap-right-0"},
        {"id": "e2", "source": "branch-r-1-0", "target": "branch-r-2-0"},
        {"id": "e3", "source": "topic", "target": "branch-l-1-0", "sourceHandle": "mindmap-left-0"},
    ]
    return nodes, connections


def test_location_helpers_match_before_and_after_migrate() -> None:
    """Side / depth / L1 stay the same when ids flip from positional to UUID."""
    nodes, connections = _positional_tree()
    before = {
        "diy": (
            mindmap_node_side("branch-r-1-0", nodes=nodes, connections=connections),
            mindmap_node_depth("branch-r-1-0", nodes=nodes, connections=connections),
            is_mindmap_l1("branch-r-1-0", connections),
            mindmap_location_path_key("branch-r-1-0", connections, nodes=nodes),
        ),
        "paint": (
            mindmap_node_side("branch-r-2-0", nodes=nodes, connections=connections),
            mindmap_node_depth("branch-r-2-0", nodes=nodes, connections=connections),
            is_mindmap_l1("branch-r-2-0", connections),
            mindmap_location_path_key("branch-r-2-0", connections, nodes=nodes),
        ),
    }
    next_nodes, next_conns, id_map = migrate_mindmap_identity_ids(nodes, connections)
    assert id_map["branch-r-1-0"] == "uid-diy"
    assert id_map["branch-r-2-0"] == "uid-paint"
    after_diy = (
        mindmap_node_side("uid-diy", nodes=next_nodes, connections=next_conns),
        mindmap_node_depth("uid-diy", nodes=next_nodes, connections=next_conns),
        is_mindmap_l1("uid-diy", next_conns),
        mindmap_location_path_key("uid-diy", next_conns, nodes=next_nodes),
    )
    after_paint = (
        mindmap_node_side("uid-paint", nodes=next_nodes, connections=next_conns),
        mindmap_node_depth("uid-paint", nodes=next_nodes, connections=next_conns),
        is_mindmap_l1("uid-paint", next_conns),
        mindmap_location_path_key("uid-paint", next_conns, nodes=next_nodes),
    )
    assert after_diy == before["diy"] == ("right", 1, True, "r/0")
    assert after_paint == before["paint"] == ("right", 2, False, "r/0/0")


def test_load_migrate_rewrites_edges_and_styles() -> None:
    """Positional spec becomes UUID ids with rewritten edges and style keys."""
    payload = {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "Cars"},
            {
                "id": "branch-r-1-0",
                "type": "branch",
                "text": "DIY",
                "data": {"mindMapUid": "uid-diy"},
            },
        ],
        "connections": [{"id": "edge-topic-branch-r-1-0", "source": "topic", "target": "branch-r-1-0"}],
        "_node_styles": {"branch-r-1-0": {"backgroundColor": "#eee"}},
    }
    id_map = migrate_mindmap_diagram_payload(payload)
    assert id_map["branch-r-1-0"] == "uid-diy"
    branch = next(node for node in payload["nodes"] if node["id"] != "topic")
    assert branch["id"] == "uid-diy"
    assert branch["text"] == "DIY"
    assert not is_positional_mindmap_branch_id(branch["id"])
    assert payload["connections"][0]["target"] == "uid-diy"
    assert payload["_node_styles"]["uid-diy"]["backgroundColor"] == "#eee"


def test_delete_slot_reuse_keeps_survivor_id() -> None:
    """Deleting A must not recycle B's identity (the Kitty targeting bug)."""
    nodes, connections = _positional_tree()
    next_nodes, next_conns, _id_map = migrate_mindmap_identity_ids(nodes, connections)
    paint_id = next(node["id"] for node in next_nodes if node.get("text") == "Paint")
    diy_id = next(node["id"] for node in next_nodes if node.get("text") == "DIY")
    survivors = [node for node in next_nodes if node["id"] != diy_id]
    survivor_conns = [conn for conn in next_conns if conn.get("source") != diy_id and conn.get("target") != diy_id]
    assert paint_id in {node["id"] for node in survivors}
    assert paint_id == "uid-paint"
    assert all(conn.get("target") != diy_id for conn in survivor_conns)


def test_classroom_focus_ids_hit_after_migrate() -> None:
    """Stored positional focus ids remap to live UUID ids."""
    spec = {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "Cars"},
            {
                "id": "branch-r-1-0",
                "type": "branch",
                "text": "DIY",
                "data": {"mindMapUid": "uid-diy"},
            },
        ],
        "connections": [{"source": "topic", "target": "branch-r-1-0"}],
    }
    migrate_mindmap_diagram_payload(spec)
    known = collect_spec_node_ids(spec)
    assert "branch-r-1-0" in known
    assert "uid-diy" in known
    steps = normalize_steps(
        [
            {
                "kind": "branch",
                "title": "DIY",
                "caption": "Talk about DIY",
                "focus_node_ids": ["branch-r-1-0"],
                "branch_node_id": "branch-r-1-0",
            }
        ],
        spec=spec,
    )
    assert steps[0]["focus_node_ids"] == ["uid-diy"]
    assert steps[0]["branch_node_id"] == "uid-diy"
    live_ids = set(spec_snapshot_node_ids(spec))
    assert job_matches_live_nodes(["branch-r-1-0"], live_ids) is True


def test_remap_focus_payload_rewrites_zhihui_fields() -> None:
    """Zhihui / classroom focus fields follow the identity map."""
    payload = {
        "focus_node_ids": ["branch-r-1-0", "topic"],
        "focus_branch": "branch-r-1-0",
        "focus_child": "branch-r-1-0",
        "branch_node_id": "branch-r-1-0",
    }
    remap_focus_payload(payload, {"branch-r-1-0": "uid-diy"})
    assert payload["focus_node_ids"] == ["uid-diy", "topic"]
    assert payload["focus_branch"] == "uid-diy"
    assert payload["focus_child"] == "uid-diy"
    assert payload["branch_node_id"] == "uid-diy"


def test_agent_compact_and_resolve_use_uuid() -> None:
    """Compact snapshot includes id+path+type; resolve accepts uid and leftover positional."""
    nodes, connections = _positional_tree()
    next_nodes, next_conns, _id_map = migrate_mindmap_identity_ids(nodes, connections)
    diagram = {"nodes": next_nodes, "connections": next_conns}
    payload = build_diagram_agent_payload({"diagram_data": diagram}, diagram_type="mindmap")
    compact = next(item for item in payload["nodes"] if item.get("text") == "DIY")
    assert compact["id"] == "uid-diy"
    assert compact["text"] == "DIY"
    assert compact["type"] == "branch"
    assert compact["path"] == "r/0"
    by_uid = resolve_diagram_node_ref(diagram, node_id="uid-diy")
    by_legacy = resolve_diagram_node_ref(diagram, node_id="branch-r-1-0")
    assert by_uid is not None
    assert by_legacy is not None
    assert by_uid["node_id"] == "uid-diy"
    assert by_legacy["node_id"] == "uid-diy"
    aliases = identity_aliases(next_nodes)
    assert aliases["branch-r-1-0"] == "uid-diy"


def test_update_and_delete_verify_by_stable_id() -> None:
    """Update proves this id's text; delete absent checks the UUID, not a recycled slot."""
    update = build_expected_effect(
        DiagramEditCommand(
            tool="diagram.update_node",
            args={"node_id": "uid-diy", "new_text": "Detail"},
            scope="test",
            diagram_type="mindmap",
        ),
        {"nodes": [{"id": "uid-diy", "text": "DIY"}]},
    )
    assert update.node_identifier == "uid-diy"
    report = verify_mindmap_effect(
        update,
        {"nodes": [{"id": "uid-diy", "text": "Detail"}, {"id": "uid-paint", "text": "Detail"}]},
        before_node_count=2,
    )
    assert report.ok is True

    delete = build_expected_effect(
        DiagramEditCommand(
            tool="diagram.delete_node",
            args={"node_id": "uid-diy"},
            scope="test",
            diagram_type="mindmap",
        ),
        {"nodes": [{"id": "uid-diy", "text": "DIY"}, {"id": "uid-paint", "text": "Paint"}]},
    )
    assert delete.node_identifier == "uid-diy"
    gone = verify_mindmap_effect(
        delete,
        {
            "nodes": [
                {"id": "topic", "type": "topic", "text": "Cars"},
                {"id": "uid-paint", "text": "Paint"},
            ],
            "connections": [],
        },
        before_node_count=2,
    )
    assert gone.ok is True
    assert extract_created_node_id(update, {}, created_node_ids=["uid-new"]) == "uid-new"

    miss = verify_mindmap_effect(
        update,
        {"nodes": [{"id": "uid-paint", "text": "Detail"}, {"id": "uid-other", "text": "Detail"}]},
        before_node_count=2,
    )
    assert miss.ok is False


def test_migrate_invented_branch_n_and_unique_label() -> None:
    """Old voice/template ``branch_0`` becomes a UUID; unique labels resolve."""
    payload: dict[str, Any] = {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "Cars"},
            {"id": "branch_0", "type": "branch", "text": "DIY"},
        ],
        "connections": [{"id": "e0", "source": "topic", "target": "branch_0"}],
    }
    id_map = migrate_mindmap_diagram_payload(payload)
    assert id_map["branch_0"]
    assert id_map["branch_0"] != "branch_0"
    branch = next(node for node in payload["nodes"] if node["text"] == "DIY")
    assert branch["id"] == id_map["branch_0"]
    branch_data = branch.get("data")
    assert isinstance(branch_data, dict)
    assert branch_data["mindMapLegacyId"] == "branch_0"
    aliases = identity_aliases(payload["nodes"])
    assert aliases["branch_0"] == branch["id"]
    assert "DIY" not in aliases


def test_as_live_mindmap_node_id_rejects_leftover() -> None:
    """Leftover invented ids are never a live canvas id."""
    assert as_live_mindmap_node_id("branch_1") is None
    assert as_live_mindmap_node_id("branch-r-1-0") is None
    assert as_live_mindmap_node_id("uid-diy", {"branch-r-1-0": "uid-diy"}) == "uid-diy"
    assert as_live_mindmap_node_id("branch-r-1-0", {"branch-r-1-0": "uid-diy"}) == "uid-diy"
    assert as_live_mindmap_node_id("topic") == "topic"


def test_is_machine_node_id_detects_uuid_and_leftover() -> None:
    """Spoken acks must treat UUIDs and leftover invented ids as machine ids."""
    assert is_machine_node_id("0292ae97-f986-4945-9b45-a175bd5a92b5") is True
    assert is_machine_node_id("branch-r-1-0") is True
    assert is_machine_node_id("争议") is False
    assert is_machine_node_id("topic") is False
