"""Extra live-spec merge tests: tombstone skips, dangling connection prune."""

from __future__ import annotations

from services.online_collab.spec.online_collab_live_spec import (
    granular_has_leftover_mindmap_ids,
    merge_granular_into_spec,
)


def test_merge_skips_patches_for_ids_deleted_in_same_batch():
    """Test merge skips patches for ids deleted in same batch."""
    spec = {
        "nodes": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "connections": [{"id": "e1", "source": "a", "target": "b"}],
    }
    merge_granular_into_spec(
        spec,
        nodes=[{"id": "a", "text": "stale-after-delete"}],
        connections=None,
        deleted_node_ids=["a"],
        deleted_connection_ids=None,
    )
    assert [n["id"] for n in spec["nodes"]] == ["b"]
    assert not any(n["id"] == "a" for n in spec["nodes"])


def test_prune_drops_edges_to_deleted_endpoints():
    """Test prune drops edges to deleted endpoints."""
    spec = {
        "nodes": [{"id": "x", "text": "X"}],
        "connections": [
            {"id": "c1", "source": "x", "target": "ghost"},
        ],
    }
    merge_granular_into_spec(spec, None, None)
    assert not spec["connections"]


def _two_mindmap_copies() -> dict:
    """One topic with the same branch stored under two UUIDs."""
    return {
        "type": "mindmap",
        "nodes": [
            {"id": "topic", "type": "topic", "text": "平面直角坐标系", "position": {"x": 0, "y": 0}},
            {
                "id": "uuid-server",
                "type": "branch",
                "text": "横轴",
                "position": {"x": 220, "y": 0},
                "data": {
                    "mindMapUid": "uuid-server",
                    "mindMapLegacyId": "branch-r-1-0",
                    "mindMapSide": "right",
                },
            },
            {
                "id": "uuid-client",
                "type": "branch",
                "text": "横轴",
                "position": {"x": -40, "y": 30},
                "data": {
                    "mindMapUid": "uuid-client",
                    "mindMapLegacyId": "branch-r-1-0",
                    "mindMapSide": "right",
                },
            },
        ],
        "connections": [
            {"id": "e-server", "source": "topic", "target": "uuid-server"},
            {"id": "e-client", "source": "topic", "target": "uuid-client"},
        ],
    }


def test_merge_binds_second_mindmap_uuid_onto_live_branch() -> None:
    """A peer's newly minted UUID for the same leftover id must not append a second tree."""
    spec = {
        "type": "mindmap",
        "nodes": [
            {"id": "topic", "type": "topic", "text": "平面直角坐标系"},
            {
                "id": "uuid-server",
                "type": "branch",
                "text": "横轴",
                "position": {"x": 220, "y": 0},
                "data": {"mindMapUid": "uuid-server", "mindMapLegacyId": "branch-r-1-0"},
            },
        ],
        "connections": [{"id": "e-server", "source": "topic", "target": "uuid-server"}],
    }
    merge_granular_into_spec(
        spec,
        [
            {
                "id": "uuid-client",
                "type": "branch",
                "text": "横轴",
                "position": {"x": 40, "y": 12},
                "data": {"mindMapUid": "uuid-client", "mindMapLegacyId": "branch-r-1-0"},
            }
        ],
        [{"id": "e-client", "source": "topic", "target": "uuid-client"}],
    )
    assert [node["id"] for node in spec["nodes"]] == ["topic", "uuid-server"]
    assert spec["nodes"][1]["position"] == {"x": 40, "y": 12}
    assert spec["nodes"][1]["data"]["mindMapUid"] == "uuid-server"
    assert [(conn["source"], conn["target"]) for conn in spec["connections"]] == [("topic", "uuid-server")]


