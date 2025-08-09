"""
Tree Map Agent

Enhances basic tree map specs by:
- Normalizing and de-duplicating branch and leaf nodes
- Auto-generating stable ids when missing
- Enforcing practical limits for branches and leaves for readable diagrams
- Recommending canvas dimensions based on content density

The agent accepts a spec of the form:
  { "topic": str, "children": [ {"id": str, "label": str, "children": [{"id": str, "label": str}] } ] }

Returns { "success": bool, "spec": Dict } on success, or { "success": False, "error": str } on failure.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Set


class TreeMapAgent:
    """Utility agent to improve tree map specs before rendering."""

    MAX_BRANCHES: int = 10
    MAX_LEAVES_PER_BRANCH: int = 10

    def enhance_spec(self, spec: Dict) -> Dict:
        """
        Clean and enhance a tree map spec.

        Args:
            spec: { "topic": str, "children": [ {"id": str, "label": str, "children": [{"id": str, "label": str}] } ] }

        Returns:
            Dict with keys:
              - success: bool
              - spec: enhanced spec (maintains original required fields)
        """
        try:
            if not isinstance(spec, dict):
                return {"success": False, "error": "Spec must be a dictionary"}

            topic_raw = spec.get("topic", "")
            children_raw = spec.get("children", [])

            if not isinstance(topic_raw, str) or not isinstance(children_raw, list):
                return {"success": False, "error": "Invalid field types in spec"}

            def clean_text(value: str) -> str:
                return (value or "").strip()

            topic: str = clean_text(topic_raw)
            if not topic:
                return {"success": False, "error": "Missing or empty topic"}

            # Normalize branches and leaves
            normalized_children: List[Dict] = []
            seen_branch_labels: Set[str] = set()

            def ensure_node(node: Dict) -> Tuple[str, str]:
                # returns (id, label) after normalization
                label = clean_text(node.get("label", node.get("name", "")))
                node_id = clean_text(node.get("id", ""))
                return node_id, label

            def make_id_from(label: str, existing_ids: Set[str]) -> str:
                base = (
                    label.lower()
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

            used_ids: Set[str] = set()

            for child in children_raw:
                if not isinstance(child, dict):
                    continue
                cid, clabel = ensure_node(child)
                if not clabel or clabel in seen_branch_labels:
                    continue
                seen_branch_labels.add(clabel)

                # Normalize child id
                if not cid:
                    cid = make_id_from(clabel, used_ids)
                if cid in used_ids:
                    cid = make_id_from(f"{clabel}-b", used_ids)
                used_ids.add(cid)

                # Normalize leaves
                leaves_raw = child.get("children", [])
                normalized_leaves: List[Dict] = []
                seen_leaf_labels: Set[str] = set()
                if isinstance(leaves_raw, list):
                    for leaf in leaves_raw:
                        if not isinstance(leaf, dict):
                            continue
                        lid, llabel = ensure_node(leaf)
                        if not llabel or llabel in seen_leaf_labels:
                            continue
                        seen_leaf_labels.add(llabel)
                        if not lid:
                            lid = make_id_from(llabel, used_ids)
                        if lid in used_ids:
                            lid = make_id_from(f"{llabel}-l", used_ids)
                        used_ids.add(lid)
                        normalized_leaves.append({"id": lid, "label": llabel})
                        if len(normalized_leaves) >= self.MAX_LEAVES_PER_BRANCH:
                            break

                normalized_children.append({
                    "id": cid,
                    "label": clabel,
                    "children": normalized_leaves,
                })
                if len(normalized_children) >= self.MAX_BRANCHES:
                    break

            if not normalized_children:
                return {"success": False, "error": "At least one branch (child) is required"}

            # Heuristics for recommended dimensions
            font_root = 20
            font_branch = 16
            font_leaf = 14
            avg_char_px = 0.6
            padding = 40

            def text_radius(text: str, font_px: int, min_r: int) -> int:
                width_px = int(max(0, len(text)) * font_px * avg_char_px)
                height_px = int(font_px * 1.2)
                diameter = max(width_px, height_px) + int(font_px * 0.8)
                return max(min_r, diameter // 2)

            # Root radius
            root_r = text_radius(topic, font_root, 22)

            # Branch width estimation
            per_branch_widths: List[int] = []
            max_leaf_count = 0
            for b in normalized_children:
                br = text_radius(b["label"], font_branch, 16)
                per_branch_widths.append(br * 2 + 20)
                max_leaf_count = max(max_leaf_count, len(b.get("children", [])))

            # Canvas width grows with branches; height grows with leaves
            branch_spacing = 40
            branches_total_width = sum(per_branch_widths) + max(0, len(per_branch_widths) - 1) * branch_spacing
            base_width = max(branches_total_width + padding * 2, 700)

            # Height: root + gap + branches + gap + leaves grid
            branch_row_h = max(60, root_r + 60)
            leaves_block_h = 0
            if max_leaf_count > 0:
                leaf_row_h = 50
                leaves_block_h = 40 + leaf_row_h  # single row under each branch
            base_height = padding + root_r * 2 + 40 + branch_row_h + leaves_block_h + padding

            enhanced_spec: Dict = {
                "topic": topic,
                "children": normalized_children,
                "_agent": {
                    "type": "tree_map",
                    "branchCount": len(normalized_children),
                    "maxLeavesPerBranch": max_leaf_count,
                },
                "_recommended_dimensions": {
                    "baseWidth": base_width,
                    "baseHeight": base_height,
                    "padding": padding,
                    "width": base_width,
                    "height": base_height,
                },
            }

            return {"success": True, "spec": enhanced_spec}
        except Exception as exc:
            return {"success": False, "error": f"Unexpected error: {exc}"}


__all__ = ["TreeMapAgent"]


