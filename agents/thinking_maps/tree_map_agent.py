"""
Tree Map Agent

Enhances basic tree map specs by:
- Normalizing and de-duplicating branch and leaf nodes
- Auto-generating stable ids when missing
- Enforcing practical limits for branches and leaves for readable diagrams
- Recommending canvas dimensions based on content density

The agent accepts a spec of the form:
  { "topic": str, "children": [ {"id": str, "label": str, "children": [{"id": str, "label": str}] } ] }

Returns { "success": bool, "spec": Dict } on success, or { "success": False, "error": str } on failure.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Set, Any, Optional
from ..core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TreeMapAgent(BaseAgent):
    """Utility agent to improve tree map specs before rendering."""
    
    def __init__(self):
        super().__init__()
        self.diagram_type = "tree_map"
    
    def generate_graph(self, prompt: str, language: str = "en") -> Dict[str, Any]:
        """Generate a tree map from a prompt."""
        try:
            # Generate the initial tree map specification
            spec = self._generate_tree_map_spec(prompt, language)
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
            enhanced_spec = self.enhance_spec(spec)
            
            logger.info(f"✅ TreeMapAgent: Successfully generated tree map")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"❌ TreeMapAgent: Error generating tree map: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    def _generate_tree_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
        """Generate the tree map specification using LLM."""
        try:
            if language == "zh":
                system_prompt = """你是一个专业的思维导图专家，专门创建树形图。树形图用于展示层次结构和分类。

请根据用户的描述，创建一个详细的树形图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "topic": "根主题",
  "children": [
    {
      "id": "branch1",
      "label": "分支1标签",
      "children": [
        {"id": "sub1", "label": "子项1"},
        {"id": "sub2", "label": "子项2"}
      ]
    },
    {
      "id": "branch2", 
      "label": "分支2标签",
      "children": [
        {"id": "sub3", "label": "子项3"}
      ]
    }
  ]
}

CRITICAL要求：
- 根主题应该清晰明确
- 每个节点都必须是字典对象，包含"id"和"label"两个字段
- 绝对不能使用字符串作为节点，必须是{"id": "xxx", "label": "xxx"}格式
- 所有叶子节点也必须有id和label字段
- 分支应该按逻辑层次组织
- 使用简洁但描述性的文本
- 确保JSON格式完全有效，没有语法错误"""
                
                user_prompt = f"请为以下描述创建一个树形图：{prompt}"
            else:
                system_prompt = """You are a professional mind mapping expert specializing in tree maps. Tree maps are used to show hierarchical structures and classifications.

Please create a detailed tree map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "topic": "Root Topic",
  "children": [
    {
      "id": "branch1",
      "label": "Branch 1 Label",
      "children": [
        {"id": "sub1", "label": "Sub-item 1"},
        {"id": "sub2", "label": "Sub-item 2"}
      ]
    },
    {
      "id": "branch2",
      "label": "Branch 2 Label", 
      "children": [
        {"id": "sub3", "label": "Sub-item 3"}
      ]
    }
  ]
}

CRITICAL Requirements:
- Root topic should be clear and specific
- Every node must be a dictionary object with "id" and "label" fields
- NEVER use strings as nodes - must be {"id": "xxx", "label": "xxx"} format
- ALL leaf nodes must also have id and label fields
- Branches should be organized in logical hierarchy
- Use concise but descriptive text
- Ensure the JSON format is completely valid with no syntax errors"""
                
                user_prompt = f"Please create a tree map for the following description: {prompt}"
            
            # Generate response from LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.llm_client.chat_completion(messages)
            
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
            
            if not topic or not isinstance(topic, str):
                return False, "Missing or invalid topic"
            if not children or not isinstance(children, list):
                return False, "Missing or invalid children"
            
            return True, "Valid tree map specification"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    MAX_BRANCHES: int = 10
    MAX_LEAVES_PER_BRANCH: int = 10

    def enhance_spec(self, spec: Dict) -> Dict:
        """
        Clean and enhance a tree map spec.

        Args:
            spec: { "topic": str, "children": [ {"id": str, "label": str, "children": [{"id": str, "label": str}] } ] }

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

            def ensure_node(node: Dict) -> Tuple[str, str]:
                # returns (id, label) after normalization
                label = clean_text(node.get("label", node.get("name", "")))
                node_id = clean_text(node.get("id", ""))
                return node_id, label

            def make_id_from(label: str, existing_ids: Set[str]) -> str:
                base = (
                    label.lower()
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
                    continue
                cid, clabel = ensure_node(child)
                if not clabel or clabel in seen_branch_labels:
                    continue
                seen_branch_labels.add(clabel)

                # Normalize child id
                if not cid:
                    cid = make_id_from(clabel, used_ids)
                if cid in used_ids:
                    cid = make_id_from(f"{clabel}-b", used_ids)
                used_ids.add(cid)

                # Normalize leaves
                leaves_raw = child.get("children", [])
                normalized_leaves: List[Dict] = []
                seen_leaf_labels: Set[str] = set()
                if isinstance(leaves_raw, list):
                    for leaf in leaves_raw:
                        if not isinstance(leaf, dict):
                            continue
                        lid, llabel = ensure_node(leaf)
                        if not llabel or llabel in seen_leaf_labels:
                            continue
                        seen_leaf_labels.add(llabel)
                        if not lid:
                            lid = make_id_from(llabel, used_ids)
                        if lid in used_ids:
                            lid = make_id_from(f"{llabel}-l", used_ids)
                        used_ids.add(lid)
                        normalized_leaves.append({"id": lid, "label": llabel})
                        if len(normalized_leaves) >= self.MAX_LEAVES_PER_BRANCH:
                            break

                normalized_children.append({
                    "id": cid,
                    "label": clabel,
                    "children": normalized_leaves,
                })
                if len(normalized_children) >= self.MAX_BRANCHES:
                    break

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
                br = text_radius(b["label"], font_branch, 16)
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

            return {"success": True, "spec": enhanced_spec}
        except Exception as exc:
            return {"success": False, "error": f"Unexpected error: {exc}"}


__all__ = ["TreeMapAgent"]