def test_position_only_peer_updates_the_live_branch() -> None:
    """After the first bind, a layout patch that only knows the peer id must not append."""
    spec = {
        "type": "mindmap",
        "nodes": [
            {"id": "topic", "type": "topic", "text": "平面直角坐标系"},
            {
                "id": "uuid-server",
                "type": "branch",
                "text": "横轴",
                "position": {"x": 220, "y": 0},
                "data": {"mindMapUid": "uuid-server", "mindMapLegacyId": "branch-r-1-0"},
            },
        ],
        "connections": [{"id": "e-server", "source": "topic", "target": "uuid-server"}],
    }
    merge_granular_into_spec(
        spec,
        [
            {
                "id": "uuid-client",
                "type": "branch",
                "text": "横轴",
                "position": {"x": 40, "y": 12},
                "data": {"mindMapUid": "uuid-client", "mindMapLegacyId": "branch-r-1-0"},
            }
        ],
        None,
    )
    merge_granular_into_spec(
        spec,
        [{"id": "uuid-client", "position": {"x": 7, "y": 9}, "width": 80, "height": 36}],
        None,
    )
    assert [node["id"] for node in spec["nodes"]] == ["topic", "uuid-server"]
    assert spec["nodes"][1]["position"] == {"x": 7, "y": 9}
    assert "uuid-client" in spec["nodes"][1]["data"]["mindMapAliasIds"]


def test_collapsed_copy_keeps_the_dropped_id_for_a_later_position_patch() -> None:
    """Healing a doubled spec remembers the dropped id for the next layout patch."""
    spec = _two_mindmap_copies()
    merge_granular_into_spec(spec, [{"id": "uuid-server", "position": {"x": 10, "y": 4}}], None)
    assert "uuid-client" in spec["nodes"][1]["data"]["mindMapAliasIds"]
    merge_granular_into_spec(spec, [{"id": "uuid-client", "position": {"x": 3, "y": 5}}], None)
    assert [node["id"] for node in spec["nodes"]] == ["topic", "uuid-server"]
    assert spec["nodes"][1]["position"] == {"x": 3, "y": 5}


def test_layout_only_unknown_mindmap_id_does_not_append() -> None:
    """A position echo for an id this room has never bound must not create a branch."""
    spec = {
        "type": "mindmap",
        "nodes": [
            {"id": "topic", "type": "topic", "text": "平面直角坐标系"},
            {
                "id": "uuid-server",
                "type": "branch",
                "text": "横轴",
                "position": {"x": 220, "y": 0},
                "data": {"mindMapUid": "uuid-server", "mindMapLegacyId": "branch-r-1-0"},
            },
        ],
        "connections": [{"id": "e-server", "source": "topic", "target": "uuid-server"}],
    }
    merge_granular_into_spec(
        spec,
        [{"id": "uuid-stranger", "position": {"x": 1, "y": 2}, "width": 40, "height": 20}],
        [{"id": "e-stranger", "source": "topic", "target": "uuid-stranger"}],
    )
    assert [node["id"] for node in spec["nodes"]] == ["topic", "uuid-server"]
    assert [conn["target"] for conn in spec["connections"]] == ["uuid-server"]


def test_new_mindmap_branch_still_appends() -> None:
    """A real new branch, sent as a whole node, is added once."""
    spec = {
        "type": "mindmap",
        "nodes": [{"id": "topic", "type": "topic", "text": "平面直角坐标系"}],
        "connections": [],
    }
    merge_granular_into_spec(
        spec,
        [
            {
                "id": "uuid-new",
                "type": "branch",
                "text": "纵轴",
                "position": {"x": 10, "y": 10},
                "data": {"mindMapUid": "uuid-new"},
            }
        ],
        [{"id": "e-new", "source": "topic", "target": "uuid-new"}],
    )
    assert [node["id"] for node in spec["nodes"]] == ["topic", "uuid-new"]
    assert spec["connections"][0]["target"] == "uuid-new"


