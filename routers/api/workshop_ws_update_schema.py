"""
Strict structural validation for canvas ``update`` WebSocket payloads.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from typing import Any, Dict, FrozenSet, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

_MAX_UPDATE_NEST_DEPTH = 4
_MAX_NODE_STRING_UTF8 = 256_000
_MAX_DATA_OBJECT_KEYS = 64

_ALLOWED_NODE_TOP_KEYS: FrozenSet[str] = frozenset({
    "id", "text", "type", "position", "style", "childIds", "parentId", "data",
    "width", "height", "zIndex", "draggable", "selectable", "expandParent",
    "sourcePosition", "targetPosition", "ariaLabel", "hidden", "connectable",
    "flowPoint", "focusable", "pointerEvents", "label",
    "selected", "dragging", "resizing", "computedPosition", "measured",
    "handleBounds", "internals", "events",
})

_ALLOWED_CONNECTION_TOP_KEYS: FrozenSet[str] = frozenset({
    "id", "source", "target", "sourceHandle", "targetHandle", "type", "style",
    "data", "label", "animated", "selected",
    "zIndex", "interactionWidth",
})


def _collab_max_node_text_bytes() -> int:
    raw = os.environ.get("COLLAB_WS_MAX_TEXT_BYTES", "1048576")
    try:
        return max(4096, int(raw))
    except (TypeError, ValueError):
        return 1048576


def _utf8_len(value: str) -> int:
    return len(value.encode("utf-8"))


def _validate_depth_and_strings(
    obj: Any,
    depth: int,
    max_depth: int,
    max_utf8: int,
) -> Optional[str]:
    if depth > max_depth:
        return f"Value exceeds maximum nesting depth ({max_depth})"
    if isinstance(obj, str):
        if _utf8_len(obj) > max_utf8:
            return "String exceeds maximum UTF-8 length for update payload"
        return None
    if isinstance(obj, dict):
        if len(obj) > _MAX_DATA_OBJECT_KEYS and depth >= 2:
            return "Object has too many keys at this nesting level"
        for key, val in obj.items():
            if isinstance(key, str) and _utf8_len(key) > 200:
                return "Object key is too long"
            err = _validate_depth_and_strings(val, depth + 1, max_depth, max_utf8)
            if err:
                return err
        return None
    if isinstance(obj, list):
        for item in obj:
            err = _validate_depth_and_strings(item, depth + 1, max_depth, max_utf8)
            if err:
                return err
        return None
    return None


def _check_top_level_keys(items: List[Any], label: str, allowed: Set[str]) -> Optional[str]:
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            return f"{label}[{idx}] must be an object"
        extra = set(item.keys()) - allowed
        if extra:
            sample = ", ".join(sorted(extra)[:12])
            return f"{label}[{idx}] has unknown keys: {sample}"
    return None


class CollabWsUpdateSchemaModel(BaseModel):
    """Subset of an ``update`` frame validated beyond coarse bounds checks."""

    model_config = ConfigDict(extra="ignore")

    type: str = Field(default="update")
    diagram_id: str = Field(min_length=1)
    spec: Optional[Dict[str, Any]] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    connections: Optional[List[Dict[str, Any]]] = None
    deleted_node_ids: Optional[List[str]] = None
    deleted_connection_ids: Optional[List[str]] = None
    client_op_id: Optional[str] = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _structural_rules(self) -> CollabWsUpdateSchemaModel:
        text_limit = min(_collab_max_node_text_bytes(), _MAX_NODE_STRING_UTF8)
        if self.nodes is not None:
            err = _check_top_level_keys(self.nodes, "nodes", set(_ALLOWED_NODE_TOP_KEYS))
            if err:
                raise ValueError(err)
            for obj in self.nodes:
                err = _validate_depth_and_strings(obj, 0, _MAX_UPDATE_NEST_DEPTH, text_limit)
                if err:
                    raise ValueError(err)
        if self.connections is not None:
            err = _check_top_level_keys(
                self.connections, "connections", set(_ALLOWED_CONNECTION_TOP_KEYS),
            )
            if err:
                raise ValueError(err)
            for obj in self.connections:
                err = _validate_depth_and_strings(obj, 0, _MAX_UPDATE_NEST_DEPTH, text_limit)
                if err:
                    raise ValueError(err)
        if self.spec is not None:
            if not isinstance(self.spec, dict):
                raise ValueError("spec must be an object")
            err = _validate_depth_and_strings(self.spec, 0, _MAX_UPDATE_NEST_DEPTH, text_limit)
            if err:
                raise ValueError(err)
        return self


def collab_update_schema_error(message: Dict[str, Any]) -> Optional[str]:
    """Return a user-facing error string, or ``None`` if validation passes."""
    try:
        CollabWsUpdateSchemaModel.model_validate(message)
    except ValidationError as exc:
        err_list = exc.errors()
        if not err_list:
            return "Invalid update payload"
        first = err_list[0]
        parts = [str(x) for x in first.get("loc", ()) if x is not None]
        loc = ".".join(parts)
        msg = str(first.get("msg", "validation failed"))
        if loc:
            return f"{loc}: {msg}"
        return msg
    return None
