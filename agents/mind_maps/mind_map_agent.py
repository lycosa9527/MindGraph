#!/usr/bin/env python3
"""
MindGraph v2.4.0 - Advanced Mind Map Agent with Clockwise Positioning System

This agent implements a revolutionary clockwise positioning system that:
- Distributes branches evenly between left and right sides
- Aligns Branch 2 and 5 with the central topic for perfect visual balance
- Maintains the proven children-first positioning system
- Provides scalable layouts for 4, 6, 8, 10+ branches
- Creates production-ready, enterprise-grade mind maps

Features:
- Clockwise branch distribution (first half → RIGHT, second half → LEFT)
- Smart branch alignment with central topic
- 5-column system preservation: [Left Children] [Left Branches] [Topic] [Right Branches] [Right Children]
- Adaptive canvas sizing and coordinate centering
- Advanced text width calculation for precise node sizing
"""

import json
import math
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from ..core.base_agent import BaseAgent

logger = logging.getLogger(__name__)

from settings import Config


@dataclass
class NodePosition:
    """Data structure for node positioning"""
    x: float
    y: float
    width: float
    height: float
    text: str
    node_type: str  # 'topic', 'branch', 'child'
    branch_index: Optional[int] = None
    child_index: Optional[int] = None
    angle: Optional[float] = None


