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

# Configuration constants
BRACE_SPACING_CONFIG = {
    'main_brace_from_topic': 20,
    'main_brace_to_secondary_brace': 20,
    'secondary_brace_to_parts': 20,
    'part_brace_from_part': 15,
    'tertiary_brace_to_subparts': 15,
    'topic_left_offset': 200,
    'minimum_brace_height': 20,
    'minimum_spacing': 10,
    'secondary_brace_width': 10,
    'tertiary_brace_width': 8
}

FONT_WEIGHT_CONFIG = {
    'topic': 'bold',
    'part': 'bold',
    'subpart': 'normal'
}

CHAR_WIDTH_CONFIG = {
    'i': 0.3, 'l': 0.3, 'I': 0.4, 'f': 0.4, 't': 0.4, 'r': 0.4,
    'm': 0.8, 'w': 0.8, 'M': 0.8, 'W': 0.8,
    'default': 0.6
}

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


@dataclass
class BraceParameters:
    """Parameters for brace creation"""
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    height: float
    is_main_brace: bool = True
    stroke_width: Optional[int] = None
    stroke_color: Optional[str] = None


@dataclass
class Block:
    """Represents a block in the block-based positioning system"""
    id: str
    x: float
    y: float
    width: float
    height: float
    text: str
    node_type: str  # 'topic', 'part', 'subpart'
    part_index: Optional[int] = None
    subpart_index: Optional[int] = None
    parent_block_id: Optional[str] = None  # For subparts belonging to parts


@dataclass
class BlockUnit:
    """Represents a unit of blocks (part + its subparts)"""
    unit_id: str
    part_block: Block
    subpart_blocks: List[Block]
    x: float
    y: float
    width: float
    height: float


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


