"""Extract mind-map outline (topic + first-level branches) from diagram spec JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MindMapBranchOutline:
    """One first-level branch and its immediate children texts."""

    id: Optional[str]
    text: str
    children: list[str] = field(default_factory=list)


@dataclass
class MindMapOutline:
    """Normalized mind-map structure for lesson planning."""

    topic: str
    branches: list[MindMapBranchOutline] = field(default_factory=list)
    diagram_type: str = "mind_map"

    def to_planner_payload(self) -> dict[str, Any]:
        """JSON-serializable outline for the lesson planner LLM."""
        return {
            "topic": self.topic,
            "branches": [
                {
                    "id": branch.id,
                    "text": branch.text,
                    "children": list(branch.children),
                }
                for branch in self.branches
            ],
        }


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _child_texts(node: dict[str, Any]) -> list[str]:
    kids = node.get("children")
    if not isinstance(kids, list):
        kids = node.get("branches")
    if not isinstance(kids, list):
        return []
    texts: list[str] = []
    for kid in kids:
        if isinstance(kid, str):
            text = kid.strip()
            if text:
                texts.append(text)
            continue
        if not isinstance(kid, dict):
            continue
        text = _clean_text(kid.get("text") or kid.get("label") or kid.get("topic"))
        if text:
            texts.append(text)
    return texts


def _branches_from_hierarchical(spec: dict[str, Any]) -> list[MindMapBranchOutline]:
    raw_branches: list[Any] = []
    if isinstance(spec.get("children"), list):
        raw_branches = spec["children"]
    elif isinstance(spec.get("branches"), list):
        raw_branches = spec["branches"]
    else:
        left = spec.get("leftBranches") or spec.get("left") or []
        right = spec.get("rightBranches") or spec.get("right") or []
        if isinstance(right, list):
            raw_branches.extend(right)
        if isinstance(left, list):
            raw_branches.extend(left)

    branches: list[MindMapBranchOutline] = []
    for index, item in enumerate(raw_branches):
        if isinstance(item, str):
            text = item.strip()
            if text:
                branches.append(MindMapBranchOutline(id=f"branch-{index}", text=text))
            continue
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text") or item.get("label") or item.get("topic"))
        if not text:
            continue
        node_id = item.get("id") or item.get("uid")
        branches.append(
            MindMapBranchOutline(
                id=str(node_id) if node_id else f"branch-{index}",
                text=text,
                children=_child_texts(item),
            )
        )
    return branches


def _branches_from_nodes(spec: dict[str, Any]) -> tuple[str, list[MindMapBranchOutline]]:
    nodes = spec.get("nodes")
    connections = spec.get("connections")
    if not isinstance(nodes, list) or not nodes:
        return "", []

    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id:
            by_id[node_id] = node

    children_map: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    if isinstance(connections, list):
        for conn in connections:
            if not isinstance(conn, dict):
                continue
            source = conn.get("source")
            target = conn.get("target")
            if isinstance(source, str) and isinstance(target, str):
                if source in children_map and target in by_id:
                    children_map[source].append(target)

    topic_id = None
    topic_text = ""
    for node_id, node in by_id.items():
        node_type = str(node.get("type") or "").lower()
        if node_type == "topic" or node_id == "topic":
            topic_id = node_id
            topic_text = _clean_text(node.get("text") or node.get("label"))
            break
    if topic_id is None:
        # Fallback: first node
        topic_id = next(iter(by_id))
        topic_text = _clean_text(by_id[topic_id].get("text") or by_id[topic_id].get("label"))

    branches: list[MindMapBranchOutline] = []
    for child_id in children_map.get(topic_id or "", []):
        node = by_id.get(child_id)
        if not node:
            continue
        text = _clean_text(node.get("text") or node.get("label"))
        if not text:
            continue
        grandchild_texts = []
        for gid in children_map.get(child_id, []):
            gnode = by_id.get(gid)
            if not gnode:
                continue
            gtext = _clean_text(gnode.get("text") or gnode.get("label"))
            if gtext:
                grandchild_texts.append(gtext)
        branches.append(MindMapBranchOutline(id=child_id, text=text, children=grandchild_texts))
    return topic_text, branches


def is_mindmap_type(diagram_type: Optional[str]) -> bool:
    """Return True for mind-map diagram type slugs."""
    slug = (diagram_type or "").strip().lower().replace("-", "_")
    return slug in {"mindmap", "mind_map"}


def extract_mindmap_outline(
    spec: Any,
    *,
    diagram_type: Optional[str] = None,
    fallback_title: str = "",
) -> MindMapOutline:
    """
    Normalize a saved diagram ``spec`` into topic + first-level branches.

    Supports hierarchical ``topic``/``children`` and flat ``nodes``/``connections``.
    """
    if not isinstance(spec, dict):
        raise ValueError("Diagram spec must be a JSON object")

    type_hint = diagram_type or spec.get("type") or spec.get("diagramType")
    if type_hint and not is_mindmap_type(str(type_hint)):
        # Still try hierarchical extract; reject clearly non-mindmap later in API.
        pass

    topic = _clean_text(spec.get("topic") or spec.get("title") or spec.get("centralTopic"))
    branches = _branches_from_hierarchical(spec)

    if (not topic or not branches) and isinstance(spec.get("nodes"), list):
        node_topic, node_branches = _branches_from_nodes(spec)
        if not topic:
            topic = node_topic
        if not branches:
            branches = node_branches

    if not topic:
        topic = _clean_text(fallback_title) or "未命名主题"
    if not branches:
        raise ValueError("Mind map has no first-level branches to teach from")

    return MindMapOutline(
        topic=topic,
        branches=branches,
        diagram_type="mind_map",
    )