class MindMapAgent(BaseAgent):
    """
    MindGraph v2.4.0 - Advanced Mind Map Agent with Clockwise Positioning System
    
    This agent implements a revolutionary clockwise positioning system that creates
    perfectly balanced, production-ready mind maps with intelligent branch distribution
    and smart alignment features.
    
    Key Features:
    - Clockwise branch distribution for perfect left/right balance
    - Smart branch alignment (Branch 2 & 5 align with central topic)
    - Children-first positioning system for optimal layout
    - Scalable layouts supporting 4+ branches
    - Enterprise-grade positioning algorithms
    """
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.diagram_type = "mindmap"
        # Cache for expensive font calculations
        self._text_width_cache = {}
        self._font_size_cache = {}
        self._node_height_cache = {}
    
    def _clear_caches(self):
        """Clear font calculation caches to prevent memory bloat."""
        self._text_width_cache.clear()
        self._font_size_cache.clear()
        self._node_height_cache.clear()
    
    def generate_graph(self, prompt: str, language: str = "en") -> Dict[str, Any]:
        """Generate a mind map from a prompt."""
        try:
            # Clear caches at the start of each generation
            self._clear_caches()
            # Generate the initial mind map specification
            spec = self._generate_mind_map_spec(prompt, language)
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate mind map specification'
                }
            
            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning(f"MindMapAgent: Validation failed: {validation_msg}")
                return {
                    'success': False,
                    'error': f'Generated invalid specification: {validation_msg}'
                }
            
            # Enhance the spec with layout and dimensions
            enhanced_spec = self.enhance_spec(spec)
            
            logger.info(f"✅ MindMapAgent: Successfully generated mind map")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"❌ MindMapAgent: Error generating mind map: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    def _generate_mind_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
        """Generate the mind map specification using LLM."""
        try:
            if language == "zh":
                system_prompt = """你是一个专业的思维导图专家，专门创建思维导图。思维导图用于展示主题的分支结构。

请根据用户的描述，创建一个详细的思维导图规范。输出必须是有效的JSON格式，严格按照以下结构：

{
  "topic": "中心主题",
  "children": [
    {
      "id": "fen_zhi_1",
      "label": "分支1标签",
      "children": [
        {"id": "zi_xiang_1_1", "label": "子项1.1"},
        {"id": "zi_xiang_1_2", "label": "子项1.2"}
      ]
    },
    {
      "id": "fen_zhi_2",
      "label": "分支2标签",
      "children": [
        {"id": "zi_xiang_2_1", "label": "子项2.1"}
      ]
    }
  ]
}

关键要求：
- 只输出有效的JSON - 不要解释，不要代码块，不要额外文字
- 中心主题应该清晰明确
- 每个节点必须有id和label字段
- 所有children数组必须用]正确闭合
- 所有对象必须用}正确闭合
- 分支应该按逻辑顺序组织
- 使用简洁但描述性的文本
- 确保JSON格式完全有效，没有语法错误"""
                
                user_prompt = f"请为以下描述创建一个思维导图：{prompt}"
            else:
                system_prompt = """You are a professional mind mapping expert specializing in mind maps. Mind maps are used to show the branch structure of topics.

Please create a detailed mind map specification based on the user's description. The output must be valid JSON, strictly following this structure:

{
  "topic": "Central Topic",
  "children": [
    {
      "id": "branch_1",
      "label": "Branch 1 Label",
      "children": [
        {"id": "sub_1_1", "label": "Sub-item 1.1"},
        {"id": "sub_1_2", "label": "Sub-item 1.2"}
      ]
    },
    {
      "id": "branch_2",
      "label": "Branch 2 Label",
      "children": [
        {"id": "sub_2_1", "label": "Sub-item 2.1"}
      ]
    }
  ]
}

CRITICAL Requirements:
- Output ONLY valid JSON - no explanations, no code blocks, no extra text
- Central topic should be clear and specific
- Each node must have both id and label fields
- ALL children arrays must be properly closed with ]
- ALL objects must be properly closed with }
- Branches should be organized in logical order
- Use concise but descriptive text
- Ensure the JSON format is completely valid with no syntax errors"""
                
                user_prompt = f"Please create a mind map for the following description: {prompt}"
            
            # Generate response from LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.llm_client.chat_completion(messages)
            
            if not response:
                logger.error("MindMapAgent: No response from LLM")
                return None
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response
                spec = extract_json_from_response(str(response))
            
            if not spec:
                logger.error("MindMapAgent: Failed to extract JSON from LLM response")
                return None
            
            return spec
            
        except Exception as e:
            logger.error(f"MindMapAgent: Error in spec generation: {e}")
            return None
    
    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """Validate a mind map specification."""
        try:
            if not spec or not isinstance(spec, dict):
                return False, "Invalid specification"
            
            if 'topic' not in spec or not spec['topic']:
                return False, "Missing topic"
            
            if 'children' not in spec or not isinstance(spec['children'], list):
                return False, "Missing children"
            
            if not spec['children']:
                return False, "At least one child branch is required"
            
            return True, "Valid mind map specification"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def validate_layout_geometry(self, layout_data: Dict) -> Tuple[bool, str, List[str]]:
        """
        Validate the geometric alignment of the layout.
        Returns: (is_valid, summary_message, detailed_issues)
        """
        issues = []
        warnings = []
        
        try:
            positions = layout_data.get('positions', {})
            if not positions:
                return False, "No position data found", ["Missing layout positions"]
            
            # Group positions by branch
            branches = {}
            children_by_branch = {}
            
            for key, pos in positions.items():
                if pos is None:
                    continue
                if pos.get('node_type') == 'branch':
                    branch_idx = pos.get('branch_index', -1)
                    branches[branch_idx] = pos
                elif pos.get('node_type') == 'child':
                    branch_idx = pos.get('branch_index', -1)
                    if branch_idx not in children_by_branch:
                        children_by_branch[branch_idx] = []
                    children_by_branch[branch_idx].append(pos)
            
            # Validate each branch's alignment to its children
            for branch_idx, branch_pos in branches.items():
                children = children_by_branch.get(branch_idx, [])
                
                if not children:
                    warnings.append(f"Branch {branch_idx} has no children")
                    continue
                
                # Calculate the true visual center of children group
                children_top_edges = [child['y'] - child['height']/2 for child in children]
                children_bottom_edges = [child['y'] + child['height']/2 for child in children]
                
                visual_top = min(children_top_edges)
                visual_bottom = max(children_bottom_edges)
                visual_center = (visual_top + visual_bottom) / 2
                
                # Calculate branch position
                branch_y = branch_pos['y']
                
                # Calculate alignment tolerance (based on typical spacing)
                tolerance = 15  # 15px tolerance for alignment
                alignment_offset = abs(branch_y - visual_center)
                
                # Check alignment
                if alignment_offset > tolerance:
                    severity = "CRITICAL" if alignment_offset > 30 else "WARNING"
                    issues.append(
                        f"{severity}: Branch {branch_idx} misaligned by {alignment_offset:.1f}px "
                        f"(Branch Y: {branch_y:.1f}, Visual Center: {visual_center:.1f})"
                    )
                    
                    # Suggest correction
                    correction = visual_center - branch_y
                    issues.append(
                        f"  → Suggested fix: Move branch {branch_idx} by {correction:+.1f}px "
                        f"(from Y={branch_y:.1f} to Y={visual_center:.1f})"
                    )
                    
                    # Analyze why it's misaligned
                    children_count = len(children)
                    children_y_positions = [child['y'] for child in children]
                    simple_average = sum(children_y_positions) / len(children_y_positions)
                    
                    if abs(branch_y - simple_average) < 5:
                        issues.append(
                            f"  → Root cause: Using simple Y average ({simple_average:.1f}) "
                            f"instead of visual bounding box center ({visual_center:.1f})"
                        )
                    
                    # Debug info
                    issues.append(
                        f"  → Debug: {children_count} children spanning Y={visual_top:.1f} to Y={visual_bottom:.1f} "
                        f"(height span: {visual_bottom - visual_top:.1f}px)"
                    )
                else:
                    warnings.append(
                        f"Branch {branch_idx} properly aligned (offset: {alignment_offset:.1f}px ≤ {tolerance}px)"
                    )
            
            # Check for overlapping nodes
            all_positions = [pos for pos in positions.values() if pos is not None]
            for i, pos1 in enumerate(all_positions):
                for j, pos2 in enumerate(all_positions[i+1:], i+1):
                    if self._nodes_overlap(pos1, pos2):
                        issues.append(
                            f"OVERLAP: {pos1.get('text', 'Node')} and {pos2.get('text', 'Node')} overlap"
                        )
            
            # Overall assessment
            critical_issues = [issue for issue in issues if issue.startswith("CRITICAL")]
            warning_issues = [issue for issue in issues if issue.startswith("WARNING")]
            overlap_issues = [issue for issue in issues if issue.startswith("OVERLAP")]
            
            is_valid = len(critical_issues) == 0 and len(overlap_issues) == 0
            
            # Summary message
            if is_valid:
                if warning_issues:
                    summary = f"Layout mostly valid with {len(warning_issues)} minor alignment issues"
                else:
                    summary = "Layout geometry is valid and well-aligned"
            else:
                summary = f"Layout has {len(critical_issues)} critical issues and {len(overlap_issues)} overlaps"
            
            all_feedback = issues + warnings
            return is_valid, summary, all_feedback
            
        except Exception as e:
            return False, f"Geometry validation error: {str(e)}", [f"Exception: {str(e)}"]
    
    def _nodes_overlap(self, pos1: Dict, pos2: Dict) -> bool:
        """Check if two nodes overlap."""
        try:
            x1, y1, w1, h1 = pos1['x'], pos1['y'], pos1['width'], pos1['height']
            x2, y2, w2, h2 = pos2['x'], pos2['y'], pos2['width'], pos2['height']
            
            # Calculate boundaries (assuming center-based coordinates)
            left1, right1 = x1 - w1/2, x1 + w1/2
            top1, bottom1 = y1 - h1/2, y1 + h1/2
            
            left2, right2 = x2 - w2/2, x2 + w2/2
            top2, bottom2 = y2 - h2/2, y2 + h2/2
            
            # Check for overlap
            horizontal_overlap = left1 < right2 and left2 < right1
            vertical_overlap = top1 < bottom2 and top2 < bottom1
            
            return horizontal_overlap and vertical_overlap
        except:
            return False
    
    def enhance_spec(self, spec: Dict) -> Dict:
        """Enhance mind map specification with layout data"""
        try:
            if not spec or not isinstance(spec, dict):
                return {"success": False, "error": "Invalid specification"}
            
            if 'topic' not in spec or not spec['topic']:
                return {"success": False, "error": "Missing topic"}
            
            if 'children' not in spec or not isinstance(spec['children'], list):
                return {"success": False, "error": "Missing children"}
            
            if not spec['children']:
                return {"success": False, "error": "At least one child branch is required"}
            
            # Generate clean layout using the existing spec (NO NEW LLM CALL)
            layout = self._generate_mind_map_layout(spec['topic'], spec['children'])
            
            # Re-enabled geometric validation to catch remaining issues
            is_valid, validation_summary, validation_details = self.validate_layout_geometry(layout)
            
            # Log validation results
            logger.info(f"Layout geometry validation: {validation_summary}")
            if validation_details:
                for detail in validation_details:
                    if detail.startswith("CRITICAL") or detail.startswith("WARNING") or detail.startswith("OVERLAP"):
                        logger.warning(f"  {detail}")
                    else:
                        logger.debug(f"  {detail}")
            
            # Store validation results
            layout['validation'] = {
                'is_valid': is_valid,
                'summary': validation_summary,
                'details': validation_details
            }
            
            # Add layout to spec
            spec['_layout'] = layout
            spec['_recommended_dimensions'] = layout.get('params', {}).copy()  # Copy params
            spec['_agent'] = 'mind_map_agent'
            
            return spec
            
        except Exception as e:
            import traceback
            logger.error(f"MindMapAgent error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "error": f"MindMapAgent failed: {e}"}
    
    def _generate_mind_map_layout(self, topic: str, children: List[Dict]) -> Dict:
        """
        Generate clean mind map layout using CLEAN POSITIONING SYSTEM:
        
        WORKFLOW: 
        1. Calculate left/right branch distribution
        2. Stack all children nodes vertically on each side
        3. Position branch nodes at the VISUAL center of their children groups (bounding box)
        4. Central topic positioned at vertical center of all subtopic nodes
        """
        # Initialize positions dictionary
        positions = {}
        
        # STEP 1: Analyze how many branches we get from LLM
        num_branches = len(children)
        # LLM returned branches
        
        # STEP 2: Calculate left/right branch distribution
        left_branch_count = (num_branches + 1) // 2  # More branches on left if odd
        right_branch_count = num_branches - left_branch_count
        
        # Branch distribution calculated
        
        # STEP 3: Calculate column positions with proper spacing
        gap_topic_to_branch = 200  # Space between topic and branches
        gap_branch_to_child = 120   # Space between branches and children
        
        # Calculate maximum dimensions using adaptive font sizes for consistency
        max_branch_width = 0
        max_child_width = 0
        
        for branch in children:
            # Calculate branch width with adaptive font size
            branch_font_size = self._get_adaptive_font_size(branch['label'], 'branch')
            branch_width = self._calculate_text_width(branch['label'], branch_font_size) + self._get_adaptive_padding(branch['label'])
            max_branch_width = max(max_branch_width, branch_width)
            
            # Calculate child widths with adaptive font sizes
            for child in branch.get('children', []):
                child_font_size = self._get_adaptive_font_size(child['label'], 'child')
                child_width = self._calculate_text_width(child['label'], child_font_size) + self._get_adaptive_padding(child['label'])
                max_child_width = max(max_child_width, child_width)
        
        # Column positions
        left_children_x = -(gap_topic_to_branch + max_branch_width + gap_branch_to_child + max_child_width/2)
        left_branches_x = -(gap_topic_to_branch + max_branch_width/2)
        right_branches_x = gap_topic_to_branch + max_branch_width/2
        right_children_x = gap_topic_to_branch + max_branch_width + gap_branch_to_child + max_child_width/2
        
        # Column positions and max dimensions calculated
        
        # STEP 4: Targeted Fix - Smart Mathematical Branch Positioning
        all_children_positions = {}  # Store child positions by branch index
        
        # Left side children stacking - small offset to prevent exact overlaps with right side
        left_children_y = 5  # Small offset to prevent identical Y positions
        left_branch_children = []
        
        # Right side children stacking  
        right_children_y = 0
        right_branch_children = []
        
        logger.debug(f"Starting targeted positioning fix for {num_branches} branches")
        
        for i, branch_data in enumerate(children):
            nested_children = branch_data.get('children', [])
            
            if nested_children:
                # Determine which side this branch goes on based on clockwise positioning
                mid_point = num_branches // 2
                is_left_side = i >= mid_point
                
                logger.debug(f"Branch {i} ('{branch_data['label']}'):")
                logger.debug(f"  Side: {'LEFT' if is_left_side else 'RIGHT'}")
                logger.debug(f"  Children count: {len(nested_children)}")
                
                # Position children in correct column
                if is_left_side:
                    child_x = left_children_x
                    current_y = left_children_y
                    side_children = left_branch_children
                else:
                    child_x = right_children_x
                    current_y = right_children_y
                    side_children = right_branch_children
                
                # Calculate total space needed for this branch group using optimal spacing
                child_heights = []
                
                for child in nested_children:
                    child_height = self._get_adaptive_node_height(child['label'], 'child')
                    child_heights.append(child_height)
                
                # Calculate optimal center-to-center spacing for this branch
                optimal_spacing = self._calculate_optimal_spacing(nested_children, child_heights)
                
                # Calculate block height using center-to-center spacing method
                if len(nested_children) > 1:
                    # Center-to-center spacing: total distance between first and last centers
                    center_to_center_distance = (len(nested_children) - 1) * optimal_spacing
                    # Add half heights for first and last nodes to get total block height
                    first_half_height = child_heights[0] / 2
                    last_half_height = child_heights[-1] / 2
                    block_height = first_half_height + center_to_center_distance + last_half_height
                else:
                    # Single child: just use its height
                    block_height = child_heights[0]
                
                logger.debug(f"  Block calculations:")
                logger.debug(f"    Child heights: {child_heights}")
                logger.debug(f"    Optimal spacing (center-to-center): {optimal_spacing}")
                logger.debug(f"    Block height: {block_height:.1f}")
                
                # TARGETED FIX: Calculate the center position for this group
                # The branch should be at the center of its allocated block
                block_center_y = current_y + (block_height / 2)
                
                logger.debug(f"  Position calculations:")
                logger.debug(f"    Current Y start: {current_y}")
                logger.debug(f"    Block center Y: {block_center_y}")
                
                # Position children using center-to-center spacing for consistent visual rhythm
                child_positions = []
                
                # Calculate starting position for first child center
                if len(nested_children) > 1:
                    # Start with first child's center position
                    first_child_center_y = current_y + child_heights[0] / 2
                else:
                    # Single child: center it in the block
                    first_child_center_y = current_y + block_height / 2
                
                for j, child in enumerate(nested_children):
                    child_font_size = self._get_adaptive_font_size(child['label'], 'child')
                    child_height = child_heights[j]  # Use pre-calculated height
                    child_width = self._calculate_text_width(child['label'], child_font_size) + self._get_adaptive_padding(child['label'])
                    
                    # Calculate child center Y using center-to-center spacing
                    if len(nested_children) == 1:
                        child_center_y = first_child_center_y
                    else:
                        child_center_y = first_child_center_y + (j * optimal_spacing)
                    
                    # Store child position
                    child_key = f'child_{i}_{j}'
                    positions[child_key] = {
                        'x': child_x, 'y': child_center_y,
                        'width': child_width, 'height': child_height,
                        'text': child['label'], 'node_type': 'child',
                        'branch_index': i, 'child_index': j, 'angle': 0
                    }
                    
                    child_positions.append({
                        'x': child_x, 'y': child_center_y,
                        'width': child_width, 'height': child_height,
                        'text': child['label'], 'node_type': 'child',
                        'branch_index': i, 'child_index': j, 'angle': 0
                    })
                    
                    logger.debug(f"    Child {j} '{child['label']}' at center Y={child_center_y:.1f} (height={child_height})")
                
                # Update tracking for this side - IMPROVED GAP to prevent overlaps
                # Calculate dynamic inter-branch gap based on branch complexity
                base_inter_branch_gap = 40  # Increased from 20px to prevent overlaps
                
                # Add extra spacing for branches with many children
                child_count_factor = min(len(nested_children), 4) * 5  # Up to 20px extra
                dynamic_gap = base_inter_branch_gap + child_count_factor
                
                logger.debug(f"  Inter-branch gap: base={base_inter_branch_gap}, child_factor={child_count_factor}, total={dynamic_gap}")
                
                if is_left_side:
                    left_children_y = current_y + block_height + dynamic_gap
                else:
                    right_children_y = current_y + block_height + dynamic_gap
                
                all_children_positions[i] = child_positions
                side_children.append((i, child_positions))
        
                logger.debug(f"  Next start position: {left_children_y if is_left_side else right_children_y}")
        
        # STEP 5: Position branch nodes using TARGETED MATHEMATICAL CENTER FIX
        for i, branch_data in enumerate(children):
            branch_text = branch_data['label']
            branch_font_size = self._get_adaptive_font_size(branch_text, 'branch')
            branch_width = self._calculate_text_width(branch_text, branch_font_size) + self._get_adaptive_padding(branch_text)
            branch_height = self._get_adaptive_node_height(branch_text, 'branch')
            
            # Determine side
            mid_point = num_branches // 2
            is_left_side = i >= mid_point
            
            # Position branch in correct column
            if is_left_side:
                branch_x = left_branches_x
            else:
                branch_x = right_branches_x
            
            # Get children for this branch
            branch_children = all_children_positions.get(i, [])
            
            # TARGETED FIX: Perfect mathematical center calculation
            if branch_children:
                # Calculate exact mathematical center of children
                children_y_positions = [child['y'] for child in branch_children]
                mathematical_center = sum(children_y_positions) / len(children_y_positions)
                
                # Also calculate visual bounding box center for comparison
                children_top_edges = [child['y'] - child['height']/2 for child in branch_children]
                children_bottom_edges = [child['y'] + child['height']/2 for child in branch_children]
                visual_top = min(children_top_edges)
                visual_bottom = max(children_bottom_edges)
                visual_center = (visual_top + visual_bottom) / 2
                
                # Use the mathematical center for perfect alignment
                branch_y = mathematical_center
                
                logger.debug(f"Branch {i} positioning analysis:")
                logger.debug(f"  Children Y positions: {children_y_positions}")
                logger.debug(f"  Mathematical center: {mathematical_center:.1f}")
                logger.debug(f"  Visual bounding box: {visual_top:.1f} to {visual_bottom:.1f}")
                logger.debug(f"  Visual center: {visual_center:.1f}")
                logger.debug(f"  Difference: {abs(mathematical_center - visual_center):.1f}px")
                logger.debug(f"  SELECTED: Mathematical center {branch_y:.1f}")
                
            else:
                # No children, use clockwise positioning
                branch_y = self._calculate_clockwise_branch_y(i, num_branches, is_left_side)
                logger.debug(f"Branch {i} (no children) positioned at Y={branch_y:.1f}")
            
            # Store branch position
            branch_data = {
                'x': branch_x, 'y': branch_y,
                'width': branch_width, 'height': branch_height,
                'text': branch_text, 'node_type': 'branch',
                'branch_index': i, 'angle': 0
            }
            logger.debug(f"  Storing branch {i}: {branch_data}")
            positions[f'branch_{i}'] = branch_data
            
            logger.debug(f"✅ Branch {i} stored at Y={branch_y:.1f}")
        
        # STEP 6: Early Overlap Prevention (Before Branch Alignment)
        # Fix overlaps in children positions before calculating final branch positions
        self._prevent_overlaps(positions)
        
        # STEP 6.1: Recalculate branch positions after overlap prevention
        # Update branch positions to match their children's final positions
        for i, branch_data in enumerate(children):
            branch_children = []
            for key, pos in positions.items():
                if (pos is not None and 
                    pos.get('node_type') == 'child' and 
                    pos.get('branch_index') == i):
                    branch_children.append(pos)
            
            if branch_children:
                # Recalculate mathematical center after overlap fixes
                children_y_positions = [child['y'] for child in branch_children]
                mathematical_center = sum(children_y_positions) / len(children_y_positions)
                
                # Update branch position
                branch_key = f'branch_{i}'
                if branch_key in positions and positions[branch_key] is not None:
                    old_y = positions[branch_key]['y']
                    positions[branch_key]['y'] = mathematical_center
                    logger.debug(f"🔄 Updated branch {i} position: {old_y:.1f} → {mathematical_center:.1f}")
        
        # STEP 6.2: Position central topic at vertical center of all subtopic nodes
        # Calculate the vertical center of all branch nodes (subtopics)
        branch_positions = [pos for pos in positions.values() if pos is not None and pos.get('node_type') == 'branch']
        
        if branch_positions:
            # Calculate vertical center of all branches using min/max range
            branch_y_positions = [pos['y'] for pos in branch_positions if pos is not None]
            min_branch_y = min(branch_y_positions)
            max_branch_y = max(branch_y_positions)
            topic_y = (min_branch_y + max_branch_y) / 2
            
            logger.debug(f"Topic center calculated at Y={topic_y:.1f}")
            logger.debug(f"Branch Y positions after overlap fixes: {branch_y_positions}")
            logger.debug(f"Min/Max branch Y: {min_branch_y:.1f} to {max_branch_y:.1f}")
            
            # STEP 6.3: Smart Middle Branch Horizontal Alignment
            # Apply strategic horizontal alignment for middle branches while preserving mathematical precision
            self._apply_middle_branch_horizontal_alignment(positions, topic_y, num_branches)
            
            # STEP 6.4: Final topic position calculation after middle branch alignment
            branch_positions = [pos for pos in positions.values() if pos is not None and pos.get('node_type') == 'branch']
            branch_y_positions = [pos['y'] for pos in branch_positions if pos is not None]
            min_branch_y = min(branch_y_positions)
            max_branch_y = max(branch_y_positions)
            topic_y = (min_branch_y + max_branch_y) / 2
            
            logger.debug(f"Final topic center after alignment: {topic_y:.1f}")
            logger.debug(f"Final branch Y positions: {branch_y_positions}")
            
            # STEP 6.5: Final overlap prevention after middle branch alignment
            # The middle branch alignment can create new cross-branch overlaps
            self._prevent_overlaps(positions)
            
            # STEP 6.6: Final branch repositioning after final overlap prevention
            # Recalculate branch positions one more time after any final overlap fixes
            for i, branch_data in enumerate(children):
                branch_children = []
                for key, pos in positions.items():
                    if (pos is not None and 
                        pos.get('node_type') == 'child' and 
                        pos.get('branch_index') == i):
                        branch_children.append(pos)
                
                if branch_children:
                    # Recalculate mathematical center after final overlap fixes
                    children_y_positions = [child['y'] for child in branch_children]
                    mathematical_center = sum(children_y_positions) / len(children_y_positions)
                    
                    # Update branch position
                    branch_key = f'branch_{i}'
                    if branch_key in positions and positions[branch_key] is not None:
                        old_y = positions[branch_key]['y']
                        positions[branch_key]['y'] = mathematical_center
                        logger.debug(f"🔧 Final branch {i} position update: {old_y:.1f} → {mathematical_center:.1f}")
            
            # STEP 6.7: Final topic position recalculation
            # Recalculate topic position based on final branch positions
            branch_positions = [pos for pos in positions.values() if pos is not None and pos.get('node_type') == 'branch']
            if branch_positions:
                branch_y_positions = [pos['y'] for pos in branch_positions if pos is not None]
                min_branch_y = min(branch_y_positions)
                max_branch_y = max(branch_y_positions)
                topic_y = (min_branch_y + max_branch_y) / 2
                logger.debug(f"🔧 Final topic Y after final branch repositioning: {topic_y:.1f}")
            
        else:
            # Fallback if no branches
            topic_y = 0
        
        # Calculate topic dimensions
        topic_font_size = self._get_adaptive_font_size(topic, 'topic')
        topic_width = self._calculate_text_width(topic, topic_font_size) + 40  # Extra padding for circles
        topic_height = self._get_adaptive_node_height(topic, 'topic')
        
        # Store topic position
        positions['topic'] = {
            'x': 0, 'y': topic_y,  # Centered horizontally, vertically among branches
            'width': topic_width, 'height': topic_height,
            'text': topic, 'node_type': 'topic', 'angle': 0
        }
        
        # STEP 7: Generate connection data
        connections = self._generate_connections(topic, children, positions)
        
        # STEP 8: Center all positions around (0,0) for proper D3 rendering
        if positions:
            # Calculate content center from all positioned elements
            x_coords = [pos.get('x', 0) for pos in positions.values() if pos is not None]
            y_coords = [pos.get('y', 0) for pos in positions.values() if pos is not None]
            
            if x_coords and y_coords:
                content_center_x = (min(x_coords) + max(x_coords)) / 2
                content_center_y = (min(y_coords) + max(y_coords)) / 2
            
            # Adjust all positions to center around (0,0)
            for key in positions:
                if positions[key] is not None:
                    positions[key]['x'] -= content_center_x
                    positions[key]['y'] -= content_center_y
        
        # STEP 9: Compute recommended dimensions AFTER all positioning and centering is complete
        recommended_dimensions = self._compute_recommended_dimensions(positions, topic, children)
        
        # Return complete layout
        return {
            'algorithm': 'clean_vertical_stack_with_horizontal_alignment',
            'positions': positions,
            'connections': connections,
            'params': {
                'leftChildrenX': left_children_x,
                'leftBranchesX': left_branches_x,
                'topicX': 0,
                'topicY': topic_y,
                'rightBranchesX': right_branches_x,
                'rightChildrenX': right_children_x,
                'numBranches': num_branches,
                'leftBranchCount': left_branch_count,
                'rightBranchCount': right_branch_count,
                'numChildren': sum(len(branch.get('children', [])) for branch in children),
                'baseWidth': recommended_dimensions['baseWidth'],
                'baseHeight': recommended_dimensions['baseHeight'],
                'width': recommended_dimensions['width'],
                'height': recommended_dimensions['height'],
                'padding': recommended_dimensions['padding'],
                'background': '#f5f5f5'
            }
        }
    
    def _apply_middle_branch_horizontal_alignment(self, positions: Dict, topic_y: float, num_branches: int) -> None:
        """
        Smart middle branch horizontal alignment while preserving mathematical precision.
        Only affects the middle branches on each side for perfect horizontal alignment.
        """
        logger.debug(f"🎯 Applying middle branch horizontal alignment")
        
        # Identify middle branches on each side
        middle_branches = self._identify_middle_branches(num_branches)
        
        logger.debug(f"Middle branches identified: {middle_branches}")
        
        # Apply horizontal alignment to middle branches
        for side, branch_index in middle_branches.items():
            branch_key = f'branch_{branch_index}'
            
            if branch_key in positions:
                branch_pos = positions[branch_key]
                if branch_pos is None:
                    logger.debug(f"⚠️ Branch position is None for {branch_key}")
                    continue
                    
                original_y = branch_pos.get('y', 0)
                
                # Apply horizontal alignment to topic center
                logger.debug(f"  Setting branch Y: {branch_pos} → {topic_y}")
                if branch_pos is None:
                    logger.error(f"  ERROR: branch_pos is None!")
                    continue
                branch_pos['y'] = topic_y
                
                # Calculate offset for children adjustment
                y_offset = topic_y - original_y
                
                # Adjust children positions to maintain visual balance
                self._adjust_children_positions(positions, branch_index, y_offset)
                
                logger.debug(f"✅ Middle branch {branch_index} ({side}): {original_y:.1f} → {topic_y:.1f} (offset: {y_offset:.1f})")
            else:
                logger.debug(f"⚠️ Middle branch {branch_index} not found in positions")
    
    def _identify_middle_branches(self, num_branches: int) -> Dict[str, int]:
        """
        Identify the true middle branch on each side.
        Returns dict with 'left' and 'right' keys pointing to branch indices.
        """
        mid_point = num_branches // 2
        
        # Right side: indices 0 to mid_point-1
        # Left side: indices mid_point to num_branches-1
        right_branches = list(range(0, mid_point))
        left_branches = list(range(mid_point, num_branches))
        
        middle_branches = {}
        
        if right_branches:
            # Find middle index of right side branches
            right_middle_idx = len(right_branches) // 2
            middle_branches['right'] = right_branches[right_middle_idx]
            logger.debug(f"Right side branches: {right_branches}, middle: {right_branches[right_middle_idx]}")
        
        if left_branches:
            # Find middle index of left side branches  
            left_middle_idx = len(left_branches) // 2
            middle_branches['left'] = left_branches[left_middle_idx]
            logger.debug(f"Left side branches: {left_branches}, middle: {left_branches[left_middle_idx]}")
        
        return middle_branches
    
    def _adjust_children_positions(self, positions: Dict, branch_index: int, y_offset: float) -> None:
        """
        Adjust children positions to maintain visual balance after branch alignment.
        After moving children, check for any new overlaps and fix them.
        """
        adjusted_count = 0
        adjusted_children = []
        
        for key, pos in positions.items():
            if (pos is not None and 
                pos.get('node_type') == 'child' and 
                pos.get('branch_index') == branch_index):
                
                old_y = pos.get('y', 0)
                pos['y'] = old_y + y_offset
                adjusted_count += 1
                adjusted_children.append(pos)
                
                logger.debug(f"    Adjusted child '{pos.get('text', 'unknown')}': {old_y:.1f} → {pos['y']:.1f}")
        
        logger.debug(f"  📝 Adjusted {adjusted_count} children by offset {y_offset:.1f}")
        
        # After adjusting children, fix any overlaps within this branch
        if len(adjusted_children) > 1:
            self._fix_intra_branch_overlaps(adjusted_children)
    
    def _fix_intra_branch_overlaps(self, children: List[Dict]) -> None:
        """Fix overlaps within a single branch after position adjustments."""
        # Sort children by Y position
        children.sort(key=lambda c: c['y'])
        
        # Ensure minimum spacing between consecutive children
        min_spacing = 50  # Minimum edge-to-edge distance
        
        for i in range(1, len(children)):
            prev_child = children[i-1]
            curr_child = children[i]
            
            # Calculate required minimum Y for current child
            prev_bottom = prev_child['y'] + prev_child['height']/2
            curr_top = curr_child['y'] - curr_child['height']/2
            
            # Check if overlap exists
            if curr_top < prev_bottom + min_spacing:
                # Move current child down to ensure minimum spacing
                required_y = prev_bottom + min_spacing + curr_child['height']/2
                old_y = curr_child['y']
                curr_child['y'] = required_y
                
                logger.debug(f"      Fixed intra-branch overlap: '{curr_child.get('text', 'child')}' {old_y:.1f} → {required_y:.1f}")
    
    def _generate_connections(self, topic: str, children: List[Dict], positions: Dict) -> List[Dict]:
        """Generate connection data for lines between nodes."""
        connections = []
        
        topic_pos = positions.get('topic', {})
        topic_x, topic_y = topic_pos.get('x', 0), topic_pos.get('y', 0)
        
        # Connections from topic to branches
        for i, child in enumerate(children):
            branch_key = f'branch_{i}'
            if branch_key in positions:
                branch_pos = positions[branch_key]
                branch_x, branch_y = branch_pos['x'], branch_pos['y']
                
                connections.append({
                    'type': 'topic_to_branch',
                    'from': {'x': topic_x, 'y': topic_y, 'type': 'topic'},
                    'to': {'x': branch_x, 'y': branch_y, 'type': 'branch'},
                    'branch_index': i,
                    'stroke_width': 3,
                    'stroke_color': '#000000'  # Black connection for better visibility
                })
                
                # Connections from branch to children
                nested_children = child.get('children', [])
                for j, nested_child in enumerate(nested_children):
                    child_key = f'child_{i}_{j}'
                    if child_key in positions:
                        child_pos = positions[child_key]
                        child_x, child_y = child_pos['x'], child_pos['y']
                        
                        connections.append({
                            'type': 'branch_to_child',
                            'from': {'x': branch_x, 'y': branch_y, 'type': 'branch'},
                            'to': {'x': child_x, 'y': child_y, 'type': 'child'},
                            'branch_index': i,
                            'child_index': j,
                            'stroke_width': 2,
                            'stroke_color': '#000000'  # Black connection for better visibility
                        })
        
        return connections
    
    def _compute_recommended_dimensions(self, positions: Dict, topic: str, children: List[Dict]) -> Dict:
        """Compute recommended canvas dimensions based on content."""
        if not positions:
            return {"baseWidth": 800, "baseHeight": 600, "width": 800, "height": 600, "padding": 80}
        
        # Calculate bounds including node dimensions
        all_x = [pos['x'] for pos in positions.values()]
        all_y = [pos['y'] for pos in positions.values()]
        all_widths = [pos['width'] for pos in positions.values()]
        all_heights = [pos['height'] for pos in positions.values()]
        
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        max_width = max(all_widths)
        max_height = max(all_heights)
        
        # Calculate content dimensions CORRECTLY
        # For width: from leftmost node edge to rightmost node edge
        # For height: from topmost node edge to bottommost node edge
        content_width = (max_x + max_width/2) - (min_x - max_width/2)
        content_height = (max_y + max_height/2) - (min_y - max_height/2)
        
        # Add generous padding to prevent cutting off
        # Increase padding for height to account for vertical stacking
        padding_x = 140
        padding_y = 200  # Increased vertical padding to prevent cutting off
        
        total_width = content_width + (padding_x * 2)
        total_height = content_height + (padding_y * 2)
        
        # Ensure minimum dimensions
        total_width = max(total_width, 1000)  # Increased minimum width
        total_height = max(total_height, 800)  # Increased minimum height
        
        # Canvas calculation completed
        
        return {
            "baseWidth": total_width,
            "baseHeight": total_height,
            "width": total_width,
            "height": total_height,
            "padding": max(padding_x, padding_y)  # Use the larger padding value
        }
    
    def _get_adaptive_font_size(self, text: str, node_type: str) -> int:
        """Get adaptive font size based on text length and node type."""
        # Use cache key to avoid recalculating
        cache_key = (text, node_type)
        if cache_key in self._font_size_cache:
            return self._font_size_cache[cache_key]
        
        text_length = len(text)
        
        if node_type == 'topic':
            if text_length <= 10:
                font_size = 28
            elif text_length <= 20:
                font_size = 24
            else:
                font_size = 20
        elif node_type == 'branch':
            if text_length <= 8:
                font_size = 20
            elif text_length <= 15:
                font_size = 18
            else:
                font_size = 16
        else:  # child
            if text_length <= 6:
                font_size = 16
            elif text_length <= 12:
                font_size = 14
            else:
                font_size = 12
        
        # Cache the result
        self._font_size_cache[cache_key] = font_size
        return font_size
    
    def _get_adaptive_node_height(self, text: str, node_type: str) -> int:
        """Get adaptive node height based on text length and node type."""
        # Use cache key to avoid recalculating
        cache_key = (text, node_type)
        if cache_key in self._node_height_cache:
            return self._node_height_cache[cache_key]
        
        text_length = len(text)
        
        if node_type == 'topic':
            if text_length <= 10:
                height = 70
            elif text_length <= 20:
                height = 60
            else:
                height = 50
        elif node_type == 'branch':
            if text_length <= 8:
                height = 60
            elif text_length <= 15:
                height = 50
            else:
                height = 45
        else:  # child
            if text_length <= 6:
                height = 45
            elif text_length <= 12:
                height = 40
            else:
                height = 35
        
        # Cache the result
        self._node_height_cache[cache_key] = height
        return height
    
    def _calculate_text_width(self, text: str, font_size: int) -> float:
        """Calculate estimated text width based on font size."""
        if not text:
            return 0
        
        # Use cache key to avoid expensive character-by-character calculation
        cache_key = (text, font_size)
        if cache_key in self._text_width_cache:
            return self._text_width_cache[cache_key]
        
        # More accurate text width calculation
        # Different character types have different widths
        total_width = 0
        for char in text:
            if char.isupper():
                # Uppercase letters are wider
                char_width = font_size * 0.8
            elif char.islower():
                # Lowercase letters are narrower
                char_width = font_size * 0.6
            elif char.isdigit():
                # Numbers are medium width
                char_width = font_size * 0.7
            elif char in '.,;:!?':
                # Punctuation is narrow
                char_width = font_size * 0.3
            elif char in 'MW':
                # Wide characters
                char_width = font_size * 1.0
            elif char in 'il|':
                # Narrow characters
                char_width = font_size * 0.3
            else:
                # Default for other characters
                char_width = font_size * 0.7
            
            total_width += char_width
        
        # Add a small amount for character spacing
        total_width += len(text) * 2
        
        # Cache the result
        self._text_width_cache[cache_key] = total_width
        return total_width
    
    def _get_adaptive_padding(self, text: str) -> int:
        """Get adaptive padding based on text length."""
        text_length = len(text)
        if text_length <= 5:
            return 30  # Increased padding
        elif text_length <= 10:
            return 35  # Increased padding
        elif text_length <= 15:
            return 40  # Increased padding
        else:
            return 45  # Increased padding
    
    def _analyze_branch_content(self, children: List[Dict]) -> Dict[str, Any]:
        """Analyze branch characteristics for optimal spacing."""
        total_children = len(children)
        avg_text_length = sum(len(child['label']) for child in children) / total_children if children else 0
        
        # Classify branch density
        if total_children <= 2:
            density_type = "sparse"
            base_factor = 1.2  # More spacing for sparse content
        elif total_children <= 4:
            density_type = "normal"
            base_factor = 1.0  # Standard spacing
        else:
            density_type = "dense"
            base_factor = 0.85  # Tighter spacing for dense content
        
        return {
            'density_type': density_type,
            'base_factor': base_factor,
            'child_count': total_children,
            'avg_text_length': avg_text_length
        }
    
    def _calculate_optimal_spacing(self, children: List[Dict], child_heights: List[int]) -> int:
        """Calculate spacing that creates consistent visual density with center-to-center rhythm."""
        if not children or not child_heights:
            return 55  # Default spacing
        
        # Base spacing for visual rhythm (center-to-center distance)
        base_spacing = 55
        
        # Analyze branch content for density adjustment
        content_analysis = self._analyze_branch_content(children)
        density_factor = content_analysis['base_factor']
        
        # Normalize for height variations - aim for consistent visual gaps
        avg_height = sum(child_heights) / len(child_heights)
        standard_height = 45  # Reference height for normalization
        height_factor = standard_height / avg_height if avg_height > 0 else 1.0
        
        # Calculate final spacing with bounds checking
        optimal_spacing = int(base_spacing * density_factor * height_factor)
        
        # Ensure spacing stays within reasonable bounds
        min_spacing = 45  # Increased from 35px to prevent overlaps 
        max_spacing = 85  # Increased from 75px to accommodate larger spacing
        
        final_spacing = max(min_spacing, min(max_spacing, optimal_spacing))
        
        logger.debug(f"    Spacing calculation: base={base_spacing}, density={density_factor:.2f}, height={height_factor:.2f}, final={final_spacing}")
        
        return final_spacing
    
    def _get_adaptive_spacing(self, num_children: int) -> int:
        """Legacy method - now redirects to optimal spacing calculation."""
        # This method is kept for backward compatibility but is no longer used directly
        if num_children <= 2:
            return 20
        elif num_children <= 4:
            return 18
        elif num_children <= 6:
            return 15
        else:
            return 12
    
    def _calculate_clockwise_branch_y(self, branch_index: int, total_branches: int, is_left_side: bool) -> float:
        """
        Calculate Y position for branch using clockwise positioning system.
        
        Clockwise positioning with corrected side distribution:
        - Branch 1,2,3... (first half): RIGHT side (top to bottom)
        - Branch 4,5,6... (second half): LEFT side (top to bottom)
        
        For 6 branches: Branch 1,2,3 → RIGHT, Branch 4,5,6 → LEFT
        For 8 branches: Branch 1,2,3,4 → RIGHT, Branch 5,6,7,8 → LEFT
        """
        mid_point = total_branches // 2
        
        if is_left_side:
            # LEFT side branches (second half)
            # Calculate position within left side (0 = first left branch)
            left_index = branch_index - mid_point
            
            if total_branches <= 4:
                # 4 branches: Branch 3,4 → LEFT
                if left_index == 0:  # Branch 3 (Lower Left)
                    return -200
                else:  # Branch 4 (Top Left)
                    return 200
            elif total_branches <= 6:
                # 6 branches: Branch 4,5,6 → LEFT
                if left_index == 0:  # Branch 4 (Lower Left, top)
                    return -150
                elif left_index == 1:  # Branch 5 (Lower Left, bottom)
                    return -250
                else:  # Branch 6 (Top Left)
                    return 200
            elif total_branches <= 8:
                # 8 branches: Branch 5,6,7,8 → LEFT
                if left_index == 0:  # Branch 5 (Lower Left, top)
                    return -200
                elif left_index == 1:  # Branch 6 (Lower Left, bottom)
                    return -300
                elif left_index == 2:  # Branch 7 (Top Left, top)
                    return 300
                else:  # Branch 8 (Top Left, bottom)
                    return 200
            else:
                # For 9+ branches, use dynamic positioning
                base_y = 200
                spacing = 100
                return -base_y + (left_index * spacing)
        else:
            # RIGHT side branches (first half)
            # Calculate position within right side (0 = first right branch)
            right_index = branch_index
            
            if total_branches <= 4:
                # 4 branches: Branch 1,2 → RIGHT
                if right_index == 0:  # Branch 1 (Top Right)
                    return 200
                else:  # Branch 2 (Lower Right)
                    return -200
            elif total_branches <= 6:
                # 6 branches: Branch 1,2,3 → RIGHT
                if right_index == 0:  # Branch 1 (Top Right, top)
                    return 250
                elif right_index == 1:  # Branch 2 (Top Right, bottom)
                    return 150
                else:  # Branch 3 (Lower Right)
                    return -200
            elif total_branches <= 8:
                # 8 branches: Branch 1,2,3,4 → RIGHT
                if right_index == 0:  # Branch 1 (Top Right, top)
                    return 300
                elif right_index == 1:  # Branch 2 (Top Right, bottom)
                    return 200
                elif right_index == 2:  # Branch 3 (Lower Right, top)
                    return -200
                else:  # Branch 4 (Lower Right, bottom)
                    return -300
            else:
                # For 9+ branches, use dynamic positioning
                base_y = 200
                spacing = 100
                return base_y - (right_index * spacing)
    
    def _generate_empty_layout(self, topic: str) -> Dict:
        """Generate empty layout for edge cases."""
        return {
            'algorithm': 'empty',
            'positions': {'topic': {'x': 0, 'y': 0, 'width': 100, 'height': 50, 'text': topic, 'node_type': 'topic'}},
            'connections': [],
            'params': {'numBranches': 0, 'numChildren': 0}
        }
    
    def _generate_error_layout(self, topic: str, error_msg: str) -> Dict:
        """Generate error layout for error cases."""
        return {
            'algorithm': 'empty',
            'positions': {'topic': {'x': 0, 'y': 0, 'width': 100, 'height': 50, 'text': topic, 'node_type': 'topic'}},
            'connections': [],
            'params': {'error': error_msg, 'numBranches': 0, 'numChildren': 0}
        }
    
    # Removed deprecated _get_middle_branch_y_positions method - no longer needed
    
    def _prevent_overlaps(self, positions: Dict) -> None:
        """
        Post-processing step to detect and fix any remaining overlaps.
        This is a safety net to ensure no overlaps exist after positioning.
        """
        logger.debug("🔧 Running post-processing overlap prevention")
        
        # Get all non-null positions
        all_positions = [(key, pos) for key, pos in positions.items() if pos is not None]
        
        overlap_fixes = 0
        max_iterations = 5  # Increased to handle complex overlaps
        
        for iteration in range(max_iterations):
            overlaps_found = []
            
            # Detect overlaps
            for i, (key1, pos1) in enumerate(all_positions):
                for j, (key2, pos2) in enumerate(all_positions[i+1:], i+1):
                    if self._nodes_overlap(pos1, pos2):
                        overlaps_found.append((key1, pos1, key2, pos2))
            
            if not overlaps_found:
                logger.debug(f"✅ No overlaps found after {iteration} iterations")
                break
            
            logger.debug(f"🔧 Iteration {iteration + 1}: Found {len(overlaps_found)} overlaps")
            
            # Fix overlaps by adjusting Y positions
            for key1, pos1, key2, pos2 in overlaps_found:
                # Fix all child-child overlaps (both same-branch and cross-branch)
                if (pos1.get('node_type') == 'child' and pos2.get('node_type') == 'child'):
                    
                    # Calculate minimal separation needed based on content
                    # Use larger separation for longer text to prevent visual crowding
                    text1_length = len(pos1.get('text', ''))
                    text2_length = len(pos2.get('text', ''))
                    avg_text_length = (text1_length + text2_length) / 2
                    
                    # Dynamic minimum separation based on text length
                    base_separation = 60  # Increased base separation
                    text_factor = min(avg_text_length * 2, 30)  # Up to 30px extra for long text
                    min_separation = base_separation + text_factor
                    
                    # Determine which node to move (prefer moving the lower one down)
                    if pos1['y'] > pos2['y']:
                        # Move pos1 down
                        required_move = (pos2['y'] + pos2['height']/2) + min_separation - (pos1['y'] - pos1['height']/2)
                        if required_move > 0:
                            pos1['y'] += required_move
                            overlap_fixes += 1
                            logger.debug(f"  Fixed overlap: moved '{pos1.get('text', 'node')}' down by {required_move:.1f}px (min_sep={min_separation:.1f}px)")
                    else:
                        # Move pos2 down
                        required_move = (pos1['y'] + pos1['height']/2) + min_separation - (pos2['y'] - pos2['height']/2)
                        if required_move > 0:
                            pos2['y'] += required_move
                            overlap_fixes += 1
                            logger.debug(f"  Fixed overlap: moved '{pos2.get('text', 'node')}' down by {required_move:.1f}px (min_sep={min_separation:.1f}px)")
        
        if overlap_fixes > 0:
            logger.debug(f"🔧 Applied {overlap_fixes} overlap fixes")
        else:
            logger.debug(f"✅ No overlap fixes needed")
    
    def _get_max_branches(self) -> int:
        """Get maximum number of branches allowed."""
        return 20  # Reasonable limit for mind maps
