"""
Circle map agent module.

Specialized agent for generating circle maps that define topics in context.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict, Optional, Tuple
import logging

from agents.core.base_agent import BaseAgent
from agents.core.agent_utils import extract_json_from_response
from config.settings import config
from prompts import get_prompt
from services.llm import llm_service

logger = logging.getLogger(__name__)


class CircleMapAgent(BaseAgent):
    """Agent for generating circle maps."""

    def __init__(self, model="qwen"):
        super().__init__(model=model)
        # llm_client is now a dynamic property from BaseAgent
        self.diagram_type = "circle_map"

    async def generate_graph(
        self,
        user_prompt: str,
        language: str = "en",
        dimension_preference: Optional[str] = None,
        fixed_dimension: Optional[str] = None,
        dimension_only_mode: Optional[bool] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate a circle map from a prompt.

        Args:
            user_prompt: User's description of what they want to define
            language: Language for generation ("en" or "zh")
            dimension_preference: Preferred dimension (unused for circle maps)
            fixed_dimension: Fixed dimension (unused for circle maps)
            dimension_only_mode: Dimension-only mode (unused for circle maps)
            **kwargs: Token tracking (user_id, organization_id, request_type, endpoint_path)

        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.debug("CircleMapAgent: Starting circle map generation for prompt")

            spec = await self._generate_circle_map_spec(user_prompt, language, **kwargs)

            if not spec:
                return {
                    "success": False,
                    "error": "Failed to generate circle map specification",
                }

            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning("CircleMapAgent: Validation failed: %s", validation_msg)
                return {
                    "success": False,
                    "error": f"Generated invalid specification: {validation_msg}",
                }

            # Enhance the spec with layout and dimensions
            enhanced_spec = self._enhance_spec(spec)

            logger.info("CircleMapAgent: Circle map generation completed successfully")
            return {
                "success": True,
                "spec": enhanced_spec,
                "diagram_type": self.diagram_type,
            }

        except Exception as e:
            logger.error("CircleMapAgent: Circle map generation failed: %s", e)
            return {"success": False, "error": f"Generation failed: {str(e)}"}

    async def _generate_circle_map_spec(self, prompt: str, language: str, **kwargs: Any) -> Optional[Dict]:
        """Generate the circle map specification using LLM."""
        try:
            system_prompt = get_prompt("circle_map_agent", language, "generation")

            if not system_prompt:
                logger.error("CircleMapAgent: No prompt found for language %s", language)
                return None
            system_prompt = system_prompt.format(topic=prompt)

            if language == "zh":
                user_prompt = f"请为以下描述创建一个圆圈图：{prompt}"
            else:
                user_prompt = f"Please create a circle map for the following description: {prompt}"

            token_params = {
                "user_id": kwargs.get("user_id"),
                "organization_id": kwargs.get("organization_id"),
                "request_type": kwargs.get("request_type", "diagram_generation"),
                "endpoint_path": kwargs.get("endpoint_path"),
                "diagram_type": "circle_map",
            }
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                **token_params,
            )

            # Extract JSON from response
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response
                spec = extract_json_from_response(str(response))

            if not spec:
                logger.error("CircleMapAgent: Failed to extract JSON from LLM response")
                response_preview = str(response)[:500]
                logger.error(
                    "CircleMapAgent: Raw response from %s: %s",
                    self.model,
                    response_preview,
                )
                return None

            return spec

        except Exception as e:
            logger.error("CircleMapAgent: Error in spec generation: %s", e)
            return None

    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            # Add layout information
            spec["_layout"] = {
                "type": "circle_map",
                "central_position": "center",
                "circle_spacing": 80,
                "inner_radius": 60,
                "middle_radius": 140,
                "outer_radius": 220,
            }

            # Add recommended dimensions
            spec["_recommended_dimensions"] = {
                "baseWidth": 900,
                "baseHeight": 700,
                "padding": 100,
                "width": 900,
                "height": 700,
            }

            # Add metadata
            spec["_metadata"] = {
                "generated_by": "CircleMapAgent",
                "version": "1.0",
                "enhanced": True,
            }

            return spec

        except Exception as e:
            logger.error("CircleMapAgent: Error enhancing spec: %s", e)
            return spec

    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate the generated circle map specification.

        Args:
            output: The specification to validate

        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            error_msg = None
            if not isinstance(output, dict):
                error_msg = "Specification must be a dictionary"
            elif "topic" not in output or not output["topic"]:
                error_msg = "Missing or empty topic"
            elif "context" not in output or not isinstance(output["context"], list):
                error_msg = "Missing or invalid context list"
            elif len(output["context"]) < 4:
                error_msg = "Must have at least 4 context elements"
            else:
                for i, ctx in enumerate(output["context"]):
                    if not isinstance(ctx, str) or not ctx.strip():
                        error_msg = f"context[{i}] must be a non-empty string"
                        break
            if error_msg:
                return False, error_msg
            return True, "Specification is valid"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing circle map specification.

        Args:
            spec: Existing specification to enhance

        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            context_count = len(spec.get("context", []))
            logger.debug(
                "CircleMapAgent: Enhancing spec - Topic: %s, Context elements: %s",
                spec.get("topic"),
                context_count,
            )

            # If already enhanced, return as-is
            if spec.get("_metadata", {}).get("enhanced"):
                logger.debug("CircleMapAgent: Spec already enhanced, skipping")
                return {"success": True, "spec": spec}

            # Enhance the spec
            enhanced_spec = self._enhance_spec(spec)

            return {"success": True, "spec": enhanced_spec}

        except Exception as e:
            logger.error("CircleMapAgent: Error enhancing spec: %s", e)
            return {"success": False, "error": f"Enhancement failed: {str(e)}"}
