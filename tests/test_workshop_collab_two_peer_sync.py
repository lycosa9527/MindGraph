"""Two-peer workshop sync: shared live spec plus Alice/Bob local merges.

Mimics the canvas-collab path without Redis or a live WebSocket:
server ``apply_live_update`` is the room SoT; each peer applies the same
granular patch the other would receive on broadcast.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from routers.api.workshop_ws_update_schema import collab_update_schema_error
from services.online_collab.spec.online_collab_live_spec import (
    apply_live_update,
    merge_granular_into_spec,
)

TOPIC = "topic"
CHILD_A = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CHILD_B = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
CHILD_C = "cccccccc-dddd-eeee-ffff-000000000000"
CHILD_D = "dddddddd-eeee-ffff-0000-111111111111"


def _branch(node_id: str, text: str, legacy: str | None = None) -> dict[str, Any]:
    """Build a mind-map branch node."""
    data: dict[str, Any] = {"mindMapUid": node_id}
    if legacy:
        data["mindMapLegacyId"] = legacy
    return {"id": node_id, "text": text, "type": "branch", "data": data}


def _edge(conn_id: str, target: str, after: str | None = None) -> dict[str, Any]:
    """Build a topic→child edge, optionally with a sibling-insert hint."""
    row: dict[str, Any] = {"id": conn_id, "source": TOPIC, "target": target}
    if after:
        row["insert_after_target"] = after
    return row


def _baseline() -> dict[str, Any]:
    """Shared starting mind map for Alice, Bob, and the live server spec."""
    return {
        "type": "mindmap",
        "v": 1,
        "nodes": [
            {"id": TOPIC, "text": "主题", "type": "topic"},
            _branch(CHILD_A, "A", "branch-r-1-0"),
            _branch(CHILD_B, "B", "branch-r-1-1"),
        ],
        "connections": [
            {"id": "e-a", "source": TOPIC, "target": CHILD_A},
            {"id": "e-b", "source": TOPIC, "target": CHILD_B},
        ],
    }


def _node_ids(spec: dict[str, Any]) -> set[str]:
    """Return live node ids."""
    return {str(node["id"]) for node in spec["nodes"] if isinstance(node, dict)}


def _child_order(spec: dict[str, Any]) -> list[str]:
    """Return topic-child order from connections."""
    return [
        str(conn["target"]) for conn in spec["connections"] if isinstance(conn, dict) and conn.get("source") == TOPIC
    ]


def _texts(spec: dict[str, Any]) -> dict[str, str]:
    """Return node text keyed by id."""
    return {
        str(node["id"]): str(node.get("text") or "")
        for node in spec["nodes"]
        if isinstance(node, dict) and node.get("id")
    }


def _assert_peers_match_server(
    server: dict[str, Any],
    alice: dict[str, Any],
    bob: dict[str, Any],
) -> None:
    """Require Alice, Bob, and the server to share ids, texts, and sibling order."""
    assert _node_ids(alice) == _node_ids(server) == _node_ids(bob)
    assert _child_order(alice) == _child_order(server) == _child_order(bob)
    assert _texts(alice) == _texts(server) == _texts(bob)
    for spec in (server, alice, bob):
        for conn in spec["connections"]:
            assert "insert_after_target" not in conn


def _commit_peer_edit(
    server: dict[str, Any],
    sender: dict[str, Any],
    peer: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Sender already has the edit locally; server then peer apply the same patch."""
    nodes = patch.get("nodes")
    connections = patch.get("connections")
    deleted_nodes = patch.get("deleted_node_ids")
    deleted_conns = patch.get("deleted_connection_ids")
    frame: dict[str, Any] = {
        "type": "update",
        "diagram_id": "diagram-two-peer",
        "client_op_id": "op-two-peer",
        **patch,
    }
    assert collab_update_schema_error(frame) is None
    next_server, _version, _changed = apply_live_update(
        server,
        None,
        nodes,
        connections,
        deleted_node_ids=deleted_nodes,
        deleted_connection_ids=deleted_conns,
    )
    merge_granular_into_spec(
        peer,
        deepcopy(nodes) if nodes else None,
        deepcopy(connections) if connections else None,
        deleted_node_ids=deleted_nodes,
        deleted_connection_ids=deleted_conns,
    )
    sender["v"] = next_server["v"]
    peer["v"] = next_server["v"]
    return next_server


