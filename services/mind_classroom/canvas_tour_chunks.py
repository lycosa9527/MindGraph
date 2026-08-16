"""Split each_node tours into per-trunk families so one LLM call stays short."""

from __future__ import annotations

from typing import Any, Optional


def split_each_node_families(tour_nodes: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group a deep walk into [trunk, ...leaves] families. Topic is omitted."""
    families: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for node in tour_nodes:
        if not isinstance(node, dict):
            continue
        if node.get("kind") == "topic":
            continue
        if node.get("stop") == "trunk":
            if current:
                families.append(current)
            current = [node]
            continue
        if current:
            current.append(node)
    if current:
        families.append(current)
    return families


def merge_usage(
    left: Optional[dict[str, Any]],
    right: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Add numeric token fields from two usage dicts."""
    if left is None:
        return dict(right) if isinstance(right, dict) else None
    if right is None:
        return dict(left)
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, int) and isinstance(merged.get(key), int):
            merged[key] = int(merged[key]) + value
        elif key not in merged:
            merged[key] = value
    return merged
