"""Map persisted library specs (non-``nodes`` native shapes) to pseudo-nodes for Kitty hydrate.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.diagram.mindmap_location import is_leftover_mindmap_branch_id
from services.diagram.thinking_map_patterns import (
    BRACE_MAP_LEGACY_ID_DATA_KEY,
    BRACE_MAP_UID_DATA_KEY,
    BRIDGE_MAP_LEGACY_ID_DATA_KEY,
    BRIDGE_MAP_UID_DATA_KEY,
    BUBBLE_MAP_LEGACY_ID_DATA_KEY,
    BUBBLE_MAP_UID_DATA_KEY,
    CIRCLE_MAP_LEGACY_ID_DATA_KEY,
    CIRCLE_MAP_UID_DATA_KEY,
    DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY,
    DOUBLE_BUBBLE_ROLE_DATA_KEY,
    DOUBLE_BUBBLE_UID_DATA_KEY,
    MULTI_FLOW_EVENT_NODE_ID,
    MULTI_FLOW_LEGACY_ID_DATA_KEY,
    MULTI_FLOW_ROLE_DATA_KEY,
    MULTI_FLOW_UID_DATA_KEY,
    TREE_MAP_LEGACY_ID_DATA_KEY,
    TREE_MAP_UID_DATA_KEY,
    TREE_TOPIC_NODE_ID,
    is_leftover_thinking_map_id,
)
from services.diagram.thinking_map_stable_id import take_thinking_map_stable_id


def _is_flow_leftover(node_id: str | None) -> bool:
    """True for leftover flow-step / flow-substep slot ids."""
    return is_leftover_thinking_map_id("flow_map", node_id)


def _as_flow_text_items(val: Any) -> List[Dict[str, str]]:
    """Parse step/substep lists into ``{id?, text}`` rows."""
    if not isinstance(val, list):
        return []
    out: List[Dict[str, str]] = []
    for item in val:
        if isinstance(item, str):
            out.append({"text": item})
        elif isinstance(item, dict) and item.get("text") is not None:
            row: Dict[str, str] = {"text": str(item.get("text") or "")}
            raw_id = item.get("id")
            if isinstance(raw_id, str) and raw_id.strip():
                row["id"] = raw_id.strip()
            out.append(row)
    return out


def _resolve_flow_parent_step_id(
    entry: Dict[str, Any],
    step_ids: List[str],
    step_texts: List[str],
    used: set[int],
) -> Optional[str]:
    """Match a substep entry to a minted step id (id, then index, then unused text)."""
    raw_id = entry.get("stepId")
    if isinstance(raw_id, str) and raw_id in step_ids:
        used.add(step_ids.index(raw_id))
        return raw_id
    idx = entry.get("stepIndex")
    if isinstance(idx, int) and 0 <= idx < len(step_ids) and idx not in used:
        used.add(idx)
        return step_ids[idx]
    step_text = str(entry.get("step") or "")
    for i, text in enumerate(step_texts):
        if i not in used and text == step_text:
            used.add(i)
            return step_ids[i]
    return None


def _flow_map_pseudo_nodes(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Mint UUID step/substep nodes from a native flow-map spec."""
    nodes: List[Dict[str, Any]] = []
    title = str(spec.get("title") or "")
    claimed = {"flow-topic"}
    if title:
        nodes.append({"id": "flow-topic", "text": title, "type": "topic"})
    step_items = _as_flow_text_items(spec.get("steps"))
    step_ids: List[str] = []
    for idx, step in enumerate(step_items):
        leftover = step.get("id") or ""
        sid = take_thinking_map_stable_id(claimed, _is_flow_leftover, leftover or None)
        data: Dict[str, Any] = {"stepIndex": idx, "flowMapUid": sid}
        if leftover and _is_flow_leftover(leftover):
            data["flowMapLegacyId"] = leftover
        nodes.append({"id": sid, "text": step["text"], "type": "flow", "data": data})
        step_ids.append(sid)
    raw_substeps = spec.get("substeps")
    used_parents: set[int] = set()
    if not isinstance(raw_substeps, list):
        return nodes
    step_texts = [item["text"] for item in step_items]
    for entry in raw_substeps:
        if not isinstance(entry, dict):
            continue
        parent_id = _resolve_flow_parent_step_id(entry, step_ids, step_texts, used_parents)
        if not parent_id:
            continue
        parent_idx = step_ids.index(parent_id)
        for sj, sub in enumerate(_as_flow_text_items(entry.get("substeps"))):
            leftover = sub.get("id") or ""
            sub_id = take_thinking_map_stable_id(claimed, _is_flow_leftover, leftover or None)
            sub_data: Dict[str, Any] = {
                "stepIndex": parent_idx,
                "substepIndex": sj,
                "parentStepId": parent_id,
                "flowMapUid": sub_id,
            }
            if leftover and _is_flow_leftover(leftover):
                sub_data["flowMapLegacyId"] = leftover
            nodes.append(
                {
                    "id": sub_id,
                    "text": sub["text"],
                    "type": "flowSubstep",
                    "data": sub_data,
                }
            )
    return nodes


