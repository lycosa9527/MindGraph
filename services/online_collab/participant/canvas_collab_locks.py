"""
Canvas collaboration — helpers for exclusive edit locks on granular WS updates.

Keeps lock logic out of the WebSocket router for readability and Pylint-friendly size.
"""

import asyncio
from collections import deque
from typing import Any, Dict, List, Optional

_MAX_SUBTREE_DEPTH = 50
_MAX_SUBTREE_SIZE = 500
_SUBTREE_OFFLOAD_THRESHOLD_NODES = 2000


def node_locked_by_other_user(
    code: str,
    sender_id: int,
    node_id: str,
    active_editors_local: Dict[str, Dict[str, Dict[int, str]]],
    editors_from_redis: Optional[Dict[str, Dict[int, str]]],
) -> bool:
    """
    Return True if node_id is being edited by a user other than sender_id.

    active_editors_local maps workshop code -> node_id -> {user_id: username}.
    When Redis fan-out is enabled, editors_from_redis is load_editors(code); else None.
    """
    editors_map: Dict[str, Dict[int, str]]
    if editors_from_redis is not None:
        editors_map = editors_from_redis
    else:
        if code not in active_editors_local:
            return False
        editors_map = active_editors_local[code]

    node_map = editors_map.get(node_id)
    if not node_map:
        return False
    for uid in node_map:
        if int(uid) != int(sender_id):
            return True
    return False


