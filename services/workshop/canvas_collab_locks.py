"""
Canvas collaboration — helpers for exclusive edit locks on granular WS updates.

Keeps lock logic out of the WebSocket router for readability and Pylint-friendly size.
"""

from typing import Any, Dict, List, Optional


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
