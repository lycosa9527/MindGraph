"""
Bubble map agent module.

Specialized agent for generating bubble maps that describe attributes of a single topic.

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


class BubbleMapAgent(BaseAgent):
    """Agent for generating bubble maps."""

    def __init__(self, model="qwen"):
        super().__init__(model=model)
        # llm_client is now a dynamic property from BaseAgent
        self.diagram_type = "bubble_map"

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
        Generate a bubble map from a prompt.

        Args:
            user_prompt: User's description of what they want
            language: Language for generation ("en" or "zh")
            dimension_preference: Preferred dimension (unused for bubble maps)
            fixed_dimension: Fixed dimension (unused for bubble maps)
            dimension_only_mode: Dimension-only mode (unused for bubble maps)
            **kwargs: Token tracking (user_id, organization_id, request_type, endpoint_path)

        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.debug("BubbleMapAgent: Starting bubble map generation for prompt")

            spec = await self._generate_bubble_map_spec(user_prompt, language, **kwargs)

            if not spec:
                return {
                    "success": False,
                    "error": "Failed to generate bubble map specification",
                }

            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning("BubbleMapAgent: Validation failed: %s", validation_msg)
                return {
                    "success": False,
                    "error": f"Generated invalid specification: {validation_msg}",
                }

            # Enhance the spec with layout and dimensions
            enhanced_spec = self._enhance_spec(spec)

            logger.info("BubbleMapAgent: Bubble map generation completed successfully")
            return {
                "success": True,
                "spec": enhanced_spec,
                "diagram_type": self.diagram_type,
            }

        except Exception as e:
            logger.error("BubbleMapAgent: Bubble map generation failed: %s", e)
            return {"success": False, "error": f"Generation failed: {str(e)}"}

    async def _generate_bubble_map_spec(self, prompt: str, language: str, **kwargs: Any) -> Optional[Dict]:
        """Generate the bubble map specification using LLM."""
        try:
            system_prompt = get_prompt("bubble_map_agent", language, "generation")

            if not system_prompt:
                logger.error("BubbleMapAgent: No prompt found for language %s", language)
                return None
            system_prompt = system_prompt.format(topic=prompt)

            if language == "zh":
                user_prompt = f"请为以下描述创建一个气泡图：{prompt}"
            else:
                user_prompt = f"Please create a bubble map for the following description: {prompt}"

            token_params = {
                "user_id": kwargs.get("user_id"),
                "organization_id": kwargs.get("organization_id"),
                "request_type": kwargs.get("request_type", "diagram_generation"),
                "endpoint_path": kwargs.get("endpoint_path"),
                "diagram_type": "bubble_map",
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
                response_str = str(response)
                spec = extract_json_from_response(response_str)

                if not spec:
                    # Log the actual response for debugging
                    response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                    logger.error(
                        "BubbleMapAgent: Failed to extract JSON from LLM response. Response preview: %s",
                        response_preview,
                    )
                    return None

            return spec

        except Exception as e:
            logger.error("BubbleMapAgent: Error in spec generation: %s", e)
            return None

    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            # Add layout information
            spec["_layout"] = {
                "type": "bubble_map",
                "topic_position": "center",
                "attribute_spacing": 120,
                "bubble_radius": 60,
            }

            # Add recommended dimensions
            spec["_recommended_dimensions"] = {
                "baseWidth": 800,
                "baseHeight": 600,
                "padding": 80,
                "width": 800,
                "height": 600,
            }

            # Add metadata
            spec["_metadata"] = {
                "generated_by": "BubbleMapAgent",
                "version": "1.0",
                "enhanced": True,
            }

            return spec

        except Exception as e:
            logger.error("BubbleMapAgent: Error enhancing spec: %s", e)
            return spec

    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate the generated bubble map specification.

        Args:
            output: The specification to validate

        Returns:
            Tuple of (is_valid, validation_message)
        """
        is_valid = True
        validation_msg = "Specification is valid"
        try:
            if not isinstance(output, dict):
                is_valid, validation_msg = False, "Specification must be a dictionary"
            elif "topic" not in output or not output["topic"]:
                is_valid, validation_msg = False, "Missing or empty topic"
            elif "attributes" not in output or not isinstance(output["attributes"], list):
                is_valid, validation_msg = False, "Missing or invalid attributes list"
            elif "connections" in output and not isinstance(output["connections"], list):
                is_valid, validation_msg = False, "Invalid connections list"
            elif len(output["attributes"]) < 3:
                is_valid, validation_msg = False, "Must have at least 3 attributes"
            elif len(output["attributes"]) > 15:
                is_valid, validation_msg = False, "Too many attributes (max 15)"
            else:
                for i, attr in enumerate(output["attributes"]):
                    if not isinstance(attr, str) or not attr.strip():
                        is_valid, validation_msg = (
                            False,
                            f"attributes[{i}] must be a non-empty string",
                        )
                        break
                if is_valid and "connections" in output:
                    if len(output["connections"]) < len(output["attributes"]):
                        is_valid, validation_msg = (
                            False,
                            "Each attribute must have at least one connection",
                        )
        except Exception as exc:
            is_valid, validation_msg = False, f"Validation error: {str(exc)}"
        return is_valid, validation_msg

    def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing bubble map specification.

        Args:
            spec: Existing specification to enhance

        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            attributes_count = len(spec.get("attributes", []))
            logger.debug(
                "BubbleMapAgent: Enhancing spec - Topic: %s, Attributes: %s",
                spec.get("topic"),
                attributes_count,
            )

            # If already enhanced, return as-is
            if spec.get("_metadata", {}).get("enhanced"):
                logger.debug("BubbleMapAgent: Spec already enhanced, skipping")
                return {"success": True, "spec": spec}

            # Enhance the spec
            enhanced_spec = self._enhance_spec(spec)

            return {"success": True, "spec": enhanced_spec}

        except Exception as e:
            logger.error("BubbleMapAgent: Error enhancing spec: %s", e)
            return {"success": False, "error": f"Enhancement failed: {str(e)}"}
