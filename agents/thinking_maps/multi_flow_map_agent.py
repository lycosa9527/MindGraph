"""
multi flow map agent module.
"""
from typing import Dict, List, Any, Tuple, Optional
import logging

from agents.core.base_agent import BaseAgent
from agents.core.agent_utils import extract_json_from_response
from config.settings import config
from prompts import get_prompt
from services.llm import llm_service

"""
Multi-Flow Map Agent

This agent enhances the basic multi-flow map spec (event, causes, effects)
by cleaning data, de-duplicating entries, applying basic heuristics for
importance ordering, and recommending canvas dimensions based on content size.

Output remains a valid spec for existing D3 renderers, with optional
metadata under private keys (prefixed with "_") that renderers can ignore.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class MultiFlowMapAgent(BaseAgent):
    """Utility agent to improve multi-flow map specs before rendering."""

    def __init__(self, model='qwen'):
        super().__init__(model=model)
        self.diagram_type = "multi_flow_map"

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
        """Generate a multi-flow map from a prompt."""
        try:
            # Generate the initial multi-flow map specification
            spec = await self._generate_multi_flow_map_spec(                prompt,
                language,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate multi-flow map specification'
                }

            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning("MultiFlowMapAgent: Validation failed: %s", validation_msg)
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

            logger.info("MultiFlowMapAgent: Multi-flow map generation completed successfully")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }

        except Exception as e:
            logger.error("MultiFlowMapAgent: Multi-flow map generation failed: %s", e)
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }

    async def _generate_multi_flow_map_spec(
        self,
        prompt: str,
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Optional[Dict]:
        """Generate the multi-flow map specification using LLM."""
        try:
            # Get prompt from centralized system - use agent-specific format
            system_prompt = get_prompt("multi_flow_map_agent", language, "generation")

            if not system_prompt:
                logger.error("MultiFlowMapAgent: No prompt found for language %s", language)
                return None

            user_prompt = f"请为以下描述创建一个复流程图：{prompt}" if language == "zh" else f"Please create a multi-flow map for the following description: {prompt}"

            # Call middleware directly - clean and efficient!
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
                diagram_type='multi_flow_map'
            )

            if not response:
                logger.error("MultiFlowMapAgent: No response from LLM")
                return None

            # Extract JSON from response
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response
                spec = extract_json_from_response(str(response))

            if not spec:
                logger.error("MultiFlowMapAgent: Failed to extract JSON from LLM response")
                return None

            return spec

        except Exception as e:
            logger.error("MultiFlowMapAgent: Error in spec generation: %s", e)
            return None

    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """Validate a multi-flow map specification."""
        try:
            if not isinstance(spec, dict):
                return False, "Spec must be a dictionary"

            # Accept both standard format and alternative format from LLM
            event = spec.get("event") or spec.get("topic")
            causes = spec.get("causes")
            effects = spec.get("effects")

            # If we have 'flows' instead of 'causes'/'effects', try to extract them
            if not causes and not effects and 'flows' in spec:
                flows = spec.get('flows', [])
                if isinstance(flows, list) and len(flows) >= 2:
                    # Assume first flow is causes, second flow is effects
                    if len(flows) >= 1 and 'steps' in flows[0]:
                        causes = [step.get('label', '') for step in flows[0].get('steps', []) if step.get('label')]
                    if len(flows) >= 2 and 'steps' in flows[1]:
                        effects = [step.get('label', '') for step in flows[1].get('steps', []) if step.get('label')]

            if not event or not isinstance(event, str):
                return False, "Missing or invalid event/topic"
            if not causes or not isinstance(causes, list):
                return False, "Missing or invalid causes"
            if not effects or not isinstance(effects, list):
                return False, "Missing or invalid effects"

            return True, "Valid multi-flow map specification"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    MAX_ITEMS_PER_SIDE: int = 10

    async def enhance_spec(self, spec: Dict) -> Dict:
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

            # Normalize field names for compatibility
            event_raw = spec.get("event", "") or spec.get("topic", "")
            causes_raw = spec.get("causes", [])
            effects_raw = spec.get("effects", [])

            # If we have 'flows' instead of 'causes'/'effects', extract them
            if not causes_raw and not effects_raw and 'flows' in spec:
                flows = spec.get('flows', [])
                if isinstance(flows, list) and len(flows) >= 2:
                    # Assume first flow is causes, second flow is effects
                    if len(flows) >= 1 and 'steps' in flows[0]:
                        causes_raw = [step.get('label', '') for step in flows[0].get('steps', []) if step.get('label')]
                    if len(flows) >= 2 and 'steps' in flows[1]:
                        effects_raw = [step.get('label', '') for step in flows[1].get('steps', []) if step.get('label')]

            if not isinstance(event_raw, str) or not isinstance(causes_raw, list) or not isinstance(effects_raw, list):
                return {"success": False, "error": "Invalid field types in spec"}

            # Normalize text values
            def clean_text(value: str) -> str:
                return (value or "").strip()

            event: str = clean_text(event_raw)
            logger.debug("MultiFlowMapAgent: Raw causes: %s, Raw effects: %s", len(causes_raw), len(effects_raw))

            def normalize_list(items: List[str]) -> List[str]:
                seen = set()
                normalized: List[str] = []
                for item in items:
                    if not isinstance(item, str):
                        logger.warning("MultiFlowMapAgent: Skipping non-string item: %s", item)
                        continue
                    cleaned = clean_text(item)
                    if not cleaned or cleaned in seen:
                        logger.warning("MultiFlowMapAgent: Skipping empty or duplicate item: '%s'", item)
                        continue
                    seen.add(cleaned)
                    normalized.append(cleaned)
                    logger.debug("MultiFlowMapAgent: Added normalized item: '%s'", cleaned)
                # Clamp to maximum supported items
                return normalized[: self.MAX_ITEMS_PER_SIDE]

            causes: List[str] = normalize_list(causes_raw)
            effects: List[str] = normalize_list(effects_raw)
            logger.debug("MultiFlowMapAgent: Final normalized - causes: %s, effects: %s", len(causes), len(effects))

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

            # Calculate dimensions based on content complexity
            max_side = max(len(causes), len(effects))
            len(causes) + len(effects)

            # Estimate text width requirements (rough approximation)
            max_cause_length = max((len(c) for c in causes), default=0)
            max_effect_length = max((len(e) for e in effects), default=0)
            max_text_length = max(max_cause_length, max_effect_length, len(event))

            # Dynamic width calculation based on content
            # Base width accounts for: margins + side gaps + central event
            base_width = 600  # Reduced base for better scaling
            text_width_factor = max_text_length * 8  # Approximate pixels per character
            width_for_sides = text_width_factor * 2 + 300  # Both sides + gaps
            width = max(base_width, width_for_sides)

            # Dynamic height calculation (optimized for minimal excess space)
            base_height = 300  # Smaller base height for better scaling

            # Realistic item height calculation with slight scaling for larger content
            base_item_height = 35  # Base: ~16px text + 19px padding/spacing
            # Add slight scaling for larger content to prevent overcrowding
            scaling_factor = 1.0 + (max_side - 2) * 0.02  # 2% per item beyond 2
            item_height_estimate = base_item_height * min(scaling_factor, 1.3)  # Cap at 30% increase

            event_and_margins = 140  # Central event (50px) + top/bottom margins (90px total)
            height_for_content = max_side * item_height_estimate + event_and_margins
            height = max(base_height, height_for_content)

            # Additional height for very long text (but more conservative)
            if max_text_length > 50:
                # Only add extra height for really long text that might wrap
                extra_height = min(100, (max_text_length - 50) * 1.5)  # Much more conservative
                height += extra_height

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


