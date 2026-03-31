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
from typing import Any, Dict, List, Optional, Tuple

from models.domain.diagrams import Diagram
from services.workshop.workshop_redis_keys import live_spec_key

logger = logging.getLogger(__name__)


def _parse_db_spec(diagram: Diagram) -> Dict[str, Any]:
    raw = diagram.spec
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _merge_node_patches(
    existing_nodes: List[Dict[str, Any]],
    patches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_index = {str(n.get("id")): i for i, n in enumerate(existing_nodes) if n.get("id")}
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        node_id = patch.get("id")
        if not node_id:
            continue
        sid = str(node_id)
        if sid in by_index:
            i = by_index[sid]
            existing_nodes[i] = {**existing_nodes[i], **patch}
        else:
            existing_nodes.append(patch)
            by_index[sid] = len(existing_nodes) - 1
    return existing_nodes


def _merge_connection_patches(
    conns: List[Dict[str, Any]],
    patches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        source = patch.get("source")
        target = patch.get("target")
        if not source or not target:
            continue
        idx = next(
            (
                i
                for i, c in enumerate(conns)
                if isinstance(c, dict) and c.get("source") == source and c.get("target") == target
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
) -> None:
    """Merge granular node/connection patches (same rules as frontend ``mergeGranularUpdate``)."""
    if nodes:
        existing_nodes: List[Dict[str, Any]] = list(spec.get("nodes") or [])
        if not isinstance(existing_nodes, list):
            existing_nodes = []
        spec["nodes"] = _merge_node_patches(existing_nodes, nodes)

    if connections:
        conns: List[Dict[str, Any]] = list(spec.get("connections") or [])
        if not isinstance(conns, list):
            conns = []
        spec["connections"] = _merge_connection_patches(conns, connections)


def apply_live_update(
    current: Optional[Dict[str, Any]],
    spec: Optional[Any],
    nodes: Optional[List[Any]],
    connections: Optional[List[Any]],
) -> Tuple[Dict[str, Any], int]:
    """
    Apply one WS update. Full ``spec`` replaces document; else merge granular.

    Returns:
        (new_document, version)
    """
    next_v = 1
    if current and isinstance(current.get("v"), int):
        next_v = int(current["v"]) + 1

    if spec is not None and not nodes and not connections:
        if isinstance(spec, dict):
            out = deepcopy(spec)
            out.pop("v", None)
            out["v"] = next_v
            return out, next_v
        logger.warning("[LiveSpec] invalid full spec type, ignoring")
        base = deepcopy(current) if current else {}
        base.pop("v", None)
        base["v"] = next_v
        return base, next_v

    out = deepcopy(current) if current else {}
    out.pop("v", None)
    gn = None
    gc = None
    if nodes is not None:
        gn = [n for n in nodes if isinstance(n, dict)]
    if connections is not None:
        gc = [c for c in connections if isinstance(c, dict)]
    merge_granular_into_spec(out, gn, gc)
    out["v"] = next_v
    return out, next_v


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
    """Client-facing snapshot without internal version key."""
    out = deepcopy(doc)
    out.pop("v", None)
    return out


def read_live_spec(redis: Any, code: str) -> Optional[Dict[str, Any]]:
    """Read live spec JSON from Redis."""
    raw = redis.get(live_spec_key(code))
    return deserialize_live_spec(raw)


def write_live_spec(
    redis: Any,
    code: str,
    doc: Dict[str, Any],
    ttl_sec: int,
) -> None:
    """Persist live spec with session-aligned TTL."""
    ttl = max(1, min(int(ttl_sec), 86400 * 14))
    redis.setex(live_spec_key(code), ttl, serialize_live_spec(doc))


def seed_live_spec_from_diagram(
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
    write_live_spec(redis, code, parsed, ttl_sec)
    return parsed