class BlockBasedPositioningSystem:
    """Block-based positioning system that arranges nodes like LEGO pieces"""
    
    def __init__(self, debugger: DiagramDebugger):
        self.debugger = debugger
    
    def arrange_blocks(self, spec: Dict, dimensions: Dict, theme: Dict) -> List[BlockUnit]:
        """Arrange blocks using LEGO-like positioning"""
        # Step 1: Create blocks from specification
        blocks = self._create_blocks_from_spec(spec, theme)
        
        # Step 2: Group blocks into units
        units = self._group_blocks_into_units(blocks)
        
        # Step 3: Calculate optimal spacing and padding
        spacing_config = self._calculate_spacing_config(spec, dimensions, theme)
        
        # Step 4: Position blocks using block-based algorithm
        positioned_units = self._position_blocks(units, spacing_config, dimensions)
        
        return positioned_units
    
    def _create_blocks_from_spec(self, spec: Dict, theme: Dict) -> List[Block]:
        """Create blocks from specification with standard heights for each block type"""
        blocks = []
        
        # Define standard block heights (only width varies based on text)
        topic_height = theme['fontTopic'] + 20
        part_height = theme['fontPart'] + 20
        subpart_height = theme['fontSubpart'] + 20
        
        # Create topic block
        topic = spec.get('topic', 'Main Topic')
        topic_width = self._calculate_text_width(topic, theme['fontTopic'])
        
        topic_block = Block(
            id='topic',
            x=0, y=0,  # Will be positioned later
            width=topic_width,
            height=topic_height,  # Standard height for all topic blocks
            text=topic,
            node_type='topic'
        )
        blocks.append(topic_block)
        
        # Create part and subpart blocks
        for i, part in enumerate(spec.get('parts', [])):
            part_width = self._calculate_text_width(part['name'], theme['fontPart'])
            
            part_block = Block(
                id=f'part_{i}',
                x=0, y=0,  # Will be positioned later
                width=part_width,
                height=part_height,  # Standard height for all part blocks
                text=part['name'],
                node_type='part',
                part_index=i
            )
            blocks.append(part_block)
            
            # Create subpart blocks
            for j, subpart in enumerate(part.get('subparts', [])):
                subpart_width = self._calculate_text_width(subpart['name'], theme['fontSubpart'])
                
                subpart_block = Block(
                    id=f'subpart_{i}_{j}',
                    x=0, y=0,  # Will be positioned later
                    width=subpart_width,
                    height=subpart_height,  # Standard height for all subpart blocks
                    text=subpart['name'],
                    node_type='subpart',
                    part_index=i,
                    subpart_index=j,
                    parent_block_id=f'part_{i}'
                )
                blocks.append(subpart_block)
        
        return blocks
    
    def _group_blocks_into_units(self, blocks: List[Block]) -> List[BlockUnit]:
        """Group blocks into units (part + subparts)"""
        units = []
        
        # Find all part blocks
        part_blocks = [block for block in blocks if block.node_type == 'part']
        
        for part_block in part_blocks:
            # Find subpart blocks belonging to this part
            subpart_blocks = [block for block in blocks 
                            if block.node_type == 'subpart' and 
                            block.parent_block_id == part_block.id]
            
            unit = BlockUnit(
                unit_id=part_block.id,
                part_block=part_block,
                subpart_blocks=subpart_blocks,
                x=0, y=0, width=0, height=0  # Will be calculated later
            )
            units.append(unit)
        
        return units
    
    def _calculate_spacing_config(self, spec: Dict, dimensions: Dict, theme: Dict) -> Dict:
        """Calculate dynamic spacing configuration based on content"""
        parts = spec.get('parts', [])
        total_parts = len(parts)
        total_subparts = sum(len(part.get('subparts', [])) for part in parts)
        
        # Calculate complexity score
        complexity_score = total_parts * 2 + total_subparts * 1.5
        
        # Dynamic spacing based on complexity (reduced values to prevent excessive Y coordinates)
        if complexity_score > 50:
            block_spacing = 20.0  # Reduced from 40.0
            unit_spacing = 30.0   # Reduced from 60.0
            brace_padding = 40.0  # Reduced from 80.0
        elif complexity_score > 25:
            block_spacing = 15.0  # Reduced from 30.0
            unit_spacing = 25.0   # Reduced from 45.0
            brace_padding = 30.0  # Reduced from 60.0
        else:
            block_spacing = 12.0  # Reduced from 25.0
            unit_spacing = 20.0   # Reduced from 35.0
            brace_padding = 25.0  # Reduced from 50.0
        
        # Calculate available space
        available_width = dimensions['width'] - 2 * dimensions['padding']
        available_height = dimensions['height'] - 2 * dimensions['padding']
        
        return {
            'block_spacing': block_spacing,
            'unit_spacing': unit_spacing,
            'brace_padding': brace_padding,
            'available_width': available_width,
            'available_height': available_height,
            'complexity_score': complexity_score
        }
    
    def _position_blocks(self, units: List[BlockUnit], spacing_config: Dict, dimensions: Dict) -> List[BlockUnit]:
        """Position blocks using fixed column layout to prevent horizontal crashes"""
        if not units:
            return units
        
        # Step 1: Calculate unit dimensions
        for unit in units:
            self._calculate_unit_dimensions(unit, spacing_config)
        
        # Step 2: Define column layout with fixed brace columns and flexible node columns
        canvas_width = dimensions['width']
        padding = dimensions['padding']

        # Fixed brace visual width (column thickness perception)
        const_main_brace_visual_width = 16.0
        const_small_brace_visual_width = 12.0

        # Gaps around braces
        gap_topic_to_main_brace = 30.0
        gap_main_brace_to_part = 30.0
        gap_part_to_small_brace = 30.0
        gap_small_brace_to_subpart = 30.0

        # Compute max widths of topic, part and subpart blocks to avoid overlap
        max_part_block_width = max((unit.part_block.width for unit in units), default=100.0)
        max_subpart_block_width = 100.0
        max_topic_block_width = 100.0
        for unit in units:
            # topic width approximated as the longest of part/subpart widths if not directly available yet
            if unit.part_block and unit.part_block.width > max_topic_block_width:
                max_topic_block_width = unit.part_block.width
            if unit.subpart_blocks:
                for sb in unit.subpart_blocks:
                    if sb.width > max_subpart_block_width:
                        max_subpart_block_width = sb.width
                    if sb.width > max_topic_block_width:
                        max_topic_block_width = sb.width

        # Column 1: Topic center (keep near left padding). Approximate topic width from part widths if unavailable.
        approx_topic_width = max(60.0, max_topic_block_width)
        topic_column_x = padding + approx_topic_width / 2.0

        # Estimate curly brace corridor widths (adaptive, conservative so parts never overlap brace)
        estimated_main_depth = min(max(24.0, canvas_width * 0.08), 100.0)
        estimated_small_depth = min(max(18.0, canvas_width * 0.06), 80.0)

        # Column 2: Main brace center X (use estimated depth/2 past topic-right + gap)
        main_brace_x = (
            topic_column_x + approx_topic_width / 2.0 + gap_topic_to_main_brace + estimated_main_depth / 2.0
        )

        # Column 3: Parts center depends on estimated brace depth + gap + half of max part width
        part_column_x = (
            topic_column_x + approx_topic_width / 2.0 + gap_topic_to_main_brace + estimated_main_depth + gap_main_brace_to_part + max_part_block_width / 2.0
        )

        # Column 4: Small brace X (use estimated small depth/2 past part-right + gap)
        small_brace_x = (
            part_column_x + max_part_block_width / 2.0 + gap_part_to_small_brace + estimated_small_depth / 2.0
        )

        # Column 5: Subparts center depends on estimated small brace depth + gap + half of max subpart width
        subpart_column_x = (
            part_column_x + max_part_block_width / 2.0 + gap_part_to_small_brace + estimated_small_depth + gap_small_brace_to_subpart + max_subpart_block_width / 2.0
        )
        
        # Step 3: Position units vertically with proper column separation
        current_y = dimensions['padding']
        
        for i, unit in enumerate(units):
            # Position unit at current_y
            unit.y = current_y
            
            # Position part block at computed parts column center
            unit.part_block.x = part_column_x
            unit.part_block.y = unit.y + (unit.height - unit.part_block.height) / 2  # Center vertically in unit
            
            # Position subpart blocks in right column (Column 3)
            if unit.subpart_blocks:
                # Calculate total subpart height for centering
                total_subpart_height = len(unit.subpart_blocks) * unit.subpart_blocks[0].height
                total_spacing = (len(unit.subpart_blocks) - 1) * spacing_config['block_spacing']
                total_height = total_subpart_height + total_spacing
                
                # Start position to center subparts within unit
                start_y = unit.y + (unit.height - total_height) / 2
                
                for j, subpart_block in enumerate(unit.subpart_blocks):
                    subpart_block.x = subpart_column_x
                    subpart_block.y = start_y + j * (subpart_block.height + spacing_config['block_spacing'])
            
            # Update current_y for next unit
            current_y = unit.y + unit.height + spacing_config['unit_spacing']
        
        return units
    
    def _calculate_unit_dimensions(self, unit: BlockUnit, spacing_config: Dict):
        """Calculate unit dimensions based on its blocks with standard heights"""
        if not unit.subpart_blocks:
            # Unit with only part block
            unit.width = unit.part_block.width + spacing_config['brace_padding']
            unit.height = unit.part_block.height  # Standard part height
        else:
            # Unit with part and subpart blocks
            # Calculate width: part width + spacing + max subpart width
            max_subpart_width = max(block.width for block in unit.subpart_blocks)
            unit.width = (unit.part_block.width + spacing_config['block_spacing'] + 
                         max_subpart_width + spacing_config['brace_padding'])
            
            # Calculate height: total height of all subpart blocks + spacing
            # All subpart blocks have the same height, so just multiply by count
            subpart_height = unit.subpart_blocks[0].height  # Standard subpart height
            total_subpart_height = len(unit.subpart_blocks) * subpart_height
            total_spacing = (len(unit.subpart_blocks) - 1) * spacing_config['block_spacing']
            unit.height = max(unit.part_block.height, total_subpart_height + total_spacing)
    
    def _calculate_text_width(self, text: str, font_size: int) -> float:
        """Calculate text width based on font size and character count"""
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
        """Calculate text width based on font size and character count with caching"""
        if not text or font_size <= 0:
            return 0
        
        # Simple caching - could be enhanced with proper cache decorator
        cache_key = f"{text}_{font_size}"
        if hasattr(self, '_text_width_cache') and cache_key in self._text_width_cache:
            return self._text_width_cache[cache_key]
        
        total_width = 0
        for char in text:
            char_width = CHAR_WIDTH_CONFIG.get(char, CHAR_WIDTH_CONFIG['default'])
            total_width += char_width * font_size
        
        # Initialize cache if not exists
        if not hasattr(self, '_text_width_cache'):
            self._text_width_cache = {}
        
        # Cache the result
        self._text_width_cache[cache_key] = total_width
        
        return total_width
    
    def _get_font_weight(self, node_type: str) -> str:
        """Get font weight for node type using configuration"""
        return FONT_WEIGHT_CONFIG.get(node_type, 'normal')


