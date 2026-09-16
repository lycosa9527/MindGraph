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
