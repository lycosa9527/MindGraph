"""Map persisted library specs (non-``nodes`` native shapes) to pseudo-nodes for Kitty hydrate."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _as_str_list(val: Any) -> List[str]:
    if not isinstance(val, list):
        return []
    out: List[str] = []
    for item in val:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and item.get("text") is not None:
            out.append(str(item.get("text") or ""))
    return out


def native_spec_to_pseudo_nodes(spec: Dict[str, Any], diagram_type: str) -> Optional[List[Dict[str, Any]]]:
    """
    Build minimal ``{id, text, type?}`` pseudo-nodes matching Vue loader inputs.

    Returns ``None`` when ``spec`` already has a non-empty ``nodes`` array (caller uses generic path).
    """
    if isinstance(spec.get("nodes"), list) and len(spec["nodes"]) > 0:
        return None

    dt = (diagram_type or "").replace("-", "_")
    nodes: List[Dict[str, Any]] = []

    if dt == "circle_map":
        topic = str(spec.get("topic") or "")
        nodes.append({"id": "topic", "text": topic, "type": "center"})
        for i, ctx in enumerate(_as_str_list(spec.get("context"))):
            nodes.append({"id": f"context-{i}", "text": ctx, "type": "bubble"})
        return nodes

    if dt == "bubble_map":
        topic = str(spec.get("topic") or "")
        nodes.append({"id": "topic", "text": topic, "type": "center"})
        for i, attr in enumerate(_as_str_list(spec.get("attributes"))):
            nodes.append({"id": f"bubble-{i}", "text": attr, "type": "bubble"})
        return nodes

    if dt == "double_bubble_map":
        left = str(spec.get("left") or spec.get("leftTopic") or "")
        right = str(spec.get("right") or spec.get("rightTopic") or "")
        if left:
            nodes.append({"id": "left-topic", "text": left, "type": "topic"})
        if right:
            nodes.append({"id": "right-topic", "text": right, "type": "topic"})
        for i, t in enumerate(_as_str_list(spec.get("similarities") or spec.get("similarity"))):
            nodes.append({"id": f"similarity-{i}", "text": t, "type": "similarity"})
        for i, t in enumerate(_as_str_list(spec.get("leftDifferences") or spec.get("left_differences"))):
            nodes.append({"id": f"left-diff-{i}", "text": t, "type": "difference"})
        for i, t in enumerate(_as_str_list(spec.get("rightDifferences") or spec.get("right_differences"))):
            nodes.append({"id": f"right-diff-{i}", "text": t, "type": "difference"})
        return nodes

    if dt in ("flow_map", "flow-map"):
        title = str(spec.get("title") or "")
        if title:
            nodes.append({"id": "flow-topic", "text": title, "type": "topic"})
        raw_steps = spec.get("steps")
        steps_list: List[Any] = raw_steps if isinstance(raw_steps, list) else []
        for idx, step in enumerate(steps_list):
            if isinstance(step, str):
                text = step
                sid = f"flow-step-{idx}"
            elif isinstance(step, dict):
                text = str(step.get("text") or "")
                sid = str(step.get("id") or f"flow-step-{idx}")
            else:
                continue
            nodes.append({"id": sid, "text": text, "type": "step"})
        substeps = spec.get("substeps")
        if isinstance(substeps, list):
            for si, entry in enumerate(substeps):
                if not isinstance(entry, dict):
                    continue
                parent_step = str(entry.get("step") or "")
                for sj, sub in enumerate(_as_str_list(entry.get("substeps"))):
                    nodes.append(
                        {
                            "id": f"flow-substep-{si}-{sj}",
                            "text": sub,
                            "type": "substep",
                            "data": {"parent_step": parent_step},
                        }
                    )
        return nodes

    if dt == "multi_flow_map":
        event = str(spec.get("event") or "")
        if event:
            nodes.append({"id": "multi-event", "text": event, "type": "event"})
        for i, c in enumerate(_as_str_list(spec.get("causes"))):
            nodes.append({"id": f"cause-{i}", "text": c, "type": "cause"})
        for i, e in enumerate(_as_str_list(spec.get("effects"))):
            nodes.append({"id": f"effect-{i}", "text": e, "type": "effect"})
        return nodes

    if dt in ("tree_map", "tree-map"):
        main = str(spec.get("root") or spec.get("main") or spec.get("topic") or "")
        if main:
            nodes.append({"id": "tree-main", "text": main, "type": "main"})
        cats = spec.get("children")
        if isinstance(cats, list):
            for ci, cat in enumerate(cats):
                if isinstance(cat, dict):
                    ctext = str(cat.get("text") or cat.get("name") or "")
                    cid = str(cat.get("id") or f"cat-{ci}")
                    nodes.append({"id": cid, "text": ctext, "type": "category"})
                    items = cat.get("items") or cat.get("children")
                    if isinstance(items, list):
                        for ii, it in enumerate(items):
                            itext = str(it) if isinstance(it, str) else str((it or {}).get("text") or "")
                            nodes.append(
                                {"id": f"{cid}-item-{ii}", "text": itext, "type": "item"},
                            )
        return nodes

    if dt == "brace_map":
        whole = str(spec.get("whole") or "")
        if whole:
            nodes.append({"id": "brace-whole", "text": whole, "type": "whole"})
        parts = spec.get("parts")
        if isinstance(parts, list):
            for pi, part in enumerate(parts):
                if isinstance(part, dict):
                    ptext = str(part.get("text") or "")
                    pid = str(part.get("id") or f"part-{pi}")
                    nodes.append({"id": pid, "text": ptext, "type": "part"})
                    for spi, sp in enumerate(part.get("subparts") or []):
                        if isinstance(sp, dict):
                            nodes.append(
                                {
                                    "id": f"{pid}-sp-{spi}",
                                    "text": str(sp.get("text") or ""),
                                    "type": "subpart",
                                },
                            )
        return nodes

    if dt == "bridge_map":
        rel = str(spec.get("relation") or "")
        if rel:
            nodes.append({"id": "bridge-rel", "text": rel, "type": "relation"})
        analogies = spec.get("analogies") or spec.get("pairs")
        if isinstance(analogies, list):
            for i, pair in enumerate(analogies):
                if isinstance(pair, dict):
                    left = str(pair.get("left") or "")
                    right = str(pair.get("right") or "")
                    if left:
                        nodes.append({"id": f"bridge-L-{i}", "text": left, "type": "pair"})
                    if right:
                        nodes.append({"id": f"bridge-R-{i}", "text": right, "type": "pair"})
        return nodes

    if dt == "concept_map":
        topic = str(spec.get("topic") or "")
        if topic:
            nodes.append({"id": "topic", "text": topic, "type": "concept"})
        concepts = spec.get("concepts")
        if isinstance(concepts, list):
            for i, c in enumerate(concepts):
                ct = str(c) if isinstance(c, str) else str((c or {}).get("text") or "")
                nodes.append({"id": f"concept-{i}", "text": ct, "type": "concept"})
        return nodes

    if dt in ("mindmap", "mind_map"):
        topic = str(spec.get("topic") or "")
        if topic:
            nodes.append({"id": "topic", "text": topic, "type": "topic"})

        def walk_branches(branches: Any, prefix: str) -> None:
            if not isinstance(branches, list):
                return
            for bi, br in enumerate(branches):
                if not isinstance(br, dict):
                    continue
                label = str(br.get("text") or br.get("label") or "")
                bid = f"{prefix}-b{bi}"
                nodes.append({"id": bid, "text": label, "type": "branch"})
                kids = br.get("children") or br.get("branches")
                walk_branches(kids, bid)

        walk_branches(spec.get("branches"), "mm")
        return nodes

    return nodes