def filter_granular_nodes_for_locks(
    code: str,
    sender_id: int,
    nodes: List[Dict[str, Any]],
    active_editors_local: Dict[str, Dict[str, Dict[int, str]]],
    editors_from_redis: Optional[Dict[str, Dict[int, str]]],
) -> List[Dict[str, Any]]:
    """Drop node patches the sender may not apply while another user holds the edit lock."""
    out: List[Dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw_id = node.get("id")
        if not raw_id or not isinstance(raw_id, str):
            out.append(node)
            continue
        if node_locked_by_other_user(code, sender_id, raw_id, active_editors_local, editors_from_redis):
            continue
        out.append(node)
    return out


def filter_granular_connections_for_locks(
    code: str,
    sender_id: int,
    connections: List[Dict[str, Any]],
    active_editors_local: Dict[str, Dict[str, Dict[int, str]]],
    editors_from_redis: Optional[Dict[str, Dict[int, str]]],
) -> List[Dict[str, Any]]:
    """Drop connection patches that touch a node another user is editing."""
    out: List[Dict[str, Any]] = []
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        src = conn.get("source")
        tgt = conn.get("target")
        if not isinstance(src, str) or not isinstance(tgt, str):
            out.append(conn)
            continue
        if node_locked_by_other_user(code, sender_id, src, active_editors_local, editors_from_redis):
            continue
        if node_locked_by_other_user(code, sender_id, tgt, active_editors_local, editors_from_redis):
            continue
        out.append(conn)
    return out


def filter_deleted_node_ids_for_locks(
    code: str,
    sender_id: int,
    deleted_node_ids: List[str],
    active_editors_local: Dict[str, Dict[str, Dict[int, str]]],
    editors_from_redis: Optional[Dict[str, Dict[int, str]]],
) -> List[str]:
    """Drop deleted_node_ids the sender may not apply while another user holds the lock."""
    out: List[str] = []
    for nid in deleted_node_ids:
        if not isinstance(nid, str) or not nid:
            continue
        if node_locked_by_other_user(code, sender_id, nid, active_editors_local, editors_from_redis):
            continue
        out.append(nid)
    return out


def filter_deleted_connection_ids_for_locks(
    code: str,
    sender_id: int,
    deleted_connection_ids: List[str],
    connection_endpoints: Dict[str, Dict[str, str]],
    active_editors_local: Dict[str, Dict[str, Dict[int, str]]],
    editors_from_redis: Optional[Dict[str, Dict[int, str]]],
) -> List[str]:
    """
    Drop deleted_connection_ids whose source/target node is being edited by another user.

    connection_endpoints maps connection_id -> {"source": ..., "target": ...} gathered
    from the inbound patch and/or the authoritative live spec. Connections not found in
    the lookup are passed through (server will accept deletion of unknown ids as a
    no-op during merge).
    """
    out: List[str] = []
    for cid in deleted_connection_ids:
        if not isinstance(cid, str) or not cid:
            continue
        endpoints = connection_endpoints.get(cid) or {}
        src = endpoints.get("source")
        tgt = endpoints.get("target")
        if isinstance(src, str) and node_locked_by_other_user(
            code, sender_id, src, active_editors_local, editors_from_redis,
        ):
            continue
        if isinstance(tgt, str) and node_locked_by_other_user(
            code, sender_id, tgt, active_editors_local, editors_from_redis,
        ):
            continue
        out.append(cid)
    return out


def build_locked_by_others_node_ids(
    code: str,
    sender_id: int,
    active_editors_local: Dict[str, Dict[str, Dict[int, str]]],
    editors_from_redis: Optional[Dict[str, Dict[int, str]]],
) -> set:
    """
    Return the set of node_ids currently locked by users other than sender.

    Call this once per request and reuse the set for membership checks instead
    of O(N) repeated node_locked_by_other_user() calls. This fixes the
    full-spec lock check hot path which previously invoked
    filter_granular_nodes_for_locks([n], ...) once per spec node.
    """
    editors_map: Dict[str, Dict[int, str]]
    if editors_from_redis is not None:
        editors_map = editors_from_redis
    else:
        editors_map = active_editors_local.get(code, {})
    sid = int(sender_id)
    out: set = set()
    for nid, node_map in editors_map.items():
        if not node_map:
            continue
        for uid in node_map:
            try:
                if int(uid) != sid:
                    out.add(str(nid))
                    break
            except (TypeError, ValueError):
                continue
    return out


def build_connection_endpoints_map(
    *connection_lists: Any,
) -> Dict[str, Dict[str, str]]:
    """Collect connection endpoints from one or more lists of connection dicts."""
    out: Dict[str, Dict[str, str]] = {}
    for connections in connection_lists:
        if not isinstance(connections, list):
            continue
        for conn in connections:
            if not isinstance(conn, dict):
                continue
            cid = conn.get("id")
            src = conn.get("source")
            tgt = conn.get("target")
            if not isinstance(cid, str) or not cid:
                continue
            endpoints: Dict[str, str] = {}
            if isinstance(src, str):
                endpoints["source"] = src
            if isinstance(tgt, str):
                endpoints["target"] = tgt
            if endpoints:
                out[cid] = endpoints
    return out


def compute_subtree_node_ids(
    live_doc: Optional[Dict[str, Any]],
    root_node_id: str,
    max_depth: int = _MAX_SUBTREE_DEPTH,
    max_size: int = _MAX_SUBTREE_SIZE,
) -> List[str]:
    """
    BFS the live_spec connections graph from root_node_id and return the list
    of descendant node ids (root inclusive).

    Parent -> child edges are inferred from connections where source == parent
    and target == child (or via explicit ``parent_id`` on nodes if present).

    Bounded by ``max_depth`` and ``max_size`` to guarantee predictable work.
    """
    if not isinstance(live_doc, dict) or not isinstance(root_node_id, str):
        return []
    if not root_node_id:
        return []

    children_by_parent: Dict[str, List[str]] = {}

    connections = live_doc.get("connections") or []
    if isinstance(connections, list):
        for conn in connections:
            if not isinstance(conn, dict):
                continue
            src = conn.get("source")
            tgt = conn.get("target")
            if not isinstance(src, str) or not isinstance(tgt, str):
                continue
            if not src or not tgt:
                continue
            children_by_parent.setdefault(src, []).append(tgt)

    nodes = live_doc.get("nodes") or []
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            nid = node.get("id")
            parent_id = node.get("parent_id")
            if (
                isinstance(nid, str)
                and isinstance(parent_id, str)
                and nid
                and parent_id
            ):
                lst = children_by_parent.setdefault(parent_id, [])
                if nid not in lst:
                    lst.append(nid)

    visited: Dict[str, int] = {root_node_id: 0}
    order: List[str] = [root_node_id]
    queue: deque = deque([(root_node_id, 0)])
    while queue:
        if len(order) >= max_size:
            break
        cur, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for child in children_by_parent.get(cur, []):
            if child in visited:
                continue
            visited[child] = depth + 1
            order.append(child)
            if len(order) >= max_size:
                break
            queue.append((child, depth + 1))
    return order


async def compute_subtree_node_ids_async(
    live_doc: Optional[Dict[str, Any]],
    root_node_id: str,
    max_depth: int = _MAX_SUBTREE_DEPTH,
    max_size: int = _MAX_SUBTREE_SIZE,
) -> List[str]:
    """
    Async wrapper around compute_subtree_node_ids that offloads the BFS to a
    worker thread when the live_spec has more than
    ``_SUBTREE_OFFLOAD_THRESHOLD_NODES`` nodes.

    For typical rooms (<2000 nodes) the sync path is several microseconds and
    offload overhead would dominate. Above the threshold the pure-Python BFS
    can stall the event loop for 10-50 ms — offloading via asyncio.to_thread
    keeps other WebSocket handlers responsive during a subtree lock request.
    """
    if not isinstance(live_doc, dict):
        return []
    nodes = live_doc.get("nodes")
    size_hint = len(nodes) if isinstance(nodes, list) else 0
    if size_hint > _SUBTREE_OFFLOAD_THRESHOLD_NODES:
        return await asyncio.to_thread(
            compute_subtree_node_ids, live_doc, root_node_id, max_depth, max_size,
        )
    return compute_subtree_node_ids(live_doc, root_node_id, max_depth, max_size)
