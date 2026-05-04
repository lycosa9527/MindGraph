"""
Authoritative live diagram spec in Redis for workshop Phase 2.

Merges WS updates into a JSON document aligned with client ``getSpecForSave`` shape.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple

from models.domain.diagrams import Diagram

from services.online_collab.spec.online_collab_live_spec_json import (
    json_get_live_spec,
    json_set_live_spec,
)

logger = logging.getLogger(__name__)


def _parse_db_spec(diagram: Diagram) -> Dict[str, Any]:
    raw = diagram.spec
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        text = raw.decode("utf-8", errors="replace")
    elif isinstance(raw, str):
        text = raw
    else:
        return {}
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _prune_dangling_connections(spec: Dict[str, Any]) -> None:
    """Drop edges whose ``source`` / ``target`` no longer exist on any node."""
    nodes = spec.get("nodes") or []
    if not isinstance(nodes, list):
        return
    valid = {
        str(n.get("id"))
        for n in nodes
        if isinstance(n, dict) and n.get("id")
    }
    conns = spec.get("connections")
    if not isinstance(conns, list):
        return
    spec["connections"] = [
        c for c in conns
        if isinstance(c, dict)
        and str(c.get("source", "")) in valid
        and str(c.get("target", "")) in valid
    ]


def _merge_node_patches(
    existing_nodes: List[Dict[str, Any]],
    patches: List[Dict[str, Any]],
    skip_node_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    skip = skip_node_ids or set()
    by_index = {str(n.get("id")): i for i, n in enumerate(existing_nodes) if n.get("id")}
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        node_id = patch.get("id")
        if not node_id:
            continue
        sid = str(node_id)
        if sid in skip:
            continue
        if sid in by_index:
            i = by_index[sid]
            old_node = existing_nodes[i]
            merged = {**old_node, **patch}
            # Keep data.label in sync with text (text is canonical, mirrors client-side fix).
            if "text" in patch and isinstance(merged.get("data"), dict):
                merged["data"] = {**merged["data"], "label": merged["text"]}
            existing_nodes[i] = merged
        else:
            new_node = dict(patch)
            # Sync data.label from text for newly inserted nodes too.
            if "text" in new_node and isinstance(new_node.get("data"), dict):
                new_node["data"] = {**new_node["data"], "label": new_node["text"]}
            existing_nodes.append(new_node)
            by_index[sid] = len(existing_nodes) - 1
    return existing_nodes


def _merge_connection_patches(
    conns: List[Dict[str, Any]],
    patches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        conn_id = patch.get("id")
        if conn_id:
            idx = next(
                (i for i, c in enumerate(conns) if isinstance(c, dict) and c.get("id") == conn_id),
                -1,
            )
        else:
            source = patch.get("source")
            target = patch.get("target")
            if not source or not target:
                continue
            idx = next(
                (
                    i
                    for i, c in enumerate(conns)
                    if isinstance(c, dict)
                    and c.get("source") == source
                    and c.get("target") == target
                ),
                -1,
            )
        if idx >= 0:
            conns[idx] = {**conns[idx], **patch}
        else:
            conns.append(patch)
    return conns


def merge_granular_into_spec(
    spec: Dict[str, Any],
    nodes: Optional[List[Dict[str, Any]]],
    connections: Optional[List[Dict[str, Any]]],
    deleted_node_ids: Optional[List[str]] = None,
    deleted_connection_ids: Optional[List[str]] = None,
) -> None:
    """Merge granular node/connection patches (same rules as frontend ``mergeGranularUpdate``).

    Optionally removes nodes/connections by ID (``deleted_node_ids`` /
    ``deleted_connection_ids``) before applying patches.
    """
    if deleted_node_ids:
        to_delete: Set[str] = {str(nid) for nid in deleted_node_ids if nid}
        spec["nodes"] = [
            n for n in (spec.get("nodes") or [])
            if isinstance(n, dict) and str(n.get("id", "")) not in to_delete
        ]

    if deleted_connection_ids:
        to_delete_c: Set[str] = {str(cid) for cid in deleted_connection_ids if cid}
        spec["connections"] = [
            c for c in (spec.get("connections") or [])
            if isinstance(c, dict) and str(c.get("id", "")) not in to_delete_c
        ]

    skip_patch_ids: Set[str] = set()
    if deleted_node_ids:
        skip_patch_ids = {str(nid) for nid in deleted_node_ids if nid}

    if nodes:
        existing_nodes: List[Dict[str, Any]] = list(spec.get("nodes") or [])
        if not isinstance(existing_nodes, list):
            existing_nodes = []
        spec["nodes"] = _merge_node_patches(
            existing_nodes, nodes, skip_node_ids=skip_patch_ids,
        )

    if connections:
        conns: List[Dict[str, Any]] = list(spec.get("connections") or [])
        if not isinstance(conns, list):
            conns = []
        spec["connections"] = _merge_connection_patches(conns, connections)

    _prune_dangling_connections(spec)


_CHANGED_FULL = frozenset({"__full__"})


def apply_live_update(
    current: Optional[Dict[str, Any]],
    spec: Optional[Any],
    nodes: Optional[List[Any]],
    connections: Optional[List[Any]],
    deleted_node_ids: Optional[List[str]] = None,
    deleted_connection_ids: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], int, frozenset]:
    """
    Apply one WS update. Full ``spec`` replaces document; else merge granular.

    ``deleted_node_ids`` / ``deleted_connection_ids`` allow granular deletions
    without requiring a full spec replacement (which bypasses node locks).

    Returns:
        (new_document, version, changed_keys) where ``changed_keys`` is a
        frozenset of top-level JSONB keys that changed.  The sentinel value
        ``frozenset({"__full__"})`` indicates a full document replacement or
        a structural deletion that requires the flush path to write the whole
        spec column rather than a partial ``jsonb_set``.
    """
    next_v = 1
    if current and isinstance(current.get("v"), int):
        next_v = int(current["v"]) + 1

    has_deletions = bool(deleted_node_ids) or bool(deleted_connection_ids)
    is_granular = nodes is not None or connections is not None or has_deletions

    if spec is not None and not is_granular:
        if isinstance(spec, dict):
            out = deepcopy(spec)
            out.pop("v", None)
            out["v"] = next_v
            return out, next_v, _CHANGED_FULL
        logger.warning("[LiveSpec] invalid full spec type, ignoring")
        base = deepcopy(current) if current else {}
        base.pop("v", None)
        base["v"] = next_v
        return base, next_v, _CHANGED_FULL

    if has_deletions:
        out = deepcopy(current) if current else {}
        out.pop("v", None)
        gn = [n for n in nodes if isinstance(n, dict)] if nodes is not None else None
        gc = [c for c in connections if isinstance(c, dict)] if connections is not None else None
        merge_granular_into_spec(
            out, gn, gc,
            deleted_node_ids=deleted_node_ids,
            deleted_connection_ids=deleted_connection_ids,
        )
        out["v"] = next_v
        return out, next_v, _CHANGED_FULL

    out = deepcopy(current) if current else {}
    out.pop("v", None)
    gn = None
    gc = None
    changed: set = set()
    if nodes is not None:
        gn = [n for n in nodes if isinstance(n, dict)]
        changed.add("nodes")
    if connections is not None:
        gc = [c for c in connections if isinstance(c, dict)]
        changed.add("connections")
    merge_granular_into_spec(out, gn, gc)
    out["v"] = next_v
    return out, next_v, frozenset(changed)


def serialize_live_spec(doc: Dict[str, Any]) -> str:
    """JSON for Redis (includes internal ``v``)."""
    return json.dumps(doc, ensure_ascii=False)


def deserialize_live_spec(raw: Any) -> Optional[Dict[str, Any]]:
    """Parse Redis bytes/str to a dict."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def spec_for_snapshot(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Client-facing snapshot without internal version / seq keys."""
    out = deepcopy(doc)
    out.pop("v", None)
    out.pop("__seq__", None)
    return out


async def read_live_spec(redis: Any, code: str) -> Optional[Dict[str, Any]]:
    """Read live spec from Redis via ``JSON.GET`` (Redis 8+)."""
    return await json_get_live_spec(redis, code)


async def write_live_spec(
    redis: Any,
    code: str,
    doc: Dict[str, Any],
    ttl_sec: int,
) -> None:
    """Persist live spec with session-aligned TTL (RedisJSON only)."""
    ttl = max(1, min(int(ttl_sec), 86400 * 14))
    if not await json_set_live_spec(redis, code, doc, ttl):
        raise RuntimeError(f"live_spec JSON.SET failed code={code}")


async def seed_live_spec_from_diagram(
    redis: Any,
    code: str,
    diagram: Diagram,
    ttl_sec: int,
) -> Dict[str, Any]:
    """Hydrate Redis from ``Diagram.spec`` JSON; version starts at 1."""
    parsed = _parse_db_spec(diagram)
    if "type" not in parsed and diagram.diagram_type:
        parsed["type"] = diagram.diagram_type
    parsed["v"] = 1
    await write_live_spec(redis, code, parsed, ttl_sec)
    return parsed
