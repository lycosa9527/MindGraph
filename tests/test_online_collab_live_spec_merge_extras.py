"""Extra live-spec merge tests: tombstone skips, dangling connection prune."""

from __future__ import annotations

from services.online_collab.spec.online_collab_live_spec import merge_granular_into_spec


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
