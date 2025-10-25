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
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Set, Any, Optional
from ..core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TreeMapAgent(BaseAgent):
    """Utility agent to improve tree map specs before rendering."""
    
    def __init__(self, model='qwen'):
        super().__init__(model=model)
        self.diagram_type = "tree_map"
    
    async def generate_graph(self, prompt: str, language: str = "en", dimension_preference: str = None) -> Dict[str, Any]:
        """Generate a tree map from a prompt."""
        try:
            # Generate the initial tree map specification
            spec = await self._generate_tree_map_spec(prompt, language, dimension_preference)
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate tree map specification'
                }
            
            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning(f"TreeMapAgent: Validation failed: {validation_msg}")
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
            
            logger.info(f"TreeMapAgent: Tree map generation completed successfully")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"TreeMapAgent: Tree map generation failed: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    async def _generate_tree_map_spec(self, prompt: str, language: str, dimension_preference: str = None) -> Optional[Dict]:
        """Generate the tree map specification using LLM."""
        try:
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Get prompt from centralized system - use agent-specific format
            system_prompt = get_prompt("tree_map_agent", language, "generation")
            
            if not system_prompt:
                logger.error(f"TreeMapAgent: No prompt found for language {language}")
                return None
            
            # Build user prompt with dimension preference if specified
            if dimension_preference:
                if language == "zh":
                    user_prompt = f"请为以下描述创建一个树形图，使用指定的分类维度'{dimension_preference}'：{prompt}"
                else:
                    user_prompt = f"Please create a tree map for the following description using the specified classification dimension '{dimension_preference}': {prompt}"
                logger.info(f"TreeMapAgent: User specified dimension preference: {dimension_preference}")
            else:
                user_prompt = f"请为以下描述创建一个树形图：{prompt}" if language == "zh" else f"Please create a tree map for the following description: {prompt}"
            
            # Call middleware directly - clean and efficient!
            from services.llm_service import llm_service
            from config.settings import config
            
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE
            )
            
            if not response:
                logger.error("TreeMapAgent: No response from LLM")
                return None
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response
                logger.info(f"TreeMapAgent: Raw LLM response: {str(response)[:500]}...")
                spec = extract_json_from_response(str(response))
            
            if not spec:
                logger.error("TreeMapAgent: Failed to extract JSON from LLM response")
                logger.error(f"TreeMapAgent: Raw response was: {str(response)}")
                return None
            
            # Log the extracted spec for debugging
            logger.info(f"TreeMapAgent: Extracted spec: {spec}")
            return spec
            
        except Exception as e:
            logger.error(f"TreeMapAgent: Error in spec generation: {e}")
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
            logger.info(f"TreeMapAgent: Raw children from LLM: {len(children_raw)} items")

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
                    logger.warning(f"TreeMapAgent: Skipping non-dict child: {child}")
                    continue
                cid, ctext = ensure_node(child)
                if not ctext or ctext in seen_branch_labels:
                    logger.warning(f"TreeMapAgent: Skipping empty or duplicate branch: '{ctext}'")
                    continue
                seen_branch_labels.add(ctext)
                logger.info(f"TreeMapAgent: Processing branch: '{ctext}'")

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

            logger.info(f"TreeMapAgent: Final normalized children: {len(normalized_children)} branches")

            if not normalized_children:
                return {"success": False, "error": "At least one branch (child) is required"}

            # Heuristics for recommended dimensions
            font_root = 20
            font_branch = 16
            font_leaf = 14
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


