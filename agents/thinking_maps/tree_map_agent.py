"""
tree map agent module.
"""
from typing import Dict, List, Tuple, Set, Any, Optional
import logging

from agents.core.base_agent import BaseAgent
from agents.core.agent_utils import extract_json_from_response
from config.settings import config
from prompts import get_prompt
from services.llm import llm_service

"""
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



logger = logging.getLogger(__name__)


class TreeMapAgent(BaseAgent):
    """Utility agent to improve tree map specs before rendering."""

    def __init__(self, model='qwen'):
        super().__init__(model=model)
        self.diagram_type = "tree_map"

    async def generate_graph(
        self,
        prompt: str,
        language: str = "en",
        dimension_preference: Optional[str] = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None,
        # Fixed dimension: user has already specified this, do NOT change it
        fixed_dimension: Optional[str] = None,
        # Dimension-only mode: user has dimension but no topic (generate topic and children)
        dimension_only_mode: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Generate a tree map from a prompt."""
        try:
            # Three-scenario system (similar to bridge_map):
            # Scenario 1: Topic only → standard generation
            # Scenario 2: Topic + dimension → fixed_dimension mode
            # Scenario 3: Dimension only (no topic) → dimension_only_mode
            if dimension_only_mode and fixed_dimension:
                # Scenario 3: Dimension-only mode - generate topic and children based on dimension
                logger.debug("TreeMapAgent: Dimension-only mode - generating topic and children for dimension '%s'", fixed_dimension)
                spec = await self._generate_from_dimension_only(                    fixed_dimension,
                    language,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path
                )
            else:
                # Scenario 1 or 2: Standard generation or fixed dimension with topic
                spec = await self._generate_tree_map_spec(
                    prompt,
                    language,
                    dimension_preference,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path,
                    fixed_dimension=fixed_dimension
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
                    'error': 'Generated invalid specification: %s' % validation_msg
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
                'error': 'Generation failed: %s' % str(e)
            }

    async def _generate_tree_map_spec(
        self,
        prompt: str,
        language: str,
        dimension_preference: str = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None,
        # Fixed dimension: user has already specified this, do NOT change it
        fixed_dimension: Optional[str] = None
    ) -> Optional[Dict]:
        """Generate the tree map specification using LLM."""
        try:
            # Choose prompt based on whether user has specified a fixed dimension
            if fixed_dimension:
                logger.debug("TreeMapAgent: Using FIXED dimension mode with '%s'", fixed_dimension)
                system_prompt = get_prompt("tree_map_agent", language, "fixed_dimension")

                if not system_prompt:
                    logger.warning("TreeMapAgent: No fixed_dimension prompt found, using fallback")
                    # Fallback prompt for fixed dimension mode
                    if language == "zh":
                        system_prompt = f"""用户已经指定了分类维度："{fixed_dimension}"
你必须使用这个指定的分类维度来生成树形图。不要改变或重新解释这个分类维度。

生成一个树形图，包含3-5个分类（基于指定的维度"{fixed_dimension}"），每个分类有2-4个子项。
返回JSON：{{"topic": "主题", "dimension": "{fixed_dimension}", "children": [...], "alternative_dimensions": [...]}}

重要：dimension字段必须完全保持为"{fixed_dimension}"，不要改变它！"""
                    else:
                        system_prompt = f"""The user has ALREADY SPECIFIED the classification dimension: "{fixed_dimension}"
You MUST use this exact dimension to generate the tree map. Do NOT change or reinterpret it.

Generate a tree map with 3-5 categories (based on the specified dimension "{fixed_dimension}"), each with 2-4 items.
Return JSON: {{"topic": "Topic", "dimension": "{fixed_dimension}", "children": [...], "alternative_dimensions": [...]}}

CRITICAL: The dimension field MUST remain exactly "{fixed_dimension}" - do NOT change it!"""

                if language == "zh":
                    user_prompt = f"主题：{prompt}\n\n请使用指定的分类维度「{fixed_dimension}」生成树形图。"
                else:
                    user_prompt = f"Topic: {prompt}\n\nGenerate a tree map using the EXACT classification dimension \"{fixed_dimension}\"."
            else:
                # No fixed dimension - use standard generation prompt
                system_prompt = get_prompt("tree_map_agent", language, "generation")

                if not system_prompt:
                    logger.error("TreeMapAgent: No prompt found for language %s", language)
                    return None

                # Build user prompt with dimension preference if specified
                if dimension_preference:
                    if language == "zh":
                        user_prompt = f"请为以下描述创建一个树形图，使用指定的分类维度'{dimension_preference}'：{prompt}"
                    else:
                        user_prompt = f"Please create a tree map for the following description using the specified classification dimension '{dimension_preference}': {prompt}"
                    logger.debug("TreeMapAgent: User specified dimension preference: %s", dimension_preference)
                else:
                    user_prompt = f"请为以下描述创建一个树形图：{prompt}" if language == "zh" else f"Please create a tree map for the following description: {prompt}"

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
                diagram_type='tree_map'
            )

            if not response:
                logger.error("TreeMapAgent: No response from LLM")
                return None

            # Extract JSON from response
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response with partial recovery enabled
                # This allows recovery from corrupted JSON structures
                response_str = str(response)
                response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                logger.debug("TreeMapAgent: Raw LLM response: %s", response_preview)
                spec = extract_json_from_response(response_str, allow_partial=True)

                # Check if we got a non-JSON response error
                if isinstance(spec, dict) and spec.get('_error') == 'non_json_response':
                    # LLM returned non-JSON asking for more info - retry with more explicit prompt
                    logger.warning(
                        "TreeMapAgent: LLM returned non-JSON response asking for more info. "
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
                        diagram_type='tree_map'
                    )

                    # Try extraction again
                    if isinstance(retry_response, dict):
                        spec = retry_response
                    else:
                        spec = extract_json_from_response(str(retry_response))

                        # If still non-JSON, return None
                        if isinstance(spec, dict) and spec.get('_error') == 'non_json_response':
                            logger.error(
                                "TreeMapAgent: Retry also returned non-JSON response. "
                                "Giving up after 1 retry attempt."
                            )
                            return None

            if not spec or (isinstance(spec, dict) and spec.get('_error')):
                # Log the actual response for debugging
                response_preview = str(response)[:500] + "..." if len(str(response)) > 500 else str(response)
                logger.error("TreeMapAgent: Failed to extract JSON from LLM response. Response preview: %s", response_preview)
                return None

            # If fixed_dimension was provided, enforce it regardless of what LLM returned
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
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
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
            logger.debug("TreeMapAgent: Dimension-only mode - generating topic and children for dimension '%s'", dimension)

            # Get the dimension-only prompt
            system_prompt = get_prompt("tree_map_agent", language, "dimension_only")

            if not system_prompt:
                logger.warning("TreeMapAgent: No dimension_only prompt found, using fixed_dimension prompt as fallback")
                system_prompt = get_prompt("tree_map_agent", language, "fixed_dimension")

            # Build user prompt with the dimension
            if language == "zh":
                user_prompt = f"用户指定的分类维度：{dimension}\n\n请根据这个分类维度生成一个合适的主题和类别。"
            else:
                user_prompt = f"User's specified classification dimension: {dimension}\n\nGenerate a suitable topic and categories following this classification dimension."

            logger.debug("User prompt: %s", user_prompt)

            # Call LLM

            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='tree_map'
            )

            response_preview = response[:500] + "..." if response and len(str(response)) > 500 else (response if response else 'None')
            logger.debug("LLM response: %s", response_preview)

            # Extract JSON from response
            if isinstance(response, dict):
                result = response
            else:
                result = extract_json_from_response(str(response))

            if not result:
                logger.error("TreeMapAgent: Failed to extract JSON from dimension-only response")
                return None

            # If fixed_dimension was provided, enforce it regardless of what LLM returned
            if dimension:
                result['dimension'] = dimension
                logger.debug("TreeMapAgent: Enforced FIXED dimension: %s", dimension)

            topic_result = result.get('topic', 'N/A')
            logger.debug("TreeMapAgent: Dimension-only complete - dimension: '%s', topic: '%s'", dimension, topic_result)

            return result

        except Exception as e:
            logger.error("TreeMapAgent: Error in dimension-only mode: %s", e)
            return None



    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """Validate a tree map specification."""
        try:
            if not isinstance(spec, dict):
                return False, "Spec must be a dictionary"

            topic = spec.get("topic")
            children = spec.get("children")
            dimension = spec.get("dimension")
            alternative_dimensions = spec.get("alternative_dimensions")

            if not topic or not isinstance(topic, str):
                return False, "Missing or invalid topic"
            if not children or not isinstance(children, list):
                return False, "Missing or invalid children"

            # dimension field is optional but should be a string if present
            if dimension is not None and not isinstance(dimension, str):
                return False, "Invalid dimension field - must be a string"

            # alternative_dimensions field is optional but should be a list if present
            if alternative_dimensions is not None:
                if not isinstance(alternative_dimensions, list):
                    return False, "Invalid alternative_dimensions field - must be a list"
                # Check that all items are strings
                if not all(isinstance(d, str) for d in alternative_dimensions):
                    return False, "All alternative dimensions must be strings"

            return True, "Valid tree map specification"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    MAX_BRANCHES: int = 10
    MAX_LEAVES_PER_BRANCH: int = 10

    async def enhance_spec(self, spec: Dict) -> Dict:
        """
        Clean and enhance a tree map spec.

        Args:
            spec: { "topic": str, "children": [ {"id": str, "text": str, "children": [{"id": str, "text": str}] } ] }

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

            def clean_text(value: str) -> str:
                return (value or "").strip()

            topic: str = clean_text(topic_raw)
            if not topic:
                return {"success": False, "error": "Missing or empty topic"}

            # Normalize branches and leaves
            normalized_children: List[Dict] = []
            seen_branch_labels: Set[str] = set()
            logger.debug("TreeMapAgent: Raw children from LLM: %s items", len(children_raw))

            def ensure_node(node: Dict) -> Tuple[str, str]:
                # returns (id, text) after normalization
                # Accept both "text" (new format) and "label" (legacy format)
                text = clean_text(node.get("text", node.get("label", node.get("name", ""))))
                node_id = clean_text(node.get("id", ""))
                return node_id, text

            def make_id_from(text: str, existing_ids: Set[str]) -> str:
                base = (
                    text.lower()
                    .replace(" ", "-")
                    .replace("/", "-")
                    .replace("\\", "-")
                ) or "node"
                candidate = base
                counter = 1
                while candidate in existing_ids:
                    counter += 1
                    candidate = f"{base}-{counter}"
                return candidate

            used_ids: Set[str] = set()

            for child in children_raw:
                if not isinstance(child, dict):
                    logger.warning("TreeMapAgent: Skipping non-dict child: %s", child)
                    continue
                cid, ctext = ensure_node(child)
                if not ctext or ctext in seen_branch_labels:
                    logger.warning("TreeMapAgent: Skipping empty or duplicate branch: '%s'", ctext)
                    continue
                seen_branch_labels.add(ctext)
                logger.debug("TreeMapAgent: Processing branch: '%s'", ctext)

                # Normalize child id
                if not cid:
                    cid = make_id_from(ctext, used_ids)
                if cid in used_ids:
                    cid = make_id_from(f"{ctext}-b", used_ids)
                used_ids.add(cid)

                # Normalize leaves
                leaves_raw = child.get("children", [])
                normalized_leaves: List[Dict] = []
                seen_leaf_labels: Set[str] = set()
                if isinstance(leaves_raw, list):
                    for leaf in leaves_raw:
                        if not isinstance(leaf, dict):
                            continue
                        lid, ltext = ensure_node(leaf)
                        if not ltext or ltext in seen_leaf_labels:
                            continue
                        seen_leaf_labels.add(ltext)
                        if not lid:
                            lid = make_id_from(ltext, used_ids)
                        if lid in used_ids:
                            lid = make_id_from(f"{ltext}-l", used_ids)
                        used_ids.add(lid)
                        normalized_leaves.append({"id": lid, "text": ltext})
                        if len(normalized_leaves) >= self.MAX_LEAVES_PER_BRANCH:
                            break

                normalized_children.append({
                    "id": cid,
                    "text": ctext,
                    "children": normalized_leaves,
                })
                if len(normalized_children) >= self.MAX_BRANCHES:
                    break

            logger.debug("TreeMapAgent: Final normalized children: %s branches", len(normalized_children))

            if not normalized_children:
                return {"success": False, "error": "At least one branch (child) is required"}

            # Heuristics for recommended dimensions
            font_root = 20
            font_branch = 16
            avg_char_px = 0.6
            padding = 40

            def text_radius(text: str, font_px: int, min_r: int) -> int:
                width_px = int(max(0, len(text)) * font_px * avg_char_px)
                height_px = int(font_px * 1.2)
                diameter = max(width_px, height_px) + int(font_px * 0.8)
                return max(min_r, diameter // 2)

            # Root radius
            root_r = text_radius(topic, font_root, 22)

            # Branch width estimation
            per_branch_widths: List[int] = []
            max_leaf_count = 0
            for b in normalized_children:
                br = text_radius(b["text"], font_branch, 16)
                per_branch_widths.append(br * 2 + 20)
                max_leaf_count = max(max_leaf_count, len(b.get("children", [])))

            # Canvas width grows with branches; height grows with leaves
            branch_spacing = 40
            branches_total_width = sum(per_branch_widths) + max(0, len(per_branch_widths) - 1) * branch_spacing
            base_width = max(branches_total_width + padding * 2, 700)

            # Height: root + gap + branches + gap + leaves grid
            branch_row_h = max(60, root_r + 60)
            leaves_block_h = 0
            if max_leaf_count > 0:
                leaf_row_h = 50
                leaves_block_h = 40 + leaf_row_h  # single row under each branch
            base_height = padding + root_r * 2 + 40 + branch_row_h + leaves_block_h + padding

            enhanced_spec: Dict = {
                "topic": topic,
                "children": normalized_children,
                "_agent": {
                    "type": "tree_map",
                    "branchCount": len(normalized_children),
                    "maxLeavesPerBranch": max_leaf_count,
                },
                "_recommended_dimensions": {
                    "baseWidth": base_width,
                    "baseHeight": base_height,
                    "padding": padding,
                    "width": base_width,
                    "height": base_height,
                },
            }

            # Preserve dimension and alternative_dimensions fields from original spec
            if "dimension" in spec:
                enhanced_spec["dimension"] = spec["dimension"]
            if "alternative_dimensions" in spec:
                enhanced_spec["alternative_dimensions"] = spec["alternative_dimensions"]

            return {"success": True, "spec": enhanced_spec}
        except Exception as exc:
            return {"success": False, "error": f"Unexpected error: {exc}"}


__all__ = ["TreeMapAgent"]


