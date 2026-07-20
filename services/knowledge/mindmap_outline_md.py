"""Convert a mind-map ``topic``/``children`` spec into Document Summary markdown."""

from __future__ import annotations

from typing import Any, Dict, List


def _node_text(node: Dict[str, Any]) -> str:
    """Prefer canonical ``text``, fall back to ``label``."""
    return str(node.get("text") or node.get("label") or "").strip()


def _append_children(lines: List[str], nodes: Any, *, depth: int) -> None:
    """Append nested markdown bullets / headings for mind-map children."""
    if not isinstance(nodes, list) or depth > 6:
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        label = _node_text(node)
        if not label:
            continue
        if depth == 0:
            lines.append(f"## {label}")
        elif depth == 1:
            lines.append(f"- {label}")
        else:
            indent = "  " * (depth - 1)
            lines.append(f"{indent}- {label}")
        nested = node.get("children")
        if nested:
            _append_children(lines, nested, depth=depth + 1)
        if depth == 0:
            lines.append("")


def mindmap_spec_to_outline_markdown(spec: Dict[str, Any]) -> str:
    """Build a human-readable outline for Document Summary extract.md."""
    topic = str(spec.get("topic") or "").strip() or "Mind Map"
    lines: List[str] = [
        f"# {topic}",
        "",
        "> Source: hand-drawn / photographed mind map (vision rebuild)",
        "",
    ]
    _append_children(lines, spec.get("children"), depth=0)
    return "\n".join(lines).strip() + "\n"
