"""
Brace Map Agent - Dynamic Positioning System

This agent implements a content-aware brace map generation system that dynamically
positions nodes based on the actual content structure, following the principles
outlined in the comprehensive architecture document.
"""

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum

# Import required components
from config import Config


class DiagramDebugger:
    """Simple debugger for diagram generation"""
    
    def __init__(self):
        self.logs = []
    
    def log(self, message: str):
        """Log a debug message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        print(log_entry)  # Also print to console for immediate feedback
    
    def get_logs(self) -> List[str]:
        """Get all logged messages"""
        return self.logs.copy()
    
    def clear_logs(self):
        """Clear all logged messages"""
        self.logs.clear()


class LayoutAlgorithm(Enum):
    """Available layout algorithms for brace maps"""
    FLEXIBLE_DYNAMIC = "flexible_dynamic"  # New single flexible algorithm


class LayoutComplexity(Enum):
    """Complexity levels for layout processing"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class LLMStrategy(Enum):
    """LLM processing strategies"""
    PYTHON_ONLY = "python_only"
    LLM_ENHANCEMENT = "llm_enhancement"
    LLM_FIRST = "llm_first"
    HYBRID_ROUTING = "hybrid_routing"


@dataclass
class NodePosition:
    """Data structure for node positioning"""
    x: float
    y: float
    width: float
    height: float
    text: str
    node_type: str  # 'topic', 'part', 'subpart'
    part_index: Optional[int] = None
    subpart_index: Optional[int] = None


@dataclass
class LayoutResult:
    """Result of layout algorithm execution"""
    nodes: List[NodePosition]
    braces: List[Dict]
    dimensions: Dict
    algorithm_used: LayoutAlgorithm
    performance_metrics: Dict[str, Any]
    layout_data: Dict[str, Any]  # Additional layout information


@dataclass
class LLMDecision:
    """Result of LLM processing"""
    success: bool
    strategy: LLMStrategy
    reasoning: str
    layout_suggestions: Optional[Dict]
    style_suggestions: Optional[Dict]
    error_message: Optional[str]
    processing_time: float 


@dataclass
class UnitPosition:
    """Data structure for unit positioning"""
    unit_index: int
    x: float
    y: float
    width: float
    height: float
    part_position: NodePosition
    subpart_positions: List[NodePosition]


@dataclass
class SpacingInfo:
    """Dynamic spacing information"""
    unit_spacing: float
    subpart_spacing: float
    brace_offset: float
    content_density: float


