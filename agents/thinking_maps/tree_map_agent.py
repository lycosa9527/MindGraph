"""
tree map agent module.

Tree Map Agent

Enhances basic tree map specs by:
- Normalizing and de-duplicating branch and leaf nodes
- Auto-generating stable ids when missing
- Enforcing practical limits for branches and leaves for readable diagrams
- Recommending canvas dimensions based on content density

The agent accepts a spec of the form:
  { "topic": str, "children": [ {"id": str, "text": str, "children": [{"id": str, "text": str}] } ] }

Returns { "success": bool, "spec": Dict } on success, or { "success": False, "error": str } on failure.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Tuple, Any, Optional
import logging

from agents.core.base_agent import BaseAgent
from agents.core.agent_utils import extract_json_from_response
from agents.thinking_maps.tree_map_helpers import (
    clean_text,
    compute_recommended_dimensions,
    normalize_children,
)
from config.settings import config
from prompts import get_prompt
from services.llm import llm_service



logger = logging.getLogger(__name__)


class TreeMapAgent(BaseAgent):
    """Utility agent to improve tree map specs before rendering."""

    def __init__(self, model='qwen'):
        super().__init__(model=model)
        self.diagram_type = "tree_map"

    async def generate_graph(
        self,
        user_prompt: str,
        language: str = "en",
        dimension_preference: Optional[str] = None,
        fixed_dimension: Optional[str] = None,
        dimension_only_mode: Optional[bool] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Generate a tree map from a prompt."""
        llm_kwargs = {
            "user_id": kwargs.get("user_id"),
            "organization_id": kwargs.get("organization_id"),
            "request_type": kwargs.get("request_type", "diagram_generation"),
            "endpoint_path": kwargs.get("endpoint_path"),
        }
        try:
            # Three-scenario system (similar to bridge_map):
            # Scenario 1: Topic only → standard generation
            # Scenario 2: Topic + dimension → fixed_dimension mode
            # Scenario 3: Dimension only (no topic) → dimension_only_mode
            if dimension_only_mode and fixed_dimension:
                # Scenario 3: Dimension-only mode - generate topic and children
                logger.debug(
                    "TreeMapAgent: Dimension-only mode - generating topic and "
                    "children for dimension '%s'",
                    fixed_dimension,
                )
                spec = await self._generate_from_dimension_only(
                    fixed_dimension,
                    language,
                    **llm_kwargs,
                )
            else:
                # Scenario 1 or 2: Standard generation or fixed dimension with topic
                spec = await self._generate_tree_map_spec(
                    user_prompt,
                    language,
                    dimension_preference,
                    fixed_dimension=fixed_dimension,
                    user_id=llm_kwargs["user_id"],
                    organization_id=llm_kwargs["organization_id"],
                    request_type=llm_kwargs["request_type"],
                    endpoint_path=llm_kwargs["endpoint_path"],
                )
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate tree map specification'
                }

            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning("TreeMapAgent: Validation failed: %s", validation_msg)
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

            logger.info("TreeMapAgent: Tree map generation completed successfully")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }

        except Exception as e:
            logger.error("TreeMapAgent: Tree map generation failed: %s", e)
            return {
                'success': False,
                'error': f'Generation failed: {e}'
            }

    def _build_tree_map_prompts(
        self,
        prompt: str,
        language: str,
        dimension_preference: Optional[str],
        fixed_dimension: Optional[str],
    ) -> Optional[Tuple[str, str]]:
        """Build (system_prompt, user_prompt) or None if generation prompt missing."""
        if fixed_dimension:
            return self._build_fixed_dim_prompts(prompt, language, fixed_dimension)
        return self._build_standard_prompts(prompt, language, dimension_preference)

    def _build_fixed_dim_prompts(
        self, prompt: str, language: str, fixed_dimension: str
    ) -> Tuple[str, str]:
        """Build prompts for fixed-dimension mode."""
        logger.debug("TreeMapAgent: Using FIXED dimension mode with '%s'", fixed_dimension)
        system_prompt = get_prompt("tree_map_agent", language, "fixed_dimension")
        if not system_prompt:
            logger.warning(
                "TreeMapAgent: No fixed_dimension prompt found, using fallback"
            )
            system_prompt = self._fallback_fixed_dim_prompt(language, fixed_dimension)
        user_prompt = (
            f"主题：{prompt}\n\n请使用指定的分类维度「{fixed_dimension}」生成树形图。"
            if language == "zh"
            else f'Topic: {prompt}\n\nGenerate a tree map using the EXACT classification dimension "{fixed_dimension}".'
        )
        return system_prompt, user_prompt

    def _fallback_fixed_dim_prompt(self, language: str, fixed_dimension: str) -> str:
        """Fallback system prompt when fixed_dimension template is missing."""
        if language == "zh":
            return (
                f'用户已经指定了分类维度："{fixed_dimension}"\n'
                "你必须使用这个指定的分类维度来生成树形图。不要改变或重新解释这个分类维度。\n\n"
                f'生成一个树形图，包含3-5个分类（基于指定的维度"{fixed_dimension}"），'
                "每个分类有2-4个子项。\n"
                f'返回JSON：{{"topic": "主题", "dimension": "{fixed_dimension}", '
                '"children": [...], "alternative_dimensions": [...]}\n\n'
                f'重要：dimension字段必须完全保持为"{fixed_dimension}"，不要改变它！'
            )
        return (
            f'The user has ALREADY SPECIFIED the classification dimension: "{fixed_dimension}"\n'
            "You MUST use this exact dimension to generate the tree map. "
            "Do NOT change or reinterpret it.\n\n"
            f'Generate a tree map with 3-5 categories (based on the specified dimension "{fixed_dimension}"), '
            "each with 2-4 items.\n"
            f'Return JSON: {{"topic": "Topic", "dimension": "{fixed_dimension}", '
            '"children": [...], "alternative_dimensions": [...]}\n\n'
            f'CRITICAL: The dimension field MUST remain exactly "{fixed_dimension}" - do NOT change it!'
        )

    def _build_standard_prompts(
        self,
        prompt: str,
        language: str,
        dimension_preference: Optional[str],
    ) -> Optional[Tuple[str, str]]:
        """Build prompts for standard (non-fixed) generation."""
        system_prompt = get_prompt("tree_map_agent", language, "generation")
        if not system_prompt:
            logger.error("TreeMapAgent: No prompt found for language %s", language)
            return None
        if dimension_preference:
            logger.debug(
                "TreeMapAgent: User specified dimension preference: %s",
                dimension_preference,
            )
            if language == "zh":
                user_prompt = (
                    f"请为以下描述创建一个树形图，使用指定的分类维度"
                    f"'{dimension_preference}'：{prompt}"
                )
            else:
                user_prompt = (
                    f"Please create a tree map for the following description "
                    f"using the specified classification dimension "
                    f"'{dimension_preference}': {prompt}"
                )
        else:
            user_prompt = (
                f"请为以下描述创建一个树形图：{prompt}"
                if language == "zh"
                else f"Please create a tree map for the following description: {prompt}"
            )
        return system_prompt, user_prompt

    async def _extract_spec_from_response(
        self,
        response: Any,
        user_prompt: str,
        system_prompt: str,
        language: str,
        llm_kwargs: Dict[str, Any],
    ) -> Optional[Dict]:
        """Extract JSON spec from LLM response, with retry on non-JSON."""
        if isinstance(response, dict):
            return response
        response_str = str(response)
        preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
        logger.debug("TreeMapAgent: Raw LLM response: %s", preview)
        spec = extract_json_from_response(response_str, allow_partial=True)
        if not (isinstance(spec, dict) and spec.get('_error') == 'non_json_response'):
            return spec
        logger.warning(
            "TreeMapAgent: LLM returned non-JSON response. Retrying with "
            "explicit JSON-only prompt."
        )
        retry_prompt = (
            f"{user_prompt}\n\n重要：你必须只返回有效的JSON格式，不要询问更多信息。"
            f"如果提示不清楚，请根据提示内容做出合理假设并直接生成JSON规范。"
            if language == "zh"
            else f"{user_prompt}\n\nIMPORTANT: You MUST respond with valid JSON only. "
            "Do not ask for more information. If the prompt is unclear, "
            "make reasonable assumptions and generate the JSON specification directly."
        )
        retry_response = await llm_service.chat(
            prompt=retry_prompt,
            model=self.model,
            system_message=system_prompt,
            max_tokens=1000,
            temperature=config.LLM_TEMPERATURE,
            diagram_type='tree_map',
            **llm_kwargs,
        )
        if isinstance(retry_response, dict):
            return retry_response
        spec = extract_json_from_response(str(retry_response))
        if isinstance(spec, dict) and spec.get('_error') == 'non_json_response':
            logger.error(
                "TreeMapAgent: Retry also returned non-JSON response. "
                "Giving up after 1 retry attempt."
            )
            return None
        return spec

    async def _generate_tree_map_spec(
        self,
        prompt: str,
        language: str,
        dimension_preference: Optional[str] = None,
        fixed_dimension: Optional[str] = None,
        **llm_kwargs: Any
    ) -> Optional[Dict]:
        """Generate the tree map specification using LLM."""
        try:
            prompts_result = self._build_tree_map_prompts(
                prompt, language, dimension_preference, fixed_dimension
            )
            if not prompts_result:
                return None
            system_prompt, user_prompt = prompts_result
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                diagram_type='tree_map',
                **llm_kwargs,
            )

            if not response:
                logger.error("TreeMapAgent: No response from LLM")
                return None

            spec = await self._extract_spec_from_response(
                response, user_prompt, system_prompt, language, llm_kwargs
            )
            if not spec or (isinstance(spec, dict) and spec.get('_error')):
                err_resp = str(response)
                logger.error(
                    "TreeMapAgent: Failed to extract JSON from LLM response. "
                    "Response preview: %s",
                    err_resp[:500] + "..." if len(err_resp) > 500 else err_resp,
                )
                return None

            if fixed_dimension:
                spec['dimension'] = fixed_dimension
                logger.debug("TreeMapAgent: Enforced FIXED dimension: %s", fixed_dimension)

            # Log the extracted spec for debugging
            logger.debug("TreeMapAgent: Extracted spec: %s", spec)
            return spec

        except Exception as e:
            logger.error("TreeMapAgent: Error in spec generation: %s", e)
            return None

    async def _generate_from_dimension_only(
        self,
        dimension: str,
        language: str,
        **llm_kwargs: Any
    ) -> Optional[Dict]:
        """
        Generate tree map from a classification dimension only (no topic).

        This is Scenario 3 of the three-scenario system:
        - Scenario 1: Topic only → standard generation
        - Scenario 2: Topic + dimension → fixed_dimension mode
        - Scenario 3: Dimension only (no topic) → generate topic and children (this method)

        Args:
            dimension: The classification dimension specified by user (e.g., "Biological Taxonomy", "Habitat")
            language: Language for generation

        Returns:
            Spec with generated topic and children following the specified dimension
        """
        try:
            logger.debug(
                "TreeMapAgent: Dimension-only mode - generating topic and "
                "children for dimension '%s'",
                dimension,
            )

            # Get the dimension-only prompt
            system_prompt = get_prompt("tree_map_agent", language, "dimension_only")

            if not system_prompt:
                logger.warning(
                    "TreeMapAgent: No dimension_only prompt found, "
                    "using fixed_dimension prompt as fallback"
                )
                system_prompt = get_prompt("tree_map_agent", language, "fixed_dimension")

            # Build user prompt with the dimension
            if language == "zh":
                user_prompt = f"用户指定的分类维度：{dimension}\n\n请根据这个分类维度生成一个合适的主题和类别。"
            else:
                user_prompt = (
                    f"User's specified classification dimension: {dimension}\n\n"
                    f"Generate a suitable topic and categories following "
                    f"this classification dimension."
                )

            logger.debug("User prompt: %s", user_prompt)

            # Call LLM

            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                diagram_type='tree_map',
                **llm_kwargs,
            )

            response_str = str(response) if response else 'None'
            response_preview = (
                response_str[:500] + "..."
                if response and len(response_str) > 500
                else response_str
            )
            logger.debug("LLM response: %s", response_preview)

            # Extract JSON from response
            if isinstance(response, dict):
                result = response
            else:
                result = extract_json_from_response(str(response))

            if not result:
                logger.error(
                    "TreeMapAgent: Failed to extract JSON from "
                    "dimension-only response"
                )
                return None

            # If fixed_dimension was provided, enforce it regardless of what LLM returned
            if dimension:
                result['dimension'] = dimension
                logger.debug("TreeMapAgent: Enforced FIXED dimension: %s", dimension)

            topic_result = result.get('topic', 'N/A')
            logger.debug(
                "TreeMapAgent: Dimension-only complete - dimension: '%s', "
                "topic: '%s'",
                dimension,
                topic_result,
            )

            return result

        except Exception as e:
            logger.error("TreeMapAgent: Error in dimension-only mode: %s", e)
            return None



    def _get_validation_error(self, output: Dict[str, Any]) -> Optional[str]:
        """Return validation error message or None if valid."""
        if not isinstance(output, dict):
            return "Spec must be a dictionary"
        topic = output.get("topic")
        children = output.get("children")
        dimension = output.get("dimension")
        alternative_dimensions = output.get("alternative_dimensions")
        validations = [
            (not topic or not isinstance(topic, str), "Missing or invalid topic"),
            (not children or not isinstance(children, list), "Missing or invalid children"),
            (
                dimension is not None and not isinstance(dimension, str),
                "Invalid dimension field - must be a string",
            ),
            (
                alternative_dimensions is not None
                and not isinstance(alternative_dimensions, list),
                "Invalid alternative_dimensions field - must be a list",
            ),
            (
                alternative_dimensions is not None
                and not all(isinstance(d, str) for d in alternative_dimensions),
                "All alternative dimensions must be strings",
            ),
        ]
        for condition, msg in validations:
            if condition:
                return msg
        return None

    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate a tree map specification."""
        try:
            err = self._get_validation_error(output)
            return (True, "Valid tree map specification") if err is None else (False, err)
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    MAX_BRANCHES: int = 10
    MAX_LEAVES_PER_BRANCH: int = 10

    async def enhance_spec(self, spec: Dict) -> Dict:
        """
        Clean and enhance a tree map spec.

        Args:
            spec: { "topic": str, "children": [ {"id": str, "text": str,
            "children": [{"id": str, "text": str}] } ] }

        Returns:
            Dict with keys:
              - success: bool
              - spec: enhanced spec (maintains original required fields)
        """
        try:
            if not isinstance(spec, dict):
                return {"success": False, "error": "Spec must be a dictionary"}

            topic_raw = spec.get("topic", "")
            children_raw = spec.get("children", [])

            if not isinstance(topic_raw, str) or not isinstance(children_raw, list):
                return {"success": False, "error": "Invalid field types in spec"}

            topic = clean_text(topic_raw)
            if not topic:
                return {"success": False, "error": "Missing or empty topic"}

            logger.debug(
                "TreeMapAgent: Raw children from LLM: %s items",
                len(children_raw),
            )
            normalized_children, norm_error = normalize_children(
                children_raw,
                self.MAX_BRANCHES,
                self.MAX_LEAVES_PER_BRANCH,
            )
            if norm_error:
                return {"success": False, "error": norm_error}

            logger.debug(
                "TreeMapAgent: Final normalized children: %s branches",
                len(normalized_children),
            )

            max_leaf_count = max(
                len(b.get("children", [])) for b in normalized_children
            )
            dims = compute_recommended_dimensions(topic, normalized_children)

            enhanced_spec: Dict = {
                "topic": topic,
                "children": normalized_children,
                "_agent": {
                    "type": "tree_map",
                    "branchCount": len(normalized_children),
                    "maxLeavesPerBranch": max_leaf_count,
                },
                "_recommended_dimensions": dims,
            }

            if "dimension" in spec:
                enhanced_spec["dimension"] = spec["dimension"]
            if "alternative_dimensions" in spec:
                enhanced_spec["alternative_dimensions"] = (
                    spec["alternative_dimensions"]
                )

            return {"success": True, "spec": enhanced_spec}
        except Exception as exc:
            return {"success": False, "error": f"Unexpected error: {exc}"}


__all__ = ["TreeMapAgent"]