def test_alice_add_then_bob_add_both_see_new_nodes() -> None:
    """Reported bug: deletes already synced; adds must become visible both ways."""
    server = _baseline()
    alice = deepcopy(server)
    bob = deepcopy(server)

    alice_nodes = [_branch(CHILD_C, "C")]
    alice_conns = [_edge("e-c", CHILD_C, CHILD_A)]
    merge_granular_into_spec(alice, deepcopy(alice_nodes), deepcopy(alice_conns))
    server = _commit_peer_edit(
        server,
        alice,
        bob,
        {"nodes": alice_nodes, "connections": alice_conns},
    )
    assert CHILD_C in _node_ids(bob)
    _assert_peers_match_server(server, alice, bob)
    assert _child_order(server) == [CHILD_A, CHILD_C, CHILD_B]

    bob_nodes = [_branch(CHILD_D, "D")]
    bob_conns = [_edge("e-d", CHILD_D, CHILD_B)]
    merge_granular_into_spec(bob, deepcopy(bob_nodes), deepcopy(bob_conns))
    server = _commit_peer_edit(
        server,
        bob,
        alice,
        {"nodes": bob_nodes, "connections": bob_conns},
    )
    assert CHILD_D in _node_ids(alice)
    _assert_peers_match_server(server, alice, bob)
    assert _child_order(server) == [CHILD_A, CHILD_C, CHILD_B, CHILD_D]


def test_alice_delete_then_bob_add_converges() -> None:
    """Deletes still sync; a later add from the other peer must not vanish."""
    server = _baseline()
    alice = deepcopy(server)
    bob = deepcopy(server)

    merge_granular_into_spec(alice, None, None, deleted_node_ids=[CHILD_B], deleted_connection_ids=["e-b"])
    server = _commit_peer_edit(
        server,
        alice,
        bob,
        {"deleted_node_ids": [CHILD_B], "deleted_connection_ids": ["e-b"]},
    )
    assert CHILD_B not in _node_ids(bob)
    _assert_peers_match_server(server, alice, bob)

    bob_nodes = [_branch(CHILD_D, "D")]
    bob_conns = [_edge("e-d", CHILD_D, CHILD_A)]
    merge_granular_into_spec(bob, deepcopy(bob_nodes), deepcopy(bob_conns))
    server = _commit_peer_edit(
        server,
        bob,
        alice,
        {"nodes": bob_nodes, "connections": bob_conns},
    )
    assert CHILD_D in _node_ids(alice)
    assert CHILD_B not in _node_ids(alice)
    _assert_peers_match_server(server, alice, bob)


def test_concurrent_adds_from_same_baseline_both_land() -> None:
    """Each peer adds from the same snapshot; sequential server apply keeps both."""
    server = _baseline()
    alice = deepcopy(server)
    bob = deepcopy(server)

    alice_nodes = [_branch(CHILD_C, "C")]
    alice_conns = [_edge("e-c", CHILD_C, CHILD_A)]
    bob_nodes = [_branch(CHILD_D, "D")]
    bob_conns = [_edge("e-d", CHILD_D, CHILD_B)]
    merge_granular_into_spec(alice, deepcopy(alice_nodes), deepcopy(alice_conns))
    merge_granular_into_spec(bob, deepcopy(bob_nodes), deepcopy(bob_conns))

    server = _commit_peer_edit(
        server,
        alice,
        bob,
        {"nodes": alice_nodes, "connections": alice_conns},
    )
    server = _commit_peer_edit(
        server,
        bob,
        alice,
        {"nodes": bob_nodes, "connections": bob_conns},
    )
    assert {CHILD_C, CHILD_D}.issubset(_node_ids(alice) & _node_ids(bob) & _node_ids(server))
    _assert_peers_match_server(server, alice, bob)


def test_leftover_sibling_hint_from_alice_still_syncs_on_bob() -> None:
    """Mixed leftover/UUID rooms: Alice's old sibling hint remaps on Bob."""
    server = _baseline()
    alice = deepcopy(server)
    bob = deepcopy(server)
    nodes = [_branch(CHILD_C, "C")]
    conns = [_edge("e-c", CHILD_C, "branch-r-1-0")]
    merge_granular_into_spec(alice, deepcopy(nodes), deepcopy(conns))
    server = _commit_peer_edit(
        server,
        alice,
        bob,
        {"nodes": nodes, "connections": conns},
    )
    assert _child_order(bob) == [CHILD_A, CHILD_C, CHILD_B]
    _assert_peers_match_server(server, alice, bob)