class ContextManager:
    """Manages user context and preferences"""
    
    def __init__(self):
        self.user_contexts = {}
        self.user_preferences = {}
    
    def store_user_prompt(self, user_id: str, prompt: str, diagram_type: str):
        """Store user prompt for context analysis"""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []
        
        self.user_contexts[user_id].append({
            'prompt': prompt,
            'diagram_type': diagram_type,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 10 prompts for context
        if len(self.user_contexts[user_id]) > 10:
            self.user_contexts[user_id] = self.user_contexts[user_id][-10:]
    
    def get_user_context(self, user_id: str) -> Dict:
        """Get user context for personalization"""
        if user_id not in self.user_contexts:
            return {'recent_prompts': [], 'preferences': {}}
        
        recent_prompts = self.user_contexts[user_id]
        preferences = self.user_preferences.get(user_id, {})
        
        return {
            'recent_prompts': recent_prompts,
            'preferences': preferences,
            'session_id': self._get_current_session(user_id)
        }
    
    def update_preferences(self, user_id: str, preferences: Dict):
        """Update user preferences"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}
        self.user_preferences[user_id].update(preferences)
    
    def alter_diagram_based_on_context(self, spec: Dict, context: Dict) -> Dict:
        """Alter diagram specification based on user context"""
        altered_spec = spec.copy()
        
        # Analyze recent prompts for common themes
        recent_prompts = context.get('recent_prompts', [])
        if recent_prompts:
            common_themes = self._extract_common_themes(recent_prompts)
            if common_themes:
                # Could enhance spec based on themes
                pass
        
        return altered_spec
    
    def _get_current_session(self, user_id: str) -> str:
        """Get current session ID for user"""
        return f"session_{user_id}_{datetime.now().strftime('%Y%m%d')}"
    
    def _extract_common_themes(self, recent_prompts: List[Dict]) -> List[str]:
        """Extract common themes from recent prompts"""
        themes = []
        # Simple theme extraction - could be enhanced with NLP
        for prompt_data in recent_prompts:
            prompt = prompt_data['prompt'].lower()
            if 'science' in prompt:
                themes.append('science')
            elif 'business' in prompt:
                themes.append('business')
            elif 'education' in prompt:
                themes.append('education')
        return list(set(themes))


class CollisionDetector:
    """Detects and resolves node collisions"""
    
    @staticmethod
    def detect_node_collisions(nodes: List[NodePosition], padding: float = 10.0) -> List[Tuple[NodePosition, NodePosition]]:
        """Detect overlapping nodes"""
        collisions = []
        for i, node1 in enumerate(nodes):
            for j, node2 in enumerate(nodes[i+1:], i+1):
                if CollisionDetector._nodes_overlap(node1, node2, padding):
                    collisions.append((node1, node2))
        return collisions
    
    @staticmethod
    def resolve_collisions(nodes: List[NodePosition], padding: float = 10.0) -> List[NodePosition]:
        """Resolve node collisions by adjusting positions"""
        resolved_nodes = nodes.copy()
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            collisions = CollisionDetector.detect_node_collisions(resolved_nodes, padding)
            if not collisions:
                break
            
            for node1, node2 in collisions:
                CollisionDetector._resolve_collision(node1, node2, padding)
            
            iteration += 1
        
        return resolved_nodes
    
    @staticmethod
    def _nodes_overlap(node1: NodePosition, node2: NodePosition, padding: float) -> bool:
        """Check if two nodes overlap"""
        return (abs(node1.x - node2.x) < (node1.width + node2.width) / 2 + padding and
                abs(node1.y - node2.y) < (node1.height + node2.height) / 2 + padding)
    
    @staticmethod
    def _resolve_collision(node1: NodePosition, node2: NodePosition, padding: float):
        """Resolve collision between two nodes"""
        # Simple resolution: move node2 away from node1
        dx = node2.x - node1.x
        dy = node2.y - node1.y
        
        # For subparts, always resolve vertically to maintain vertical alignment
        if node2.node_type == 'subpart' or node1.node_type == 'subpart':
            # Vertical collision resolution for subparts
            if dy >= 0:
                node2.y = node1.y + (node1.height + node2.height) / 2 + padding
            else:
                node2.y = node1.y - (node1.height + node2.height) / 2 - padding
        else:
            # Normal collision resolution for non-subparts
            if abs(dx) > abs(dy):
                # Horizontal collision - move vertically
                if dy >= 0:
                    node2.y = node1.y + (node1.height + node2.height) / 2 + padding
                else:
                    node2.y = node1.y - (node1.height + node2.height) / 2 - padding
            else:
                # Vertical collision - move horizontally
                if dx >= 0:
                    node2.x = node1.x + (node1.width + node2.width) / 2 + padding
                else:
                    node2.x = node1.x - (node1.width + node2.width) / 2 - padding


class LLMHybridProcessor:
    """Processes content complexity and determines LLM strategy"""
        
    def analyze_complexity(self, spec: Dict) -> LayoutComplexity:
        """Analyze content complexity for layout strategy"""
        total_parts = len(spec.get('parts', []))
        total_subparts = sum(len(part.get('subparts', [])) for part in spec.get('parts', []))
        
        total_elements = total_parts + total_subparts
        
        if total_elements <= 5:
            return LayoutComplexity.SIMPLE
        elif total_elements <= 15:
            return LayoutComplexity.MODERATE
        else:
            return LayoutComplexity.COMPLEX
                
    def determine_strategy(self, complexity: LayoutComplexity, user_preferences: Optional[Dict]) -> LLMStrategy:
        """Determine LLM processing strategy"""
        if complexity == LayoutComplexity.SIMPLE:
            return LLMStrategy.PYTHON_ONLY
        elif complexity == LayoutComplexity.MODERATE:
            return LLMStrategy.LLM_ENHANCEMENT
        else:
            return LLMStrategy.LLM_FIRST
    

class ContextAwareAlgorithmSelector:
    """Selects layout algorithm based on context"""
    
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
    
    def select_algorithm(self, spec: Dict, user_id: str = None) -> LayoutAlgorithm:
        """Select the appropriate layout algorithm"""
        # With the new flexible algorithm, we always use FLEXIBLE_DYNAMIC
        return LayoutAlgorithm.FLEXIBLE_DYNAMIC


class FlexibleLayoutCalculator:
    """Implements the flexible dynamic layout algorithm"""
    
    def __init__(self, debugger: DiagramDebugger):
        self.debugger = debugger
    
    def calculate_text_dimensions(self, spec: Dict, theme: Dict) -> Dict[str, Any]:
        """Calculate text dimensions for all nodes"""
        dimensions = {
            'topic': {'width': 0, 'height': 0},
            'parts': [],
            'subparts': []
        }
        
        # Calculate topic dimensions
        topic = spec.get('topic', 'Main Topic')
        topic_width = self._calculate_text_width(topic, theme['fontTopic'])
        topic_height = theme['fontTopic'] + 20
        dimensions['topic'] = {'width': topic_width, 'height': topic_height}
        
        # Calculate part dimensions
        for part in spec.get('parts', []):
            part_width = self._calculate_text_width(part['name'], theme['fontPart'])
            part_height = theme['fontPart'] + 20
            dimensions['parts'].append({'width': part_width, 'height': part_height})
        
        # Calculate subpart dimensions
        for part in spec.get('parts', []):
            part_subparts = []
            for subpart in part.get('subparts', []):
                subpart_width = self._calculate_text_width(subpart['name'], theme['fontSubpart'])
                subpart_height = theme['fontSubpart'] + 20
                part_subparts.append({'width': subpart_width, 'height': subpart_height})
            dimensions['subparts'].append(part_subparts)
        
        return dimensions
    
    def calculate_density(self, total_parts: int, subparts_per_part: List[int]) -> float:
        """Calculate content density for dynamic spacing"""
        total_elements = total_parts + sum(subparts_per_part)
        estimated_canvas_area = 800 * 600  # Default canvas size
        return total_elements / estimated_canvas_area
    
    def calculate_unit_spacing(self, units: List[Union[Dict, UnitPosition]]) -> float:
        """Calculate dynamic unit spacing based on content analysis"""
        total_units = len(units)
        if total_units <= 1:
            return 30.0  # Minimum spacing
        
        # Analyze content complexity dynamically
        total_subparts = 0
        avg_unit_height = 0
        max_unit_height = 0
        
        for unit in units:
            if isinstance(unit, UnitPosition):
                height = unit.height
                subpart_count = len(unit.subpart_positions)
            elif isinstance(unit, dict):
                height = unit.get('height', 100.0)
                subpart_count = unit.get('subpart_count', 0)
            else:
                height = 100.0
                subpart_count = 0
            
            total_subparts += subpart_count
            avg_unit_height += height
            max_unit_height = max(max_unit_height, height)
        
        if units:
            avg_unit_height /= len(units)
        
        # Dynamic spacing factors based on content analysis
        content_density = (total_units + total_subparts) / max(1, total_units)
        height_factor = max_unit_height / 100.0  # Normalize to 100px baseline
        complexity_factor = min(2.5, content_density * height_factor)
        
        # Base spacing that scales with content complexity
        base_spacing = 30.0 * complexity_factor
        
        # Additional spacing for complex diagrams
        if total_units > 3:
            base_spacing += 10.0 * (total_units - 3)
        if total_subparts > total_units * 2:
            base_spacing += 15.0  # Extra spacing for parts with many subparts
        
        return max(30.0, base_spacing)  # Ensure minimum spacing
    
    def calculate_subpart_spacing(self, subparts: List[Dict]) -> float:
        """Calculate dynamic subpart spacing"""
        total_subparts = len(subparts)
        if total_subparts <= 1:
            return 20.0
        
        # Dynamic spacing based on subpart count and content complexity
        base_spacing = 15.0
        density_factor = min(1.5, total_subparts / 2.0)
        
        # Adjust based on text length (longer text needs more space)
        if subparts:
            avg_text_length = sum(len(subpart.get('name', '')) for subpart in subparts) / len(subparts)
            text_factor = min(1.3, avg_text_length / 20.0)
            return base_spacing * density_factor * text_factor
        
        return base_spacing * density_factor
    
    def calculate_main_topic_position(self, units: List[UnitPosition], dimensions: Dict) -> Tuple[float, float]:
        """Calculate main topic position (center-left of entire unit group)"""
        if not units:
            return (dimensions['padding'] + 50, dimensions['height'] / 2)
        
        # Sort units by Y position to ensure proper ordering
        sorted_units = sorted(units, key=lambda u: u.y)
        
        # Calculate the center of all units
        first_unit_y = sorted_units[0].y
        last_unit_y = sorted_units[-1].y + sorted_units[-1].height
        center_y = (first_unit_y + last_unit_y) / 2
        
        # Find the leftmost part position to avoid overlap
        leftmost_part_x = min(unit.part_position.x for unit in units)
        
        # Position topic to the left of all parts with proper spacing
        # Ensure topic is positioned at least 300px to the left of the leftmost part
        topic_x = max(dimensions['padding'] + 20, leftmost_part_x - 300)  # Increased spacing to 300px
        topic_y = center_y
        
        return (topic_x, topic_y)
    
    def calculate_unit_positions(self, spec: Dict, dimensions: Dict, theme: Dict) -> List[UnitPosition]:
        """Calculate positions for all units (part + subparts) using global grid alignment"""
        units = []
        parts = spec.get('parts', [])
        
        # Start with padding to account for canvas boundaries
        current_y = dimensions['padding']
        
        # Calculate dynamic positioning based on content structure
        total_parts = len(parts)
        total_subparts = sum(len(part.get('subparts', [])) for part in parts)
        
        # Analyze content for dynamic positioning
        max_topic_width = self._calculate_text_width(spec.get('topic', 'Main Topic'), theme['fontTopic'])
        max_part_width = max([self._calculate_text_width(part['name'], theme['fontPart']) for part in parts]) if parts else 100
        max_subpart_width = 0
        if total_subparts > 0:
            for part in parts:
                for subpart in part.get('subparts', []):
                    width = self._calculate_text_width(subpart['name'], theme['fontSubpart'])
                    max_subpart_width = max(max_subpart_width, width)
        
        # Dynamic horizontal positioning based on content analysis
        canvas_width = dimensions['width']
        available_width = canvas_width - 2 * dimensions['padding']
        
        # Calculate optimal spacing based on content
        topic_offset = max(30, min(80, available_width * 0.1))  # 10% of available width, min 30, max 80
        part_offset = max(100, min(200, available_width * 0.25))  # 25% of available width, min 100, max 200
        subpart_offset = max(80, min(150, available_width * 0.2))  # Reduced from 25% to 20% of available width, min 80, max 150
        
        # Calculate global grid positions for all subparts across all parts
        all_subparts = []
        for i, part in enumerate(parts):
            subparts = part.get('subparts', [])
            for j, subpart in enumerate(subparts):
                all_subparts.append({
                    'part_index': i,
                    'subpart_index': j,
                    'name': subpart['name'],
                    'height': theme['fontSubpart'] + 20
                })
        
        # Calculate global grid spacing
        # Calculate single global X position for ALL subparts (perfect vertical line)
        global_subpart_x = dimensions['padding'] + part_offset + subpart_offset
        
        if all_subparts:
            subpart_spacing = self.calculate_subpart_spacing([{'name': 'dummy'} for _ in range(len(all_subparts))])
            
            # Calculate global grid positions
            grid_positions = {}
            grid_y = current_y
            for subpart_info in all_subparts:
                grid_positions[(subpart_info['part_index'], subpart_info['subpart_index'])] = grid_y
                grid_y += subpart_info['height'] + subpart_spacing
        else:
            # No subparts case
            subpart_spacing = 20.0
            grid_positions = {}
        
        # Now position each unit using the global grid
        for i, part in enumerate(parts):
            subparts = part.get('subparts', [])
            
            if subparts:
                # Find the grid positions for this part's subparts
                part_subpart_positions = []
                for j, subpart in enumerate(subparts):
                    grid_y = grid_positions.get((i, j), current_y)
                    part_subpart_positions.append(grid_y)
                
                # Calculate part position (center of its subpart grid span)
                if part_subpart_positions:
                    first_j = 0
                    last_j = len(subparts) - 1
                    first_center = grid_positions[(i, first_j)] + (theme['fontSubpart'] + 20) / 2
                    last_center = grid_positions[(i, last_j)] + (theme['fontSubpart'] + 20) / 2
                    part_center_y = (first_center + last_center) / 2
                else:
                    part_center_y = current_y
                
                # Ensure part is properly centered with its subparts
                # The part should be at the vertical center of its subpart group's span
                
                # Ensure part is properly centered with its subparts
                # The part should be at the vertical center of its subpart group's span
                
                # Ensure part is properly centered with its subparts
                # The part should be at the vertical center of its subpart group's span
                
                # Ensure part is properly centered with its subparts
                # The part should be at the vertical center of its subpart group's span
                
                # Ensure part is properly centered with its subparts
                # The part should be at the vertical center of its subpart group's span
                
                # Double-check that part is properly centered with its subparts
                # The part should be at the vertical center of its subpart group's span
                
                # Ensure part is properly centered with its subparts
                # The part should be at the vertical center of its subpart group
                
                # Position part at center-left of its subpart grid span
                part_x = dimensions['padding'] + part_offset
                part_y = part_center_y - (theme['fontPart'] + 20) / 2  # Y is now the top of the part box
                
                # Create part node
                part_node = NodePosition(
                    x=part_x, y=part_y,
                    width=self._calculate_text_width(part['name'], theme['fontPart']),
                    height=theme['fontPart'] + 20,
                    text=part['name'], node_type='part', part_index=i
                )
                
                # Calculate subpart positions using global grid (all subparts in one vertical line)
                subpart_positions = []
                for j, subpart in enumerate(subparts):
                    subpart_x = global_subpart_x  # All subparts use the same X position
                    subpart_y = grid_positions[(i, j)]
                    
                    subpart_node = NodePosition(
                        x=subpart_x, y=subpart_y,
                        width=self._calculate_text_width(subpart['name'], theme['fontSubpart']),
                        height=theme['fontSubpart'] + 20,
                        text=subpart['name'], node_type='subpart',
                        part_index=i, subpart_index=j
                    )
                    subpart_positions.append(subpart_node)
                
                # Create unit with dynamic width and height based on grid span
                if part_subpart_positions:
                    first_j = 0
                    last_j = len(subparts) - 1
                    first_top = grid_positions[(i, first_j)]
                    last_bottom = grid_positions[(i, last_j)] + (theme['fontSubpart'] + 20)
                    unit_height = last_bottom - first_top
                    unit_y = first_top
                else:
                    unit_height = part_node.height
                    unit_y = current_y

                # Calculate unit spacing - pass all units for better context
                temp_units = []
                for k in range(i + 1):
                    if k < len(units):
                        temp_units.append(units[k])
                    else:
                        temp_units.append({'height': unit_height})
                unit_spacing = self.calculate_unit_spacing(temp_units)

                # Calculate next_y with overlap prevention
                if part_subpart_positions:
                    next_y = last_bottom + unit_spacing
                else:
                    next_y = current_y + unit_height + unit_spacing
                
                # Ensure no overlap with previous units
                if i > 0 and units:
                    # Check against all previous units, not just the last one
                    min_spacing = 30.0  # Increased minimum spacing between units
                    max_prev_bottom = 0
                    for prev_unit in units:
                        prev_bottom = prev_unit.y + prev_unit.height
                        max_prev_bottom = max(max_prev_bottom, prev_bottom)
                    
                    if unit_y < max_prev_bottom + min_spacing:
                        # Adjust current unit position to prevent overlap
                        unit_y = max_prev_bottom + min_spacing
                        # Update subpart positions to match new unit position
                        if part_subpart_positions:
                            # Recalculate subpart positions based on new unit_y
                            subpart_positions = []
                            for j, subpart in enumerate(subparts):
                                subpart_x = global_subpart_x
                                subpart_y = unit_y + j * (theme['fontSubpart'] + 20 + subpart_spacing)
                                
                                subpart_node = NodePosition(
                                    x=subpart_x, y=subpart_y,
                                    width=self._calculate_text_width(subpart['name'], theme['fontSubpart']),
                                    height=theme['fontSubpart'] + 20,
                                    text=subpart['name'], node_type='subpart',
                                    part_index=i, subpart_index=j
                                )
                                subpart_positions.append(subpart_node)
                            
                            # Recalculate part position to maintain centering
                            if subpart_positions:
                                first_center = subpart_positions[0].y + (theme['fontSubpart'] + 20) / 2
                                last_center = subpart_positions[-1].y + (theme['fontSubpart'] + 20) / 2
                                part_center_y = (first_center + last_center) / 2
                                part_y = part_center_y - (theme['fontPart'] + 20) / 2
                                part_node = NodePosition(
                                    x=part_x, y=part_y,
                                    width=self._calculate_text_width(part['name'], theme['fontPart']),
                                    height=theme['fontPart'] + 20,
                                    text=part['name'], node_type='part', part_index=i
                                )
                
                unit_width = max(400, part_node.width + subpart_offset + 50)  # Dynamic width
                unit = UnitPosition(
                    unit_index=i,
                    x=part_x, y=unit_y,
                    width=unit_width,
                    height=unit_height,
                    part_position=part_node,
                    subpart_positions=subpart_positions
                )
                
                # Final overlap check and adjustment using actual subpart bounds
                if i > 0 and units and subpart_positions:
                    # Calculate actual unit bounds based on subpart positions
                    subpart_ys = [s.y for s in subpart_positions]
                    subpart_heights = [s.height for s in subpart_positions]
                    actual_unit_min_y = min(subpart_ys)
                    actual_unit_max_y = max(y + h for y, h in zip(subpart_ys, subpart_heights))
                    actual_unit_height = actual_unit_max_y - actual_unit_min_y
                    
                    for prev_unit in units:
                        prev_bottom = prev_unit.y + prev_unit.height
                        # Check for actual overlap: if current unit starts before previous unit ends + spacing
                        if actual_unit_min_y < prev_bottom + min_spacing:
                            # Force adjust the unit position
                            adjustment_needed = prev_bottom + min_spacing - actual_unit_min_y
                            unit.y += adjustment_needed
                            # Update all subpart positions
                            for subpart in subpart_positions:
                                subpart.y += adjustment_needed
                            # Update part position to maintain centering
                            if subpart_positions:
                                first_center = subpart_positions[0].y + (theme['fontSubpart'] + 20) / 2
                                last_center = subpart_positions[-1].y + (theme['fontSubpart'] + 20) / 2
                                part_center_y = (first_center + last_center) / 2
                                unit.part_position.y = part_center_y - (theme['fontPart'] + 20) / 2
                        else:
                            pass # No debug print for OK case
                
                units.append(unit)
                
                # Update current_y for next iteration
                current_y = next_y
            else:
                # Part without subparts - dynamic positioning
                part_x = dimensions['padding'] + part_offset
                part_y = current_y + (theme['fontPart'] + 20) / 2  # Center the part
                
                part_node = NodePosition(
                    x=part_x, y=part_y,
                    width=self._calculate_text_width(part['name'], theme['fontPart']),
                    height=theme['fontPart'] + 20,
                    text=part['name'], node_type='part', part_index=i
                )
                
                # Dynamic height for unit without subparts
                unit_height = max(60, theme['fontPart'] + 40)  # Based on font size
                unit_width = max(200, part_node.width + 50)  # Dynamic width
                unit = UnitPosition(
                    unit_index=i,
                    x=part_x, y=current_y,
                    width=unit_width,
                    height=unit_height,
                    part_position=part_node,
                    subpart_positions=[]
                )
                units.append(unit)
                
                # Calculate unit spacing for next iteration - pass all units for better context
                temp_units = []
                for k in range(i + 1):
                    if k < len(units):
                        temp_units.append(units[k])
                    else:
                        # Estimate for remaining units
                        temp_units.append({'height': unit_height})
                unit_spacing = self.calculate_unit_spacing(temp_units)
                current_y += unit_height + unit_spacing
        
        return units
    
    def calculate_spacing_info(self, units: List[UnitPosition]) -> SpacingInfo:
        """Calculate dynamic spacing information"""
        total_units = len(units)
        total_subparts = sum(len(unit.subpart_positions) for unit in units)
        
        # Calculate unit spacing based on actual unit heights
        unit_heights = [unit.height for unit in units]
        unit_spacing = self.calculate_unit_spacing([{'height': height} for height in unit_heights])
        
        # Calculate subpart spacing based on actual subpart counts
        subpart_spacing = 20.0  # Default
        if total_subparts > 0:
            # Use the first unit with subparts to calculate spacing
            for unit in units:
                if unit.subpart_positions:
                    subpart_spacing = self.calculate_subpart_spacing([{'name': 'dummy'} for _ in unit.subpart_positions])
                    break
        
        brace_offset = 50.0  # Distance from nodes to brace
        content_density = (total_units + total_subparts) / 1000.0  # Normalized density
        
        return SpacingInfo(
            unit_spacing=unit_spacing,
            subpart_spacing=subpart_spacing,
            brace_offset=brace_offset,
            content_density=content_density
        )
    
    def _calculate_text_width(self, text: str, font_size: int) -> float:
        """Calculate text width based on font size and character count"""
        # Improved approximation with better character width estimation
        char_widths = {
            'i': 0.3, 'l': 0.3, 'I': 0.4, 'f': 0.4, 't': 0.4, 'r': 0.4,
            'm': 0.8, 'w': 0.8, 'M': 0.8, 'W': 0.8,
            'default': 0.6
        }
        
        total_width = 0
        for char in text:
            char_width = char_widths.get(char, char_widths['default'])
            total_width += char_width * font_size
        
        return total_width


class BraceMapAgent:
    """Brace Map Agent with flexible dynamic layout"""
    
    def __init__(self):
        self.debugger = DiagramDebugger()
        self.context_manager = ContextManager()
        self.llm_processor = LLMHybridProcessor()
        self.algorithm_selector = ContextAwareAlgorithmSelector(self.context_manager)
        self.layout_calculator = FlexibleLayoutCalculator(self.debugger)
        
        # Initialize with default theme
        self.default_theme = {
            'fontTopic': 24,
            'fontPart': 18,
            'fontSubpart': 14,
            'topicColor': '#2c3e50',
            'partColor': '#34495e',
            'subpartColor': '#7f8c8d',
            'strokeColor': '#95a5a6',
            'strokeWidth': 2
        }
    
    def generate_diagram(self, spec: Dict, user_id: str = None) -> Dict:
        """Generate brace map diagram using flexible dynamic layout"""
        start_time = datetime.now()
        self.debugger.log("Starting brace map generation")
        
        try:
            # Validate input spec
            if not spec or not isinstance(spec, dict):
                return {
                    'success': False,
                    'error': 'Invalid specification: must be a non-empty dictionary',
                    'debug_logs': self.debugger.get_logs()
                }
            
            # Validate required fields
            if 'topic' not in spec:
                spec['topic'] = 'Main Topic'
            
            if 'parts' not in spec or not isinstance(spec['parts'], list):
                return {
                    'success': False,
                    'error': 'Invalid specification: missing or invalid "parts" field',
                    'debug_logs': self.debugger.get_logs()
                }
            
            # Validate parts structure
            for i, part in enumerate(spec['parts']):
                if not isinstance(part, dict) or 'name' not in part:
                    return {
                        'success': False,
                        'error': f'Invalid part at index {i}: missing "name" field',
                        'debug_logs': self.debugger.get_logs()
                    }
                
                # Ensure subparts is a list
                if 'subparts' not in part:
                    part['subparts'] = []
                elif not isinstance(part['subparts'], list):
                    part['subparts'] = []
                
                # Validate subparts
                for j, subpart in enumerate(part['subparts']):
                    if not isinstance(subpart, dict) or 'name' not in subpart:
                        return {
                            'success': False,
                            'error': f'Invalid subpart at part {i}, subpart {j}: missing "name" field',
                            'debug_logs': self.debugger.get_logs()
                        }
            
            # Store user context if user_id provided
            if user_id and 'prompt' in spec:
                self.context_manager.store_user_prompt(user_id, spec['prompt'], 'brace_map')
            
            # Get user context for personalization
            context = self.context_manager.get_user_context(user_id) if user_id else {}
            
            # Alter specification based on context
            spec = self.context_manager.alter_diagram_based_on_context(spec, context)
            
            # Analyze complexity and determine strategy
            complexity = self.llm_processor.analyze_complexity(spec)
            strategy = self.llm_processor.determine_strategy(complexity, context.get('preferences'))
            
            self.debugger.log(f"Complexity: {complexity.value}, Strategy: {strategy.value}")
            
            # Select layout algorithm (always flexible dynamic now)
            algorithm = self.algorithm_selector.select_algorithm(spec, user_id)
            
            # Calculate dimensions
            dimensions = self._calculate_dimensions(spec)
            
            # Handle positioning with flexible algorithm
            layout_result = self._handle_positioning(spec, dimensions, self.default_theme)
            
            # Generate SVG data
            svg_data = self._generate_svg_data(layout_result, self.default_theme)
            
            # Calculate performance metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                'success': True,
                'svg_data': svg_data,
                'layout_data': layout_result.layout_data,
                'algorithm_used': algorithm.value,
                'complexity': complexity.value,
                'strategy': strategy.value,
                'processing_time': processing_time,
                'debug_logs': self.debugger.get_logs()
            }
            
            self.debugger.log(f"Generation completed in {processing_time:.3f}s")
            return result
            
        except Exception as e:
            self.debugger.log(f"Error in diagram generation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'debug_logs': self.debugger.get_logs()
            }
    
    def _calculate_dimensions(self, spec: Dict) -> Dict:
        """Calculate initial canvas dimensions based on content analysis"""
        parts = spec.get('parts', [])
        topic = spec.get('topic', 'Main Topic')
        total_subparts = sum(len(part.get('subparts', [])) for part in parts)
        
        # Analyze content complexity for initial sizing
        total_elements = len(parts) + total_subparts
        
        # Calculate max text length safely
        text_lengths = [len(topic)]
        if parts:
            text_lengths.extend(len(part['name']) for part in parts)
            for part in parts:
                if 'subparts' in part and part['subparts']:
                    text_lengths.extend(len(subpart['name']) for subpart in part['subparts'])
        
        max_text_length = max(text_lengths) if text_lengths else len(topic)
        
        # Initial canvas sizing based on content analysis
        base_width = 800
        base_height = 600
        
        # Adjust initial size based on content complexity
        if max_text_length > 30 or total_elements > 15:
            base_width = 1400
            base_height = 900
        elif max_text_length > 20 or total_elements > 10:
            base_width = 1200
            base_height = 800
        elif max_text_length > 15 or total_elements > 5:
            base_width = 1000
            base_height = 700
        elif len(parts) > 3 or total_subparts > 3:
            base_width = 900
            base_height = 650
        
        # Initial padding - reduced for less blank space
        padding = 25  # Reduced from 40
        
        return {
            'width': base_width,
            'height': base_height,
            'padding': padding
        }
    
    def _calculate_optimal_dimensions(self, nodes: List[NodePosition], initial_dimensions: Dict) -> Dict:
        """Calculate optimal canvas dimensions based on actual node positions"""
        if not nodes:
            return initial_dimensions
        
        # Filter out nodes with invalid coordinates
        valid_nodes = [node for node in nodes if node.x is not None and node.y is not None and node.width > 0 and node.height > 0]
        
        if not valid_nodes:
            return initial_dimensions
        
        # Calculate actual bounds of all nodes (using node boundaries, not centers)
        min_x = min(node.x for node in valid_nodes)
        max_x = max(node.x + node.width for node in valid_nodes)
        min_y = min(node.y for node in valid_nodes)
        max_y = max(node.y + node.height for node in valid_nodes)
        
        # Calculate required canvas size
        content_width = max_x - min_x
        content_height = max_y - min_y
        
        # Add padding and ensure minimum size
        padding = initial_dimensions['padding']
        optimal_width = max(content_width + 2 * padding, 600)  # Reduced from 800 to 600
        optimal_height = max(content_height + 2 * padding, 500)  # Reduced from 600 to 500
        
        # Add extra space for visual comfort and to prevent cutoff
        # Reduced padding for less blank space
        extra_padding = max(15, len(valid_nodes) * 2)  # Further reduced from 25 + 3*node_count
        optimal_width += extra_padding
        optimal_height += extra_padding
        
        # Ensure reasonable aspect ratio
        aspect_ratio = optimal_width / optimal_height
        if aspect_ratio > 3:  # Too wide
            optimal_width = optimal_height * 2.5
        elif aspect_ratio < 0.5:  # Too tall
            optimal_height = optimal_width * 0.8
        
        return {
            'width': int(optimal_width),
            'height': int(optimal_height),
            'padding': padding,
            'content_bounds': {
                'min_x': min_x,
                'max_x': max_x,
                'min_y': min_y,
                'max_y': max_y
            }
        }
    
    def _adjust_node_positions_for_optimal_canvas(self, nodes: List[NodePosition], initial_dimensions: Dict, optimal_dimensions: Dict) -> List[NodePosition]:
        """Adjust node positions to center them in the optimal canvas"""
        if not nodes:
            return nodes
        
        content_bounds = optimal_dimensions['content_bounds']
        padding = optimal_dimensions['padding']
        
        # Calculate offset to center content
        content_width = content_bounds['max_x'] - content_bounds['min_x']
        content_height = content_bounds['max_y'] - content_bounds['min_y']
        
        # Calculate centering offsets
        offset_x = padding - content_bounds['min_x']
        offset_y = padding - content_bounds['min_y']
        
        # Apply offset to all nodes
        adjusted_nodes = []
        for node in nodes:
            adjusted_node = NodePosition(
                x=node.x + offset_x,
                y=node.y + offset_y,
                width=node.width,
                height=node.height,
                text=node.text,
                node_type=node.node_type,
                part_index=node.part_index,
                subpart_index=node.subpart_index
            )
            adjusted_nodes.append(adjusted_node)
        
        return adjusted_nodes
    
    def _handle_positioning(self, spec: Dict, dimensions: Dict, theme: Dict) -> LayoutResult:
        """Handle node positioning using flexible dynamic algorithm with optimal canvas sizing"""
        start_time = datetime.now()
        
        # Calculate text dimensions
        text_dimensions = self.layout_calculator.calculate_text_dimensions(spec, theme)
        
        # Calculate unit positions using initial dimensions
        units = self.layout_calculator.calculate_unit_positions(spec, dimensions, theme)
        
        # Calculate spacing information
        spacing_info = self.layout_calculator.calculate_spacing_info(units)
        
        # Create all nodes
        nodes = []
        
        # Add all unit nodes first
        for unit in units:
            nodes.append(unit.part_position)
            nodes.extend(unit.subpart_positions)
        
        # Calculate main topic position BEFORE adjustments
        topic_x, topic_y = self.layout_calculator.calculate_main_topic_position(units, dimensions)
        
        # Add main topic
        topic = spec.get('topic', 'Main Topic')
        topic_node = NodePosition(
            x=topic_x, y=topic_y,
            width=text_dimensions['topic']['width'],
            height=text_dimensions['topic']['height'],
            text=topic, node_type='topic'
        )
        nodes.append(topic_node)
        
        # Calculate optimal canvas dimensions based on actual node positions
        optimal_dimensions = self._calculate_optimal_dimensions(nodes, dimensions)
        
        # Adjust node positions to center them in the optimal canvas
        nodes = self._adjust_node_positions_for_optimal_canvas(nodes, dimensions, optimal_dimensions)
        
        # Validate and resolve collisions using optimal dimensions
        nodes = self._validate_and_adjust_boundaries(nodes, optimal_dimensions)
        nodes = CollisionDetector.resolve_collisions(nodes, padding=20.0)
        
        # Update unit positions to match adjusted nodes
        adjusted_units = []
        for i, unit in enumerate(units):
            # Find the adjusted part node
            adjusted_part = next((node for node in nodes if node.node_type == 'part' and node.part_index == i), None)
            if adjusted_part is None:
                # Create a new part node if not found
                adjusted_part = NodePosition(
                    x=unit.part_position.x, y=unit.part_position.y,
                    width=unit.part_position.width, height=unit.part_position.height,
                    text=unit.part_position.text, node_type='part', part_index=i
                )
            
            # Find the adjusted subpart nodes
            adjusted_subparts = [node for node in nodes if node.node_type == 'subpart' and node.part_index == i]
            
            # Create adjusted unit
            adjusted_unit = UnitPosition(
                unit_index=unit.unit_index,
                x=adjusted_part.x,
                y=adjusted_part.y,
                width=unit.width,
                height=unit.height,
                part_position=adjusted_part,
                subpart_positions=adjusted_subparts
            )
            adjusted_units.append(adjusted_unit)
        
        # Create layout data with optimal dimensions
        layout_data = {
            'units': self._serialize_units(adjusted_units),
            'spacing_info': self._serialize_spacing_info(spacing_info),
            'text_dimensions': text_dimensions,
            'canvas_dimensions': optimal_dimensions,
            'nodes': self._serialize_nodes(nodes)
        }
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return LayoutResult(
            nodes=nodes,
            braces=[],  # Braces will be handled in rendering phase
            dimensions=optimal_dimensions,  # Use optimal dimensions
            algorithm_used=LayoutAlgorithm.FLEXIBLE_DYNAMIC,
            performance_metrics={'processing_time': processing_time},
            layout_data=layout_data
        )
    
    def _serialize_units(self, units: List[UnitPosition]) -> List[Dict]:
        """Convert UnitPosition objects to JSON-serializable dictionaries"""
        serialized_units = []
        for unit in units:
            serialized_unit = {
                'unit_index': unit.unit_index,
                'x': unit.x,
                'y': unit.y,
                'width': unit.width,
                'height': unit.height,
                'part_position': {
                    'x': unit.part_position.x,
                    'y': unit.part_position.y,
                    'width': unit.part_position.width,
                    'height': unit.part_position.height,
                    'text': unit.part_position.text,
                    'node_type': unit.part_position.node_type,
                    'part_index': unit.part_position.part_index,
                    'subpart_index': unit.part_position.subpart_index
                },
                'subpart_positions': [
                    {
                        'x': subpart.x,
                        'y': subpart.y,
                        'width': subpart.width,
                        'height': subpart.height,
                        'text': subpart.text,
                        'node_type': subpart.node_type,
                        'part_index': subpart.part_index,
                        'subpart_index': subpart.subpart_index
                    }
                    for subpart in unit.subpart_positions
                ]
            }
            serialized_units.append(serialized_unit)
        return serialized_units
    
    def _serialize_spacing_info(self, spacing_info: SpacingInfo) -> Dict:
        """Convert SpacingInfo object to JSON-serializable dictionary"""
        return {
            'unit_spacing': spacing_info.unit_spacing,
            'subpart_spacing': spacing_info.subpart_spacing,
            'brace_offset': spacing_info.brace_offset,
            'content_density': spacing_info.content_density
        }
    
    def _serialize_nodes(self, nodes: List[NodePosition]) -> List[Dict]:
        """Convert NodePosition objects to JSON-serializable dictionaries"""
        serialized_nodes = []
        for node in nodes:
            serialized_node = {
                'x': node.x,
                'y': node.y,
                'width': node.width,
                'height': node.height,
                'text': node.text,
                'node_type': node.node_type,
                'part_index': node.part_index,
                'subpart_index': node.subpart_index
            }
            serialized_nodes.append(serialized_node)
        return serialized_nodes

    def _validate_and_adjust_boundaries(self, nodes: List[NodePosition], dimensions: Dict) -> List[NodePosition]:
        """Validate node boundaries and adjust if necessary"""
        adjusted_nodes = []
        
        for node in nodes:
            # Check if node extends beyond canvas boundaries
            # Nodes are positioned with their top-left corner at (x, y)
            if node.x < dimensions['padding']:
                node.x = dimensions['padding']
            if node.x + node.width > dimensions['width'] - dimensions['padding']:
                node.x = dimensions['width'] - dimensions['padding'] - node.width
            if node.y < dimensions['padding']:
                node.y = dimensions['padding']
            if node.y + node.height > dimensions['height'] - dimensions['padding']:
                node.y = dimensions['height'] - dimensions['padding'] - node.height
            
            adjusted_nodes.append(node)
        
        return adjusted_nodes
    
    def _generate_svg_data(self, layout_result: LayoutResult, theme: Dict) -> Dict:
        """Generate SVG data for rendering (layout phase only)"""
        svg_elements = []
        
        # Generate nodes only (braces will be handled in rendering phase)
        for node in layout_result.nodes:
            element = {
                'type': 'text',
                'x': node.x,
                'y': node.y,
                'text': node.text,
                'node_type': node.node_type,  # Add node_type for identification
                'font_size': self._get_font_size(node.node_type, theme),
                'fill': self._get_node_color(node.node_type, theme),
                'text_anchor': 'middle',
                'dominant_baseline': 'middle'
            }
            svg_elements.append(element)
        
        # Use optimal dimensions from layout result
        optimal_dimensions = layout_result.dimensions
        
        return {
            'elements': svg_elements,
            'width': optimal_dimensions['width'],
            'height': optimal_dimensions['height'],
            'background': '#ffffff',
            'layout_data': layout_result.layout_data  # Include layout data for rendering phase
        }
    
    def _get_font_size(self, node_type: str, theme: Dict) -> int:
        """Get font size for node type"""
        font_map = {
            'topic': theme['fontTopic'],
            'part': theme['fontPart'],
            'subpart': theme['fontSubpart']
        }
        return font_map.get(node_type, theme['fontPart'])
    
    def _get_node_color(self, node_type: str, theme: Dict) -> str:
        """Get color for node type"""
        color_map = {
            'topic': theme['topicColor'],
            'part': theme['partColor'],
            'subpart': theme['subpartColor']
        }
        return color_map.get(node_type, theme['partColor'])


# Export the main agent class
__all__ = ['BraceMapAgent', 'LayoutAlgorithm', 'LayoutComplexity', 'LLMStrategy'] 