"""
Double bubble map agent module.

Specialized agent for generating double bubble maps that compare and contrast two topics.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Any, Dict, Optional, Tuple
import logging

from agents.core.base_agent import BaseAgent
from agents.core.agent_utils import extract_json_from_response
from agents.core.topic_extraction import extract_double_bubble_topics_llm
from config.settings import config
from prompts import get_prompt
from services.llm import llm_service

logger = logging.getLogger(__name__)

class DoubleBubbleMapAgent(BaseAgent):
    """Agent for generating double bubble maps."""

    def __init__(self, model='qwen'):
        super().__init__(model=model)
        # llm_client is now a dynamic property from BaseAgent
        self.diagram_type = "double_bubble_map"

    async def generate_graph(
        self,
        user_prompt: str,
        language: str = 'zh',
        dimension_preference: str | None = None,
        fixed_dimension: str | None = None,
        dimension_only_mode: bool | None = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Generate a double bubble map from a prompt.

        Args:
            user_prompt: User's description of what they want to compare
            language: Language for generation ("en" or "zh")
            dimension_preference: Unused, for base class compatibility
            fixed_dimension: Unused, for base class compatibility
            dimension_only_mode: Unused, for base class compatibility
            **kwargs: May include user_id, organization_id, request_type, endpoint_path

        Returns:
            Dict containing success status and generated spec
        """
        token_kwargs = {
            'user_id': kwargs.get('user_id'),
            'organization_id': kwargs.get('organization_id'),
            'request_type': kwargs.get('request_type', 'diagram_generation'),
            'endpoint_path': kwargs.get('endpoint_path'),
        }
        try:
            logger.debug(
                "DoubleBubbleMapAgent: Starting double bubble map generation"
            )
            spec = await self._generate_double_bubble_map_spec(
                user_prompt, language, **token_kwargs
            )
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate double bubble map specification'
                }
            spec, error = await self._validate_and_retry_if_needed(
                spec, user_prompt, language, token_kwargs
            )
            if error:
                return {'success': False, 'error': error}
            enhanced_spec = self._enhance_spec(spec)
            logger.info(
                "DoubleBubbleMapAgent: Double bubble map generation completed"
            )
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
        except Exception as e:
            logger.error(
                "DoubleBubbleMapAgent: Generation failed: %s", e
            )
            return {'success': False, 'error': f'Generation failed: {str(e)}'}

    async def _validate_and_retry_if_needed(
        self,
        spec: Dict,
        user_prompt: str,
        language: str,
        token_kwargs: Dict[str, Any]
    ) -> Tuple[Dict, Optional[str]]:
        """Validate spec; retry with enhanced prompt if invalid. Return (spec, error)."""
        is_valid, validation_msg = self.validate_output(spec)
        if is_valid:
            return spec, None
        logger.warning(
            "DoubleBubbleMapAgent: Validation failed: %s. Attempting retry.",
            validation_msg
        )
        retry_prompt = self._build_retry_prompt(user_prompt, validation_msg, language)
        retry_spec = await self._generate_double_bubble_map_spec(
            retry_prompt, language, **token_kwargs
        )
        if not retry_spec or (isinstance(retry_spec, dict) and retry_spec.get('_error')):
            logger.error(
                "DoubleBubbleMapAgent: Retry failed to extract valid JSON"
            )
            return spec, f'Generated invalid specification: {validation_msg}'
        retry_valid, retry_msg = self.validate_output(retry_spec)
        if retry_valid:
            logger.info(
                "DoubleBubbleMapAgent: Retry generation succeeded"
            )
            return retry_spec, None
        logger.error(
            "DoubleBubbleMapAgent: Retry also failed validation: %s",
            retry_msg
        )
        return spec, f'Generated invalid specification after retry: {retry_msg}'

    def _build_retry_prompt(
        self, user_prompt: str, validation_msg: str, language: str
    ) -> str:
        """Build retry prompt with validation feedback."""
        if language == "zh":
            return (
                f"{user_prompt}\n\n"
                f"重要：之前的生成未通过验证：{validation_msg}。"
                f"请确保生成的JSON规范满足以下要求："
                f"左主题和右主题都必须至少包含2个属性，相似性至少包含1个属性。"
            )
        return (
            f"{user_prompt}\n\n"
            f"IMPORTANT: Previous generation failed validation: {validation_msg}. "
            f"Please ensure the generated JSON specification meets these "
            f"requirements: both left and right topics must have at least 2 "
            f"attributes, and similarities must have at least 1 attribute."
        )

    async def _generate_double_bubble_map_spec(
        self,
        prompt: str,
        language: str,
        **token_kwargs: Any
    ) -> Optional[Dict]:
        """Generate the double bubble map specification using LLM."""
        try:
            topics = await extract_double_bubble_topics_llm(
                prompt, language, self.model
            )
            logger.debug("DoubleBubbleMapAgent: Extracted topics: %s", topics)
            system_prompt = get_prompt(
                "double_bubble_map_agent", language, "generation"
            )
            if not system_prompt:
                logger.error(
                    "DoubleBubbleMapAgent: No prompt found for language %s",
                    language
                )
                return None
            user_prompt = self._build_user_prompt(topics, language)
            chat_kwargs = {
                'prompt': user_prompt,
                'model': self.model,
                'system_message': system_prompt,
                'max_tokens': 1000,
                'temperature': config.LLM_TEMPERATURE,
                'diagram_type': 'double_bubble_map',
                **token_kwargs
            }
            response = await llm_service.chat(**chat_kwargs)
            if isinstance(response, dict):
                return response
            return await self._extract_spec_from_response(
                response, user_prompt, language, chat_kwargs
            )
        except Exception as e:
            logger.error(
                "DoubleBubbleMapAgent: Error in spec generation: %s", e
            )
            return None

    def _build_user_prompt(self, topics: str, language: str) -> str:
        """Build user prompt from extracted topics."""
        if language == "zh":
            return f"请为以下描述创建一个双气泡图：{topics}"
        return (
            f"Please create a double bubble map for the following "
            f"description: {topics}"
        )

    async def _extract_spec_from_response(
        self,
        response: Any,
        user_prompt: str,
        language: str,
        chat_kwargs: Dict[str, Any]
    ) -> Optional[Dict]:
        """Extract spec from string response, retrying if non-JSON."""
        response_str = str(response)
        spec = extract_json_from_response(response_str)
        if isinstance(spec, dict) and spec.get('_error') == 'non_json_response':
            spec = await self._retry_json_extraction(
                user_prompt, language, chat_kwargs
            )
        if not spec or (isinstance(spec, dict) and spec.get('_error')):
            self._log_extraction_failure(response_str)
            return None
        return spec

    async def _retry_json_extraction(
        self,
        user_prompt: str,
        language: str,
        chat_kwargs: Dict[str, Any]
    ) -> Optional[Dict]:
        """Retry LLM call with explicit JSON-only prompt."""
        logger.warning(
            "DoubleBubbleMapAgent: LLM returned non-JSON. Retrying."
        )
        retry_prompt = (
            f"{user_prompt}\n\n"
            f"重要：你必须只返回有效的JSON格式，不要询问更多信息。"
            f"如果提示不清楚，请根据提示内容做出合理假设并直接生成JSON规范。"
            if language == "zh" else
            f"{user_prompt}\n\n"
            f"IMPORTANT: You MUST respond with valid JSON only. "
            f"Do not ask for more information. If the prompt is unclear, "
            f"make reasonable assumptions and generate the JSON spec."
        )
        retry_response = await llm_service.chat(
            **{**chat_kwargs, 'prompt': retry_prompt}
        )
        if isinstance(retry_response, dict):
            return retry_response
        spec = extract_json_from_response(str(retry_response))
        if isinstance(spec, dict) and spec.get('_error') == 'non_json_response':
            logger.error(
                "DoubleBubbleMapAgent: Retry also returned non-JSON"
            )
            return None
        return spec

    def _log_extraction_failure(self, response_str: str) -> None:
        """Log JSON extraction failure with context."""
        response_preview = (
            response_str[:500] + "..."
            if len(response_str) > 500 else response_str
        )
        logger.error(
            "DoubleBubbleMapAgent: Failed to extract JSON from response"
        )
        logger.error(
            "DoubleBubbleMapAgent: Response length: %s, Preview: %s",
            len(response_str), response_preview
        )

    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            logger.debug(
                "DoubleBubbleMapAgent: Enhancing spec - Left: %s, Right: %s",
                spec.get('left'), spec.get('right')
            )
            left_attrs_count = len(spec.get('left_differences', []))
            right_attrs_count = len(spec.get('right_differences', []))
            shared_attrs_count = len(spec.get('similarities', []))
            logger.debug(
                "DoubleBubbleMapAgent: Left attributes: %s, Right attributes: %s, Shared: %s",
                left_attrs_count, right_attrs_count, shared_attrs_count
            )

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

    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate the generated double bubble map specification.

        Args:
            output: The specification to validate

        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            error_msg = self._get_validation_error(output)
            if error_msg:
                return False, error_msg
            return True, "Specification is valid"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _get_validation_error(self, output: Dict[str, Any]) -> Optional[str]:
        """Return validation error message or None if valid."""
        checks = [
            (lambda: not isinstance(output, dict),
             "Specification must be a dictionary"),
            (lambda: 'left' not in output or not output['left'],
             "Missing or empty left topic"),
            (lambda: 'right' not in output or not output['right'],
             "Missing or empty right topic"),
            (lambda: 'left_differences' not in output or not isinstance(
                output.get('left_differences'), list),
             "Missing or invalid left_differences list"),
            (lambda: 'right_differences' not in output or not isinstance(
                output.get('right_differences'), list),
             "Missing or invalid right_differences list"),
            (lambda: 'similarities' not in output or not isinstance(
                output.get('similarities'), list),
             "Missing or invalid similarities list"),
            (lambda: len(output.get('left_differences', [])) < 2,
             "Left topic must have at least 2 attributes"),
            (lambda: len(output.get('right_differences', [])) < 2,
             "Right topic must have at least 2 attributes"),
            (lambda: len(output.get('similarities', [])) < 1,
             "Must have at least 1 shared attribute"),
        ]
        for condition, message in checks:
            if condition():
                return message
        total = (len(output.get('left_differences', [])) +
                 len(output.get('right_differences', [])) +
                 len(output.get('similarities', [])))
        if total > 20:
            return "Too many total attributes (max 20)"
        return None

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
