"""
Flow Map Agent

Enhances basic flow map specs by:
- Normalizing and de-duplicating major steps
- Validating and aligning sub-steps to their corresponding major steps
- Providing recommended canvas dimensions based on content density
- Preserving renderer compatibility (required fields unchanged)

The agent accepts specs that include optional "substeps" and augments the
spec with normalized sub-step metadata under private keys that renderers can
ignore safely.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


class FlowMapAgent:
    """Utility agent to improve flow map specs before rendering."""

    MAX_STEPS: int = 15
    MAX_SUBSTEPS_PER_STEP: int = 8

    def enhance_spec(self, spec: Dict) -> Dict:
        """
        Clean and enhance a flow map spec.

        Expected base spec:
            { "title": str, "steps": List[str], "substeps": Optional[List[{step, substeps[]}]] }

        Returns:
            Dict with keys:
              - success: bool
              - spec: enhanced spec (maintains original required fields)
        """
        try:
            if not isinstance(spec, dict):
                return {"success": False, "error": "Spec must be a dictionary"}

            title_raw = spec.get("title", "")
            steps_raw = spec.get("steps", [])
            substeps_raw = (
                spec.get("substeps")
                or spec.get("sub_steps")
                or spec.get("subSteps")
                or []
            )

            if not isinstance(title_raw, str) or not isinstance(steps_raw, list):
                return {"success": False, "error": "Invalid field types in spec"}

            # Normalize strings
            def clean_text(value: str) -> str:
                return (value or "").strip()

            title: str = clean_text(title_raw)

            # Normalize steps: de-duplicate, preserve order, clamp
            seen = set()
            normalized_steps: List[str] = []
            for item in steps_raw:
                if not isinstance(item, str):
                    continue
                cleaned = clean_text(item)
                if not cleaned or cleaned in seen:
                    continue
                seen.add(cleaned)
                normalized_steps.append(cleaned)
                if len(normalized_steps) >= self.MAX_STEPS:
                    break

            if not title:
                return {"success": False, "error": "Missing or empty title"}
            if not normalized_steps:
                return {"success": False, "error": "At least one step is required"}

            # Normalize substeps mappings
            step_to_substeps: Dict[str, List[str]] = {s: [] for s in normalized_steps}

            def add_substeps_for(step_name: str, sub_list: List[str]) -> None:
                if step_name not in step_to_substeps:
                    return
                existing = step_to_substeps[step_name]
                for sub in sub_list or []:
                    if not isinstance(sub, str):
                        continue
                    cleaned = clean_text(sub)
                    if not cleaned or cleaned in existing:
                        continue
                    existing.append(cleaned)
                    if len(existing) >= self.MAX_SUBSTEPS_PER_STEP:
                        break

            if isinstance(substeps_raw, list):
                for entry in substeps_raw:
                    if not isinstance(entry, dict):
                        continue
                    step_name = clean_text(entry.get("step", ""))
                    sub_list = entry.get("substeps") or entry.get("sub_steps") or entry.get("subSteps") or []
                    if not isinstance(sub_list, list):
                        continue
                    add_substeps_for(step_name, sub_list)

            # Heuristics for recommended dimensions
            # 1) Determine all MAJOR steps first (normalized_steps)
            # 2) Estimate text-based sizes for each step and title
            font_step = 14
            font_title = 18
            avg_char_px = 0.6  # Approx pixels per char relative to font size
            hpad_step = 14
            vpad_step = 10
            hpad_title = 12
            vpad_title = 8
            step_spacing = 80  # Vertical spacing between steps
            padding = 40

            def estimate_text_size(text: str, font_px: int) -> Tuple[int, int]:
                width_px = int(max(0, len(text)) * font_px * avg_char_px)
                height_px = int(font_px * 1.2)
                return max(1, width_px), max(1, height_px)

            # Title size
            t_w_raw, t_h_raw = estimate_text_size(title, font_title)
            title_w = t_w_raw + hpad_title * 2
            title_h = t_h_raw + vpad_title * 2

            # Step sizes and aggregate metrics
            step_sizes: List[Tuple[int, int]] = []
            max_step_w = 0
            total_steps_h = 0
            for s in normalized_steps:
                s_w_raw, s_h_raw = estimate_text_size(s, font_step)
                w = s_w_raw + hpad_step * 2
                h = s_h_raw + vpad_step * 2
                step_sizes.append((w, h))
                max_step_w = max(max_step_w, w)
                total_steps_h += h

            total_vertical_spacing = max(0, len(normalized_steps) - 1) * step_spacing

            # Compute required canvas strictly from content
            width = max(title_w, max_step_w) + padding * 2
            height = padding + title_h + 30 + total_steps_h + total_vertical_spacing + padding

            enhanced_spec: Dict = {
                "title": title,
                "steps": normalized_steps,
                # Keep normalized substeps in a consistent public key for downstream use
                "substeps": [
                    {"step": step, "substeps": step_to_substeps.get(step, [])}
                    for step in normalized_steps
                    if step_to_substeps.get(step)
                ],
                "_agent": {
                    "type": "flow_map",
                    "layout": "vertical",
                    "hasSubsteps": any(step_to_substeps.values()),
                    "substepCounts": {k: len(v) for k, v in step_to_substeps.items()},
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
        except Exception as exc:
            return {"success": False, "error": f"Unexpected error: {exc}"}


