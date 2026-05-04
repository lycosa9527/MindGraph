"""Extra live-spec merge tests: tombstone skips, dangling connection prune."""

from __future__ import annotations

from services.online_collab.spec.online_collab_live_spec import merge_granular_into_spec


def test_merge_skips_patches_for_ids_deleted_in_same_batch():
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
    spec = {
        "nodes": [{"id": "x", "text": "X"}],
        "connections": [
            {"id": "c1", "source": "x", "target": "ghost"},
        ],
    }
    merge_granular_into_spec(spec, None, None)
    assert spec["connections"] == []
