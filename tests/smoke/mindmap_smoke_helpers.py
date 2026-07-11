"""Shared helpers for LIVE_LLM one-sentence / mindmap smoke tests.

Layout contract: after structural edits, every pre-existing node keeps its
``position`` (layout must not be destroyed / full-relayouted).
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.diagram_edit.types import ExpectedEffect
from services.diagram_edit.verify import normalize_diagram_text, verify_mindmap_effect


def mindmap_smoke_helpers_load_dotenv(env_path: Path) -> None:
    """Load KEY=VALUE lines from ``.env`` without executing shell comments."""
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value


def live_llm_enabled() -> bool:
    """True when LIVE_LLM=1 and a real QWEN_API_KEY is configured."""
    if os.getenv("LIVE_LLM", "").strip().lower() not in ("1", "true", "yes"):
        return False
    api_key = (os.getenv("QWEN_API_KEY") or "").strip()
    return bool(api_key) and "your-" not in api_key.lower()


def _node_label(node: Dict[str, Any]) -> str:
    text = node.get("text")
    if isinstance(text, str) and text.strip():
        return normalize_diagram_text(text)
    data = node.get("data")
    if isinstance(data, dict):
        label = data.get("label")
        if isinstance(label, str):
            return normalize_diagram_text(label)
    return ""


def layout_fingerprint(nodes: List[Dict[str, Any]]) -> Dict[str, Tuple[float, float]]:
    """Map node id → (x, y) for layout-preservation checks."""
    out: Dict[str, Tuple[float, float]] = {}
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            continue
        pos = node.get("position")
        if not isinstance(pos, dict):
            continue
        x_raw = pos.get("x")
        y_raw = pos.get("y")
        if isinstance(x_raw, (int, float)) and isinstance(y_raw, (int, float)):
            out[node_id] = (float(x_raw), float(y_raw))
    return out


def assert_layout_preserved(
    before_nodes: List[Dict[str, Any]],
    after_nodes: List[Dict[str, Any]],
    *,
    allow_removed_ids: Optional[set[str]] = None,
) -> None:
    """
    Assert every node that still exists kept the same canvas position.

    New nodes may appear; removed ids listed in ``allow_removed_ids`` are OK.
    """
    before = layout_fingerprint(before_nodes)
    after = layout_fingerprint(after_nodes)
    removed = allow_removed_ids or set()
    for node_id, pos in before.items():
        if node_id in removed:
            continue
        assert node_id in after, f"layout destroyed: node {node_id} missing after edit"
        assert after[node_id] == pos, f"layout destroyed: node {node_id} moved from {pos} to {after[node_id]}"


def mindmap_spec_to_canvas(
    spec: Dict[str, Any],
    *,
    origin_x: float = 400.0,
    origin_y: float = 300.0,
    col_gap: float = 220.0,
    row_gap: float = 80.0,
) -> Dict[str, Any]:
    """
    Materialize LLM mindmap JSON (topic + children tree) into nodes/connections
    with stable synthetic positions (simulates a laid-out canvas).
    """
    topic = str(spec.get("topic") or "Topic").strip() or "Topic"
    nodes: List[Dict[str, Any]] = [
        {
            "id": "topic",
            "type": "topic",
            "text": topic,
            "position": {"x": origin_x, "y": origin_y},
        }
    ]
    connections: List[Dict[str, Any]] = []

    def walk(
        children: Any,
        parent_id: str,
        depth: int,
        side: str,
        start_index: int,
    ) -> int:
        if not isinstance(children, list):
            return start_index
        idx = start_index
        for child in children:
            if not isinstance(child, dict):
                continue
            label = str(child.get("text") or child.get("label") or "").strip()
            if not label:
                continue
            node_id = f"branch-{side[0]}-{depth}-{idx}"
            x_off = col_gap * depth if side == "right" else -col_gap * depth
            y_off = (idx - start_index) * row_gap
            nodes.append(
                {
                    "id": node_id,
                    "type": "branch",
                    "text": label,
                    "position": {
                        "x": origin_x + x_off,
                        "y": origin_y + y_off,
                    },
                }
            )
            connections.append(
                {
                    "id": f"e-{parent_id}-{node_id}",
                    "source": parent_id,
                    "target": node_id,
                }
            )
            nested = child.get("children")
            walk(nested, node_id, depth + 1, side, 0)
            idx += 1
        return idx

    children = spec.get("children") or []
    if isinstance(children, list) and children:
        mid = (len(children) + 1) // 2
        walk(children[:mid], "topic", 1, "right", 0)
        walk(children[mid:], "topic", 1, "left", 0)

    return {
        "topic": topic,
        "nodes": nodes,
        "connections": connections,
        "diagram_type": "mindmap",
    }


def canvas_branch_labels(canvas: Dict[str, Any]) -> List[str]:
    """Top-level branch labels under topic (depth-1)."""
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    if not isinstance(nodes, list) or not isinstance(conns, list):
        return []
    child_ids = {str(c.get("target")) for c in conns if isinstance(c, dict) and c.get("source") == "topic"}
    labels: List[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if str(node.get("id")) in child_ids:
            labels.append(_node_label(node))
    return [label for label in labels if label]


def apply_add_branch(
    canvas: Dict[str, Any],
    label: str,
    *,
    side: str = "right",
) -> Dict[str, Any]:
    """Append a top-level branch without moving existing nodes."""
    next_canvas = copy.deepcopy(canvas)
    nodes = next_canvas["nodes"]
    connections = next_canvas["connections"]
    assert isinstance(nodes, list)
    assert isinstance(connections, list)

    existing = [n for n in nodes if isinstance(n, dict) and str(n.get("id", "")).startswith(f"branch-{side[0]}-1-")]
    next_idx = len(existing)
    node_id = f"branch-{side[0]}-1-{next_idx}"
    topic = next((n for n in nodes if isinstance(n, dict) and n.get("id") == "topic"), None)
    base_x = 400.0
    base_y = 300.0
    if isinstance(topic, dict) and isinstance(topic.get("position"), dict):
        base_x = float(topic["position"].get("x", base_x))
        base_y = float(topic["position"].get("y", base_y))

    x_off = 220.0 if side == "right" else -220.0
    y_off = next_idx * 80.0
    nodes.append(
        {
            "id": node_id,
            "type": "branch",
            "text": label,
            "position": {"x": base_x + x_off, "y": base_y + y_off},
        }
    )
    connections.append(
        {
            "id": f"e-topic-{node_id}",
            "source": "topic",
            "target": node_id,
        }
    )
    return next_canvas


def apply_delete_node_by_label(canvas: Dict[str, Any], label: str) -> Tuple[Dict[str, Any], str]:
    """Delete first node matching label; returns (canvas, removed_id)."""
    next_canvas = copy.deepcopy(canvas)
    nodes = next_canvas["nodes"]
    connections = next_canvas["connections"]
    assert isinstance(nodes, list)
    assert isinstance(connections, list)
    target = normalize_diagram_text(label)
    removed_id: Optional[str] = None
    kept: List[Dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if removed_id is None and _node_label(node) == target and node.get("id") != "topic":
            removed_id = str(node.get("id"))
            continue
        kept.append(node)
    if removed_id is None:
        raise AssertionError(f"node label not found for delete: {label}")
    next_canvas["nodes"] = kept
    next_canvas["connections"] = [
        c
        for c in connections
        if isinstance(c, dict) and c.get("source") != removed_id and c.get("target") != removed_id
    ]
    return next_canvas, removed_id


def apply_update_node_label(
    canvas: Dict[str, Any],
    old_label: str,
    new_label: str,
) -> Dict[str, Any]:
    """Rename a node in place without changing positions."""
    next_canvas = copy.deepcopy(canvas)
    nodes = next_canvas["nodes"]
    assert isinstance(nodes, list)
    old_n = normalize_diagram_text(old_label)
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if _node_label(node) == old_n:
            node["text"] = new_label
            return next_canvas
    raise AssertionError(f"node label not found for update: {old_label}")


def apply_update_center(canvas: Dict[str, Any], new_topic: str) -> Dict[str, Any]:
    """Update topic text only."""
    next_canvas = copy.deepcopy(canvas)
    nodes = next_canvas["nodes"]
    assert isinstance(nodes, list)
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == "topic":
            node["text"] = new_topic
            next_canvas["topic"] = new_topic
            return next_canvas
    raise AssertionError("topic node missing")


def evidence_from_canvas(canvas: Dict[str, Any]) -> Dict[str, Any]:
    """Shape expected by ``verify_mindmap_effect``."""
    return {
        "nodes": list(canvas.get("nodes") or []),
        "connections": list(canvas.get("connections") or []),
    }


def assert_add_branch_verified(before: Dict[str, Any], after: Dict[str, Any], label: str) -> None:
    """Run backend mindmap verification for add_branch."""
    effect = ExpectedEffect(
        op="add_branch",
        text=label,
        parent_ref="topic",
        checks=["node_exists", "text_matches", "parent_edge_exists", "delta_nodes"],
    )
    report = verify_mindmap_effect(
        effect,
        evidence_from_canvas(after),
        before_node_count=len(before.get("nodes") or []),
    )
    assert report.ok, f"add_branch verify failed: {report.error} checks={report.checks}"
