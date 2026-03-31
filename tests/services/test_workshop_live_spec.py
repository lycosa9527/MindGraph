"""Tests for Redis live spec merge (Phase 2)."""

from services.workshop.workshop_live_spec import (
    apply_live_update,
    merge_granular_into_spec,
)


def test_merge_granular_nodes():
    spec: dict = {"type": "bubble_map", "nodes": [{"id": "a", "text": "1"}]}
    merge_granular_into_spec(
        spec,
        [{"id": "a", "text": "2"}],
        None,
    )
    assert spec["nodes"][0]["text"] == "2"


def test_apply_full_spec_replace():
    cur = {"v": 2, "type": "bubble_map", "nodes": []}
    nxt, ver = apply_live_update(
        cur,
        {"type": "bubble_map", "nodes": [{"id": "x"}]},
        None,
        None,
    )
    assert ver == 3
    assert nxt["v"] == 3
    assert nxt["nodes"][0]["id"] == "x"
