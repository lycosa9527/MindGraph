"""
Tree map enhancement helpers.

Extracted from tree_map_agent to reduce complexity and improve maintainability.
"""
from typing import Dict, List, Set, Tuple

from utils.text_width_estimate import estimate_text_width_px


def clean_text(value: str) -> str:
    """Strip and normalize text."""
    return (value or "").strip()


def ensure_node(node: Dict) -> Tuple[str, str]:
    """Extract (id, text) from node, accepting text/label/name formats."""
    label_or_name = node.get("label", node.get("name", ""))
    text = clean_text(node.get("text", label_or_name))
    node_id = clean_text(node.get("id", ""))
    return node_id, text


def make_id_from(text: str, existing_ids: Set[str]) -> str:
    """Generate unique id from text."""
    base = (
        text.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("\\", "-")
    ) or "node"
    candidate = base
    counter = 1
    while candidate in existing_ids:
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


def _normalize_leaves(
    leaves_raw: List,
    used_ids: Set[str],
    max_leaves: int,
) -> List[Dict]:
    """Normalize leaf nodes for a single branch."""
    normalized: List[Dict] = []
    seen: Set[str] = set()
    for leaf in leaves_raw if isinstance(leaves_raw, list) else []:
        if not isinstance(leaf, dict):
            continue
        lid, ltext = ensure_node(leaf)
        if not ltext or ltext in seen:
            continue
        seen.add(ltext)
        if not lid:
            lid = make_id_from(ltext, used_ids)
        if lid in used_ids:
            lid = make_id_from(f"{ltext}-l", used_ids)
        used_ids.add(lid)
        normalized.append({"id": lid, "text": ltext})
        if len(normalized) >= max_leaves:
            break
    return normalized


def normalize_children(
    children_raw: List,
    max_branches: int,
    max_leaves_per_branch: int,
) -> Tuple[List[Dict], str]:
    """
    Normalize and de-duplicate branch and leaf nodes.

    Returns:
        (normalized_children, error_message)
        error_message is non-empty on failure.
    """
    result: List[Dict] = []
    seen_branch_labels: Set[str] = set()
    used_ids: Set[str] = set()

    for child in children_raw:
        if not isinstance(child, dict):
            continue
        cid, ctext = ensure_node(child)
        if not ctext or ctext in seen_branch_labels:
            continue
        seen_branch_labels.add(ctext)

        if not cid:
            cid = make_id_from(ctext, used_ids)
        if cid in used_ids:
            cid = make_id_from(f"{ctext}-b", used_ids)
        used_ids.add(cid)

        leaves_raw = child.get("children", [])
        normalized_leaves = _normalize_leaves(
            leaves_raw, used_ids, max_leaves_per_branch
        )

        result.append({"id": cid, "text": ctext, "children": normalized_leaves})
        if len(result) >= max_branches:
            break

    if not result:
        return [], "At least one branch (child) is required"
    return result, ""


def _text_radius(text: str, font_px: int, min_r: int) -> int:
    """Compute radius for text at given font size."""
    width_px = int(estimate_text_width_px(text, float(font_px), is_topic=False))
    height_px = int(font_px * 1.2)
    diameter = max(width_px, height_px) + int(font_px * 0.8)
    return max(min_r, diameter // 2)


def compute_recommended_dimensions(
    topic: str,
    normalized_children: List[Dict],
) -> Dict:
    """Compute recommended canvas dimensions from content."""
    padding = 40
    root_r = _text_radius(topic, 20, 22)
    branch_widths = [
        _text_radius(b["text"], 16, 16) * 2 + 20
        for b in normalized_children
    ]
    leaf_counts = [len(b.get("children", [])) for b in normalized_children]
    max_leaf_count = max(leaf_counts) if leaf_counts else 0

    total_width = (
        sum(branch_widths)
        + max(0, len(branch_widths) - 1) * 40
    )
    base_width = max(total_width + padding * 2, 700)
    branch_row_h = max(60, root_r + 60)
    leaves_block_h = 90 if max_leaf_count > 0 else 0
    base_height = padding + root_r * 2 + 40 + branch_row_h + leaves_block_h + padding

    return {
        "baseWidth": base_width,
        "baseHeight": base_height,
        "padding": padding,
        "width": base_width,
        "height": base_height,
    }
