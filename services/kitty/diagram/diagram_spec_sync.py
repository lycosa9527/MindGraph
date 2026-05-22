"""Keep diagram_data children[] aligned with type-specific spec fields for desktop sync."""

from __future__ import annotations

from typing import Any, Dict, List


def _child_texts(children: Any) -> List[str]:
    if not isinstance(children, list):
        return []
    texts: List[str] = []
    for node in children:
        if isinstance(node, dict):
            raw = node.get("text") or node.get("label") or ""
            texts.append(str(raw).strip())
        elif isinstance(node, str):
            texts.append(node.strip())
        else:
            texts.append(str(node).strip())
    return texts


def _center_text(diagram_data: Dict[str, Any]) -> str:
    center = diagram_data.get("center")
    if isinstance(center, dict):
        raw = center.get("text")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    topic = diagram_data.get("topic")
    if isinstance(topic, str) and topic.strip():
        return topic.strip()
    title = diagram_data.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return ""


def sync_diagram_data_to_spec_shape(diagram_type: str, diagram_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    After voice mutations, mirror ``children[]`` into spec fields consumed by ``loadFromSpec``.

    Mutates and returns ``diagram_data``.
    """
    if not isinstance(diagram_data, dict):
        return {}

    children = diagram_data.get("children")
    texts = _child_texts(children)
    center = _center_text(diagram_data)

    if diagram_type == "circle_map":
        diagram_data["topic"] = center
        if not isinstance(diagram_data.get("center"), dict):
            diagram_data["center"] = {"text": center}
        else:
            diagram_data["center"]["text"] = center
        diagram_data["context"] = texts

    elif diagram_type == "bubble_map":
        diagram_data["topic"] = center
        if not isinstance(diagram_data.get("center"), dict):
            diagram_data["center"] = {"text": center}
        else:
            diagram_data["center"]["text"] = center
        diagram_data["attributes"] = [{"text": t} for t in texts if t]

    elif diagram_type == "flow_map":
        title = center or str(diagram_data.get("title") or "")
        diagram_data["title"] = title

    elif diagram_type == "multi_flow_map":
        event = center or str(diagram_data.get("event") or "")
        diagram_data["event"] = event

    elif diagram_type == "double_bubble_map":
        left = diagram_data.get("left")
        right = diagram_data.get("right")
        if isinstance(left, str):
            diagram_data["left"] = left.strip()
        if isinstance(right, str):
            diagram_data["right"] = right.strip()

    elif diagram_type == "mindmap":
        diagram_data["topic"] = center
        if not isinstance(diagram_data.get("center"), dict):
            diagram_data["center"] = {"text": center}
        else:
            diagram_data["center"]["text"] = center

    elif diagram_type == "tree_map":
        diagram_data["topic"] = center
        if not isinstance(diagram_data.get("center"), dict):
            diagram_data["center"] = {"text": center}
        else:
            diagram_data["center"]["text"] = center

    elif diagram_type == "bridge_map":
        analogies: List[Dict[str, str]] = []
        if isinstance(children, list):
            for node in children:
                if not isinstance(node, dict):
                    continue
                left_val = str(node.get("left") or node.get("text") or "").strip()
                right_val = str(node.get("right") or "").strip()
                if left_val and right_val:
                    analogies.append({"left": left_val, "right": right_val})
        if analogies:
            diagram_data["analogies"] = analogies

    elif diagram_type == "brace_map":
        whole = center or str(diagram_data.get("whole") or "")
        diagram_data["whole"] = whole

    elif diagram_type == "concept_map":
        diagram_data["topic"] = center
        if not isinstance(diagram_data.get("center"), dict):
            diagram_data["center"] = {"text": center}
        else:
            diagram_data["center"]["text"] = center

    diagram_data["diagram_type"] = diagram_type
    return diagram_data