def _append_thinking_map_child(
    nodes: List[Dict[str, Any]],
    claimed: set[str],
    diagram_type: str,
    leftover: str,
    text: str,
    ntype: str,
    uid_key: str,
    legacy_key: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Mint a UUID child and stamp leftover + location."""
    sid = take_thinking_map_stable_id(
        claimed,
        lambda node_id: is_leftover_thinking_map_id(diagram_type, node_id),
        None,
    )
    data: Dict[str, Any] = {uid_key: sid, legacy_key: leftover}
    if extra:
        data.update(extra)
    nodes.append({"id": sid, "text": text, "type": ntype, "data": data})
    return sid


def _as_str_list(val: Any) -> List[str]:
    """As str list."""
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
        claimed = {"topic", "outer-boundary"}
        nodes.append({"id": "topic", "text": topic, "type": "center"})
        for i, ctx in enumerate(_as_str_list(spec.get("context"))):
            _append_thinking_map_child(
                nodes,
                claimed,
                dt,
                f"context-{i}",
                ctx,
                "bubble",
                CIRCLE_MAP_UID_DATA_KEY,
                CIRCLE_MAP_LEGACY_ID_DATA_KEY,
                {"groupIndex": i},
            )
        return nodes

    if dt == "bubble_map":
        topic = str(spec.get("topic") or "")
        claimed = {"topic"}
        nodes.append({"id": "topic", "text": topic, "type": "center"})
        for i, attr in enumerate(_as_str_list(spec.get("attributes"))):
            _append_thinking_map_child(
                nodes,
                claimed,
                dt,
                f"bubble-{i}",
                attr,
                "bubble",
                BUBBLE_MAP_UID_DATA_KEY,
                BUBBLE_MAP_LEGACY_ID_DATA_KEY,
                {"groupIndex": i},
            )
        return nodes

    if dt == "double_bubble_map":
        left = str(spec.get("left") or spec.get("leftTopic") or "")
        right = str(spec.get("right") or spec.get("rightTopic") or "")
        claimed = {"left-topic", "right-topic"}
        if left:
            nodes.append({"id": "left-topic", "text": left, "type": "topic"})
        if right:
            nodes.append({"id": "right-topic", "text": right, "type": "topic"})
        for i, t in enumerate(_as_str_list(spec.get("similarities") or spec.get("similarity"))):
            _append_thinking_map_child(
                nodes,
                claimed,
                dt,
                f"similarity-{i}",
                t,
                "similarity",
                DOUBLE_BUBBLE_UID_DATA_KEY,
                DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY,
                {"groupIndex": i, DOUBLE_BUBBLE_ROLE_DATA_KEY: "similarity"},
            )
        for i, t in enumerate(_as_str_list(spec.get("leftDifferences") or spec.get("left_differences"))):
            _append_thinking_map_child(
                nodes,
                claimed,
                dt,
                f"left-diff-{i}",
                t,
                "difference",
                DOUBLE_BUBBLE_UID_DATA_KEY,
                DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY,
                {"groupIndex": i, DOUBLE_BUBBLE_ROLE_DATA_KEY: "leftDiff"},
            )
        for i, t in enumerate(_as_str_list(spec.get("rightDifferences") or spec.get("right_differences"))):
            _append_thinking_map_child(
                nodes,
                claimed,
                dt,
                f"right-diff-{i}",
                t,
                "difference",
                DOUBLE_BUBBLE_UID_DATA_KEY,
                DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY,
                {"groupIndex": i, DOUBLE_BUBBLE_ROLE_DATA_KEY: "rightDiff"},
            )
        return nodes

    if dt in ("flow_map", "flow-map"):
        return _flow_map_pseudo_nodes(spec)

    if dt == "multi_flow_map":
        event = str(spec.get("event") or "")
        claimed = {MULTI_FLOW_EVENT_NODE_ID}
        if event:
            nodes.append({"id": MULTI_FLOW_EVENT_NODE_ID, "text": event, "type": "event"})
        for i, c in enumerate(_as_str_list(spec.get("causes"))):
            _append_thinking_map_child(
                nodes,
                claimed,
                dt,
                f"cause-{i}",
                c,
                "cause",
                MULTI_FLOW_UID_DATA_KEY,
                MULTI_FLOW_LEGACY_ID_DATA_KEY,
                {"groupIndex": i, MULTI_FLOW_ROLE_DATA_KEY: "cause"},
            )
        for i, e in enumerate(_as_str_list(spec.get("effects"))):
            _append_thinking_map_child(
                nodes,
                claimed,
                dt,
                f"effect-{i}",
                e,
                "effect",
                MULTI_FLOW_UID_DATA_KEY,
                MULTI_FLOW_LEGACY_ID_DATA_KEY,
                {"groupIndex": i, MULTI_FLOW_ROLE_DATA_KEY: "effect"},
            )
        return nodes

    if dt in ("tree_map", "tree-map"):
        main = str(spec.get("root") or spec.get("main") or spec.get("topic") or "")
        claimed = {TREE_TOPIC_NODE_ID, "dimension-label"}
        if main:
            nodes.append({"id": TREE_TOPIC_NODE_ID, "text": main, "type": "main"})
        cats = spec.get("children")
        if isinstance(cats, list):
            for ci, cat in enumerate(cats):
                if not isinstance(cat, dict):
                    continue
                ctext = str(cat.get("text") or cat.get("name") or "")
                cid = _append_thinking_map_child(
                    nodes,
                    claimed,
                    "tree_map",
                    f"tree-cat-{ci}",
                    ctext,
                    "category",
                    TREE_MAP_UID_DATA_KEY,
                    TREE_MAP_LEGACY_ID_DATA_KEY,
                    {"groupIndex": ci, "categoryIndex": ci, "nodeType": "branch"},
                )
                items = cat.get("items") or cat.get("children")
                if not isinstance(items, list):
                    continue
                for ii, it in enumerate(items):
                    itext = str(it) if isinstance(it, str) else str((it or {}).get("text") or "")
                    _append_thinking_map_child(
                        nodes,
                        claimed,
                        "tree_map",
                        f"tree-leaf-{ci}-{ii}",
                        itext,
                        "item",
                        TREE_MAP_UID_DATA_KEY,
                        TREE_MAP_LEGACY_ID_DATA_KEY,
                        {
                            "groupIndex": ci,
                            "categoryIndex": ci,
                            "leafIndex": ii,
                            "parentCategoryId": cid,
                            "nodeType": "leaf",
                        },
                    )
        return nodes

    if dt == "brace_map":
        whole = str(spec.get("whole") or "")
        claimed = {"brace-whole", "dimension-label"}
        if whole:
            nodes.append({"id": "brace-whole", "text": whole, "type": "whole"})
        parts = spec.get("parts")
        if isinstance(parts, list):
            for pi, part in enumerate(parts):
                if not isinstance(part, dict):
                    continue
                ptext = str(part.get("text") or "")
                pid = _append_thinking_map_child(
                    nodes,
                    claimed,
                    dt,
                    f"brace-part-{pi}",
                    ptext,
                    "part",
                    BRACE_MAP_UID_DATA_KEY,
                    BRACE_MAP_LEGACY_ID_DATA_KEY,
                    {"groupIndex": pi},
                )
                for spi, sp in enumerate(part.get("subparts") or []):
                    if not isinstance(sp, dict):
                        continue
                    _append_thinking_map_child(
                        nodes,
                        claimed,
                        dt,
                        f"brace-subpart-{pi}-{spi}",
                        str(sp.get("text") or ""),
                        "subpart",
                        BRACE_MAP_UID_DATA_KEY,
                        BRACE_MAP_LEGACY_ID_DATA_KEY,
                        {"groupIndex": pi, "parentPartId": pid},
                    )
        return nodes

    if dt == "bridge_map":
        rel = str(spec.get("relation") or "")
        claimed = {"dimension-label"}
        if rel:
            nodes.append({"id": "dimension-label", "text": rel, "type": "relation"})
        analogies = spec.get("analogies") or spec.get("pairs")
        if isinstance(analogies, list):
            for i, pair in enumerate(analogies):
                if not isinstance(pair, dict):
                    continue
                left = str(pair.get("left") or "")
                right = str(pair.get("right") or "")
                if left:
                    _append_thinking_map_child(
                        nodes,
                        claimed,
                        dt,
                        f"pair-{i}-left",
                        left,
                        "pair",
                        BRIDGE_MAP_UID_DATA_KEY,
                        BRIDGE_MAP_LEGACY_ID_DATA_KEY,
                        {"pairIndex": i, "position": "left"},
                    )
                if right:
                    _append_thinking_map_child(
                        nodes,
                        claimed,
                        dt,
                        f"pair-{i}-right",
                        right,
                        "pair",
                        BRIDGE_MAP_UID_DATA_KEY,
                        BRIDGE_MAP_LEGACY_ID_DATA_KEY,
                        {"pairIndex": i, "position": "right"},
                    )
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

        def walk_branches(branches: Any) -> None:
            if not isinstance(branches, list):
                return
            for br in branches:
                if not isinstance(br, dict):
                    continue
                label = str(br.get("text") or br.get("label") or "")
                raw_id = br.get("id")
                leftover = ""
                if isinstance(raw_id, str) and raw_id.strip():
                    leftover = raw_id.strip()
                if leftover and not is_leftover_mindmap_branch_id(leftover):
                    bid = leftover
                    leftover = ""
                else:
                    bid = str(uuid4())
                row: Dict[str, Any] = {"id": bid, "text": label, "type": "branch"}
                if leftover:
                    row["data"] = {"mindMapLegacyId": leftover}
                nodes.append(row)
                kids = br.get("children") or br.get("branches")
                walk_branches(kids)

        top_branches = spec.get("branches")
        if not isinstance(top_branches, list) or not top_branches:
            top_branches = spec.get("children")
        walk_branches(top_branches)
        return nodes

    return nodes
