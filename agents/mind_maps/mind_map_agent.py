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

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import logging
import traceback

from agents.core.base_agent import BaseAgent
from agents.core.agent_utils import extract_json_from_response
from config.settings import Config
from prompts import get_prompt
from services.llm import llm_service


logger = logging.getLogger(__name__)



@dataclass
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

    # Maximum text widths before wrapping (must match JavaScript renderer)
    # JavaScript: branchMaxTextWidth = 200, childMaxTextWidth = 180
    MAX_BRANCH_TEXT_WIDTH = 200
    MAX_CHILD_TEXT_WIDTH = 180
    # Padding values (must match JavaScript renderer)
    BRANCH_PADDING = 24  # JavaScript uses 24px padding for branches
    CHILD_PADDING = 20   # JavaScript uses 20px padding for children

    def __init__(self, model='qwen'):
        super().__init__(model=model)
        self.config = Config()
        self.diagram_type = "mindmap"
        # Cache for expensive font calculations
        self._text_width_cache = {}
        self._font_size_cache = {}
        self._node_height_cache = {}

    def _clear_caches(self) -> None:
        """Clear font calculation caches to prevent memory bloat."""
        self._text_width_cache.clear()
        self._font_size_cache.clear()
        self._node_height_cache.clear()

    def _get_node_text(self, node: Dict, default: str = '') -> str:
        """
        Safely extract text from a node that may have 'label' or 'text' field.

        Root cause: LLM responses sometimes use 'label', sometimes 'text'.
        This helper ensures we handle both cases gracefully.

        Args:
            node: Node dictionary that may have 'label' or 'text' key
            default: Default value if neither key exists

        Returns:
            Text content from node
        """
        if not isinstance(node, dict):
            return default

        # Try 'label' first (standard format), then 'text' (fallback)
        return node.get('label') or node.get('text') or default

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
            # Clear caches at the start of each generation
            self._clear_caches()            # Generate the initial mind map specification
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
                # If this was a partial recovery attempt, enhance the error message
                if recovery_warnings:
                    error_msg = f'Partial recovery attempted but validation failed: {validation_msg}. Original LLM response had issues.'
                else:
                    error_msg = f'Generated invalid specification: {validation_msg}'
                return {
                    'success': False,
                    'error': error_msg
                }

            # Enhance the spec with layout and dimensions
            enhanced_spec = await self.enhance_spec(spec)

            logger.info("MindMapAgent: Successfully generated mind map")
            result = {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }

            # Add recovery warnings if present
            if recovery_warnings:
                result['warning'] = 'LLM response had issues. Some branches may be missing. You can use auto-complete to add more.'
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
            # Get prompt from centralized system
            system_prompt = get_prompt("mind_map", language, "generation")

            if not system_prompt:
                logger.error("MindMapAgent: No prompt found for language %s", language)
                return None, None

            user_prompt = (
                f"请为以下描述创建一个思维导图：{prompt}"
                if language == "zh"
                else f"Please create a mind map for the following description: {prompt}"
            )

            # Call middleware directly - clean and efficient!
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=1.0,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='mind_map'
            )

            if not response:
                logger.error("MindMapAgent: No response from LLM")
                return None, None

            # Extract JSON from response
            # Check if response is already a dictionary (from mock client)
            recovery_warnings = None
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response with partial recovery enabled
                response_str = str(response)
                spec = extract_json_from_response(response_str, allow_partial=True)

                if not spec:
                    # Log the actual response for debugging with more context
                    response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                    logger.error("MindMapAgent: Failed to extract JSON from LLM response")
                    logger.error("MindMapAgent: Response length: %s, Preview: %s", len(response_str), response_preview)
                    logger.error("MindMapAgent: This may indicate LLM returned invalid JSON or non-JSON response")
                    # Return None to trigger error handling upstream
                    return None, None

                # Check if this was a partial recovery
                if spec.get("_partial_recovery"):
                    warnings = spec.get("_recovery_warnings", [])
                    recovered_count = spec.get("_recovered_count", 0)
                    logger.warning(
                        "MindMapAgent: Partial JSON recovery succeeded. Recovered %s branches. Warnings: %s",
                        recovered_count,
                        ', '.join(warnings)
                    )
                    # Store warnings to return separately
                    recovery_warnings = warnings
                    # Remove metadata fields before returning (they'll be added to response separately)
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

            for _key, pos in positions.items():
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
                for _j, pos2 in enumerate(all_positions[i+1:], i+1):
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
        except (KeyError, TypeError, ValueError):
            return False

    async def enhance_spec(self, spec: Dict) -> Dict:
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
            logger.debug("Layout geometry validation: %s", validation_summary)
            if validation_details:
                for detail in validation_details:
                    if detail.startswith("CRITICAL") or detail.startswith("WARNING") or detail.startswith("OVERLAP"):
                        logger.warning("  %s", detail)
                    else:
                        logger.debug("  %s", detail)

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
            logger.error("MindMapAgent error: %s", e)
            logger.error("Traceback: %s", traceback.format_exc())
            return {"success": False, "error": f"MindMapAgent failed: {e}"}

    def _generate_mind_map_layout(self, topic: str, children: List[Dict]) -> Dict:
        """
        Generate mind map layout using SIMPLE BALANCED LAYOUT SYSTEM:

        CORE PRINCIPLES:
        1. Always even number of branches (enforced by LLM prompts)
        2. Clean left/right split (first half → right, second half → left)
        3. Height balancing with intelligent padding
        4. Mathematical branch centering (perfect alignment guaranteed)
        5. Central topic at (0,0) for natural visual balance

        SIMPLE WORKFLOW:
        1. Split branches evenly between left and right sides
        2. Stack children vertically on each side with consistent spacing
        3. Balance side heights using padding to shorter side
        4. Position branches at mathematical centers of their children
        5. Place central topic at (0,0) - perfect balance achieved
        """
        logger.debug("Starting simple balanced layout for %s branches", len(children))

        # Initialize positions dictionary
        positions = {}
        num_branches = len(children)

        if num_branches == 0:
            return self._generate_empty_layout(topic)

        # STEP 1: Calculate column positions (same as before for consistency)
        gap_topic_to_branch = 200  # Space between topic and branches
        gap_branch_to_child = 120   # Space between branches and children

        # Calculate maximum dimensions
        max_branch_width = 0
        max_child_width = 0

        for branch in children:
            # Use capped width to prevent excessively wide nodes for long text
            # Use helper function to safely get text (handles both 'label' and 'text' fields)
            branch_label = self._get_node_text(branch)
            if not branch_label:
                logger.warning("Branch missing 'label' and 'text' keys: %s", branch)
                continue
            branch_width = self._get_capped_node_width(branch_label, 'branch')
            max_branch_width = max(max_branch_width, branch_width)

            for child in branch.get('children', []):
                # Use capped width to prevent excessively wide nodes for long text
                # Use helper function to safely get text (handles both 'label' and 'text' fields)
                child_label = self._get_node_text(child)
                if not child_label:
                    logger.warning("Child node missing 'label' and 'text' keys: %s", child)
                    continue
                child_width = self._get_capped_node_width(child_label, 'child')
                max_child_width = max(max_child_width, child_width)

        # Column positions
        left_children_x = -(gap_topic_to_branch + max_branch_width + gap_branch_to_child + max_child_width/2)
        left_branches_x = -(gap_topic_to_branch + max_branch_width/2)
        right_branches_x = gap_topic_to_branch + max_branch_width/2
        right_children_x = gap_topic_to_branch + max_branch_width + gap_branch_to_child + max_child_width/2

        logger.debug(
            "Column positions: Left Children=%.1f, Left Branches=%.1f, "
            "Right Branches=%.1f, Right Children=%.1f",
            left_children_x, left_branches_x, right_branches_x, right_children_x
        )

        # STEP 2: Simple Balanced Layout System
        layout_result = self._simple_balanced_layout(children, left_children_x, right_children_x, left_branches_x, right_branches_x)

        # Use the result from simple balanced system
        positions = layout_result['positions'].copy()

        # Add central topic at Y=0 (two-stage system positions everything relative to Y=0)
        topic_width = self._get_capped_node_width(topic, 'topic')
        topic_height = self._get_adaptive_node_height(topic, 'topic')

        positions['topic'] = {
            'x': 0, 'y': 0,  # Central topic always at origin
            'width': topic_width, 'height': topic_height,
            'text': topic, 'node_type': 'topic', 'angle': 0
        }

        logger.debug("Two-stage system completed, topic added at (0, 0)")

        # STEP 3: Center all positions around (0,0) for proper D3 rendering
        # Keep topic fixed at (0, 0) as visual anchor, only center branches/children
        content_center_x = 0
        content_center_y = 0
        try:
            if positions:
                # Calculate content center from all positioned elements EXCEPT topic
                x_coords = [pos.get('x', 0) for pos in positions.values() if pos is not None]
                y_coords = [pos.get('y', 0) for pos in positions.values() if pos is not None]

                if x_coords and y_coords:
                    # For mind maps, keep topic fixed at (0, 0) and only center branches/children
                    # Calculate center from all positions EXCEPT topic
                    non_topic_x_coords = [pos.get('x', 0) for key, pos in positions.items()
                                         if pos is not None and key != 'topic']
                    non_topic_y_coords = [pos.get('y', 0) for key, pos in positions.items()
                                         if pos is not None and key != 'topic']

                    if non_topic_x_coords and non_topic_y_coords:
                        content_center_x = (min(non_topic_x_coords) + max(non_topic_x_coords)) / 2
                        content_center_y = (min(non_topic_y_coords) + max(non_topic_y_coords)) / 2
                    else:
                        # Fallback: use all coordinates if no non-topic positions
                        content_center_x = (min(x_coords) + max(x_coords)) / 2
                        content_center_y = (min(y_coords) + max(y_coords)) / 2

                    # Adjust all positions EXCEPT topic to center around (0,0)
                    # Topic stays fixed at (0, 0) as the visual anchor
                    # CRITICAL: Modify positions dictionary in place so connections read updated values
                    adjusted_count = 0
                    for key, pos_value in positions.items():
                        if pos_value is not None and key != 'topic':
                            pos_value['x'] -= content_center_x
                            pos_value['y'] -= content_center_y
                            adjusted_count += 1

                    logger.debug(
                        "Centered %s positions (topic kept at origin): "
                        "offset X=%.1f, Y=%.1f",
                        adjusted_count, content_center_x, content_center_y
                    )
                else:
                    logger.debug("Centering skipped: no valid coordinates")
            else:
                logger.warning("Positions dict is empty or None!")
        except Exception as e:
            logger.error("ERROR in centering step: %s", e)
            logger.error("Traceback: %s", traceback.format_exc())

        # STEP 4: Generate connection data AFTER all positions are finalized and centered
        # Since all node positions are now finalized, we can directly read coordinates from positions
        # This ensures connections perfectly align with node positions
        # IMPORTANT: positions dictionary has been modified in place, so connections will read centered coordinates
        connections = self._generate_connections(topic, children, positions)

        # STEP 5: Compute recommended dimensions
        recommended_dimensions = self._compute_recommended_dimensions(positions, topic, children)

        logger.debug("🎉 SIMPLE BALANCED LAYOUT - Layout complete!")

        # Return complete layout
        return {
            'algorithm': 'simple_balanced_layout',
            'positions': positions,
            'connections': connections,
            'params': {
                'leftChildrenX': left_children_x,
                'leftBranchesX': left_branches_x,
                'topicX': 0,
                'topicY': 0,  # Always at center
                'rightBranchesX': right_branches_x,
                'rightChildrenX': right_children_x,
                'numBranches': num_branches,
                'numChildren': sum(len(branch.get('children', [])) for branch in children),
                'baseWidth': recommended_dimensions['baseWidth'],
                'baseHeight': recommended_dimensions['baseHeight'],
                'width': recommended_dimensions['width'],
                'height': recommended_dimensions['height'],
                'padding': recommended_dimensions['padding'],
                'background': '#f5f5f5'
            }
        }

    def _simple_balanced_layout(self, children: List[Dict], left_children_x: float, right_children_x: float, left_branches_x: float, right_branches_x: float) -> Dict:
        """
        Simple balanced layout system with parent nodes centered on children height centers.

        NEW WORKFLOW:
        1. Clean left/right split of branches
        2. Stack children vertically (no auto-centering)
        3. Calculate branch positions at children height centers
        4. Calculate left/right branch height centers and translate to origin
        5. Translate all nodes (branches + children) together
        """
        logger.debug("📍 Simple balanced layout: Processing %s branches", len(children))

        num_branches = len(children)
        is_odd = num_branches % 2 != 0

        if is_odd:
            logger.debug(
                "Odd number of branches (%s) detected - will handle uneven distribution",
                num_branches
            )

        # STEP 1: Clean left/right split with clockwise ordering
        # For odd numbers: put more branches on the right side
        # Example: 5 branches → right: 3, left: 2
        mid_point = (num_branches + 1) // 2  # For odd: rounds up, so right gets more
        right_branches = children[:mid_point]      # First half → RIGHT side (keep original order)
        left_branches = children[mid_point:][::-1]  # Second half → LEFT side (reverse for clockwise)

        logger.debug("Split: %s right branches, %s left branches (clockwise layout)", len(right_branches), len(left_branches))
        if is_odd:
            logger.debug("  Note: Odd distribution - right side has %s, left side has %s", len(right_branches), len(left_branches))

        # STEP 2: Stack children vertically on each side (no auto-centering)
        right_positions = self._stack_children_vertically(right_branches, right_children_x, "right", num_branches)
        left_positions = self._stack_children_vertically(left_branches, left_children_x, "left", num_branches)

        # Combine child positions
        all_child_positions = {}
        all_child_positions.update(left_positions)
        all_child_positions.update(right_positions)

        # STEP 3: Calculate branch positions at children height centers
        branch_positions = self._position_branches_at_mathematical_centers(
            children, all_child_positions, left_branches_x, right_branches_x, mid_point
        )

        # STEP 4: Calculate left/right branch height centers and translate to origin
        all_positions = {}
        all_positions.update(all_child_positions)
        all_positions.update(branch_positions)

        # Translate left and right sides to center at origin
        all_positions = self._translate_sides_to_origin(
            all_positions, children, left_branches_x, right_branches_x, mid_point
        )

        logger.debug("Simple layout complete: %s total positions", len(all_positions))

        return {
            'positions': all_positions,
            'algorithm': 'simple_balanced_layout'
        }

    def _stack_children_vertically(self, branches: List[Dict], column_x: float, side: str, num_branches: int) -> Dict:
        """
        Stack all children from multiple branches vertically on one side.
        Starts from a fixed position (not auto-centered).

        Args:
            branches: List of branches on this side
            column_x: X coordinate for this column
            side: "right" or "left"
            num_branches: Total number of branches (needed for clockwise index mapping)
        """
        positions = {}
        # Start from a fixed position (will be translated later)
        current_y = 0

        logger.debug("Stacking children on %s side at X=%s", side, column_x)

        # Collect all children from all branches on this side
        # For clockwise ordering: right side children in original order, left side children reversed
        all_children = []
        for branch_idx, branch in enumerate(branches):
            branch_children = branch.get('children', [])

            # For clockwise reading: left side children should be reversed
            # Right side: read top to bottom (original order)
            # Left side: read bottom to top (reversed order) for clockwise flow
            if side == "left":
                branch_children = branch_children[::-1]  # Reverse for clockwise

            for child_idx, child in enumerate(branch_children):
                # Calculate actual branch index in original children list
                if side == "right":
                    actual_branch_idx = branch_idx  # Right side: indices 0, 1, 2...
                    # Child index matches original order
                    original_child_idx = child_idx
                else:
                    # Left side: reversed list, so map back to original index
                    # Formula: actual_branch_idx = num_branches - 1 - branch_idx
                    # Example: 6 branches, branch_idx=0 → actual_branch_idx=5 (last branch)
                    actual_branch_idx = num_branches - 1 - branch_idx
                    # Map reversed child index back to original
                    # If we reversed [c0, c1, c2] → [c2, c1, c0], then child_idx=0 maps to original_idx=2
                    original_child_count = len(branch.get('children', []))
                    original_child_idx = original_child_count - 1 - child_idx

                child_info = {
                    'branch_idx': actual_branch_idx,
                    'child_idx': original_child_idx,  # Use original index for key generation
                    'data': child,
                    'side': side
                }
                all_children.append(child_info)

        # Calculate dynamic spacing based on actual font sizes
        if all_children:
            font_sizes = []
            for child_info in all_children:
                child_text = self._get_node_text(child_info['data'])
                child_font_size = self._get_adaptive_font_size(child_text, 'child')
                font_sizes.append(child_font_size)
            avg_font_size = sum(font_sizes) / len(font_sizes)

            # Dynamic spacing: 6px base + 0.3x average font size (scales with font changes)
            child_spacing = max(6, int(6 + avg_font_size * 0.3))
            logger.debug("Dynamic spacing: %spx (based on avg font size %.1f)", child_spacing, avg_font_size)
        else:
            child_spacing = 8  # Fallback for empty case

        # Calculate dimensions and positions for all children
        for i, child_info in enumerate(all_children):
            child_data = child_info['data']
            child_text = self._get_node_text(child_data)
            # Use capped width to prevent excessively wide nodes for long text
            child_width = self._get_capped_node_width(child_text, 'child')
            child_height = self._get_adaptive_node_height(child_text, 'child')

            child_key = f"child_{child_info['branch_idx']}_{child_info['child_idx']}"

            positions[child_key] = {
                'x': column_x, 'y': current_y,
                'width': child_width, 'height': child_height,
                'text': child_text, 'node_type': 'child',
                'branch_index': child_info['branch_idx'],
                'child_index': child_info['child_idx'], 'angle': 0
            }

            # Move to next position with dynamic spacing
            if i < len(all_children) - 1:
                next_child_info = all_children[i + 1]
                next_child_text = self._get_node_text(next_child_info['data'])
                next_child_height = self._get_adaptive_node_height(next_child_text, 'child')

                # Check if next child is from a different branch group
                current_branch = child_info['branch_idx']
                next_branch = next_child_info['branch_idx']

                if current_branch != next_branch:
                    # Triple spacing between different branch groups
                    spacing_multiplier = 3.0
                    gap_type = "group"
                    logger.debug(
                        "Branch group boundary: %s → %s, using triple spacing",
                        current_branch, next_branch
                    )
                else:
                    # Normal spacing within same branch group
                    spacing_multiplier = 1.0
                    gap_type = "normal"

                # Calculate spacing with multiplier
                base_gap = child_spacing * spacing_multiplier
                center_to_center = (child_height / 2) + base_gap + (next_child_height / 2)
                current_y += center_to_center

                if i == 0 or gap_type == "group":  # Log spacing details for first gap and group boundaries
                    logger.debug("%s gap: %.1f + %.1f + %.1f = %.1fpx", gap_type.capitalize(), child_height/2, base_gap, next_child_height/2, center_to_center)

        logger.debug("Stacked %s children on %s side", len(all_children), side)
        return positions

    def _balance_side_heights(self, left_positions: Dict, right_positions: Dict) -> Dict:
        """
        Balance the heights of left and right sides by adding padding to the shorter side.
        """
        # Calculate total heights of each side
        if left_positions:
            left_y_values = [pos['y'] for pos in left_positions.values()]
            left_heights = [pos['height'] for pos in left_positions.values()]
            left_total_height = (
                max(left_y_values) + max(left_heights)/2 -
                (min(left_y_values) - max(left_heights)/2)
            )
        else:
            left_total_height = 0

        if right_positions:
            right_y_values = [pos['y'] for pos in right_positions.values()]
            right_heights = [pos['height'] for pos in right_positions.values()]
            right_total_height = (
                max(right_y_values) + max(right_heights)/2 -
                (min(right_y_values) - max(right_heights)/2)
            )
        else:
            right_total_height = 0

        height_diff = abs(left_total_height - right_total_height)

        logger.debug("Height balance: Left=%.1f, Right=%.1f, Diff=%.1f", left_total_height, right_total_height, height_diff)

        # Add padding to shorter side by shifting positions
        balanced_positions = {}
        balanced_positions.update(left_positions)
        balanced_positions.update(right_positions)

        if height_diff > 10:  # Only apply padding if significant difference
            padding = height_diff / 2

            if left_total_height < right_total_height:
                # Left side is shorter, add padding (shift down)
                for key, pos in left_positions.items():
                    balanced_positions[key]['y'] += padding
                logger.debug("Added %.1fpx padding to left side", padding)
            else:
                # Right side is shorter, add padding (shift down)
                for key, pos in right_positions.items():
                    balanced_positions[key]['y'] += padding
                logger.debug("Added %.1fpx padding to right side", padding)

        # Center both sides around Y=0 while preserving spacing
        if balanced_positions:
            all_y = [pos['y'] for pos in balanced_positions.values()]
            center_offset = (max(all_y) + min(all_y)) / 2

            for pos in balanced_positions.values():
                pos['y'] -= center_offset

            logger.debug("Centered all children around Y=0 (offset: %.1f)", center_offset)

            # Verify no overlaps after centering
            positions_list = list(balanced_positions.values())
            overlaps_detected = 0
            for i, pos1 in enumerate(positions_list):
                for _j, pos2 in enumerate(positions_list[i+1:], i+1):
                    if self._nodes_overlap(pos1, pos2):
                        overlaps_detected += 1

            if overlaps_detected > 0:
                logger.warning(
                    "WARNING: %s overlaps detected after centering - spacing may need adjustment",
                    overlaps_detected
                )

        return balanced_positions

    def _position_branches_at_mathematical_centers(self, children: List[Dict], child_positions: Dict, left_branches_x: float, right_branches_x: float, mid_point: int) -> Dict:
        """
        Position branches at the exact mathematical centers of their children.

        Args:
            children: List of branch data
            child_positions: Dictionary of child node positions
            left_branches_x: X coordinate for left branch column
            right_branches_x: X coordinate for right branch column
            mid_point: Index where left side starts (calculated in caller to handle odd numbers)
        """
        positions = {}
        num_branches = len(children)

        for branch_idx, branch in enumerate(children):
            branch_text = self._get_node_text(branch)
            if not branch_text:
                logger.warning("Branch %s missing text, skipping", branch_idx)
                continue

            # Calculate branch dimensions (use capped width for text wrapping)
            branch_width = self._get_capped_node_width(branch_text, 'branch')
            branch_height = self._get_adaptive_node_height(branch_text, 'branch')

            # Determine side and column
            is_left_side = branch_idx >= mid_point
            branch_x = left_branches_x if is_left_side else right_branches_x

            # Find this branch's children
            branch_children = []
            for _key, pos in child_positions.items():
                if pos.get('branch_index') == branch_idx:
                    branch_children.append(pos)

            # Calculate exact mathematical center
            if branch_children:
                children_y_positions = [child['y'] for child in branch_children]
                branch_y = sum(children_y_positions) / len(children_y_positions)
                logger.debug(
                    "Branch %s ('%s'): Mathematical center at Y=%.1f",
                    branch_idx, branch_text, branch_y
                )
            else:
                # For branches without children, spread them vertically to avoid overlaps
                empty_branch_spacing = 80  # 80px spacing between empty branches
                empty_branch_offset = (branch_idx - num_branches // 2) * empty_branch_spacing
                branch_y = empty_branch_offset
                logger.debug("Branch %s ('%s'): No children, positioned at Y=%s (offset=%s)", branch_idx, branch_text, branch_y, empty_branch_offset)

            # Store branch position
            branch_key = f'branch_{branch_idx}'
            positions[branch_key] = {
                'x': branch_x, 'y': branch_y,
                'width': branch_width, 'height': branch_height,
                'text': branch_text, 'node_type': 'branch',
                'branch_index': branch_idx, 'angle': 0
            }

        logger.debug("Positioned %s branches at mathematical centers", len(positions))
        return positions

    def _translate_sides_to_origin(self, all_positions: Dict, children: List[Dict], _left_branches_x: float, _right_branches_x: float, mid_point: int) -> Dict:
        """
        Translate left and right side branch nodes (and their children) so that
        each side's branch height center is at the origin (Y=0).

        Args:
            all_positions: Dictionary containing all node positions (children + branches)
            children: List of branch data
            left_branches_x: X coordinate for left branch column
            right_branches_x: X coordinate for right branch column
            mid_point: Index where left side starts

        Returns:
            Dictionary with translated positions
        """
        logger.debug("🔄 Translating sides to origin based on branch height centers")
        logger.debug("Total branches: %s, mid_point: %s", len(children), mid_point)

        # Separate left and right branch positions
        left_branches = []
        right_branches = []

        for branch_idx in range(len(children)):
            branch_key = f'branch_{branch_idx}'
            if branch_key in all_positions:
                branch_pos = all_positions[branch_key]
                if branch_idx >= mid_point:
                    left_branches.append((branch_idx, branch_pos))
                    logger.debug("  Left branch %s: Y=%.1f", branch_idx, branch_pos['y'])
                else:
                    right_branches.append((branch_idx, branch_pos))
                    logger.debug("  Right branch %s: Y=%.1f", branch_idx, branch_pos['y'])
            else:
                logger.warning("Branch %s not found in all_positions!", branch_idx)

        logger.debug("Found %s left branches, %s right branches", len(left_branches), len(right_branches))

        # Calculate height centers for each side
        # Note: y coordinate is already the center of the node (as per renderer convention)
        # So height center = average of y coordinates
        def calculate_height_center(branches: List[Tuple[int, Dict]]) -> float:
            if not branches:
                logger.warning("No branches found for height center calculation!")
                return 0.0
            # y is already the center coordinate, so just average them
            branch_centers = [pos['y'] for _, pos in branches]
            height_center = sum(branch_centers) / len(branch_centers)
            branch_y_str = ', '.join([f'{pos["y"]:.1f}' for _, pos in branches])
            logger.debug("  Branch Y values: [%s]", branch_y_str)
            logger.debug("  Calculated height center: %.1f", height_center)
            return height_center

        left_center_y = calculate_height_center(left_branches)
        right_center_y = calculate_height_center(right_branches)

        logger.debug("Left side branch height center: %.1f (from %s branches)", left_center_y, len(left_branches))
        logger.debug("Right side branch height center: %.1f (from %s branches)", right_center_y, len(right_branches))

        # Calculate translation offsets (to move centers to Y=0)
        left_offset = 0.0 - left_center_y
        right_offset = 0.0 - right_center_y

        logger.debug("Left side translation offset: %.1f", left_offset)
        logger.debug("Right side translation offset: %.1f", right_offset)

        # Apply translations
        translated_positions = {}
        left_translated_count = 0
        right_translated_count = 0

        for key, pos in all_positions.items():
            new_pos = pos.copy()
            node_type = pos.get('node_type', '')
            branch_index = pos.get('branch_index')

            # Determine which side this node belongs to
            if node_type == 'branch':
                # Branch node: translate based on its side
                if branch_index is not None and branch_index >= mid_point:
                    new_pos['y'] += left_offset
                    left_translated_count += 1
                    logger.debug(
                        "  Translated left branch %s: %.1f → %.1f",
                        branch_index, pos['y'], new_pos['y']
                    )
                elif branch_index is not None:
                    new_pos['y'] += right_offset
                    right_translated_count += 1
                    logger.debug(
                        "  Translated right branch %s: %.1f → %.1f",
                        branch_index, pos['y'], new_pos['y']
                    )
            elif node_type == 'child':
                # Child node: translate based on its parent branch's side
                if branch_index is not None and branch_index >= mid_point:
                    new_pos['y'] += left_offset
                elif branch_index is not None:
                    new_pos['y'] += right_offset
            else:
                # Other node types (like topic) - keep as is
                pass

            translated_positions[key] = new_pos

        logger.debug(
            "Translation applied: %s left branches, %s right branches",
            left_translated_count, right_translated_count
        )
        logger.debug("Translation complete: %s total positions", len(translated_positions))

        return translated_positions

    def _two_stage_smart_positioning(self, children: List[Dict], left_children_x: float, right_children_x: float, left_branches_x: float, right_branches_x: float) -> Dict:
        """
        Complete two-stage positioning system with all solutions integrated.

        STAGE 1: Natural perfect layout with validation
        STAGE 2: Strategic phantom compensation if needed
        """
        logger.debug("Starting Two-Stage Smart Positioning System for %s branches", len(children))

        # STAGE 1: Natural perfect layout
        stage1_result = self._stage1_natural_layout(
            children, left_children_x, right_children_x,
            left_branches_x, right_branches_x
        )

        if stage1_result['all_principles_satisfied']:
            logger.debug("Stage 1 SUCCESS: Natural layout satisfies all principles")
            return {
                'positions': stage1_result['positions'],
                'stage_used': 1,
                'violations': []
            }

        logger.debug("WARNING Stage 1: %s violations detected", len(stage1_result['violations']))
        for violation in stage1_result['violations']:
            logger.debug("  Violation: %s", violation)

        # STAGE 2: Strategic phantom compensation
        stage2_result = self._stage2_phantom_compensation(
            stage1_result['positions'],
            stage1_result['violations'],
            children
        )

        if stage2_result['all_principles_satisfied']:
            logger.debug("Stage 2 SUCCESS: Phantom compensation solved all violations")
            return {
                'positions': stage2_result['positions'],
                'stage_used': 2,
                'violations': []
            }

        # FALLBACK: Use best available result
        logger.debug("WARNING Stage 2: Could not achieve perfect alignment, using best result")
        return {
            'positions': stage2_result['positions'],
            'stage_used': 2,
            'violations': stage2_result['remaining_violations']
        }

    def _stage1_natural_layout(self, children: List[Dict], left_children_x: float, right_children_x: float, left_branches_x: float, right_branches_x: float) -> Dict:
        """
        STAGE 1: Natural perfect layout with comprehensive validation.

        Creates perfect spacing layout using only real children, then validates all principles.
        """
        logger.debug("📍 Stage 1: Creating natural perfect layout")

        # Step 1: Assign children to sides with branch coherence
        side_assignments = self._assign_children_to_sides_coherently(children)

        # Step 2: Calculate true even spacing for each side
        left_positions = self._position_children_with_even_spacing(side_assignments['left_children'], left_children_x)
        right_positions = self._position_children_with_even_spacing(side_assignments['right_children'], right_children_x)

        # Step 3: Combine child positions
        all_child_positions = {}
        all_child_positions.update(left_positions)
        all_child_positions.update(right_positions)

        # Step 4: Position branches at mathematical centers of their children
        branch_positions = self._position_branches_at_centers(children, all_child_positions, left_branches_x, right_branches_x)

        # Step 5: Combine all positions
        all_positions = {}
        all_positions.update(all_child_positions)
        all_positions.update(branch_positions)

        # Step 6: Comprehensive validation
        validation_results = self._validate_all_principles(all_positions, children)

        logger.debug("Stage 1 validation: %s", validation_results['summary'])

        return {
            'positions': all_positions,
            'all_principles_satisfied': validation_results['all_satisfied'],
            'violations': validation_results['violations'],
            'stage': 1
        }

    def _assign_children_to_sides_coherently(self, children: List[Dict]) -> Dict:
        """
        Assign children to sides maintaining branch coherence.
        """
        num_branches = len(children)
        mid_point = num_branches // 2

        left_side_children = []
        right_side_children = []

        for branch_idx, branch in enumerate(children):
            branch_children = branch.get('children', [])

            for child_idx, child in enumerate(branch_children):
                child_info = {
                    'branch_idx': branch_idx,
                    'child_idx': child_idx,
                    'data': child,
                    'side': 'left' if branch_idx >= mid_point else 'right'
                }

                if branch_idx >= mid_point:
                    left_side_children.append(child_info)
                else:
                    right_side_children.append(child_info)

        logger.debug("Side assignment: Left=%s, Right=%s", len(left_side_children), len(right_side_children))

        return {
            'left_children': left_side_children,
            'right_children': right_side_children
        }

    def _position_children_with_even_spacing(self, side_children: List[Dict], column_x: float) -> Dict:
        """
        Position children with true even spacing (8px edge-to-edge).
        """
        if not side_children:
            return {}

        edge_buffer = 8  # Fixed 8px gap between node edges

        # Calculate heights for all children
        for child_info in side_children:
            child_data = child_info['data']
            child_text = self._get_node_text(child_data)
            child_info['height'] = self._get_adaptive_node_height(child_text, 'child')
            # Use capped width for text wrapping
            child_info['width'] = self._get_capped_node_width(child_text, 'child')

        # Calculate dynamic center-to-center spacings
        spacings = []
        for i in range(len(side_children) - 1):
            current_height = side_children[i]['height']
            next_height = side_children[i + 1]['height']

            # Center-to-center = half of current + buffer + half of next
            center_spacing = (current_height / 2) + edge_buffer + (next_height / 2)
            spacings.append(center_spacing)

        # Position children using calculated spacings
        positions = {}
        current_y = 0  # Start at center

        for i, child_info in enumerate(side_children):
            child_key = f"child_{child_info['branch_idx']}_{child_info['child_idx']}"

            child_text = self._get_node_text(child_info['data'])
            positions[child_key] = {
                'x': column_x, 'y': current_y,
                'width': child_info['width'], 'height': child_info['height'],
                'text': child_text, 'node_type': 'child',
                'branch_index': child_info['branch_idx'],
                'child_index': child_info['child_idx'], 'angle': 0
            }

            if i < len(spacings):
                current_y += spacings[i]  # Move to next position

        # Center the entire group around Y=0
        if positions:
            all_y = [pos['y'] for pos in positions.values()]
            center_offset = sum(all_y) / len(all_y)

            for pos in positions.values():
                pos['y'] -= center_offset

        logger.debug("Positioned %s children with even spacing", len(positions))
        return positions

    def _position_branches_at_centers(self, children: List[Dict], child_positions: Dict, left_branches_x: float, right_branches_x: float) -> Dict:
        """
        Position branches at mathematical centers of their children.
        """
        num_branches = len(children)
        mid_point = num_branches // 2
        positions = {}

        for branch_idx, branch in enumerate(children):
            branch_text = self._get_node_text(branch)
            if not branch_text:
                logger.warning("Branch %s missing text, skipping", branch_idx)
                continue

            # Calculate branch dimensions (use capped width for text wrapping)
            branch_width = self._get_capped_node_width(branch_text, 'branch')
            branch_height = self._get_adaptive_node_height(branch_text, 'branch')

            # Determine side and column
            is_left_side = branch_idx >= mid_point
            branch_x = left_branches_x if is_left_side else right_branches_x

            # Find this branch's children
            branch_children = []
            for _key, pos in child_positions.items():
                if pos.get('branch_index') == branch_idx:
                    branch_children.append(pos)

            # Calculate mathematical center of children
            if branch_children:
                children_y_positions = [child['y'] for child in branch_children]
                branch_y = sum(children_y_positions) / len(children_y_positions)
                logger.debug(
                    "Branch %s: center-aligned to children at Y=%.1f",
                    branch_idx, branch_y
                )
            else:
                branch_y = 0.0  # Default to center if no children
                logger.debug("Branch %s: no children, positioned at Y=0", branch_idx)

            # Store branch position
            branch_key = f'branch_{branch_idx}'
            positions[branch_key] = {
                'x': branch_x, 'y': branch_y,
                'width': branch_width, 'height': branch_height,
                'text': branch_text, 'node_type': 'branch',
                'branch_index': branch_idx, 'angle': 0
            }

        logger.debug("Positioned %s branches at mathematical centers", len(positions))
        return positions

    def _validate_all_principles(self, positions: Dict, children: List[Dict]) -> Dict:
        """
        Comprehensive validation of all positioning principles.
        """
        violations = []

        # Principle 1: Branch center alignment (5px tolerance)
        center_violations = self._validate_branch_center_alignment(positions, children)
        violations.extend(center_violations)

        # Principle 2: Middle branch horizontal alignment (5px tolerance)
        horizontal_violations = self._validate_middle_branch_horizontal_alignment(positions, children)
        violations.extend(horizontal_violations)

        # Principle 3: No overlaps
        overlap_violations = self._validate_no_overlaps(positions)
        violations.extend(overlap_violations)

        # Generate summary
        critical_count = len([v for v in violations if 'CRITICAL' in v])
        overlap_count = len([v for v in violations if 'OVERLAP' in v])

        if len(violations) == 0:
            summary = "All principles satisfied perfectly"
        elif critical_count == 0 and overlap_count == 0:
            summary = f"Minor violations: {len(violations)} warnings"
        else:
            summary = f"Major violations: {critical_count} critical, {overlap_count} overlaps"

        return {
            'all_satisfied': len(violations) == 0,
            'violations': violations,
            'summary': summary,
            'critical_count': critical_count,
            'overlap_count': overlap_count
        }

    def _validate_branch_center_alignment(self, positions: Dict, children: List[Dict]) -> List[str]:
        """
        Validate that branches are center-aligned to their children.
        """
        violations = []

        for branch_idx, _branch in enumerate(children):
            branch_key = f'branch_{branch_idx}'
            if branch_key not in positions:
                continue

            branch_pos = positions[branch_key]
            branch_y = branch_pos['y']

            # Find children for this branch
            branch_children = []
            for _key, pos in positions.items():
                if pos.get('branch_index') == branch_idx and pos.get('node_type') == 'child':
                    branch_children.append(pos)

            if branch_children:
                # Calculate mathematical center
                children_y_positions = [child['y'] for child in branch_children]
                mathematical_center = sum(children_y_positions) / len(children_y_positions)

                # Check alignment (5px tolerance)
                error = abs(branch_y - mathematical_center)

                if error > 5:
                    violations.append(
                        f"CRITICAL: Branch {branch_idx} misaligned by {error:.1f}px "
                        f"(Branch Y: {branch_y:.1f}, Center: {mathematical_center:.1f})"
                    )

        return violations

    def _validate_middle_branch_horizontal_alignment(self, positions: Dict, children: List[Dict]) -> List[str]:
        """
        Validate that middle branches are aligned with central topic (Y=0).
        """
        violations = []
        num_branches = len(children)

        # Identify middle branches
        middle_branches = self._identify_middle_branches_systematically(num_branches)

        for branch_idx in middle_branches:
            branch_key = f'branch_{branch_idx}'
            if branch_key in positions:
                branch_y = positions[branch_key]['y']
                error = abs(branch_y - 0)  # Should be at Y=0

                if error > 5:  # 5px tolerance
                    violations.append(
                        f"CRITICAL: Middle branch {branch_idx} not horizontally aligned "
                        f"(Y={branch_y:.1f}, should be 0)"
                    )

        return violations

    def _validate_no_overlaps(self, positions: Dict) -> List[str]:
        """
        Validate that no nodes overlap.
        """
        violations = []

        # Get all non-phantom positions
        real_positions = [(key, pos) for key, pos in positions.items()
                         if pos and pos.get('node_type') in ['topic', 'branch', 'child']]

        for i, (_key1, pos1) in enumerate(real_positions):
            for _j, (_key2, pos2) in enumerate(real_positions[i+1:], i+1):
                if self._nodes_overlap(pos1, pos2):
                    violations.append(f"OVERLAP: {pos1.get('text', 'Node')} and {pos2.get('text', 'Node')} overlap")

        return violations

    def _identify_middle_branches_systematically(self, num_branches: int) -> List[int]:
        """
        Systematically identify middle branches that should align with central topic.

        For odd numbers: Pick the two branches closest to center (excluding center branch if exists)
        For even numbers: Pick the two center branches
        """
        if num_branches == 1:
            return [0]  # Only branch is middle
        elif num_branches == 2:
            return [0, 1]  # Both are middle
        elif num_branches == 3:
            return [0, 2]  # First and last (skip center branch 1)
        elif num_branches == 4:
            return [1, 2]  # Two center branches
        elif num_branches == 5:
            return [1, 3]  # Two branches closest to center (skip center branch 2)
        elif num_branches == 6:
            return [2, 3]  # Two center branches
        else:
            # General case for larger numbers
            mid_point = num_branches // 2
            if num_branches % 2 == 0:
                # Even: two center branches
                return [mid_point - 1, mid_point]
            else:
                # Odd: two branches around center (skip center)
                return [mid_point - 1, mid_point + 1]

    def _stage2_phantom_compensation(self, positions: Dict, violations: List[str], children: List[Dict]) -> Dict:
        """
        STAGE 2: Strategic phantom compensation for alignment violations.
        """
        logger.debug("Stage 2: Starting phantom compensation for %s violations", len(violations))

        # Identify middle branch alignment violations
        middle_violations = [v for v in violations if 'Middle branch' in v and 'not horizontally aligned' in v]

        if not middle_violations:
            logger.debug("No middle branch violations found, returning original positions")
            return {
                'positions': positions,
                'all_principles_satisfied': len(violations) == 0,
                'remaining_violations': violations,
                'stage': 2
            }

        # Add phantom compensation for middle branch violations
        compensated_positions = self._add_phantom_compensation(positions, middle_violations, children)

        # Re-validate with phantom compensation
        validation_results = self._validate_all_principles(compensated_positions, children)

        logger.debug("Stage 2 validation: %s", validation_results['summary'])

        return {
            'positions': compensated_positions,
            'all_principles_satisfied': validation_results['all_satisfied'],
            'remaining_violations': validation_results['violations'],
            'stage': 2
        }

    def _add_phantom_compensation(self, positions: Dict, _violations: List[str], children: List[Dict]) -> Dict:
        """
        Add strategic phantom nodes to fix middle branch alignment violations.
        """
        logger.debug("🎭 Adding phantom compensation for violations")

        compensated_positions = positions.copy()
        middle_branches = self._identify_middle_branches_systematically(len(children))

        for branch_idx in middle_branches:
            branch_key = f'branch_{branch_idx}'
            if branch_key not in positions:
                continue

            # Get current branch position and children
            branch_pos = positions[branch_key]
            current_branch_y = branch_pos['y']

            # Find children for this branch
            branch_children = []
            for _key, pos in positions.items():
                if pos.get('branch_index') == branch_idx and pos.get('node_type') == 'child':
                    branch_children.append(pos)

            if not branch_children:
                continue

            # Calculate current mathematical center
            children_y_positions = [child['y'] for child in branch_children]
            current_center = sum(children_y_positions) / len(children_y_positions)
            target_center = 0  # Should align with topic at Y=0

            offset_needed = target_center - current_center

            if abs(offset_needed) > 5:  # Need phantom compensation
                phantoms = self._calculate_phantom_compensation(branch_children, target_center)

                # Add phantoms to positions
                for i, phantom in enumerate(phantoms):
                    phantom_key = f"phantom_{branch_idx}_{i}"
                    compensated_positions[phantom_key] = phantom

                # Recalculate branch position with phantoms included
                phantom_y_positions = [p['y'] for p in phantoms]
                all_y_positions = children_y_positions + phantom_y_positions
                new_branch_y = sum(all_y_positions) / len(all_y_positions)

                compensated_positions[branch_key]['y'] = new_branch_y

                logger.debug("Branch %s: Added %s phantoms", branch_idx, len(phantoms))
                logger.debug("  Children Y: %s", children_y_positions)
                logger.debug("  Phantom Y: %s", phantom_y_positions)
                logger.debug("  All Y: %s", all_y_positions)
                logger.debug("  Branch Y: %.1f→%.1f (target=0)", current_branch_y, new_branch_y)

        return compensated_positions

    def _calculate_phantom_compensation(self, branch_children: List[Dict], target_center: float = 0) -> List[Dict]:
        """
        Calculate symmetric phantom pairs to achieve target center.
        """
        children_y = [child['y'] for child in branch_children]
        current_center = sum(children_y) / len(children_y)
        offset_needed = target_center - current_center

        if abs(offset_needed) < 1:  # Already close enough
            return []

        # Use targeted phantom placement based on offset direction
        current_sum = sum(children_y)
        current_count = len(children_y)

        logger.debug("Phantom calculation:")
        logger.debug("  Children Y: %s", children_y)
        logger.debug("  Current sum: %s, count: %s", current_sum, current_count)
        logger.debug("  Current center: %.1f", current_center)
        logger.debug("  Target center: %s", target_center)
        logger.debug("  Offset needed: %.1f", offset_needed)

        # Simple targeted approach: add phantoms in the direction needed to shift center
        if offset_needed > 0:
            # Need to shift center UP → Add phantoms ABOVE current center
            phantom_y = max(children_y) + 60  # 60px above highest child
            logger.debug("  Strategy: Add phantoms ABOVE at Y=%s", phantom_y)
        else:
            # Need to shift center DOWN → Add phantoms BELOW current center
            phantom_y = min(children_y) - 60  # 60px below lowest child
            logger.debug("  Strategy: Add phantoms BELOW at Y=%s", phantom_y)

        # Calculate how many phantoms needed: new_center = (current_sum + N*phantom_y) / (current_count + N) = target_center
        # Solve: current_sum + N*phantom_y = target_center * (current_count + N)
        # current_sum + N*phantom_y = target_center*current_count + target_center*N
        # N*(phantom_y - target_center) = target_center*current_count - current_sum

        denominator = phantom_y - target_center
        numerator = target_center * current_count - current_sum

        logger.debug("  Equation: N * %s = %s", denominator, numerator)

        if abs(denominator) > 0.1:
            phantom_count_exact = numerator / denominator

            # Use exact calculation for precision, but ensure it's reasonable
            if phantom_count_exact > 0 and phantom_count_exact < 10:
                phantom_count = phantom_count_exact  # Use exact value for precision
            else:
                phantom_count = max(1, round(abs(phantom_count_exact)))  # Fallback to rounding

            logger.debug("  Phantom count: %.2f → %.2f", phantom_count_exact, phantom_count)
        else:
            phantom_count = 1
            logger.debug("  Denominator too small, using 1 phantom")

        # Verification
        verification_center = (current_sum + phantom_count * phantom_y) / (current_count + phantom_count)
        logger.debug("  Verification: new center would be %.1f (target=%s)", verification_center, target_center)

        phantoms = []

        # Handle fractional phantom count by creating a single phantom with appropriate "weight"
        if phantom_count != int(phantom_count):
            # For fractional phantoms, create one phantom but calculate its position for exact centering
            exact_phantom_y = (target_center * (current_count + 1) - current_sum) / 1
            phantoms.append({
                'x': branch_children[0]['x'],  # Same X as children
                'y': exact_phantom_y, 'width': 50, 'height': 30,
                'text': 'phantom_exact', 'node_type': 'phantom',
                'is_phantom': True, 'angle': 0
            })
            logger.debug("  Created 1 exact phantom at Y=%.1f", exact_phantom_y)
        else:
            # For integer phantom count, spread them to avoid overlaps
            phantom_count_int = int(phantom_count)
            for i in range(phantom_count_int):
                # Spread phantoms slightly to avoid overlaps
                spread_offset = i * 10  # 10px spacing between phantoms
                adjusted_phantom_y = phantom_y + spread_offset

                phantoms.append({
                    'x': branch_children[0]['x'],  # Same X as children
                    'y': adjusted_phantom_y, 'width': 50, 'height': 30,
                    'text': f'phantom_{i}', 'node_type': 'phantom',
                    'is_phantom': True, 'angle': 0
                })
            logger.debug("  Created %s spread phantoms at Y=%s+offset", phantom_count_int, phantom_y)

        logger.debug("Calculated %s phantom nodes for offset %.1f", len(phantoms), offset_needed)
        return phantoms

    def _position_balanced_children(self, balanced_data: Dict, left_children_x: float, right_children_x: float) -> Dict:
        """
        STEP 3: Position all children (real + phantom) with perfect spacing.

        This creates perfect vertical alignment on both sides with no overlaps.
        """
        logger.debug("📍 Positioning balanced children")

        positions = {}

        # Calculate optimal spacing for perfect distribution
        total_children_per_side = balanced_data['total_children_per_side']
        base_spacing = 70  # Base spacing between children centers

        # Position left side children
        left_children = balanced_data['left_children']
        if left_children:
            # Start from top and work down
            start_y = -(total_children_per_side - 1) * base_spacing / 2

            for i, child_info in enumerate(left_children):
                child_y = start_y + (i * base_spacing)

                if not child_info['is_phantom']:
                    # Real child - create position
                    child_data = child_info['data']
                    child_text = self._get_node_text(child_data)
                    # Use capped width for text wrapping
                    child_width = self._get_capped_node_width(child_text, 'child')
                    child_height = self._get_adaptive_node_height(child_text, 'child')

                    child_key = f"child_{child_info['branch_idx']}_{child_info['child_idx']}"
                    positions[child_key] = {
                        'x': left_children_x, 'y': child_y,
                        'width': child_width, 'height': child_height,
                        'text': child_text, 'node_type': 'child',
                        'branch_index': child_info['branch_idx'],
                        'child_index': child_info['child_idx'], 'angle': 0
                    }

                    logger.debug(
                        "  Left child %s_%s: '%s' at Y=%.1f",
                        child_info['branch_idx'], child_info['child_idx'], child_text, child_y
                    )
                else:
                    # Phantom child - just reserve space, don't create position
                    logger.debug(
                        "  Left phantom %s_%s: reserved space at Y=%.1f",
                        child_info['branch_idx'], child_info['child_idx'], child_y
                    )

        # Position right side children
        right_children = balanced_data['right_children']
        if right_children:
            # Start from top and work down
            start_y = -(total_children_per_side - 1) * base_spacing / 2

            for i, child_info in enumerate(right_children):
                child_y = start_y + (i * base_spacing)

                if not child_info['is_phantom']:
                    # Real child - create position
                    child_data = child_info['data']
                    child_text = self._get_node_text(child_data)
                    # Use capped width for text wrapping
                    child_width = self._get_capped_node_width(child_text, 'child')
                    child_height = self._get_adaptive_node_height(child_text, 'child')

                    child_key = f"child_{child_info['branch_idx']}_{child_info['child_idx']}"
                    positions[child_key] = {
                        'x': right_children_x, 'y': child_y,
                        'width': child_width, 'height': child_height,
                        'text': child_text, 'node_type': 'child',
                        'branch_index': child_info['branch_idx'],
                        'child_index': child_info['child_idx'], 'angle': 0
                    }

                    logger.debug(
                        "  Right child %s_%s: '%s' at Y=%.1f",
                        child_info['branch_idx'], child_info['child_idx'], child_text, child_y
                    )
                else:
                    # Phantom child - just reserve space, don't create position
                    logger.debug(
                        "  Right phantom %s_%s: reserved space at Y=%.1f",
                        child_info['branch_idx'], child_info['child_idx'], child_y
                    )

        logger.debug("Positioned %s real children with perfect spacing", len(positions))
        return positions

    def _calculate_center_out_branches(self, children: List[Dict], child_positions: Dict, left_branches_x: float, right_branches_x: float) -> Dict:
        """
        STEP 4: Calculate branch positions center-out (middle branches first).

        This is the key innovation that ensures middle branches align with central topic.
        """
        logger.debug("Calculating center-out branch positions")

        positions = {}
        num_branches = len(children)
        mid_point = num_branches // 2

        # CORE PRINCIPLE: Start with middle branches at Y=0
        middle_branches = self._identify_middle_branches_smart(num_branches)

        logger.debug("Middle branches identified: %s", middle_branches)

        for branch_idx in range(num_branches):
            branch_data = children[branch_idx]
            branch_text = self._get_node_text(branch_data)
            if not branch_text:
                logger.warning("Branch %s missing text, skipping", branch_idx)
                continue

            # Calculate branch dimensions (use capped width for text wrapping)
            branch_width = self._get_capped_node_width(branch_text, 'branch')
            branch_height = self._get_adaptive_node_height(branch_text, 'branch')

            # Determine side and column
            is_left_side = branch_idx >= mid_point
            branch_x = left_branches_x if is_left_side else right_branches_x

            # Find this branch's children
            branch_children = []
            for _key, pos in child_positions.items():
                if pos.get('branch_index') == branch_idx:
                    branch_children.append(pos)

            # SMART POSITIONING: Middle branches forced to Y=0, others center-aligned
            if branch_idx in middle_branches:
                # FORCE middle branches to Y=0 (same as central topic)
                branch_y = 0.0
                logger.debug("MIDDLE branch %s: FORCED to Y=0", branch_idx)
            else:
                # Other branches: center-aligned to their children
                if branch_children:
                    children_y_positions = [child['y'] for child in branch_children]
                    branch_y = sum(children_y_positions) / len(children_y_positions)
                    logger.debug("  Regular branch %s: center-aligned to children at Y=%.1f", branch_idx, branch_y)
                else:
                    # No children: position relative to middle branches
                    branch_y = 0.0  # Default to center
                    logger.debug("  Childless branch %s: positioned at Y=0", branch_idx)

            # Store branch position
            branch_key = f'branch_{branch_idx}'
            positions[branch_key] = {
                'x': branch_x, 'y': branch_y,
                'width': branch_width, 'height': branch_height,
                'text': branch_text, 'node_type': 'branch',
                'branch_index': branch_idx, 'angle': 0
            }

            side = "LEFT" if is_left_side else "RIGHT"
            logger.debug("  Branch %s (%s): '%s' at Y=%.1f", branch_idx, side, branch_text, branch_y)

        logger.debug("All %s branches positioned with center-out method", num_branches)
        return positions

    def _identify_middle_branches_smart(self, num_branches: int) -> List[int]:
        """
        Identify which branches should be the 'middle' branches that align with central topic.

        This is the core logic that determines which branches get forced to Y=0.
        """
        mid_point = num_branches // 2

        if num_branches % 2 == 0:
            # Even number of branches: take one from each side closest to center
            right_middle = mid_point - 1  # Last right branch (closest to center)
            left_middle = mid_point        # First left branch (closest to center)
            return [right_middle, left_middle]
        else:
            # Odd number of branches: return the single middle branch
            return [mid_point]

    def _apply_middle_branch_horizontal_alignment(
        self, positions: Dict, topic_y: float, num_branches: int
    ) -> None:
        """
        Smart middle branch horizontal alignment while preserving mathematical precision.
        Only affects the middle branches on each side for perfect horizontal alignment.
        """
        logger.debug("Applying middle branch horizontal alignment")

        # Identify middle branches on each side
        middle_branches = self._identify_middle_branches(num_branches)

        logger.debug("Middle branches identified: %s", middle_branches)

        # Apply horizontal alignment to middle branches
        for side, branch_index in middle_branches.items():
            branch_key = f'branch_{branch_index}'

            if branch_key in positions:
                branch_pos = positions[branch_key]
                if branch_pos is None:
                    logger.debug("WARNING: Branch position is None for %s", branch_key)
                    continue

                original_y = branch_pos.get('y', 0)

                # Apply horizontal alignment to topic center
                logger.debug("  Setting branch Y: %s → %s", branch_pos, topic_y)
                if branch_pos is None:
                    logger.error("  ERROR: branch_pos is None!")
                    continue
                branch_pos['y'] = topic_y

                # Calculate offset for children adjustment
                y_offset = topic_y - original_y

                # Adjust children positions to maintain visual balance
                self._adjust_children_positions(positions, branch_index, y_offset)

                logger.debug("Middle branch %s (%s): %.1f → %.1f (offset: %.1f)", branch_index, side, original_y, topic_y, y_offset)
            else:
                logger.debug("WARNING: Middle branch %s not found in positions", branch_index)

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
            logger.debug("Right side branches: %s, middle: %s", right_branches, right_branches[right_middle_idx])

        if left_branches:
            # Find middle index of left side branches
            left_middle_idx = len(left_branches) // 2
            middle_branches['left'] = left_branches[left_middle_idx]
            logger.debug("Left side branches: %s, middle: %s", left_branches, left_branches[left_middle_idx])

        return middle_branches

    def _adjust_children_positions(self, positions: Dict, branch_index: int, y_offset: float) -> None:
        """
        Adjust children positions to maintain visual balance after branch alignment.
        After moving children, check for any new overlaps and fix them.
        """
        adjusted_count = 0
        adjusted_children = []

        for _key, pos in positions.items():
            if (pos is not None and
                pos.get('node_type') == 'child' and
                pos.get('branch_index') == branch_index):

                old_y = pos.get('y', 0)
                pos['y'] = old_y + y_offset
                adjusted_count += 1
                adjusted_children.append(pos)

                logger.debug("    Adjusted child '%s': %.1f → %.1f", pos.get('text', 'unknown'), old_y, pos['y'])

        logger.debug("  📝 Adjusted %s children by offset %.1f", adjusted_count, y_offset)

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

                logger.debug(
                    "      Fixed intra-branch overlap: '%s' %.1f → %.1f",
                    curr_child.get('text', 'child'), old_y, required_y
                )

    def _generate_connections(self, _topic: str, children: List[Dict], positions: Dict) -> List[Dict]:
        """
        Generate connection data for lines between nodes.

        This method is called AFTER all node positions have been finalized and centered.
        It directly reads coordinates from the positions dictionary, ensuring perfect alignment.

        Args:
            topic: Central topic text
            children: List of branch data (from spec)
            positions: Dictionary of finalized node positions (already centered)

        Returns:
            List of connection dictionaries with 'from' and 'to' coordinates
        """
        connections = []

        # Get topic position (should be at or near origin after centering)
        topic_pos = positions.get('topic', {})
        if not topic_pos:
            logger.warning("Topic position not found in positions dictionary")
            return connections

        topic_x = topic_pos.get('x', 0)
        topic_y = topic_pos.get('y', 0)

        logger.debug("Generating connections: %s branches, %s positions", len(children), len(positions))
        logger.debug("Topic position: (%.1f, %.1f)", topic_x, topic_y)

        # Connections from topic to branches
        # Use array index i which matches branch_key = f'branch_{i}'
        for i, branch_data in enumerate(children):
            branch_key = f'branch_{i}'

            if branch_key not in positions:
                logger.warning("Branch %s not found in positions (key: %s)", i, branch_key)
                continue

            branch_pos = positions[branch_key]
            branch_x = branch_pos.get('x', 0)
            branch_y = branch_pos.get('y', 0)

            # Create topic-to-branch connection
            connections.append({
                'type': 'topic_to_branch',
                'from': {'x': topic_x, 'y': topic_y, 'type': 'topic'},
                'to': {'x': branch_x, 'y': branch_y, 'type': 'branch'},
                'branch_index': i,
                'stroke_width': 3
                # Removed hardcoded stroke_color - let frontend theme system handle colors
            })

            # Connections from branch to children
            # CRITICAL: Children are stored with branch_index matching array index i
            # The actual_branch_idx in _stack_children_vertically maps back to original array index
            # So we use i (array index) to find children, which matches how they're stored
            nested_children = branch_data.get('children', [])
            logger.debug(
                "Branch %s ('%s'): %s children in spec",
                i, branch_data.get('label', ''), len(nested_children)
            )

            for j, _nested_child in enumerate(nested_children):
                child_key = f'child_{i}_{j}'

                if child_key not in positions:
                    # Child key not found - log for debugging
                    available_keys = [k for k in positions.keys() if k.startswith('child_')]
                    available_for_branch = [k for k in positions.keys() if k.startswith(f'child_{i}_')]
                    logger.warning("Connection generation: Child key '%s' not found for branch %s, child %s", child_key, i, j)
                    logger.debug("  Branch %s has %s children in spec", i, len(nested_children))
                    logger.debug("  Available child keys for branch %s: %s", i, available_for_branch)
                    logger.debug("  All child keys in positions: %s", sorted(available_keys))
                    # Check by branch_index to see what's actually stored
                    available_by_index = [
                        (k, p.get('branch_index'), p.get('child_index'), p.get('text', '')[:20])
                        for k, p in positions.items()
                        if p.get('branch_index') == i and p.get('node_type') == 'child'
                    ]
                    logger.debug("  Children with branch_index=%s: %s", i, available_by_index)
                    continue

                child_pos = positions[child_key]
                child_x = child_pos.get('x', 0)
                child_y = child_pos.get('y', 0)

                # Verify coordinates are valid
                if not (isinstance(child_x, (int, float)) and isinstance(child_y, (int, float))):
                    logger.warning("Invalid coordinates for child %s: (%s, %s)", child_key, child_x, child_y)
                    continue

                logger.debug("  Connection %s→%s: branch(%.1f,%.1f) → child(%.1f,%.1f)", i, j, branch_x, branch_y, child_x, child_y)

                # Create branch-to-child connection
                # CRITICAL: Use the exact coordinates from positions dictionary (already centered)
                connections.append({
                    'type': 'branch_to_child',
                    'from': {'x': branch_x, 'y': branch_y, 'type': 'branch'},
                    'to': {'x': child_x, 'y': child_y, 'type': 'child'},
                    'branch_index': i,
                    'child_index': j,
                    'stroke_width': 2
                    # Removed hardcoded stroke_color - let frontend theme system handle colors
                })

        # Verify connections match node positions
        if connections:
            sample_conn = connections[0]
            logger.debug(
                "Sample connection coordinates: from(%.1f, %.1f) to(%.1f, %.1f)",
                sample_conn['from']['x'], sample_conn['from']['y'],
                sample_conn['to']['x'], sample_conn['to']['y']
            )
            # Verify the 'from' position matches a node position
            if sample_conn['from']['type'] == 'topic':
                topic_pos = positions.get('topic', {})
                if topic_pos:
                    expected_x, expected_y = topic_pos.get('x', 0), topic_pos.get('y', 0)
                    if abs(sample_conn['from']['x'] - expected_x) > 0.1 or abs(sample_conn['from']['y'] - expected_y) > 0.1:
                        logger.warning(
                            "Connection topic position mismatch! Expected (%.1f, %.1f), got (%.1f, %.1f)",
                            expected_x, expected_y, sample_conn['from']['x'], sample_conn['from']['y']
                        )

        logger.debug("Generated %s connections total", len(connections))
        return connections

    def _compute_recommended_dimensions(self, positions: Dict, _topic: str, _children: List[Dict]) -> Dict:
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
            if text_length <= 4:
                height = 40  # Very short text
            elif text_length <= 8:
                height = 45  # Short text
            elif text_length <= 15:
                height = 50  # Medium text
            elif text_length <= 25:
                height = 55  # Long text
            elif text_length <= 40:
                height = 60  # Very long text
            else:
                height = 65  # Extremely long text (may need line wrapping)

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

        # Enhanced text width calculation with better symbol and Unicode support
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
            elif char in '()[]{}':
                # Brackets and parentheses
                char_width = font_size * 0.4
            elif char in '+-*/=<>':
                # Math and comparison symbols
                char_width = font_size * 0.6
            elif char in '&@#$%':
                # Special symbols
                char_width = font_size * 0.7
            elif char in '/\\':
                # Slashes
                char_width = font_size * 0.4
            elif char == ' ':
                # Spaces
                char_width = font_size * 0.3
            elif ord(char) > 127:
                # Unicode characters (Chinese, Japanese, etc.) are typically wider
                if ord(char) >= 0x4e00 and ord(char) <= 0x9fff:
                    # Chinese characters (CJK Unified Ideographs)
                    char_width = font_size * 1.2
                elif ord(char) >= 0x3040 and ord(char) <= 0x309f:
                    # Japanese Hiragana
                    char_width = font_size * 1.1
                elif ord(char) >= 0x30a0 and ord(char) <= 0x30ff:
                    # Japanese Katakana
                    char_width = font_size * 1.1
                else:
                    # Other Unicode characters
                    char_width = font_size * 0.8
            else:
                # Default for other characters
                char_width = font_size * 0.7

            total_width += char_width

        # Add a small amount for character spacing
        total_width += len(text) * 2

        # Cache the result
        self._text_width_cache[cache_key] = total_width
        return total_width

    def _get_capped_node_width(self, text: str, node_type: str) -> float:
        """
        Calculate node width based on the longest line (matching JavaScript renderer).

        The JavaScript renderer wraps text at max width, so:
        1. Split text by newlines to get individual lines
        2. Calculate width of longest line
        3. Cap at max_text_width (since JS will wrap longer lines)
        4. Add padding

        This ensures node width matches what the JavaScript renderer expects.
        """
        if not text:
            return 80 if node_type == 'child' else 100

        font_size = self._get_adaptive_font_size(text, node_type)

        if node_type == 'branch':
            max_text_width = self.MAX_BRANCH_TEXT_WIDTH
            padding = self.BRANCH_PADDING
            min_width = 100
        elif node_type == 'child':
            max_text_width = self.MAX_CHILD_TEXT_WIDTH
            padding = self.CHILD_PADDING
            min_width = 80
        elif node_type == 'topic':
            # Topic uses circle, calculate based on raw width with extra padding
            raw_text_width = self._calculate_text_width(text, font_size)
            return raw_text_width + 40
        else:
            # Default: use raw width with adaptive padding
            raw_text_width = self._calculate_text_width(text, font_size)
            return raw_text_width + self._get_adaptive_padding(text)

        # Split by newlines and find the longest line's width
        lines = text.split('\n')
        line_widths = [self._calculate_text_width(line, font_size) for line in lines]
        longest_line_width = max(line_widths) if line_widths else 0

        # Cap at max_text_width (since JavaScript will wrap longer lines)
        capped_width = min(longest_line_width, max_text_width)

        # Return capped width + padding (with minimum width)
        return max(min_width, capped_width + padding)

    def _get_adaptive_padding(self, text: str) -> int:
        """Get adaptive padding based on text length and content type."""
        text_length = len(text)

        # Base padding based on length
        if text_length <= 3:
            base_padding = 25  # Very short text needs less padding
        elif text_length <= 6:
            base_padding = 30  # Short text
        elif text_length <= 12:
            base_padding = 35  # Medium text
        elif text_length <= 20:
            base_padding = 40  # Long text
        elif text_length <= 30:
            base_padding = 45  # Very long text
        else:
            base_padding = 50  # Extremely long text

        # Additional padding for special characters that need more space
        symbol_bonus = 0
        if any(char in text for char in '()[]{}'):
            symbol_bonus += 3  # Brackets need extra space
        if any(char in text for char in '&@#$%/\\'):
            symbol_bonus += 2  # Special symbols need extra space
        if any(ord(char) > 127 for char in text):
            symbol_bonus += 5  # Unicode characters often need more space

        return base_padding + symbol_bonus

    def _analyze_branch_content(self, children: List[Dict]) -> Dict[str, Any]:
        """Analyze branch characteristics for optimal spacing."""
        total_children = len(children)
        avg_text_length = sum(len(self._get_node_text(child)) for child in children) / total_children if children else 0

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

        logger.debug(
            "    Spacing calculation: base=%s, density=%.2f, height=%.2f, final=%s",
            base_spacing, density_factor, height_factor, final_spacing
        )

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
        logger.debug("Running post-processing overlap prevention")

        # Get all non-null positions
        all_positions = [(key, pos) for key, pos in positions.items() if pos is not None]

        overlap_fixes = 0
        max_iterations = 5  # Increased to handle complex overlaps

        for iteration in range(max_iterations):
            overlaps_found = []

            # Detect overlaps
            for i, (key1, pos1) in enumerate(all_positions):
                for _j, (key2, pos2) in enumerate(all_positions[i+1:], i+1):
                    if self._nodes_overlap(pos1, pos2):
                        overlaps_found.append((key1, pos1, key2, pos2))

            if not overlaps_found:
                logger.debug("No overlaps found after %s iterations", iteration)
                break

            logger.debug("Iteration %s: Found %s overlaps", iteration + 1, len(overlaps_found))

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
                            logger.debug(
                                "  Fixed overlap: moved '%s' down by %.1fpx (min_sep=%.1fpx)",
                                pos1.get('text', 'node'), required_move, min_separation
                            )
                    else:
                        # Move pos2 down
                        required_move = (pos1['y'] + pos1['height']/2) + min_separation - (pos2['y'] - pos2['height']/2)
                        if required_move > 0:
                            pos2['y'] += required_move
                            overlap_fixes += 1
                            logger.debug(
                                "  Fixed overlap: moved '%s' down by %.1fpx (min_sep=%.1fpx)",
                                pos2.get('text', 'node'), required_move, min_separation
                            )

        if overlap_fixes > 0:
            logger.debug("Applied %s overlap fixes", overlap_fixes)
        else:
            logger.debug("No overlap fixes needed")

    def _get_max_branches(self) -> int:
        """Get maximum number of branches allowed."""
        return 20  # Reasonable limit for mind maps
