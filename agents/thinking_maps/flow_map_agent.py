"""
Flow map agent module.

Enhances basic flow map specs by:
- Normalizing and de-duplicating major steps
- Validating and aligning sub-steps to their corresponding major steps
- Providing recommended canvas dimensions based on content density
- Preserving renderer compatibility (required fields unchanged)

The agent accepts specs that include optional "substeps" and augments the
spec with normalized sub-step metadata under private keys that renderers can
ignore safely.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from agents.core.agent_result import agent_validation_failure
from agents.core.agent_utils import extract_json_from_response
from agents.core.fixed_structure import (
    append_fixed_labels_user_note,
    extract_part_names,
    fixed_labels_from_nodes,
    validate_fixed_labels,
)
from agents.core.llm_spec_stream import dispatch_llm_chat
from agents.core.base_agent import BaseAgent
from config.settings import config
from prompts import get_prompt
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.prompt_locale import is_chinese_prompt_shell_language
from utils.text_width_estimate import estimate_text_width_px

logger = logging.getLogger(__name__)


def _spec_has_substeps(spec: Dict[str, Any]) -> bool:
    """True when spec contains at least one non-empty substep list."""
    substeps_raw = spec.get("substeps") or spec.get("sub_steps") or spec.get("subSteps") or []
    if not isinstance(substeps_raw, list):
        return False
    for entry in substeps_raw:
        if not isinstance(entry, dict):
            continue
        sub_list = entry.get("substeps") or entry.get("sub_steps") or entry.get("subSteps") or []
        if isinstance(sub_list, list) and any(str(s).strip() for s in sub_list):
            return True
    return False


class FlowMapAgent(BaseAgent):
    """Utility agent to improve flow map specs before rendering."""

    def __init__(self, model="qwen"):
        """init  ."""
        super().__init__(model=model)
        self.diagram_type = "flow_map"

    async def generate_graph(
        self,
        user_prompt: str,
        language: str = "en",
        dimension_preference: str | None = None,
        fixed_dimension: str | None = None,
        dimension_only_mode: bool | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate a flow map from a prompt."""
        token_kwargs = {
            "user_id": kwargs.get("user_id"),
            "organization_id": kwargs.get("organization_id"),
            "request_type": kwargs.get("request_type", "diagram_generation"),
            "endpoint_path": kwargs.get("endpoint_path"),
            "phase_emit": kwargs.get("phase_emit"),
        }
        structure_mode = kwargs.get("structure_mode", "free")
        fixed_nodes = kwargs.get("fixed_nodes") or {}
        fixed_step_labels = fixed_labels_from_nodes(fixed_nodes, "steps") if structure_mode == "fixed" else None
        try:
            spec = await self._generate_flow_map_spec(
                user_prompt,
                language,
                structure_mode=structure_mode,
                fixed_nodes=fixed_nodes,
                user_id=token_kwargs["user_id"],
                organization_id=token_kwargs["organization_id"],
                request_type=token_kwargs["request_type"],
                endpoint_path=token_kwargs["endpoint_path"],
                phase_emit=token_kwargs["phase_emit"],
            )
            if not spec:
                return {
                    "success": False,
                    "error": "Failed to generate flow map specification",
                }

            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(
                spec,
                fixed_step_labels=fixed_step_labels,
            )
            if not is_valid:
                logger.warning("FlowMapAgent: Validation failed: %s", validation_msg)
                return agent_validation_failure(f"Generated invalid specification: {validation_msg}")

            # Enhance the spec with layout and dimensions
            enhanced_result = await self.enhance_spec(spec)
            if not enhanced_result.get("success"):
                return {
                    "success": False,
                    "error": enhanced_result.get("error", "Enhancement failed"),
                }
            enhanced_spec = enhanced_result["spec"]

            logger.info("FlowMapAgent: Flow map generation completed successfully")
            return {
                "success": True,
                "spec": enhanced_spec,
                "diagram_type": self.diagram_type,
            }

        except LLM_PIPELINE_ERRORS as e:
            logger.error("FlowMapAgent: Flow map generation failed: %s", e)
            return {"success": False, "error": f"Generation failed: {e}"}

    async def _generate_flow_map_spec(
        self,
        prompt: str,
        language: str,
        structure_mode: str = "free",
        fixed_nodes: Optional[Dict[str, Any]] = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = "diagram_generation",
        endpoint_path: Optional[str] = None,
        phase_emit=None,
    ) -> Optional[Dict]:
        """Generate the flow map specification using LLM."""
        fixed_nodes = fixed_nodes or {}
        fixed_steps = structure_mode == "fixed" and fixed_labels_from_nodes(fixed_nodes, "steps")
        try:
            prompt_type = "fixed_steps" if fixed_steps else "generation"
            system_prompt = get_prompt("flow_map_agent", language, prompt_type)

            if not system_prompt:
                logger.error("FlowMapAgent: No prompt found for language %s type %s", language, prompt_type)
                return None
            system_prompt = system_prompt.format(topic=prompt)

            base_user = (
                f"请为以下描述创建一个流程图：{prompt}"
                if is_chinese_prompt_shell_language(language)
                else f"Please create a flow map for the following description: {prompt}"
            )
            if fixed_steps:
                logger.debug(
                    "FlowMapAgent: Using FIXED steps mode with %s labels",
                    len(fixed_steps),
                )
                user_prompt = append_fixed_labels_user_note(
                    base_user,
                    language,
                    zh_intro="用户指定的步骤（必须原样按顺序使用）：",
                    en_intro="User-specified steps (use EXACT labels in order): ",
                    labels=fixed_steps,
                )
            else:
                user_prompt = base_user

            # Call middleware directly - clean and efficient!
            response = await dispatch_llm_chat(
                phase_emit=phase_emit,
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type="flow_map",
            )

            if not response:
                logger.error("FlowMapAgent: No response from LLM")
                return None

            spec = await self._extract_spec_from_response(
                response=response,
                user_prompt=user_prompt,
                language=language,
                system_prompt=system_prompt,
                phase_emit=phase_emit,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
            )
            if spec is None:
                return None

            if fixed_steps and not _spec_has_substeps(spec):
                logger.warning(
                    "FlowMapAgent: Fixed steps mode returned no substeps; retrying with explicit substep requirement."
                )
                retry_suffix = (
                    "\n\n重要：必须为每个指定步骤生成 2-4 个子步骤。"
                    "返回包含 substeps 数组的完整 JSON，substeps[].step 与 steps[] 完全一致。"
                    if is_chinese_prompt_shell_language(language)
                    else (
                        "\n\nIMPORTANT: Generate 2-4 substeps for EACH specified step. "
                        "Return complete JSON with a substeps array; substeps[].step must match steps[] exactly."
                    )
                )
                retry_response = await dispatch_llm_chat(
                    phase_emit=phase_emit,
                    prompt=user_prompt + retry_suffix,
                    model=self.model,
                    system_message=system_prompt,
                    max_tokens=1000,
                    temperature=config.LLM_TEMPERATURE,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path,
                    diagram_type="flow_map",
                )
                if retry_response:
                    retry_spec = await self._extract_spec_from_response(
                        response=retry_response,
                        user_prompt=user_prompt + retry_suffix,
                        language=language,
                        system_prompt=system_prompt,
                        phase_emit=phase_emit,
                        user_id=user_id,
                        organization_id=organization_id,
                        request_type=request_type,
                        endpoint_path=endpoint_path,
                    )
                    if retry_spec is not None:
                        spec = retry_spec

            return spec

        except LLM_PIPELINE_ERRORS as e:
            logger.error("FlowMapAgent: Error in spec generation: %s", e)
            return None

    async def _extract_spec_from_response(
        self,
        response: Any,
        user_prompt: str,
        language: str,
        system_prompt: str,
        phase_emit,
        user_id: Optional[int],
        organization_id: Optional[int],
        request_type: str,
        endpoint_path: Optional[str],
    ) -> Optional[Dict]:
        """Extract JSON spec from LLM response; retry once on non-JSON ask-for-info replies."""
        if isinstance(response, dict):
            return response

        response_str = str(response)
        spec = extract_json_from_response(response_str)

        if isinstance(spec, dict) and spec.get("_error") == "non_json_response":
            logger.warning(
                "FlowMapAgent: LLM returned non-JSON response asking for more info. "
                "Retrying with explicit JSON-only prompt."
            )

            retry_user_prompt = (
                f"{user_prompt}\n\n"
                f"重要：你必须只返回有效的JSON格式，不要询问更多信息。"
                f"如果提示不清楚，请根据提示内容做出合理假设并直接生成JSON规范。"
                if is_chinese_prompt_shell_language(language)
                else (
                    f"{user_prompt}\n\n"
                    f"IMPORTANT: You MUST respond with valid JSON only. "
                    f"Do not ask for more information. "
                    f"If the prompt is unclear, make reasonable assumptions "
                    f"and generate the JSON specification directly."
                )
            )

            retry_response = await dispatch_llm_chat(
                phase_emit=phase_emit,
                prompt=retry_user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type="flow_map",
            )

            if isinstance(retry_response, dict):
                return retry_response

            retry_spec = extract_json_from_response(str(retry_response))
            if isinstance(retry_spec, dict) and retry_spec.get("_error") == "non_json_response":
                logger.error(
                    "FlowMapAgent: Retry also returned non-JSON response. Giving up after 1 retry attempt."
                )
                return None

            if not retry_spec or (isinstance(retry_spec, dict) and retry_spec.get("_error")):
                return None
            return retry_spec

        if not spec or (isinstance(spec, dict) and spec.get("_error")):
            response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
            logger.error(
                "FlowMapAgent: Failed to extract JSON from LLM response. Response preview: %s",
                response_preview,
            )
            return None

        return spec

    def validate_output(
        self,
        output: Dict[str, Any],
        fixed_step_labels: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Validate a flow map specification."""
        try:
            if not isinstance(output, dict):
                return False, "Spec must be a dictionary"

            # Accept both 'title' and 'topic' fields for flexibility
            title = output.get("title") or output.get("topic")
            steps = output.get("steps")

            if not title or not isinstance(title, str):
                return False, "Missing or invalid title/topic"
            if not steps or not isinstance(steps, list):
                return False, "Missing or invalid steps"

            if fixed_step_labels:
                expected = [str(label).strip() for label in fixed_step_labels if str(label).strip()]
                actual = extract_part_names(steps)
                ok, msg = validate_fixed_labels(actual, expected, "steps")
                if not ok:
                    return False, msg

            return True, "Valid flow map specification"
        except LLM_PIPELINE_ERRORS as e:
            return False, f"Validation error: {str(e)}"

    MAX_STEPS: int = 15
    MAX_SUBSTEPS_PER_STEP: int = 8

    async def enhance_spec(self, spec: Dict) -> Dict:
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

            title_raw = spec.get("title", "") or spec.get("topic", "")
            steps_raw = spec.get("steps", [])
            substeps_raw = spec.get("substeps") or spec.get("sub_steps") or spec.get("subSteps") or []

            if not isinstance(title_raw, str) or not isinstance(steps_raw, list):
                return {"success": False, "error": "Invalid field types in spec"}

            # Normalize strings
            def clean_text(value: str) -> str:
                return (value or "").strip()

            title: str = clean_text(title_raw)

            # Normalize steps: de-duplicate, preserve order, clamp
            seen = set()
            normalized_steps: List[str] = []
            logger.debug("FlowMapAgent: Raw steps from LLM: %s", steps_raw)
            for item in steps_raw:
                # Handle both string and object formats
                if isinstance(item, str):
                    step_text = item
                elif isinstance(item, dict) and "label" in item:
                    step_text = item["label"]
                else:
                    logger.warning("FlowMapAgent: Skipping invalid step item: %s", item)
                    continue

                cleaned = clean_text(step_text)
                if not cleaned or cleaned in seen:
                    logger.warning(
                        "FlowMapAgent: Skipping empty or duplicate step: '%s'",
                        step_text,
                    )
                    continue
                seen.add(cleaned)
                normalized_steps.append(cleaned)
                logger.debug("FlowMapAgent: Added normalized step: '%s'", cleaned)
                if len(normalized_steps) >= self.MAX_STEPS:
                    break

            logger.debug("FlowMapAgent: Final normalized steps: %s", normalized_steps)

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
                logger.debug("FlowMapAgent: Processing %s substeps entries", len(substeps_raw))
                for entry in substeps_raw:
                    if not isinstance(entry, dict):
                        continue
                    step_name = clean_text(entry.get("step", ""))
                    sub_list = entry.get("substeps") or entry.get("sub_steps") or entry.get("subSteps") or []
                    if not isinstance(sub_list, list):
                        continue
                    logger.debug(
                        "FlowMapAgent: Matching substeps for step '%s': %s",
                        step_name,
                        sub_list,
                    )
                    if step_name not in step_to_substeps:
                        step_keys = list(step_to_substeps.keys())
                        logger.warning(
                            "FlowMapAgent: Step '%s' not found in normalized steps %s",
                            step_name,
                            step_keys,
                        )
                    add_substeps_for(step_name, sub_list)

            # Heuristics for recommended dimensions
            # 1) Determine all MAJOR steps first (normalized_steps)
            # 2) Estimate text-based sizes for each step and title
            font_step = 14
            font_title = 18
            hpad_step = 14
            vpad_step = 10
            hpad_title = 12
            vpad_title = 8
            padding = 40

            def estimate_text_size(text: str, font_px: int) -> Tuple[int, int]:
                width_px = int(estimate_text_width_px(text, float(font_px), is_topic=False))
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

            # Calculate adaptive spacing for each step based on substeps
            total_vertical_spacing = 0
            if len(normalized_steps) > 1:
                for i in range(len(normalized_steps) - 1):
                    current_step = normalized_steps[i]
                    next_step = normalized_steps[i + 1]

                    # Estimate substep heights
                    current_substeps = step_to_substeps.get(current_step, [])
                    next_substeps = step_to_substeps.get(next_step, [])

                    # Each substep needs height + spacing (30 = sub spacing)
                    sub_height_per = font_step * 1.2 + vpad_step * 2 + 30
                    current_sub_height = len(current_substeps) * sub_height_per
                    next_sub_height = len(next_substeps) * sub_height_per

                    # More efficient spacing calculation (matching D3.js)
                    max_sub_height = max(current_sub_height, next_sub_height)
                    min_base_spacing = 45  # Matches D3.js minBaseSpacing
                    adaptive_spacing = (
                        max(min_base_spacing, max_sub_height * 0.4 + 20) if max_sub_height > 0 else min_base_spacing
                    )

                    total_vertical_spacing += adaptive_spacing

            # Estimate substep space requirements
            max_substep_w = 0
            has_substeps = False
            for step in normalized_steps:
                substeps = step_to_substeps.get(step, [])
                if substeps:
                    has_substeps = True
                    for substep in substeps:
                        s_w_raw, _ = estimate_text_size(substep, font_step)
                        substep_w = s_w_raw + hpad_step * 2
                        max_substep_w = max(max_substep_w, substep_w)

            # Compute required canvas width accounting for substeps
            base_content_width = max(title_w, max_step_w)
            extra_padding = 20  # Additional safety margin for text rendering (matches D3.js)
            if has_substeps:
                # Add space for substeps: gap + substep width
                substep_gap = 40  # Gap between step and substeps
                width = base_content_width + substep_gap + max_substep_w + padding * 2 + extra_padding
            else:
                width = base_content_width + padding * 2 + extra_padding

            # Ensure minimum readable width (reduced for better content fit)
            min_width = 250  # Reduced minimum for better content-to-canvas ratio
            width = max(width, min_width)

            # Height calculation remains the same
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
                    "layout": "horizontal",
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
        except LLM_PIPELINE_ERRORS as exc:
            return {"success": False, "error": f"Unexpected error: {exc}"}
