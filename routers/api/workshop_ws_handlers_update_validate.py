"""Validation helpers for canvas-collab update messages."""

import json
from typing import Any, Dict, List, Optional

_MAX_COLLAB_UPDATE_NODES = 100
_MAX_COLLAB_UPDATE_CONNECTIONS = 200
_MAX_COLLAB_DELETED_NODE_IDS = 200
_MAX_COLLAB_DELETED_CONNECTION_IDS = 200
_MAX_COLLAB_ID_LENGTH = 200
_MAX_CLIENT_OP_ID_LENGTH = 128
_FULL_SPEC_MAX_NODES = 512
_FULL_SPEC_MAX_CONNECTIONS = 1024
_FULL_SPEC_MAX_UTF8_BYTES = 786432


def _full_spec_validation_error(spec: Any) -> Optional[str]:
    """Bounds for full-document replacement updates (beyond raw WS frame limits)."""
    if spec is None:
        return None
    if not isinstance(spec, dict):
        return "spec must be an object"
    nodes = spec.get("nodes")
    connections = spec.get("connections")
    if nodes is not None and not isinstance(nodes, list):
        return "spec.nodes must be an array"
    if connections is not None and not isinstance(connections, list):
        return "spec.connections must be an array"
    if nodes is not None and len(nodes) > _FULL_SPEC_MAX_NODES:
        return f"spec.nodes exceeds max length ({_FULL_SPEC_MAX_NODES})"
    if connections is not None and len(connections) > _FULL_SPEC_MAX_CONNECTIONS:
        return f"spec.connections exceeds max length ({_FULL_SPEC_MAX_CONNECTIONS})"
    try:
        serialised_len = len(json.dumps(spec, ensure_ascii=False).encode("utf-8"))
        if serialised_len > _FULL_SPEC_MAX_UTF8_BYTES:
            return f"spec JSON exceeds {_FULL_SPEC_MAX_UTF8_BYTES // 1024} KiB"
    except (TypeError, ValueError):
        return "spec is not serialisable"
    return None


def _diagram_update_validation_error(
    diagram_id: str,
    message: Dict[str, Any],
) -> Optional[str]:
    """Return an error string for invalid updates, else ``None``."""
    errors: List[str] = []
    if message.get("diagram_id") != diagram_id:
        errors.append("Diagram ID mismatch")
    spec = message.get("spec")
    nodes = message.get("nodes")
    connections = message.get("connections")
    deleted_node_ids_raw = message.get("deleted_node_ids")
    deleted_connection_ids_raw = message.get("deleted_connection_ids")
    has_deletions = bool(deleted_node_ids_raw) or bool(deleted_connection_ids_raw)

    if not spec and not nodes and not connections and not has_deletions:
        errors.append("Missing spec, nodes, connections, or deletions in update")
    if nodes is not None:
        if not isinstance(nodes, list):
            errors.append("Invalid nodes format (must be array)")
        elif len(nodes) > _MAX_COLLAB_UPDATE_NODES:
            errors.append(f"Too many nodes in update (max {_MAX_COLLAB_UPDATE_NODES})")
    if connections is not None:
        if not isinstance(connections, list):
            errors.append("Invalid connections format (must be array)")
        elif len(connections) > _MAX_COLLAB_UPDATE_CONNECTIONS:
            errors.append(
                "Too many connections in update "
                f"(max {_MAX_COLLAB_UPDATE_CONNECTIONS})"
            )
    if deleted_node_ids_raw is not None:
        if not isinstance(deleted_node_ids_raw, list):
            errors.append("Invalid deleted_node_ids format (must be array)")
        elif len(deleted_node_ids_raw) > _MAX_COLLAB_DELETED_NODE_IDS:
            errors.append(
                "Too many deleted_node_ids in update "
                f"(max {_MAX_COLLAB_DELETED_NODE_IDS})"
            )
        elif any(
            not isinstance(i, str) or len(i) > _MAX_COLLAB_ID_LENGTH
            for i in deleted_node_ids_raw
            if i is not None
        ):
            errors.append(
                "Invalid deleted_node_ids entry (must be string, "
                f"max {_MAX_COLLAB_ID_LENGTH} chars)"
            )
    if deleted_connection_ids_raw is not None:
        if not isinstance(deleted_connection_ids_raw, list):
            errors.append("Invalid deleted_connection_ids format (must be array)")
        elif len(deleted_connection_ids_raw) > _MAX_COLLAB_DELETED_CONNECTION_IDS:
            errors.append(
                "Too many deleted_connection_ids in update "
                f"(max {_MAX_COLLAB_DELETED_CONNECTION_IDS})"
            )
        elif any(
            not isinstance(i, str) or len(i) > _MAX_COLLAB_ID_LENGTH
            for i in deleted_connection_ids_raw
            if i is not None
        ):
            errors.append(
                "Invalid deleted_connection_ids entry (must be string, "
                f"max {_MAX_COLLAB_ID_LENGTH} chars)"
            )

    granular = nodes is not None or connections is not None
    if spec is not None and not granular:
        fs_err = _full_spec_validation_error(spec)
        if fs_err:
            errors.append(fs_err)
    cop_raw = message.get("client_op_id")
    if cop_raw is not None:
        if not isinstance(cop_raw, str):
            errors.append("client_op_id must be a string")
        elif len(cop_raw) > _MAX_CLIENT_OP_ID_LENGTH:
            errors.append(
                f"client_op_id exceeds max length ({_MAX_CLIENT_OP_ID_LENGTH})"
            )
    return errors[0] if errors else None
