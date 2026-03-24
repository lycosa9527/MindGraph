"""
Mind Map Agent - LLM-based mind map spec generation.

Layout is handled entirely by the frontend (loadMindMapSpec / correctYPositions).
This agent only generates the JSON spec (topic + children tree) via LLM and
tags it with ``_agent = 'mind_map_agent'``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional, Tuple, Any
import logging

from agents.core.base_agent import BaseAgent
from agents.core.agent_utils import extract_json_from_response
from config.settings import Config
from prompts import get_prompt
from services.llm import llm_service


logger = logging.getLogger(__name__)


class MindMapAgent(BaseAgent):
    """
    Mind Map Agent - generates mind map specs via LLM.

    Layout is handled entirely on the frontend; this agent only
    produces the JSON spec (topic + children tree) via LLM.
    """

    def __init__(self, model='qwen'):
        super().__init__(model=model)
        self.config = Config()
        self.diagram_type = "mindmap"

    def _get_node_text(self, node: Dict, default: str = '') -> str:
        """
        Safely extract text from a node. Canonical field is 'text' (matches frontend
        and tree/brace map prompts). Fallback to 'label' for backward compatibility.

        Args:
            node: Node dictionary with 'text' or 'label' key
            default: Default value if neither key exists

        Returns:
            Text content from node
        """
        if not isinstance(node, dict):
            return default

        return node.get('text') or node.get('label') or default

    async def generate_graph(
        self,
        user_prompt: str,
        language: str = "en",
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Generate a mind map from a prompt."""
        try:
            # Generate the initial mind map specification
            spec, recovery_warnings = await self._generate_mind_map_spec(
                user_prompt,
                language,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate mind map specification'
                }

            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning("MindMapAgent: Validation failed: %s", validation_msg)
                if recovery_warnings:
                    error_msg = (
                        f'Partial recovery attempted but validation failed: '
                        f'{validation_msg}. Original LLM response had issues.'
                    )
                else:
                    error_msg = f'Generated invalid specification: {validation_msg}'
                return {
                    'success': False,
                    'error': error_msg
                }

            enhanced_spec = await self.enhance_spec(spec)

            logger.info("MindMapAgent: Successfully generated mind map")
            result = {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }

            if recovery_warnings:
                result['warning'] = (
                    'LLM response had issues. Some branches may be missing. '
                    'You can use auto-complete to add more.'
                )
                result['recovery_warnings'] = recovery_warnings

            return result

        except Exception as e:
            logger.error("MindMapAgent: Error generating mind map: %s", e)
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }

    async def _generate_mind_map_spec(
        self,
        prompt: str,
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[List[str]]]:
        """Generate the mind map specification using LLM."""
        try:
            system_prompt = get_prompt("mind_map", language, "generation")

            if not system_prompt:
                logger.error(
                    "MindMapAgent: No prompt found for language %s", language
                )
                return None, None

            user_prompt = (
                f"请为以下描述创建一个思维导图：{prompt}"
                if language == "zh"
                else f"Please create a mind map for the following description: {prompt}"
            )

            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=1.0,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='mind_map'
            )

            if not response:
                logger.error("MindMapAgent: No response from LLM")
                return None, None

            recovery_warnings = None
            if isinstance(response, dict):
                spec = response
            else:
                response_str = str(response)
                spec = extract_json_from_response(
                    response_str, allow_partial=True
                )

                if not spec:
                    response_preview = (
                        response_str[:500] + "..."
                        if len(response_str) > 500
                        else response_str
                    )
                    logger.error(
                        "MindMapAgent: Failed to extract JSON from LLM response"
                    )
                    logger.error(
                        "MindMapAgent: Response length: %s, Preview: %s",
                        len(response_str), response_preview
                    )
                    return None, None

                if spec.get("_partial_recovery"):
                    warnings = spec.get("_recovery_warnings", [])
                    recovered_count = spec.get("_recovered_count", 0)
                    logger.warning(
                        "MindMapAgent: Partial JSON recovery succeeded. "
                        "Recovered %s branches. Warnings: %s",
                        recovered_count,
                        ', '.join(warnings)
                    )
                    recovery_warnings = warnings
                    spec.pop("_partial_recovery", None)
                    spec.pop("_recovery_warnings", None)
                    spec.pop("_recovered_count", None)

            return spec, recovery_warnings

        except Exception as e:
            logger.error("MindMapAgent: Error in spec generation: %s", e)
            return None, None

    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate a mind map specification."""
        try:
            if not output or not isinstance(output, dict):
                return False, "Invalid specification"

            if 'topic' not in output or not output['topic']:
                return False, "Missing topic"

            if 'children' not in output or not isinstance(output['children'], list):
                return False, "Missing children"

            if not output['children']:
                return False, "At least one child branch is required"

            return True, "Valid mind map specification"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def enhance_spec(self, spec: Dict) -> Dict:
        """Tag the spec so downstream code knows which agent produced it.

        Layout is computed entirely on the frontend; this method no longer
        generates positions or connections.
        """
        if not spec or 'topic' not in spec or 'children' not in spec:
            return {"success": False, "error": "Invalid specification"}
        spec['_agent'] = 'mind_map_agent'
        return spec
