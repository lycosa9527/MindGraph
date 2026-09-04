"""``collab_update_schema_error`` boundary tests."""

from __future__ import annotations

from routers.api.workshop_ws_handlers_update_validate import (
    client_op_id_from_message,
    error_payload_with_update_client_op,
)
from routers.api.workshop_ws_update_schema import collab_update_schema_error


def test_schema_accepts_minimal_granular():
    """Test schema accepts minimal granular."""
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
    """Test schema rejects unknown node key."""
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
    """Test schema rejects deep nesting."""
    deep = {"k": {"k": {"k": {"k": {"k": "too_deep"}}}}}
    err = collab_update_schema_error(
        {
            "type": "update",
            "diagram_id": "d1",
            "nodes": [{"id": "n1", "text": "x", "type": "child", "data": deep}],
        },
    )
    assert err is not None


def test_schema_accepts_sibling_insert_after_target():
    """Enter-to-add sends insert_after_target; schema must not drop the whole update."""
    new_id = "3f2a9c1e-7b4d-4e8a-9c1e-7b4d4e8a9c1e"
    err = collab_update_schema_error(
        {
            "type": "update",
            "diagram_id": "d1",
            "nodes": [
                {
                    "id": new_id,
                    "text": "",
                    "type": "branch",
                    "position": {"x": 10, "y": 20},
                    "data": {"mindMapUid": new_id, "mindMapSide": "right", "mindMapDepth": 1},
                }
            ],
            "connections": [
                {
                    "id": f"edge-topic-{new_id}",
                    "source": "topic",
                    "target": new_id,
                    "sourceHandle": "mindmap-right",
                    "targetHandle": "left",
                    "style": {"strokeColor": "#333"},
                    "insert_after_target": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                }
            ],
        },
    )
    assert err is None


def test_schema_accepts_full_spec_mindmap_canvas_styles():
    """Theme/collapse full spec nests canvas path styles deeper than granular nodes."""
    err = collab_update_schema_error(
        {
            "type": "update",
            "diagram_id": "d1",
            "spec": {
                "type": "mindmap",
                "nodes": [{"id": "topic", "text": "T", "type": "topic"}],
                "connections": [],
                "_mindmap_canvas": {
                    "v2": {
                        "theme": "vibrantBlue",
                        "node_styles_by_path": {"r/0": {"backgroundColor": "#fff", "nodeShape": "rounded"}},
                    }
                },
            },
        },
    )
    assert err is None


def test_client_op_id_from_message_bounds_and_strips():
    """Outbound nack needs a bounded echoed client_op_id on update errors."""
    assert client_op_id_from_message({}) is None
    assert client_op_id_from_message({"client_op_id": "  abc  "}) == "abc"
    assert client_op_id_from_message({"client_op_id": "x" * 200}) == "x" * 128


def test_error_payload_echoes_client_op_only_for_update_frames():
    """Rate-limit and handler errors must not nack the update queue on claim frames."""
    base = {"type": "error", "message": "Rate limit exceeded"}
    update = {"type": "update", "client_op_id": "op-add-1", "nodes": []}
    claim = {"type": "claim_node_edit", "client_op_id": "op-add-1", "node_id": "n1"}
    echoed = error_payload_with_update_client_op(base, update)
    assert echoed["client_op_id"] == "op-add-1"
    assert error_payload_with_update_client_op(base, claim) == base
    assert error_payload_with_update_client_op(base, {"type": "update"}) == base
