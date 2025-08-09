"""
Multi-Flow Map Agent

This agent enhances the basic multi-flow map spec (event, causes, effects)
by cleaning data, de-duplicating entries, applying basic heuristics for
importance ordering, and recommending canvas dimensions based on content size.

Output remains a valid spec for existing D3 renderers, with optional
metadata under private keys (prefixed with "_") that renderers can ignore.
"""

from __future__ import annotations

from typing import Dict, List


class MultiFlowMapAgent:
    """Utility agent to improve multi-flow map specs before rendering."""

    MAX_ITEMS_PER_SIDE: int = 10

    def enhance_spec(self, spec: Dict) -> Dict:
        """
        Clean and enhance a multi-flow map spec.

        Args:
            spec: { "event": str, "causes": List[str], "effects": List[str] }

        Returns:
            Dict with keys:
              - success: bool
              - spec: enhanced spec (always valid against existing schema)
        """
        try:
            if not isinstance(spec, dict):
                return {"success": False, "error": "Spec must be a dictionary"}

            event_raw = spec.get("event", "")
            causes_raw = spec.get("causes", [])
            effects_raw = spec.get("effects", [])

            if not isinstance(event_raw, str) or not isinstance(causes_raw, list) or not isinstance(effects_raw, list):
                return {"success": False, "error": "Invalid field types in spec"}

            # Normalize text values
            def clean_text(value: str) -> str:
                return (value or "").strip()

            event: str = clean_text(event_raw)

            def normalize_list(items: List[str]) -> List[str]:
                seen = set()
                normalized: List[str] = []
                for item in items:
                    if not isinstance(item, str):
                        continue
                    cleaned = clean_text(item)
                    if not cleaned or cleaned in seen:
                        continue
                    seen.add(cleaned)
                    normalized.append(cleaned)
                # Clamp to maximum supported items
                return normalized[: self.MAX_ITEMS_PER_SIDE]

            causes: List[str] = normalize_list(causes_raw)
            effects: List[str] = normalize_list(effects_raw)

            if not event:
                return {"success": False, "error": "Missing or empty event"}
            if not causes:
                return {"success": False, "error": "At least one cause is required"}
            if not effects:
                return {"success": False, "error": "At least one effect is required"}

            # Basic importance heuristic (longer text may need larger radius)
            def score_importance(text: str) -> int:
                length = len(text)
                if length >= 30:
                    return 3
                if length >= 15:
                    return 2
                return 1

            cause_importance = [score_importance(c) for c in causes]
            effect_importance = [score_importance(e) for e in effects]

            # Recommend dimensions based on content density
            max_side = max(len(causes), len(effects))
            base_width = 900
            base_height = 500
            width = base_width + max(0, (max_side - 4)) * 80
            # Height grows with total items but is capped moderately
            total_items = len(causes) + len(effects)
            height = base_height + max(0, (total_items - 8)) * 50

            enhanced_spec: Dict = {
                "event": event,
                "causes": causes,
                "effects": effects,
                # Private metadata for optional renderer consumption
                "_agent": {
                    "type": "multi_flow_map",
                    "cause_importance": cause_importance,
                    "effect_importance": effect_importance,
                },
                "_recommended_dimensions": {
                    "baseWidth": width,
                    "baseHeight": height,
                    "padding": 40,
                    "width": width,
                    "height": height,
                },
            }

            return {"success": True, "spec": enhanced_spec}
        except Exception as exc:  # Defensive guard
            return {"success": False, "error": f"Unexpected error: {exc}"}


