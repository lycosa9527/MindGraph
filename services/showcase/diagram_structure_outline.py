"""
Build a readable structural outline from showcase diagram specs for AI copy.

Library diagrams usually persist as ``nodes`` + ``connections``. Native specs use
typed fields (topic/branches, causes/effects, …). Either way the LLM needs
hierarchy and roles, not a flat bag of labels.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from services.kitty.infra.bootstrap.kitty_native_spec import native_spec_to_pseudo_nodes

_DIAGRAM_TYPE_ZH: Dict[str, str] = {
    "circle_map": "圆圈图",
    "bubble_map": "气泡图",
    "double_bubble_map": "双气泡图",
    "brace_map": "括号图",
    "tree_map": "树形图",
    "flow_map": "流程图",
    "multi_flow_map": "复流程图",
    "bridge_map": "桥型图",
    "mind_map": "思维导图",
    "mindmap": "思维导图",
    "concept_map": "概念图",
    "combined": "组合应用",
}

_ROLE_SECTION_ZH: Dict[str, str] = {
    "topic": "中心主题",
    "center": "中心主题",
    "main": "中心主题",
    "whole": "整体",
    "event": "事件",
    "branch": "分支",
    "bubble": "特征/属性",
    "context": "背景/关联",
    "similarity": "相同点",
    "difference": "不同点",
    "cause": "原因",
    "effect": "结果",
    "step": "步骤",
    "substep": "子步骤",
    "category": "类别",
    "item": "项目",
    "part": "部分",
    "subpart": "子部分",
    "relation": "类比关系",
    "pair": "类比对",
    "concept": "概念",
}

_ROOT_ROLE_TYPES = frozenset({"topic", "center", "main", "whole", "event"})
_MAX_TREE_DEPTH = 12
_MAX_OUTLINE_NODES = 400


def normalize_diagram_type_slug(diagram_type: str) -> str:
    """Normalize slug variants (``mindmap`` → ``mind_map``, hyphens → underscores)."""
    raw = (diagram_type or "").strip().replace("-", "_")
    if raw == "mindmap":
        return "mind_map"
    return raw


def resolve_diagram_type(spec: Dict[str, Any], diagram_type: str) -> str:
    """Prefer ``spec.type`` when it is a known diagram slug; else request type."""
    spec_type = spec.get("type")
    if isinstance(spec_type, str) and spec_type.strip():
        candidate = normalize_diagram_type_slug(spec_type)
        if candidate in _DIAGRAM_TYPE_ZH:
            return candidate
    fallback = normalize_diagram_type_slug(diagram_type)
    return fallback or "mind_map"


def diagram_type_zh_label(diagram_type: str) -> str:
    """Chinese display name for a diagram type slug."""
    slug = normalize_diagram_type_slug(diagram_type)
    return _DIAGRAM_TYPE_ZH.get(slug, slug or "未指定")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _node_text(node: Dict[str, Any]) -> str:
    for key in ("text", "label", "topic", "title", "name"):
        cleaned = _clean_text(node.get(key))
        if cleaned:
            return cleaned
    return ""


def _header_lines(diagram_type: str) -> List[str]:
    slug = resolve_diagram_type({"type": diagram_type}, diagram_type)
    zh = diagram_type_zh_label(slug)
    return [
        f"图示类型：{zh}（{slug}）",
        "结构概要：",
    ]


def _walk_nested_text(value: Any, sink: List[str], *, depth: int = 0) -> None:
    if depth > 40:
        return
    if isinstance(value, dict):
        for key in ("text", "label", "topic", "title", "name"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                sink.append(raw.strip())
        for child_key in ("children", "branches", "nodes", "items", "parts", "subparts"):
            child = value.get(child_key)
            if isinstance(child, list):
                for item in child:
                    _walk_nested_text(item, sink, depth=depth + 1)
        return
    if isinstance(value, list):
        for item in value:
            _walk_nested_text(item, sink, depth=depth + 1)


def _format_native_branch_tree(branches: Any, *, depth: int = 0) -> List[str]:
    if not isinstance(branches, list) or depth > _MAX_TREE_DEPTH:
        return []
    lines: List[str] = []
    indent = "  " * depth
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        label = _clean_text(branch.get("text") or branch.get("label"))
        if not label:
            continue
        lines.append(f"{indent}- {label}")
        kids = branch.get("children") or branch.get("branches")
        lines.extend(_format_native_branch_tree(kids, depth=depth + 1))
    return lines


def _outline_from_native_mind_map(spec: Dict[str, Any]) -> Optional[str]:
    topic = _clean_text(spec.get("topic"))
    branch_lines = _format_native_branch_tree(spec.get("branches"))
    if not topic and not branch_lines:
        return None
    lines: List[str] = []
    if topic:
        lines.append(f"中心主题：{topic}")
    if branch_lines:
        lines.append("分支结构：")
        lines.extend(branch_lines)
    return "\n".join(lines)


def _outline_from_native_typed(spec: Dict[str, Any], diagram_type: str) -> Optional[str]:
    """Role-aware outline for native (non-nodes) specs via pseudo-nodes + specials."""
    slug = resolve_diagram_type(spec, diagram_type)
    if slug in ("mind_map", "mindmap"):
        native = _outline_from_native_mind_map(spec)
        if native:
            return native

    if slug == "concept_map":
        return _outline_from_native_concept_map(spec)

    if slug == "bridge_map":
        return _outline_from_native_bridge_map(spec)

    if slug == "double_bubble_map":
        return _outline_from_native_double_bubble(spec)

    if slug in ("flow_map",):
        return _outline_from_native_flow_map(spec)

    if slug in ("tree_map",):
        return _outline_from_native_tree_map(spec)

    if slug == "brace_map":
        return _outline_from_native_brace_map(spec)

    pseudo = native_spec_to_pseudo_nodes(spec, slug)
    if not pseudo:
        return None
    return _outline_from_role_nodes(pseudo)


def _unique_texts(items: Sequence[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _append_section(lines: List[str], title: str, items: Sequence[str]) -> None:
    cleaned = _unique_texts(items)
    if not cleaned:
        return
    lines.append(f"{title}：")
    for item in cleaned:
        lines.append(f"- {item}")


def _as_text_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
        elif isinstance(item, dict):
            text = _node_text(item)
            if text:
                out.append(text)
    return out


def _outline_from_native_double_bubble(spec: Dict[str, Any]) -> Optional[str]:
    left = _clean_text(spec.get("left") or spec.get("leftTopic"))
    right = _clean_text(spec.get("right") or spec.get("rightTopic"))
    lines: List[str] = []
    if left:
        lines.append(f"左侧主题：{left}")
    if right:
        lines.append(f"右侧主题：{right}")
    _append_section(lines, "相同点", _as_text_list(spec.get("similarities") or spec.get("similarity")))
    _append_section(
        lines,
        "左侧不同点",
        _as_text_list(spec.get("leftDifferences") or spec.get("left_differences")),
    )
    _append_section(
        lines,
        "右侧不同点",
        _as_text_list(spec.get("rightDifferences") or spec.get("right_differences")),
    )
    return "\n".join(lines) if lines else None


def _outline_from_native_flow_map(spec: Dict[str, Any]) -> Optional[str]:
    lines: List[str] = []
    title = _clean_text(spec.get("title"))
    if title:
        lines.append(f"流程主题：{title}")
    steps = spec.get("steps")
    step_texts: List[str] = []
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, str) and step.strip():
                step_texts.append(step.strip())
            elif isinstance(step, dict):
                text = _node_text(step)
                if text:
                    step_texts.append(text)
    _append_section(lines, "步骤", step_texts)
    substeps = spec.get("substeps")
    if isinstance(substeps, list):
        for entry in substeps:
            if not isinstance(entry, dict):
                continue
            parent = _clean_text(entry.get("step"))
            kids = _as_text_list(entry.get("substeps"))
            if not kids:
                continue
            label = f"子步骤（隶属：{parent}）" if parent else "子步骤"
            _append_section(lines, label, kids)
    return "\n".join(lines) if lines else None


def _outline_from_native_tree_map(spec: Dict[str, Any]) -> Optional[str]:
    lines: List[str] = []
    main = _clean_text(spec.get("root") or spec.get("main") or spec.get("topic"))
    if main:
        lines.append(f"分类主题：{main}")
    cats = spec.get("children")
    if isinstance(cats, list):
        lines.append("分类结构：")
        for cat in cats:
            if not isinstance(cat, dict):
                continue
            ctext = _clean_text(cat.get("text") or cat.get("name"))
            if not ctext:
                continue
            lines.append(f"- {ctext}")
            items = cat.get("items") or cat.get("children")
            for item in _as_text_list(items):
                lines.append(f"  - {item}")
    return "\n".join(lines) if lines else None


def _outline_from_native_brace_map(spec: Dict[str, Any]) -> Optional[str]:
    lines: List[str] = []
    whole = _clean_text(spec.get("whole"))
    if whole:
        lines.append(f"整体：{whole}")
    parts = spec.get("parts")
    if isinstance(parts, list):
        lines.append("部分结构：")
        for part in parts:
            if not isinstance(part, dict):
                continue
            ptext = _node_text(part)
            if not ptext:
                continue
            lines.append(f"- {ptext}")
            for sub in part.get("subparts") or []:
                if isinstance(sub, dict):
                    stext = _node_text(sub)
                    if stext:
                        lines.append(f"  - {stext}")
    return "\n".join(lines) if lines else None


def _outline_from_native_bridge_map(spec: Dict[str, Any]) -> Optional[str]:
    lines: List[str] = []
    rel = _clean_text(spec.get("relation"))
    if rel:
        lines.append(f"类比维度：{rel}")
    analogies = spec.get("analogies") or spec.get("pairs")
    pairs: List[str] = []
    if isinstance(analogies, list):
        for pair in analogies:
            if not isinstance(pair, dict):
                continue
            left = _clean_text(pair.get("left"))
            right = _clean_text(pair.get("right"))
            if left and right:
                pairs.append(f"{left} ↔ {right}")
            elif left or right:
                pairs.append(left or right)
    _append_section(lines, "类比对", pairs)
    return "\n".join(lines) if lines else None


def _outline_from_native_concept_map(spec: Dict[str, Any]) -> Optional[str]:
    lines: List[str] = []
    topic = _clean_text(spec.get("topic"))
    if topic:
        lines.append(f"中心概念：{topic}")
    _append_section(lines, "概念", _as_text_list(spec.get("concepts")))
    return "\n".join(lines) if lines else None


def _outline_from_role_nodes(nodes: Iterable[Any]) -> Optional[str]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    left_diffs: List[str] = []
    right_diffs: List[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        text = _node_text(node)
        if not text:
            continue
        role = _clean_text(node.get("type")) or "node"
        node_id = _clean_text(node.get("id"))
        if role == "difference":
            if node_id.startswith("left-diff"):
                left_diffs.append(text)
            elif node_id.startswith("right-diff"):
                right_diffs.append(text)
            else:
                grouped["difference"].append(text)
            continue
        if role in _ROOT_ROLE_TYPES:
            grouped[role].append(text)
            continue
        grouped[role].append(text)

    lines: List[str] = []
    for role in ("topic", "center", "main", "whole", "event"):
        items = grouped.pop(role, [])
        if not items:
            continue
        title = _ROLE_SECTION_ZH.get(role, role)
        if len(items) == 1:
            lines.append(f"{title}：{items[0]}")
        else:
            _append_section(lines, title, items)

    _append_section(lines, "左侧不同点", left_diffs)
    _append_section(lines, "右侧不同点", right_diffs)

    preferred_order = (
        "similarity",
        "difference",
        "cause",
        "effect",
        "step",
        "substep",
        "category",
        "item",
        "part",
        "subpart",
        "bubble",
        "context",
        "branch",
        "relation",
        "pair",
        "concept",
        "node",
    )
    for role in preferred_order:
        items = grouped.pop(role, [])
        if items:
            _append_section(lines, _ROLE_SECTION_ZH.get(role, role), items)
    for role, items in grouped.items():
        if items:
            _append_section(lines, _ROLE_SECTION_ZH.get(role, role), items)

    return "\n".join(lines) if lines else None


def _connection_endpoints(
    connections: Sequence[Any],
) -> Tuple[Dict[str, List[Tuple[str, str]]], Set[str]]:
    children: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    targets: Set[str] = set()
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        src = conn.get("source")
        tgt = conn.get("target")
        if not isinstance(src, str) or not isinstance(tgt, str):
            continue
        if not src or not tgt:
            continue
        label = _clean_text(conn.get("label") or conn.get("text"))
        children[src].append((tgt, label))
        targets.add(tgt)
    return children, targets


def _pick_tree_roots(
    by_id: Dict[str, Dict[str, Any]],
    targets: Set[str],
) -> List[str]:
    candidates = [nid for nid in by_id if nid not in targets]
    if not candidates:
        # Cycle / fully connected: prefer topic-like nodes, else first id.
        topic_like = [nid for nid, node in by_id.items() if _clean_text(node.get("type")) in _ROOT_ROLE_TYPES]
        return topic_like[:1] or (list(by_id.keys())[:1])
    topic_roots = [nid for nid in candidates if _clean_text(by_id[nid].get("type")) in _ROOT_ROLE_TYPES]
    return topic_roots or candidates


def _outline_from_nodes_connections(
    nodes: Sequence[Any],
    connections: Sequence[Any],
    *,
    diagram_type: str,
) -> Optional[str]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = node.get("id")
        if not isinstance(nid, str) or not nid:
            continue
        by_id[nid] = node
    if not by_id:
        return None

    children, targets = _connection_endpoints(connections)
    slug = resolve_diagram_type({"type": diagram_type}, diagram_type)

    # Concept maps are relation graphs; keep labeled propositions.
    if slug == "concept_map":
        concept_outline = _outline_graph_with_relations(by_id, children)
        if concept_outline:
            return concept_outline

    if not children:
        typed = [n for n in by_id.values() if _clean_text(n.get("type"))]
        if typed:
            return _outline_from_role_nodes(typed)
        flat = [_node_text(n) for n in by_id.values()]
        flat = [t for t in flat if t]
        if not flat:
            return None
        return "节点文字：\n" + "\n".join(f"- {t}" for t in flat)

    roots = _pick_tree_roots(by_id, targets)
    lines: List[str] = []
    visited: Set[str] = set()

    def walk(node_id: str, depth: int) -> None:
        if node_id in visited or depth > _MAX_TREE_DEPTH or len(visited) >= _MAX_OUTLINE_NODES:
            return
        node = by_id.get(node_id)
        if node is None:
            return
        text = _node_text(node)
        visited.add(node_id)
        if not text:
            for child_id, _label in children.get(node_id, []):
                walk(child_id, depth)
            return
        role = _clean_text(node.get("type"))
        if depth == 0 and role in _ROOT_ROLE_TYPES:
            title = _ROLE_SECTION_ZH.get(role, "中心主题")
            lines.append(f"{title}：{text}")
            if children.get(node_id):
                lines.append("分支结构：")
        elif depth == 0:
            lines.append(f"{text}")
            if children.get(node_id):
                lines.append("结构：")
        else:
            indent = "  " * (depth - 1)
            lines.append(f"{indent}- {text}")
        for child_id, _label in children.get(node_id, []):
            walk(child_id, depth + 1 if text else depth)

    for root in roots:
        walk(root, 0)

    orphans = [text for nid, node in by_id.items() if nid not in visited and (text := _node_text(node))]
    _append_section(lines, "其他节点", orphans)
    return "\n".join(lines) if lines else None


def _outline_graph_with_relations(
    by_id: Dict[str, Dict[str, Any]],
    children: Dict[str, List[Tuple[str, str]]],
) -> Optional[str]:
    concept_texts: List[str] = []
    seen: Set[str] = set()
    for node in by_id.values():
        text = _node_text(node)
        if text and text not in seen:
            seen.add(text)
            concept_texts.append(text)
    relations: List[str] = []
    for src, pairs in children.items():
        src_text = _node_text(by_id[src]) if src in by_id else src
        if not src_text:
            continue
        for tgt, label in pairs:
            tgt_text = _node_text(by_id[tgt]) if tgt in by_id else tgt
            if not tgt_text:
                continue
            if label:
                relations.append(f"{src_text} —{label}→ {tgt_text}")
            else:
                relations.append(f"{src_text} → {tgt_text}")
    lines: List[str] = []
    _append_section(lines, "概念", concept_texts)
    _append_section(lines, "关系", relations)
    return "\n".join(lines) if lines else None


def build_diagram_structure_outline(
    spec: Dict[str, Any],
    diagram_type: str,
) -> str:
    """
    Build a Chinese structural outline for LLM prompting.

    Raises ``ValueError('no_text_extracted')`` when no usable labels exist.
    """
    slug = resolve_diagram_type(spec, diagram_type)
    body: Optional[str] = None

    nodes = spec.get("nodes")
    connections = spec.get("connections")
    if not isinstance(connections, list):
        connections = spec.get("edges")
    if isinstance(nodes, list) and nodes:
        conn_list = connections if isinstance(connections, list) else []
        body = _outline_from_nodes_connections(nodes, conn_list, diagram_type=slug)
        if body is None:
            body = _outline_from_role_nodes(nodes)

    if body is None:
        body = _outline_from_native_typed(spec, slug)

    if body is None:
        sink: List[str] = []
        _walk_nested_text(spec, sink)
        unique: List[str] = []
        seen: Set[str] = set()
        for item in sink:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        if unique:
            body = "节点文字：\n" + "\n".join(f"- {t}" for t in unique)

    if not body or not body.strip():
        raise ValueError("no_text_extracted")

    return "\n".join(_header_lines(slug) + [body.strip()])