def test_merge_collapses_mindmap_already_stored_twice() -> None:
    """A live spec that already holds both trees drops the later copy on the next merge."""
    spec = _two_mindmap_copies()
    merge_granular_into_spec(spec, [{"id": "uuid-server", "position": {"x": 10, "y": 4}}], None)
    assert [node["id"] for node in spec["nodes"]] == ["topic", "uuid-server"]
    assert [(conn["source"], conn["target"]) for conn in spec["connections"]] == [("topic", "uuid-server")]
    assert spec["nodes"][1]["position"]["x"] == 10


def test_merge_remaps_leftover_patch_id_onto_live_uuid() -> None:
    """Stale positional patches hit the live UUID via leftover alias."""
    spec = {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "Cars"},
            {
                "id": "uid-diy",
                "type": "branch",
                "text": "DIY",
                "data": {"mindMapLegacyId": "branch_1"},
            },
        ],
        "connections": [{"id": "e1", "source": "topic", "target": "uid-diy"}],
    }
    merge_granular_into_spec(spec, [{"id": "branch_1", "text": "Detail"}], None)
    diy = next(node for node in spec["nodes"] if node["id"] == "uid-diy")
    assert diy["text"] == "Detail"
    assert not any(node.get("id") == "branch_1" for node in spec["nodes"])


def _circle_live_spec() -> dict:
    return {
        "type": "circle_map",
        "nodes": [
            {"id": "topic", "type": "topic", "text": "水"},
            {
                "id": "uid-evap",
                "type": "bubble",
                "text": "蒸发",
                "data": {"circleMapLegacyId": "context-0", "circleMapUid": "uid-evap"},
            },
            {
                "id": "uid-rain",
                "type": "bubble",
                "text": "降水",
                "data": {"circleMapLegacyId": "context-1", "circleMapUid": "uid-rain"},
            },
        ],
        "connections": [
            {"id": "e1", "source": "topic", "target": "uid-evap"},
            {"id": "e2", "source": "topic", "target": "uid-rain"},
        ],
    }


def test_merge_remaps_thinking_map_leftover_patch_id() -> None:
    """Stale ``context-0`` patches hit the live circle-map UUID."""
    spec = _circle_live_spec()
    merge_granular_into_spec(spec, [{"id": "context-0", "text": "蒸腾"}], None)
    evap = next(node for node in spec["nodes"] if node["id"] == "uid-evap")
    assert evap["text"] == "蒸腾"
    assert not any(node.get("id") == "context-0" for node in spec["nodes"])


def test_merge_remaps_thinking_map_leftover_delete_and_insert_after() -> None:
    """Leftover delete + insert_after_target remap onto live Thinking Map UUIDs."""
    spec = _circle_live_spec()
    merge_granular_into_spec(
        spec,
        [{"id": "uid-new", "type": "bubble", "text": "径流"}],
        [
            {
                "id": "e-new",
                "source": "topic",
                "target": "uid-new",
                "insert_after_target": "context-0",
            }
        ],
        deleted_node_ids=["context-1"],
    )
    assert not any(node.get("id") == "uid-rain" for node in spec["nodes"])
    targets = [conn["target"] for conn in spec["connections"] if conn["source"] == "topic"]
    assert targets == ["uid-evap", "uid-new"]


def test_granular_detects_thinking_map_leftover_ids() -> None:
    """``context-0`` / leftover insert hints skip the FCALL fast path."""
    leftover_spec = {
        "type": "circle_map",
        "nodes": [{"id": "context-0", "text": "蒸发"}],
        "connections": [],
    }
    assert granular_has_leftover_mindmap_ids(leftover_spec, None, None, None)
    uuid_spec = {
        "type": "circle_map",
        "nodes": [{"id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "text": "蒸发"}],
        "connections": [],
    }
    assert not granular_has_leftover_mindmap_ids(uuid_spec, None, None, None)
    leftover_hint = {
        "id": "e-new",
        "source": "topic",
        "target": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "insert_after_target": "context-0",
    }
    assert granular_has_leftover_mindmap_ids(uuid_spec, None, [leftover_hint], None)
