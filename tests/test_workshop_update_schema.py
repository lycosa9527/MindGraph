"""``collab_update_schema_error`` boundary tests."""

from __future__ import annotations

from routers.api.workshop_ws_update_schema import collab_update_schema_error


def test_schema_accepts_minimal_granular():
    assert (
        collab_update_schema_error(
            {
                "type": "update",
                "diagram_id": "d1",
                "nodes": [{"id": "n1", "text": "hi", "type": "child"}],
            },
        )
        is None
    )


def test_schema_rejects_unknown_node_key():
    err = collab_update_schema_error(
        {
            "type": "update",
            "diagram_id": "d1",
            "nodes": [{"id": "n1", "text": "x", "type": "child", "evil": 1}],
        },
    )
    assert err is not None
    assert "unknown keys" in err


def test_schema_rejects_deep_nesting():
    deep = {"k": {"k": {"k": {"k": {"k": "too_deep"}}}}}
    err = collab_update_schema_error(
        {
            "type": "update",
            "diagram_id": "d1",
            "nodes": [{"id": "n1", "text": "x", "type": "child", "data": deep}],
        },
    )
    assert err is not None
