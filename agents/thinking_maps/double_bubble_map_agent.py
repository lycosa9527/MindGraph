"""
double bubble map agent module.
"""
from typing import Any, Dict, Optional, Tuple
import logging

from agents.core.base_agent import BaseAgent
from agents.core.agent_utils import extract_json_from_response
from agents.core.topic_extraction import extract_double_bubble_topics_llm
from config.settings import config
from prompts import get_prompt
from services.llm import llm_service

"""
Double Bubble Map Agent

Specialized agent for generating double bubble maps that compare and contrast two topics.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)

class DoubleBubbleMapAgent(BaseAgent):
    """Agent for generating double bubble maps."""

    def __init__(self, model='qwen'):
        super().__init__(model=model)
        # llm_client is now a dynamic property from BaseAgent
        self.diagram_type = "double_bubble_map"

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
        """
        Generate a double bubble map from a prompt.

        Args:
            prompt: User's description of what they want to compare
            language: Language for generation ("en" or "zh")
            user_id: User ID for token tracking
            organization_id: Organization ID for token tracking
            request_type: Request type for token tracking
            endpoint_path: Endpoint path for token tracking

        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.debug("DoubleBubbleMapAgent: Starting double bubble map generation for prompt")

            # Generate the double bubble map specification
            spec = await self._generate_double_bubble_map_spec(                prompt,
                language,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )

            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate double bubble map specification'
                }

            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning("DoubleBubbleMapAgent: Validation failed: %s. Attempting retry with improved prompt.", validation_msg)

                # Retry generation with validation error included in original prompt
                # Reuse original prompt instead of regenerating topics for consistency
                retry_user_prompt = (
                    f"{prompt}\n\n"
                    f"重要：之前的生成未通过验证：{validation_msg}。"
                    f"请确保生成的JSON规范满足以下要求：左主题和右主题都必须至少包含2个属性，相似性至少包含1个属性。"
                    if language == "zh" else
                    f"{prompt}\n\n"
                    f"IMPORTANT: Previous generation failed validation: {validation_msg}. "
                    f"Please ensure the generated JSON specification meets these requirements: "
                    f"both left and right topics must have at least 2 attributes, and similarities must have at least 1 attribute."
                )

                # Retry generation by calling the spec generation method again with enhanced prompt
                retry_spec = await self._generate_double_bubble_map_spec(
                    retry_user_prompt,
                    language,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path
                )

                # Validate retry spec
                if retry_spec and not (isinstance(retry_spec, dict) and retry_spec.get('_error')):
                    retry_is_valid, retry_validation_msg = self.validate_output(retry_spec)
                    if retry_is_valid:
                        logger.info("DoubleBubbleMapAgent: Retry generation succeeded after validation failure")
                        spec = retry_spec
                    else:
                        logger.error("DoubleBubbleMapAgent: Retry generation also failed validation: %s", retry_validation_msg)
                        return {
                            'success': False,
                            'error': f'Generated invalid specification after retry: {retry_validation_msg}'
                        }
                else:
                    logger.error("DoubleBubbleMapAgent: Retry generation failed to extract valid JSON")
                    return {
                        'success': False,
                        'error': f'Generated invalid specification: {validation_msg}'
                    }

            # Enhance the spec with layout and dimensions
            enhanced_spec = self._enhance_spec(spec)

            logger.info("DoubleBubbleMapAgent: Double bubble map generation completed successfully")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }

        except Exception as e:
            logger.error("DoubleBubbleMapAgent: Double bubble map generation failed: %s", e)
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }

    async def _generate_double_bubble_map_spec(
        self,
        prompt: str,
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Optional[Dict]:
        """Generate the double bubble map specification using LLM."""
        try:
            # Extract two topics for comparison using specialized LLM extraction (async)
            topics = await extract_double_bubble_topics_llm(prompt, language, self.model)
            logger.debug("DoubleBubbleMapAgent: Extracted topics: %s", topics)

            # Get prompt from centralized system - use agent-specific format
            system_prompt = get_prompt("double_bubble_map_agent", language, "generation")

            if not system_prompt:
                logger.error("DoubleBubbleMapAgent: No prompt found for language %s", language)
                return None

            # Use the extracted topics instead of raw prompt
            user_prompt = f"请为以下描述创建一个双气泡图：{topics}" if language == "zh" else f"Please create a double bubble map for the following description: {topics}"

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
                diagram_type='double_bubble_map'
            )

            # Extract JSON from response
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response
                response_str = str(response)
                spec = extract_json_from_response(response_str)

                # Check if we got a non-JSON response error
                if isinstance(spec, dict) and spec.get('_error') == 'non_json_response':
                    # LLM returned non-JSON asking for more info - retry with more explicit prompt
                    logger.warning(
                        "DoubleBubbleMapAgent: LLM returned non-JSON response asking for more info. "
                        "Retrying with explicit JSON-only prompt."
                    )

                    # Retry with more explicit prompt emphasizing JSON-only output
                    retry_user_prompt = (
                        f"{user_prompt}\n\n"
                        f"重要：你必须只返回有效的JSON格式，不要询问更多信息。"
                        f"如果提示不清楚，请根据提示内容做出合理假设并直接生成JSON规范。"
                        if language == "zh" else
                        f"{user_prompt}\n\n"
                        f"IMPORTANT: You MUST respond with valid JSON only. Do not ask for more information. "
                        f"If the prompt is unclear, make reasonable assumptions and generate the JSON specification directly."
                    )

                    retry_response = await llm_service.chat(
                        prompt=retry_user_prompt,
                        model=self.model,
                        system_message=system_prompt,
                        max_tokens=1000,
                        temperature=config.LLM_TEMPERATURE,
                        user_id=user_id,
                        organization_id=organization_id,
                        request_type=request_type,
                        endpoint_path=endpoint_path,
                        diagram_type='double_bubble_map'
                    )

                    # Try extraction again
                    if isinstance(retry_response, dict):
                        spec = retry_response
                    else:
                        spec = extract_json_from_response(str(retry_response))

                        # If still non-JSON, return None
                        if isinstance(spec, dict) and spec.get('_error') == 'non_json_response':
                            logger.error(
                                "DoubleBubbleMapAgent: Retry also returned non-JSON response. "
                                "Giving up after 1 retry attempt."
                            )
                            return None

                if not spec or (isinstance(spec, dict) and spec.get('_error')):
                    # Log the actual response for debugging with more context
                    response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                    logger.error("DoubleBubbleMapAgent: Failed to extract JSON from LLM response")
                    logger.error("DoubleBubbleMapAgent: Response length: %s, Preview: %s", len(response_str), response_preview)
                    logger.error("DoubleBubbleMapAgent: This may indicate LLM returned invalid JSON or non-JSON response")
                    # Return None to trigger error handling upstream
                    return None

            return spec

        except Exception as e:
            logger.error("DoubleBubbleMapAgent: Error in spec generation: %s", e)
            return None

    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            logger.debug("DoubleBubbleMapAgent: Enhancing spec - Left: %s, Right: %s", spec.get('left'), spec.get('right'))
            left_attrs_count = len(spec.get('left_only', []))
            right_attrs_count = len(spec.get('right_only', []))
            shared_attrs_count = len(spec.get('shared', []))
            logger.debug("DoubleBubbleMapAgent: Left attributes: %s, Right attributes: %s, Shared: %s", left_attrs_count, right_attrs_count, shared_attrs_count)

            # Agent already generates correct renderer format, just enhance it
            enhanced_spec = spec.copy()

            # Add layout information
            enhanced_spec['_layout'] = {
                'type': 'double_bubble_map',
                'left_position': 'left',
                'right_position': 'right',
                'shared_position': 'center',
                'attribute_spacing': 100,
                'bubble_radius': 50
            }

            # Add recommended dimensions
            enhanced_spec['_recommended_dimensions'] = {
                'baseWidth': 1000,
                'baseHeight': 700,
                'padding': 100,
                'width': 1000,
                'height': 700
            }

            # Add metadata
            enhanced_spec['_metadata'] = {
                'generated_by': 'DoubleBubbleMapAgent',
                'version': '1.0',
                'enhanced': True
            }

            return enhanced_spec

        except Exception as e:
            logger.error("DoubleBubbleMapAgent: Error enhancing spec: %s", e)
            return spec

    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """
        Validate the generated double bubble map specification.

        Args:
            spec: The specification to validate

        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            # Check required fields
            if not isinstance(spec, dict):
                return False, "Specification must be a dictionary"

            if 'left' not in spec or not spec['left']:
                return False, "Missing or empty left topic"

            if 'right' not in spec or not spec['right']:
                return False, "Missing or empty right topic"

            if 'left_differences' not in spec or not isinstance(spec['left_differences'], list):
                return False, "Missing or invalid left_differences list"

            if 'right_differences' not in spec or not isinstance(spec['right_differences'], list):
                return False, "Missing or invalid right_differences list"

            if 'similarities' not in spec or not isinstance(spec['similarities'], list):
                return False, "Missing or invalid similarities list"

            # Validate attributes
            if len(spec['left_differences']) < 2:
                return False, "Left topic must have at least 2 attributes"

            if len(spec['right_differences']) < 2:
                return False, "Right topic must have at least 2 attributes"

            if len(spec['similarities']) < 1:
                return False, "Must have at least 1 shared attribute"

            # Check total attribute count
            total_attrs = (len(spec['left_differences']) +
                          len(spec['right_differences']) +
                          len(spec['similarities']))
            if total_attrs > 20:
                return False, "Too many total attributes (max 20)"

            return True, "Specification is valid"

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing double bubble map specification.

        Args:
            spec: Existing specification to enhance

        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            logger.debug("DoubleBubbleMapAgent: Enhancing existing specification")

            # If already enhanced, return as-is
            if spec.get('_metadata', {}).get('enhanced'):
                return {'success': True, 'spec': spec}

            # Enhance the spec
            enhanced_spec = self._enhance_spec(spec)

            return {
                'success': True,
                'spec': enhanced_spec
            }

        except Exception as e:
            logger.error("DoubleBubbleMapAgent: Error enhancing spec: %s", e)
            return {
                'success': False,
                'error': f'Enhancement failed: {str(e)}'
            }
