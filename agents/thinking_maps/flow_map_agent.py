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

import logging
from typing import Dict, List, Tuple, Any, Optional
from ..core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class FlowMapAgent(BaseAgent):
    """Utility agent to improve flow map specs before rendering."""
    
    def __init__(self, model='qwen'):
        super().__init__(model=model)
        self.diagram_type = "flow_map"
    
    async def generate_graph(
        self, 
        prompt: str, 
        language: str = "en",
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a flow map from a prompt."""
        try:
            # Generate the initial flow map specification
            spec = await self._generate_flow_map_spec(
                prompt, 
                language,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate flow map specification'
                }
            
            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning(f"FlowMapAgent: Validation failed: {validation_msg}")
                return {
                    'success': False,
                    'error': f'Generated invalid specification: {validation_msg}'
                }
            
            # Enhance the spec with layout and dimensions
            enhanced_result = await self.enhance_spec(spec)
            if not enhanced_result.get('success'):
                return {
                    'success': False,
                    'error': enhanced_result.get('error', 'Enhancement failed')
                }
            enhanced_spec = enhanced_result['spec']
            
            logger.info(f"FlowMapAgent: Flow map generation completed successfully")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"FlowMapAgent: Flow map generation failed: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    async def _generate_flow_map_spec(
        self, 
        prompt: str, 
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Optional[Dict]:
        """Generate the flow map specification using LLM."""
        try:
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Get prompt from centralized system - use agent-specific format
            system_prompt = get_prompt("flow_map_agent", language, "generation")
            
            if not system_prompt:
                logger.error(f"FlowMapAgent: No prompt found for language {language}")
                return None
                
            user_prompt = f"请为以下描述创建一个流程图：{prompt}" if language == "zh" else f"Please create a flow map for the following description: {prompt}"
            
            # Call middleware directly - clean and efficient!
            from services.llm_service import llm_service
            from config.settings import config
            
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='flow_map'
            )
            
            if not response:
                logger.error("FlowMapAgent: No response from LLM")
                return None
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response
                response_str = str(response)
                spec = extract_json_from_response(response_str)
                
                if not spec:
                    # Log the actual response for debugging
                    response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                    logger.error(f"FlowMapAgent: Failed to extract JSON from LLM response. Response preview: {response_preview}")
                    return None
            
            return spec
            
        except Exception as e:
            logger.error(f"FlowMapAgent: Error in spec generation: {e}")
            return None
    
    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """Validate a flow map specification."""
        try:
            if not isinstance(spec, dict):
                return False, "Spec must as a dictionary"
            
            # Accept both 'title' and 'topic' fields for flexibility
            title = spec.get("title") or spec.get("topic")
            steps = spec.get("steps")
            
            if not title or not isinstance(title, str):
                return False, "Missing or invalid title/topic"
            if not steps or not isinstance(steps, list):
                return False, "Missing or invalid steps"
            
            return True, "Valid flow map specification"
        except Exception as e:
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
            logger.debug(f"FlowMapAgent: Raw steps from LLM: {steps_raw}")
            for item in steps_raw:
                # Handle both string and object formats
                if isinstance(item, str):
                    step_text = item
                elif isinstance(item, dict) and 'label' in item:
                    step_text = item['label']
                else:
                    logger.warning(f"FlowMapAgent: Skipping invalid step item: {item}")
                    continue
                
                cleaned = clean_text(step_text)
                if not cleaned or cleaned in seen:
                    logger.warning(f"FlowMapAgent: Skipping empty or duplicate step: '{step_text}'")
                    continue
                seen.add(cleaned)
                normalized_steps.append(cleaned)
                logger.debug(f"FlowMapAgent: Added normalized step: '{cleaned}'")
                if len(normalized_steps) >= self.MAX_STEPS:
                    break
            
            logger.debug(f"FlowMapAgent: Final normalized steps: {normalized_steps}")

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
                logger.debug(f"FlowMapAgent: Processing {len(substeps_raw)} substeps entries")
                for entry in substeps_raw:
                    if not isinstance(entry, dict):
                        continue
                    step_name = clean_text(entry.get("step", ""))
                    sub_list = entry.get("substeps") or entry.get("sub_steps") or entry.get("subSteps") or []
                    if not isinstance(sub_list, list):
                        continue
                    logger.debug(f"FlowMapAgent: Matching substeps for step '{step_name}': {sub_list}")
                    if step_name not in step_to_substeps:
                        logger.warning(f"FlowMapAgent: Step '{step_name}' not found in normalized steps {list(step_to_substeps.keys())}")
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

            # Calculate adaptive spacing for each step based on substeps
            total_vertical_spacing = 0
            if len(normalized_steps) > 1:
                for i in range(len(normalized_steps) - 1):
                    current_step = normalized_steps[i]
                    next_step = normalized_steps[i + 1]
                    
                    # Estimate substep heights
                    current_substeps = step_to_substeps.get(current_step, [])
                    next_substeps = step_to_substeps.get(next_step, [])
                    
                    # Each substep needs height + spacing
                    current_sub_height = len(current_substeps) * (font_step * 1.2 + vpad_step * 2 + 30)  # 30 = sub spacing
                    next_sub_height = len(next_substeps) * (font_step * 1.2 + vpad_step * 2 + 30)
                    
                    # More efficient spacing calculation (matching D3.js)
                    max_sub_height = max(current_sub_height, next_sub_height)
                    min_base_spacing = 45  # Matches D3.js minBaseSpacing
                    adaptive_spacing = max(min_base_spacing, max_sub_height * 0.4 + 20) if max_sub_height > 0 else min_base_spacing
                    
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