class BraceMapAgent:
    """Brace Map Agent with block-based positioning system"""
    
    def __init__(self):
        self.debugger = DiagramDebugger()
        self.context_manager = ContextManager()
        self.llm_processor = LLMHybridProcessor()
        self.algorithm_selector = ContextAwareAlgorithmSelector(self.context_manager)
        self.layout_calculator = FlexibleLayoutCalculator(self.debugger)
        self.block_positioning = BlockBasedPositioningSystem(self.debugger)
        
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
        """Generate brace map diagram using block-based positioning with enhanced validation"""
        start_time = datetime.now()
        self.debugger.log("Starting block-based brace map generation")
        
        try:
            # Enhanced input validation
            if not spec or not isinstance(spec, dict):
                return {
                    'success': False,
                    'error': 'Invalid specification: must be a non-empty dictionary',
                    'debug_logs': self.debugger.get_logs()
                }
            
            # Validate required fields with defaults
            if 'topic' not in spec or not spec['topic']:
                spec['topic'] = 'Main Topic'
            
            if 'parts' not in spec or not isinstance(spec['parts'], list):
                return {
                    'success': False,
                    'error': 'Invalid specification: missing or invalid "parts" field',
                    'debug_logs': self.debugger.get_logs()
                }
            
            # Validate parts structure with enhanced error messages
            for i, part in enumerate(spec['parts']):
                if not isinstance(part, dict):
                    return {
                        'success': False,
                        'error': f'Invalid part at index {i}: must be a dictionary',
                        'debug_logs': self.debugger.get_logs()
                    }
                
                if 'name' not in part or not part['name']:
                    return {
                        'success': False,
                        'error': f'Invalid part at index {i}: missing or empty "name" field',
                        'debug_logs': self.debugger.get_logs()
                    }
                
                # Ensure subparts is a list
                if 'subparts' not in part:
                    part['subparts'] = []
                elif not isinstance(part['subparts'], list):
                    part['subparts'] = []
                
                # Validate subparts with enhanced error messages
                for j, subpart in enumerate(part['subparts']):
                    if not isinstance(subpart, dict):
                        return {
                            'success': False,
                            'error': f'Invalid subpart at part {i}, subpart {j}: must be a dictionary',
                            'debug_logs': self.debugger.get_logs()
                        }
                    
                    if 'name' not in subpart or not subpart['name']:
                        return {
                            'success': False,
                            'error': f'Invalid subpart at part {i}, subpart {j}: missing or empty "name" field',
                            'debug_logs': self.debugger.get_logs()
                        }
            
            # Validate empty specification
            if not spec['parts']:
                return {
                    'success': False,
                    'error': 'Invalid specification: must have at least one part',
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
            
            # Select layout algorithm
            algorithm = self.algorithm_selector.select_algorithm(spec, user_id)
            
            # Calculate dimensions
            dimensions = self._calculate_dimensions(spec)
            
            # Use block-based positioning system
            self.debugger.log("Using block-based positioning system")
            block_units = self.block_positioning.arrange_blocks(spec, dimensions, self.default_theme)
            
            # Convert block units to NodePosition format for compatibility
            nodes, units = self._convert_blocks_to_nodes(block_units, spec, dimensions)
            
            # Validate that we have nodes
            if not nodes:
                return {
                    'success': False,
                    'error': 'Failed to generate nodes from specification',
                    'debug_logs': self.debugger.get_logs()
                }
            
            # Calculate optimal canvas dimensions
            optimal_dimensions = self._calculate_optimal_dimensions(nodes, dimensions)
            
            # Adjust node positions to center them in the optimal canvas
            nodes = self._adjust_node_positions_for_optimal_canvas(nodes, dimensions, optimal_dimensions)
            
            # Create layout data
            layout_data = {
                'units': self._serialize_units(units),
                'spacing_info': self._serialize_spacing_info(SpacingInfo(
                    unit_spacing=50.0,
                    subpart_spacing=20.0,
                    brace_offset=50.0,
                    content_density=1.0
                )),
                'text_dimensions': self.layout_calculator.calculate_text_dimensions(spec, self.default_theme),
                'canvas_dimensions': optimal_dimensions,
                'nodes': self._serialize_nodes(nodes)
            }
            
            # Generate SVG data
            svg_data = self._generate_svg_data_from_layout(layout_data, self.default_theme)
            
            # Validate SVG data
            if not svg_data or 'elements' not in svg_data:
                return {
                    'success': False,
                    'error': 'Failed to generate SVG data',
                    'debug_logs': self.debugger.get_logs()
                }
            
            # Calculate performance metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                'success': True,
                'svg_data': svg_data,
                'layout_data': layout_data,
                'algorithm_used': algorithm.value,
                'complexity': complexity.value,
                'strategy': strategy.value,
                'processing_time': processing_time,
                'debug_logs': self.debugger.get_logs()
            }
            
            self.debugger.log(f"Block-based generation completed in {processing_time:.3f}s")
            return result
            
        except Exception as e:
            self.debugger.log(f"Error in block-based diagram generation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'debug_logs': self.debugger.get_logs()
            }
    
    def _convert_blocks_to_nodes(self, block_units: List[BlockUnit], spec: Dict, dimensions: Dict) -> Tuple[List[NodePosition], List[UnitPosition]]:
        """Convert block units to NodePosition and UnitPosition format with fixed column layout"""
        nodes = []
        units = []
        
        # Create topic node with enhanced height to prevent squeezing
        topic = spec.get('topic', 'Main Topic')
        topic_width = self._calculate_text_width(topic, self.default_theme['fontTopic'])
        
        # Set topic height to be larger than standard blocks but not full canvas
        # This prevents squeezing while maintaining proper positioning
        topic_height = self.default_theme['fontTopic'] + 60  # Enhanced height for topic blocks
        
        # Position topic in left column (Column 1) - like in the image
        canvas_width = dimensions['width']
        padding = dimensions['padding']
        
        # Topic goes in left column (Column 1) - exactly at padding + 50
        # Since text is centered within the block, we need to adjust for the block width
        topic_x = padding + 50  # Same as topic_column_x in _position_blocks
        
        # Calculate topic Y position to be center-aligned with the group of parts
        if block_units:
            # Calculate the center of all part blocks
            part_centers = []
            for unit in block_units:
                # Part blocks are centered vertically within their units
                # Use the actual part block position: unit.y + (unit.height - part_block.height) / 2
                part_center_y = unit.y + (unit.height - unit.part_block.height) / 2 + unit.part_block.height / 2
                part_centers.append(part_center_y)
            
            # Find the center of all part centers
            parts_center_y = sum(part_centers) / len(part_centers)
            
            # Position topic so its center aligns with the parts center
            topic_y = parts_center_y - topic_height / 2
        else:
            # Fallback: center in canvas if no parts
            topic_y = (dimensions['height'] - topic_height) / 2
        
        # Ensure topic doesn't extend beyond canvas bounds
        if topic_x + topic_width > dimensions['width'] - dimensions['padding']:
            topic_x = dimensions['width'] - dimensions['padding'] - topic_width
        
        topic_node = NodePosition(
            x=topic_x, y=topic_y,
            width=topic_width, height=topic_height,
            text=topic, node_type='topic'
        )
        nodes.append(topic_node)
        
        # Convert block units to UnitPosition format
        for i, block_unit in enumerate(block_units):
            # Convert part block
            part_node = NodePosition(
                x=block_unit.part_block.x, y=block_unit.part_block.y,
                width=block_unit.part_block.width, height=block_unit.part_block.height,
                text=block_unit.part_block.text, node_type='part', part_index=i
            )
            nodes.append(part_node)
            
            # Convert subpart blocks
            subpart_nodes = []
            for j, subpart_block in enumerate(block_unit.subpart_blocks):
                subpart_node = NodePosition(
                    x=subpart_block.x, y=subpart_block.y,
                    width=subpart_block.width, height=subpart_block.height,
                    text=subpart_block.text, node_type='subpart',
                    part_index=i, subpart_index=j
                )
                subpart_nodes.append(subpart_node)
                nodes.append(subpart_node)
            
            # Create UnitPosition
            unit = UnitPosition(
                unit_index=i,
                x=block_unit.x, y=block_unit.y,
                width=block_unit.width, height=block_unit.height,
                part_position=part_node,
                subpart_positions=subpart_nodes
            )
            units.append(unit)
        
        return nodes, units
    
    def _generate_svg_data_from_layout(self, layout_data: Dict, theme: Dict) -> Dict:
        """Generate SVG data from layout data with improved text alignment within blocks"""
        svg_elements = []
        
        # Generate nodes from layout data
        nodes_data = layout_data.get('nodes', [])
        
        # Add text elements for all nodes with improved alignment
        for node_data in nodes_data:
            # Calculate text position to center it within the block
            node_x = node_data['x']
            node_y = node_data['y']
            node_width = node_data['width']
            node_height = node_data['height']
            
            # Center text within the block
            text_x = node_x + node_width / 2
            text_y = node_y + node_height / 2
            
            element = {
                'type': 'text',
                'x': text_x,
                'y': text_y,
                'text': node_data['text'],
                'node_type': node_data['node_type'],
                'font_size': self._get_font_size(node_data['node_type'], theme),
                'fill': self._get_node_color(node_data['node_type'], theme),
                'text_anchor': 'middle',  # Center horizontally
                'dominant_baseline': 'middle',  # Center vertically
                'font_weight': self._get_font_weight(node_data['node_type'])
            }
            svg_elements.append(element)
        
        # Generate brace elements using minimalist design (adaptive to canvas size)
        brace_elements = self._generate_brace_elements(nodes_data, theme, layout_data.get('canvas_dimensions', {}))
        svg_elements.extend(brace_elements)
        
        # Use canvas dimensions from layout data
        canvas_dimensions = layout_data.get('canvas_dimensions', {})
        
        return {
            'elements': svg_elements,
            'width': canvas_dimensions.get('width', 800),
            'height': canvas_dimensions.get('height', 600),
            'background': '#ffffff',
            'layout_data': layout_data
        }
    
    def _generate_brace_elements(self, nodes_data: List[Dict], theme: Dict, canvas_dimensions: Dict) -> List[Dict]:
        """Generate brace path elements (curly style) with adaptive widths and outline (Option 3)"""
        brace_elements = []

        # Determine adaptive stroke widths based on canvas size
        canvas_width = float(canvas_dimensions.get('width', 1000))
        canvas_height = float(canvas_dimensions.get('height', 600))
        # Base on height for visual consistency; clamp to sensible bounds
        scale_h = max(0.5, min(2.0, canvas_height / 600.0))
        main_stroke_width = max(1.5, min(5.5, 3.2 * scale_h))
        small_stroke_width = max(1.0, min(4.5, main_stroke_width * 0.66))

        # Outline widths slightly larger than main strokes
        main_outline_width = min(main_stroke_width * 1.6, main_stroke_width + 3.0)
        small_outline_width = min(small_stroke_width * 1.6, small_stroke_width + 3.0)

        # Colors
        outline_color = theme.get('braceOutlineColor', '#333333')
        brace_color = theme.get('braceColor', '#666666')
        
        # Separate nodes by type
        topic_nodes = [n for n in nodes_data if n['node_type'] == 'topic']
        part_nodes = [n for n in nodes_data if n['node_type'] == 'part']
        subpart_nodes = [n for n in nodes_data if n['node_type'] == 'subpart']
        
        if not topic_nodes or not part_nodes:
            return brace_elements
        
        topic_node = topic_nodes[0]
        topic_center_x = topic_node['x'] + topic_node['width'] / 2
        topic_center_y = topic_node['y'] + topic_node['height'] / 2
        
        # Generate main brace (connects topic to all parts)
        if part_nodes:
            # Find the full vertical extent of all parts (top to bottom)
            parts_top_y = min(n['y'] for n in part_nodes)
            parts_bottom_y = max(n['y'] + n['height'] for n in part_nodes)
            first_part_y = parts_top_y
            last_part_y = parts_bottom_y
            brace_height = last_part_y - first_part_y
            
            # Overlap-safe main brace placement between topic and parts
            topic_right = topic_node['x'] + topic_node['width']
            parts_left = min(n['x'] for n in part_nodes)

            # Curly (math-style) main brace opening to the right (adaptive, balanced spacing)
            safety_gap = max(40.0, canvas_width * 0.05)
            total_lane = max(0.0, (parts_left - safety_gap) - (topic_right + safety_gap))
            depth = min(max(12.0, total_lane * 0.40), 80.0)
            # Compute lane available for placing brace anchor X (excluding depth)
            min_x = topic_right + safety_gap
            max_x = parts_left - safety_gap - depth
            if min_x > max_x:
                # Very tight lane: reduce depth and pin to safe position
                depth = max(6.0, total_lane * 0.25)
                max_x = parts_left - safety_gap - depth
                brace_x = max(min_x, max_x)
            else:
                # Center within lane segment for equal left/right spacing
                brace_x = (min_x + max_x) / 2.0

            y_top = first_part_y
            y_bot = last_part_y
            y_mid = (y_top + y_bot) / 2.0
            d1 = brace_height * 0.18
            d2 = brace_height * 0.12
            mid = brace_height * 0.08

            brace_path = (
                f"M {brace_x:.2f} {y_top:.2f} "
                f"C {brace_x:.2f} {y_top + d2:.2f} {brace_x + depth:.2f} {y_top + d1:.2f} {brace_x + depth:.2f} {y_mid - mid:.2f} "
                f"C {brace_x + depth:.2f} {y_mid - mid/2:.2f} {brace_x:.2f} {y_mid:.2f} {brace_x:.2f} {y_mid:.2f} "
                f"C {brace_x:.2f} {y_mid:.2f} {brace_x + depth:.2f} {y_mid + mid/2:.2f} {brace_x + depth:.2f} {y_bot - d1:.2f} "
                f"C {brace_x + depth:.2f} {y_bot - d2:.2f} {brace_x:.2f} {y_bot - d2/2:.2f} {brace_x:.2f} {y_bot:.2f}"
            )
            
            # Outline (draw first)
            brace_elements.append({
                'type': 'path',
                'd': brace_path,
                'fill': 'none',
                'stroke': outline_color,
                'stroke_width': main_outline_width,
                'stroke_linecap': 'round',
                'stroke_linejoin': 'round'
            })
            # Main stroke (on top)
            brace_elements.append({
                'type': 'path',
                'd': brace_path,
                'fill': 'none',
                'stroke': brace_color,
                'stroke_width': main_stroke_width,
                'stroke_linecap': 'round',
                'stroke_linejoin': 'round'
            })
        
        # Generate small braces (connect each part to its subparts)
        for part_node in part_nodes:
            part_center_x = part_node['x'] + part_node['width'] / 2
            part_center_y = part_node['y'] + part_node['height'] / 2
            part_index = part_node.get('part_index', 0)
            
            # Find subparts for this part
            part_subparts = [n for n in subpart_nodes if n.get('part_index') == part_index]
            
            if part_subparts:
                # Find the full vertical extent of subparts for this part (top to bottom)
                subparts_top_y = min(n['y'] for n in part_subparts)
                subparts_bottom_y = max(n['y'] + n['height'] for n in part_subparts)
                first_subpart_y = subparts_top_y
                last_subpart_y = subparts_bottom_y
                subpart_brace_height = last_subpart_y - first_subpart_y
                
                # Overlap-safe small brace placement between part and subparts
                part_right = part_node['x'] + part_node['width']
                subparts_left = min(n['x'] for n in part_subparts)

                small_brace_width = 6
                small_safety_gap = max(32.0, canvas_width * 0.04)

                # Compute available lane between part and subparts
                small_total_lane = max(0.0, (subparts_left - small_safety_gap) - (part_right + small_safety_gap))
                s_depth = min(max(10.0, small_total_lane * 0.40), 60.0)

                # Clamp small brace x so that x >= part_right+gap and x+s_depth <= subparts_left-gap
                min_sx = part_right + small_safety_gap
                max_sx = subparts_left - small_safety_gap - s_depth
                if min_sx > max_sx:
                    s_depth = max(6.0, small_total_lane * 0.25)
                    max_sx = subparts_left - small_safety_gap - s_depth
                    small_brace_x = max(min_sx, max_sx)
                else:
                    # Center within lane segment for equal left/right spacing
                    small_brace_x = (min_sx + max_sx) / 2.0

                yt = first_subpart_y
                yb = last_subpart_y
                ym = (yt + yb) / 2.0
                sd1 = subpart_brace_height * 0.18
                sd2 = subpart_brace_height * 0.12
                smid = subpart_brace_height * 0.08

                small_brace_path = (
                    f"M {small_brace_x:.2f} {yt:.2f} "
                    f"C {small_brace_x:.2f} {yt + sd2:.2f} {small_brace_x + s_depth:.2f} {yt + sd1:.2f} {small_brace_x + s_depth:.2f} {ym - smid:.2f} "
                    f"C {small_brace_x + s_depth:.2f} {ym - smid/2:.2f} {small_brace_x:.2f} {ym:.2f} {small_brace_x:.2f} {ym:.2f} "
                    f"C {small_brace_x:.2f} {ym:.2f} {small_brace_x + s_depth:.2f} {ym + smid/2:.2f} {small_brace_x + s_depth:.2f} {yb - sd1:.2f} "
                    f"C {small_brace_x + s_depth:.2f} {yb - sd2:.2f} {small_brace_x:.2f} {yb - sd2/2:.2f} {small_brace_x:.2f} {yb:.2f}"
                )
                
                # Outline (draw first)
                brace_elements.append({
                    'type': 'path',
                    'd': small_brace_path,
                    'fill': 'none',
                    'stroke': outline_color,
                    'stroke_width': small_outline_width,
                    'stroke_linecap': 'round',
                    'stroke_linejoin': 'round'
                })
                # Main stroke (on top)
                brace_elements.append({
                    'type': 'path',
                    'd': small_brace_path,
                    'fill': 'none',
                    'stroke': brace_color,
                    'stroke_width': small_stroke_width,
                    'stroke_linecap': 'round',
                    'stroke_linejoin': 'round'
                })
        
        return brace_elements
    
    def _get_font_weight(self, node_type: str) -> str:
        """Get font weight for node type using configuration"""
        return FONT_WEIGHT_CONFIG.get(node_type, 'normal')
    
    def _calculate_dimensions(self, spec: Dict) -> Dict:
        """Calculate initial canvas dimensions based on actual content analysis"""
        parts = spec.get('parts', [])
        topic = spec.get('topic', 'Main Topic')
        total_subparts = sum(len(part.get('subparts', [])) for part in parts)
        total_parts = len(parts)
        
        # Calculate max text length safely
        text_lengths = [len(topic)]
        if parts:
            text_lengths.extend(len(part['name']) for part in parts)
            for part in parts:
                if 'subparts' in part and part['subparts']:
                    text_lengths.extend(len(subpart['name']) for subpart in part['subparts'])
        
        max_text_length = max(text_lengths) if text_lengths else len(topic)
        
        # Calculate dimensions based on actual content
        # Base dimensions per element type
        topic_height = 84  # fontTopic + 60
        part_height = 38   # fontPart + 20
        subpart_height = 34  # fontSubpart + 20
        
        # Calculate required height based on content
        if total_subparts == 0:
            # Only topic and parts
            required_height = topic_height + (total_parts * part_height) + (total_parts * 20)  # 20px spacing between parts
        else:
            # Topic + parts + subparts
            required_height = topic_height + (total_parts * part_height) + (total_subparts * subpart_height) + (total_parts * 30) + (total_subparts * 15)  # Spacing
        
        # Calculate required width for 5-column layout
        # Column 1: Topic, Column 2: Main brace, Column 3: Parts, Column 4: Small braces, Column 5: Subparts
        estimated_topic_width = max_text_length * 12  # Approximate character width
        estimated_part_width = max(len(part['name']) for part in parts) * 10 if parts else 100
        estimated_subpart_width = max(len(subpart['name']) for part in parts for subpart in part.get('subparts', [])) * 8 if total_subparts > 0 else 100
        
        # 5-column layout requires more width
        required_width = estimated_topic_width + 150 + estimated_part_width + 150 + estimated_subpart_width + 120  # Tighter trailing spacing
        
        # Add watermark space (bottom and right margins)
        watermark_margin = 24  # Tighter watermark margin
        
        # Calculate final dimensions with minimal padding
        final_width = max(required_width + watermark_margin, 800)  # Increased minimum width for 5-column layout
        final_height = max(required_height + watermark_margin, 400)  # Minimum height
        
        # Ensure reasonable aspect ratio without shrinking content width/height
        aspect_ratio = final_width / final_height
        if aspect_ratio > 3:  # Too wide: increase height instead of reducing width
            final_height = max(final_height, int(final_width / 2.5))
        elif aspect_ratio < 0.5:  # Too tall: increase width instead of reducing height
            final_width = max(final_width, int(final_height * 0.8))
        
        # Minimal padding for content
        padding = 16  # Tighter padding for brace map
        
        return {
            'width': int(final_width),
            'height': int(final_height),
            'padding': padding
        }
    
    def _calculate_optimal_dimensions(self, nodes: List[NodePosition], initial_dimensions: Dict) -> Dict:
        """Calculate optimal canvas dimensions based on actual node positions with watermark space"""
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
        
        # Add minimal padding for content (left padding target)
        content_padding = 24  # Tighter left margin
        
        # Add watermark space (bottom and right margins)
        watermark_margin = 80  # Space for watermark
        
        # Calculate optimal dimensions with asymmetric margins
        # Left: content_padding, Right: very small fixed spacing to trim trailing gap
        right_spacing = 12  # keep a small buffer after subparts
        optimal_width = int(content_width + content_padding + right_spacing)
        # Height keeps additional space for watermark at bottom
        optimal_height = int(content_height + 2 * content_padding + watermark_margin)
        
        # Ensure minimum size and trim excessive right-side whitespace by fitting to content bounds
        optimal_width = max(int(optimal_width), 600)
        optimal_height = max(int(optimal_height), 400)
        
        # Ensure reasonable aspect ratio without shrinking content; expand the smaller side
        aspect_ratio = optimal_width / optimal_height
        if aspect_ratio > 3:  # Too wide: expand height
            optimal_height = max(optimal_height, int(optimal_width / 2.5))
        elif aspect_ratio < 0.5:  # Too tall: expand width
            optimal_width = max(optimal_width, int(optimal_height * 0.8))
        
        return {
            'width': int(optimal_width),
            'height': int(optimal_height),
            'padding': initial_dimensions['padding'],
            'content_bounds': {
                'min_x': min_x,
                'max_x': max_x,
                'min_y': min_y,
                'max_y': max_y
            }
        }
    
    def _adjust_node_positions_for_optimal_canvas(self, nodes: List[NodePosition], initial_dimensions: Dict, optimal_dimensions: Dict) -> List[NodePosition]:
        """Adjust node positions to center them in the optimal canvas while preserving topic alignment"""
        if not nodes:
            return nodes
        
        content_bounds = optimal_dimensions['content_bounds']
        
        # Calculate content dimensions
        content_width = content_bounds['max_x'] - content_bounds['min_x']
        content_height = content_bounds['max_y'] - content_bounds['min_y']
        
        # Calculate minimal padding for centering
        content_padding = 40  # Minimal padding around content
        
        # Calculate centering offsets with minimal padding (never negative)
        offset_x = max(0, content_padding - content_bounds['min_x'])
        offset_y = max(0, content_padding - content_bounds['min_y'])
        
        # Find topic and part nodes
        topic_nodes = [node for node in nodes if node.node_type == 'topic']
        part_nodes = [node for node in nodes if node.node_type == 'part']
        
        # Calculate the original alignment between topic and parts
        original_topic_part_alignment = None
        if topic_nodes and part_nodes:
            topic_node = topic_nodes[0]
            part_centers = [part.y + part.height / 2 for part in part_nodes]
            parts_center_y = sum(part_centers) / len(part_centers)
            topic_center_y = topic_node.y + topic_node.height / 2
            original_topic_part_alignment = topic_center_y - parts_center_y
            print(f"DEBUG: Original topic-part alignment: {original_topic_part_alignment:.1f}")
        
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
        
        # If we had topic-part alignment, preserve it after adjustment
        if original_topic_part_alignment is not None and topic_nodes and part_nodes:
            adjusted_topic = next((node for node in adjusted_nodes if node.node_type == 'topic'), None)
            adjusted_parts = [node for node in adjusted_nodes if node.node_type == 'part']
            
            if adjusted_topic and adjusted_parts:
                # Calculate new parts center after adjustment
                new_part_centers = [part.y + part.height / 2 for part in adjusted_parts]
                new_parts_center_y = sum(new_part_centers) / len(new_part_centers)
                
                # Calculate what the topic center should be to maintain alignment
                target_topic_center_y = new_parts_center_y + original_topic_part_alignment
                
                # Calculate the new topic Y position
                new_topic_y = target_topic_center_y - adjusted_topic.height / 2
                
                print(f"DEBUG: New parts center: {new_parts_center_y:.1f}")
                print(f"DEBUG: Target topic center: {target_topic_center_y:.1f}")
                print(f"DEBUG: New topic Y: {new_topic_y:.1f}")
                print(f"DEBUG: Before adjustment - topic Y: {adjusted_topic.y:.1f}")
                
                # Update topic position
                adjusted_topic.y = new_topic_y
                
                print(f"DEBUG: After adjustment - topic Y: {adjusted_topic.y:.1f}")
        
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
        
        # After adjustments, recompute tight canvas width to trim right-side spacing
        if nodes:
            adjusted_max_x = max(node.x + node.width for node in nodes)
            # Keep a small right buffer; do not re-add left padding (nodes are absolute)
            tight_right_buffer = 12
            tight_width = int(max(adjusted_max_x + tight_right_buffer, 600))
            # Update optimal dimensions width only (preserve height and padding)
            optimal_dimensions = {
                **optimal_dimensions,
                'width': tight_width,
            }

        # Create layout data with updated optimal dimensions
        layout_data = {
            'units': self._serialize_units(adjusted_units),
            'spacing_info': self._serialize_spacing_info(SpacingInfo(
                unit_spacing=50.0,
                subpart_spacing=20.0,
                brace_offset=50.0,
                content_density=1.0
            )),
            'text_dimensions': text_dimensions,
            'canvas_dimensions': optimal_dimensions,
            'nodes': self._serialize_nodes(nodes)
        }
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return LayoutResult(
            nodes=nodes,
            braces=[],  # Braces will be handled in rendering phase
            dimensions=optimal_dimensions,  # Use updated optimal dimensions
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
    
    def _calculate_text_width(self, text: str, font_size: int) -> float:
        """Calculate text width based on font size and character count"""
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


# Export the main agent class
__all__ = ['BraceMapAgent', 'LayoutAlgorithm', 'LayoutComplexity', 'LLMStrategy'] 