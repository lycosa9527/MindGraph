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
from typing import Dict, List, Optional, Tuple, Any
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
    VERTICAL_NODE_GROUP = "vertical_node_group"
    VERTICAL_STACK = "vertical_stack"
    HORIZONTAL_BRACE = "horizontal_brace"
    GROUPED_SEQUENTIAL = "grouped_sequential"


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


class ContextManager:
    """Context management for user preferences and session data"""
    
    def __init__(self):
        self.user_sessions = {}
        self.prompt_history = {}
        self.preferences = {}
    
    def store_user_prompt(self, user_id: str, prompt: str, diagram_type: str):
        """Store user prompt for context-aware generation"""
        if user_id not in self.prompt_history:
            self.prompt_history[user_id] = []
        
        self.prompt_history[user_id].append({
            'prompt': prompt,
            'diagram_type': diagram_type,
            'timestamp': datetime.now(),
            'session_id': self._get_current_session(user_id)
        })
    
    def get_user_context(self, user_id: str) -> Dict:
        """Retrieve user context for personalized generation"""
        context = {
            'recent_prompts': self.prompt_history.get(user_id, [])[-5:],
            'preferences': self.preferences.get(user_id, {}),
            'session_data': self.user_sessions.get(user_id, {})
        }
        return context
    
    def update_preferences(self, user_id: str, preferences: Dict):
        """Update user preferences for future generations"""
        if user_id not in self.preferences:
            self.preferences[user_id] = {}
        self.preferences[user_id].update(preferences)
    
    def alter_diagram_based_on_context(self, spec: Dict, context: Dict) -> Dict:
        """Modify diagram specification based on stored context"""
        modified_spec = spec.copy()
        
        # Apply user preferences
        if 'style_preferences' in context['preferences']:
            modified_spec['style'] = context['preferences']['style_preferences']
        
        # Apply context from recent prompts
        recent_prompts = context['recent_prompts']
        if recent_prompts:
            # Analyze recent prompts for patterns
            common_themes = self._extract_common_themes(recent_prompts)
            modified_spec['context_themes'] = common_themes
        
        return modified_spec
    
    def _get_current_session(self, user_id: str) -> str:
        """Get current session ID for user"""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _extract_common_themes(self, recent_prompts: List[Dict]) -> List[str]:
        """Extract common themes from recent prompts"""
        # Simple theme extraction - can be enhanced with NLP
        themes = []
        for prompt_data in recent_prompts:
            prompt = prompt_data.get('prompt', '').lower()
            if 'animals' in prompt:
                themes.append('animals')
            elif 'science' in prompt:
                themes.append('science')
            elif 'business' in prompt:
                themes.append('business')
        return list(set(themes))


class CollisionDetector:
    """Detect and resolve node collisions"""
    
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
        max_iterations = 50
        iteration = 0
        
        while iteration < max_iterations:
            collisions = CollisionDetector.detect_node_collisions(nodes, padding)
            if not collisions:
                break
            
            # Resolve each collision
            for node1, node2 in collisions:
                CollisionDetector._resolve_collision(node1, node2, padding)
            
            iteration += 1
        
        return nodes
    
    @staticmethod
    def _nodes_overlap(node1: NodePosition, node2: NodePosition, padding: float) -> bool:
        """Check if two nodes overlap"""
        return (abs(node1.x - node2.x) < (node1.width + node2.width) / 2 + padding and
                abs(node1.y - node2.y) < (node1.height + node2.height) / 2 + padding)
    
    @staticmethod
    def _resolve_collision(node1: NodePosition, node2: NodePosition, padding: float):
        """Resolve collision between two nodes"""
        # Calculate separation vector
        dx = node2.x - node1.x
        dy = node2.y - node1.y
        
        # Calculate required separation
        required_separation = (node1.width + node2.width) / 2 + padding
        
        # Calculate current distance
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance > 0:
            # Normalize and scale separation vector
            scale = (required_separation - distance) / distance
            node1.x -= dx * scale * 0.5
            node1.y -= dy * scale * 0.5
            node2.x += dx * scale * 0.5
            node2.y += dy * scale * 0.5


class LLMHybridProcessor:
    """Hybrid LLM + Python processing for layout optimization"""
        
    def analyze_complexity(self, spec: Dict) -> LayoutComplexity:
        """Analyze content complexity to determine processing strategy"""
        num_parts = len(spec.get('parts', []))
        max_subparts = max([len(part.get('subparts', [])) for part in spec.get('parts', [])], default=0)
        total_subparts = sum([len(part.get('subparts', [])) for part in spec.get('parts', [])])
        
        if num_parts <= 3 and max_subparts <= 5 and total_subparts <= 15:
            return LayoutComplexity.SIMPLE
        elif num_parts <= 6 and total_subparts <= 30:
            return LayoutComplexity.MODERATE
        else:
            return LayoutComplexity.COMPLEX
                
    def determine_strategy(self, complexity: LayoutComplexity, user_preferences: Optional[Dict]) -> LLMStrategy:
        """Determine LLM strategy based on complexity and preferences"""
        if user_preferences and user_preferences.get('python_only', False):
            return LLMStrategy.PYTHON_ONLY
        
        if complexity == LayoutComplexity.SIMPLE:
            return LLMStrategy.PYTHON_ONLY
        elif complexity == LayoutComplexity.MODERATE:
            return LLMStrategy.LLM_ENHANCEMENT
        else:
            return LLMStrategy.LLM_FIRST
    

class ContextAwareAlgorithmSelector:
    """Select algorithms based on user context and preferences"""
    
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
    
    def select_algorithm(self, spec: Dict, user_id: str = None) -> LayoutAlgorithm:
        """Select layout algorithm based on context"""
        if not user_id:
            return self._default_algorithm_selection(spec)
        
        context = self.context_manager.get_user_context(user_id)
        preferences = context.get('preferences', {})
        
        # Check user's preferred algorithm
        if 'preferred_algorithm' in preferences:
            return self._get_algorithm_from_preference(preferences['preferred_algorithm'])
        
        # Check recent usage patterns
        recent_prompts = context.get('recent_prompts', [])
        if recent_prompts:
            return self._analyze_usage_patterns(recent_prompts, spec)
        
        return self._default_algorithm_selection(spec)
    
    def _default_algorithm_selection(self, spec: Dict) -> LayoutAlgorithm:
        """Default algorithm selection based on content characteristics"""
        num_parts = len(spec.get('parts', []))
        max_subparts = max([len(part.get('subparts', [])) for part in spec.get('parts', [])], default=0)
        
        # User preference for no braces
        if hasattr(self, 'user_preferences') and self.user_preferences.get('no_braces', False):
            return LayoutAlgorithm.VERTICAL_NODE_GROUP
        
        # Specific structure requirements
        if num_parts == 3 and all(len(part.get('subparts', [])) == 3 for part in spec.get('parts', [])):
            return LayoutAlgorithm.HORIZONTAL_BRACE
        
        # Content-based selection
        if num_parts <= 3 and max_subparts <= 5:
            return LayoutAlgorithm.VERTICAL_STACK
        elif num_parts <= 6:
            return LayoutAlgorithm.VERTICAL_NODE_GROUP
        else:
            return LayoutAlgorithm.VERTICAL_NODE_GROUP  # Most scalable
    
    def _get_algorithm_from_preference(self, preference: str) -> LayoutAlgorithm:
        """Get algorithm from user preference string"""
        preference_map = {
            'vertical_node_group': LayoutAlgorithm.VERTICAL_NODE_GROUP,
            'vertical_stack': LayoutAlgorithm.VERTICAL_STACK,
            'horizontal_brace': LayoutAlgorithm.HORIZONTAL_BRACE,
            'grouped_sequential': LayoutAlgorithm.GROUPED_SEQUENTIAL
        }
        return preference_map.get(preference, LayoutAlgorithm.VERTICAL_NODE_GROUP)
    
    def _analyze_usage_patterns(self, recent_prompts: List, spec: Dict) -> LayoutAlgorithm:
        """Analyze recent prompts to determine optimal algorithm"""
        # Simple pattern analysis - can be enhanced
        return self._default_algorithm_selection(spec) 


class BraceMapAgent:
    """
    Brace Map Agent with Dynamic Positioning System
    
    Implements content-aware brace map generation with dynamic positioning
    based on actual content structure rather than hardcoded layouts.
    """
    
    def __init__(self):
        self.debugger = DiagramDebugger()
        self.context_manager = ContextManager()
        self.user_preferences = {}
        self.llm_processor = LLMHybridProcessor()
        self.algorithm_selector = ContextAwareAlgorithmSelector(self.context_manager)
        
        # Default dimensions and theme
        self.dimensions = {
            'width': 800,
            'height': 600,
            'padding': 40
        }
        
        self.theme = {
            'fontTopic': 24,
            'fontPart': 18,
            'fontSubpart': 14,
            'topicColor': '#ffd700',
            'partColor': '#87CEFA',
            'subpartColor': '#98FB98',
            'strokeColor': '#333',
            'strokeWidth': 2
        }
        
        self.diagram_type = 'brace_map'
    
    def generate_diagram(self, spec: Dict, user_id: str = None) -> Dict:
        """Main entry point with context-aware generation"""
        start_time = datetime.now()
        
        try:
            # Get user context and modify spec
            if user_id:
                context = self.context_manager.get_user_context(user_id)
                spec = self.context_manager.alter_diagram_based_on_context(spec, context)
            
            # Select algorithm based on context
            algorithm = self.algorithm_selector.select_algorithm(spec, user_id)
            
            # Execute positioning (agent-specific)
            layout_result = self._handle_positioning(spec, self.dimensions, self.theme)
            
            # Validate positioning (agent-specific)
            layout_result.nodes = self._validate_positioning(layout_result.nodes, layout_result.dimensions)
            
            # Generate SVG
            svg_data = self._generate_svg_data(layout_result, self.theme)
            
            # Store context
            if user_id:
                self.context_manager.store_user_prompt(user_id, spec.get('prompt', ''), self.diagram_type)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Convert LayoutResult to JSON-serializable format
            serializable_layout = {
                'nodes': [
                    {
                        'x': node.x,
                        'y': node.y,
                        'width': node.width,
                        'height': node.height,
                        'text': node.text,
                        'node_type': node.node_type,
                        'part_index': node.part_index,
                        'subpart_index': node.subpart_index
                    }
                    for node in layout_result.nodes
                ],
                'braces': layout_result.braces,
                'dimensions': layout_result.dimensions,
                'algorithm_used': layout_result.algorithm_used.value,
                'performance_metrics': layout_result.performance_metrics
            }
            
            return {
                'success': True,
                'svg_data': svg_data,
                'layout_result': serializable_layout,
                'processing_time': processing_time,
                'algorithm_used': algorithm.value
            }
            
        except Exception as e:
            self.debugger.log(f"Error generating brace map: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
    
    def _handle_positioning(self, spec: Dict, dimensions: Dict, theme: Dict) -> LayoutResult:
        """Brace map specific positioning logic"""
        # Analyze complexity and select algorithm
        complexity = self.llm_processor.analyze_complexity(spec)
        strategy = self.llm_processor.determine_strategy(complexity, self.user_preferences)
        
        # Select appropriate algorithm
        algorithm = self._select_layout_algorithm(spec, dimensions)
        
        # Execute the selected algorithm
        return self._execute_layout_algorithm(algorithm, spec, dimensions, theme)
    
    def _validate_positioning(self, nodes: List[NodePosition], dimensions: Dict) -> List[NodePosition]:
        """Brace map specific positioning validation"""
        # Validate boundaries
        adjusted_nodes = self._validate_and_adjust_boundaries(nodes, dimensions)
        
        # Resolve collisions
        adjusted_nodes = CollisionDetector.resolve_collisions(adjusted_nodes, padding=20.0)
        
        return adjusted_nodes
    
    def _select_layout_algorithm(self, spec: Dict, dimensions: Dict) -> LayoutAlgorithm:
        """Enhanced algorithm selection based on content characteristics"""
        num_parts = len(spec.get('parts', []))
        max_subparts = max([len(part.get('subparts', [])) for part in spec.get('parts', [])], default=0)
        total_subparts = sum([len(part.get('subparts', [])) for part in spec.get('parts', [])])
        
        # User preference for no braces
        if self.user_preferences.get('no_braces', False):
            return LayoutAlgorithm.VERTICAL_NODE_GROUP
        
        # Specific structure requirements
        if num_parts == 3 and all(len(part.get('subparts', [])) == 3 for part in spec.get('parts', [])):
            return LayoutAlgorithm.HORIZONTAL_BRACE
        
        # Content-based selection
        if num_parts <= 3 and max_subparts <= 5:
            return LayoutAlgorithm.VERTICAL_STACK
        elif num_parts <= 6:
            return LayoutAlgorithm.VERTICAL_NODE_GROUP
        else:
            return LayoutAlgorithm.VERTICAL_NODE_GROUP  # Most scalable
    
    def _execute_layout_algorithm(self, algorithm: LayoutAlgorithm, spec: Dict, dimensions: Dict, theme: Dict) -> LayoutResult:
        """Execute the selected layout algorithm"""
        start_time = datetime.now()
        
        if algorithm == LayoutAlgorithm.VERTICAL_NODE_GROUP:
            return self._vertical_node_group_layout(spec, dimensions, theme)
        elif algorithm == LayoutAlgorithm.VERTICAL_STACK:
            return self._vertical_stack_layout(spec, dimensions, theme)
        elif algorithm == LayoutAlgorithm.HORIZONTAL_BRACE:
            return self._horizontal_brace_layout(spec, dimensions, theme)
        elif algorithm == LayoutAlgorithm.GROUPED_SEQUENTIAL:
            return self._grouped_sequential_layout(spec, dimensions, theme)
        else:
            # Fallback to default algorithm
            return self._vertical_node_group_layout(spec, dimensions, theme)
    
    def _vertical_node_group_layout(self, spec: Dict, dimensions: Dict, theme: Dict) -> LayoutResult:
        """Vertical node group layout without braces - clean and scalable"""
        start_time = datetime.now()
        nodes = []
        braces = []
        
        parts = spec.get('parts', [])
        topic = spec.get('topic', 'Main Topic')
        
        # Calculate positions for all parts and subparts
        for i, part in enumerate(parts):
            # Position part
            part_x = dimensions['padding'] + 50
            part_y = self._calculate_part_y_position(i, parts, dimensions)
            
            nodes.append(NodePosition(
                x=part_x, y=part_y,
                width=self._calculate_text_width(part['name'], theme['fontPart']),
                height=theme['fontPart'] + 20,
                text=part['name'], node_type='part', part_index=i
            ))
            
            # Position subparts
            if 'subparts' in part and part['subparts']:
                subpart_x = part_x + 200  # Right of part
                for j, subpart in enumerate(part['subparts']):
                    subpart_y = self._calculate_subpart_y_position(j, part['subparts'], dimensions)
                    
                    nodes.append(NodePosition(
                        x=subpart_x, y=subpart_y,
                        width=self._calculate_text_width(subpart['name'], theme['fontSubpart']),
                        height=theme['fontSubpart'] + 20,
                        text=subpart['name'], node_type='subpart',
                        part_index=i, subpart_index=j
                    ))
        
        # Position main topic
        topic_x, topic_y = self._calculate_main_topic_position(parts, dimensions)
        nodes.append(NodePosition(
            x=topic_x, y=topic_y,
            width=self._calculate_text_width(topic, theme['fontTopic']),
            height=theme['fontTopic'] + 20,
            text=topic, node_type='topic'
        ))
        
        # Validate and resolve collisions
        nodes = self._validate_and_adjust_boundaries(nodes, dimensions)
        nodes = CollisionDetector.resolve_collisions(nodes, padding=20.0)
        
        return LayoutResult(
            nodes=nodes, braces=braces, dimensions=dimensions,
            algorithm_used=LayoutAlgorithm.VERTICAL_NODE_GROUP,
            performance_metrics={'processing_time': (datetime.now() - start_time).total_seconds()}
        )
    
    def _vertical_stack_layout(self, spec: Dict, dimensions: Dict, theme: Dict) -> LayoutResult:
        """Traditional brace map with vertical arrangement and braces"""
        start_time = datetime.now()
        nodes = []
        braces = []
        
        parts = spec.get('parts', [])
        topic = spec.get('topic', 'Main Topic')
        
        # Position main topic on the left
        topic_x = dimensions['padding'] + 50
        topic_y = dimensions['height'] / 2
        
        nodes.append(NodePosition(
            x=topic_x, y=topic_y,
            width=self._calculate_text_width(topic, theme['fontTopic']),
            height=theme['fontTopic'] + 20,
            text=topic, node_type='topic'
        ))
        
        # Position parts to the right of main topic
        for i, part in enumerate(parts):
            part_x = topic_x + 150
            part_y = self._calculate_part_y_position(i, parts, dimensions)
            
            nodes.append(NodePosition(
                x=part_x, y=part_y,
                width=self._calculate_text_width(part['name'], theme['fontPart']),
                height=theme['fontPart'] + 20,
                text=part['name'], node_type='part', part_index=i
            ))
        
            # Add brace from topic to part
            braces.append({
                'type': 'brace',
                'start': {'x': topic_x + self._calculate_text_width(topic, theme['fontTopic']) / 2, 'y': topic_y},
                'end': {'x': part_x, 'y': part_y}
            })
            
            # Position subparts to the right of parts
            if 'subparts' in part and part['subparts']:
                subpart_x = part_x + 150
                for j, subpart in enumerate(part['subparts']):
                    subpart_y = self._calculate_subpart_y_position(j, part['subparts'], dimensions)
                    
                    nodes.append(NodePosition(
                        x=subpart_x, y=subpart_y,
                        width=self._calculate_text_width(subpart['name'], theme['fontSubpart']),
                        height=theme['fontSubpart'] + 20,
                        text=subpart['name'], node_type='subpart',
                        part_index=i, subpart_index=j
                    ))
                    
                    # Add brace from part to subpart
                    braces.append({
                        'type': 'brace',
                        'start': {'x': part_x + self._calculate_text_width(part['name'], theme['fontPart']) / 2, 'y': part_y},
                        'end': {'x': subpart_x, 'y': subpart_y}
                    })
        
        # Validate and resolve collisions
        nodes = self._validate_and_adjust_boundaries(nodes, dimensions)
        nodes = CollisionDetector.resolve_collisions(nodes, padding=20.0)
        
        return LayoutResult(
            nodes=nodes, braces=braces, dimensions=dimensions,
            algorithm_used=LayoutAlgorithm.VERTICAL_STACK,
            performance_metrics={'processing_time': (datetime.now() - start_time).total_seconds()}
        )
    
    def _horizontal_brace_layout(self, spec: Dict, dimensions: Dict, theme: Dict) -> LayoutResult:
        """Horizontal arrangement for 3x3 structures"""
        start_time = datetime.now()
        nodes = []
        braces = []
        
        parts = spec.get('parts', [])
        topic = spec.get('topic', 'Main Topic')
        
        # Position main topic at top center
        topic_x = dimensions['width'] / 2
        topic_y = dimensions['padding'] + 50
        
        nodes.append(NodePosition(
            x=topic_x, y=topic_y,
            width=self._calculate_text_width(topic, theme['fontTopic']),
            height=theme['fontTopic'] + 20,
            text=topic, node_type='topic'
        ))
        
        # Position 3 parts horizontally below main topic
        for i, part in enumerate(parts):
            part_x = dimensions['padding'] + 100 + i * 200
            part_y = topic_y + 100
            
            nodes.append(NodePosition(
                x=part_x, y=part_y,
                width=self._calculate_text_width(part['name'], theme['fontPart']),
                height=theme['fontPart'] + 20,
                text=part['name'], node_type='part', part_index=i
            ))
        
            # Add brace from topic to part
            braces.append({
                'type': 'brace',
                'start': {'x': topic_x, 'y': topic_y + theme['fontTopic'] + 20},
                'end': {'x': part_x, 'y': part_y}
            })
            
            # Position 3 subparts vertically to the right of each part
            if 'subparts' in part and part['subparts']:
                for j, subpart in enumerate(part['subparts']):
                    subpart_x = part_x + 150
                    subpart_y = part_y - 50 + j * 50
                
                nodes.append(NodePosition(
                    x=subpart_x, y=subpart_y,
                    width=self._calculate_text_width(subpart['name'], theme['fontSubpart']),
                    height=theme['fontSubpart'] + 20,
                    text=subpart['name'], node_type='subpart',
                    part_index=i, subpart_index=j
                ))
                
                # Add brace from part to subpart
                braces.append({
                    'type': 'brace',
                    'start': {'x': part_x + self._calculate_text_width(part['name'], theme['fontPart']) / 2, 'y': part_y},
                    'end': {'x': subpart_x, 'y': subpart_y}
                })
        
        # Validate and resolve collisions
        nodes = self._validate_and_adjust_boundaries(nodes, dimensions)
        nodes = CollisionDetector.resolve_collisions(nodes, padding=20.0)
        
        return LayoutResult(
            nodes=nodes, braces=braces, dimensions=dimensions,
            algorithm_used=LayoutAlgorithm.HORIZONTAL_BRACE,
            performance_metrics={'processing_time': (datetime.now() - start_time).total_seconds()}
        )
    
    def _grouped_sequential_layout(self, spec: Dict, dimensions: Dict, theme: Dict) -> LayoutResult:
        """Block-based layout with left-aligned groups"""
        start_time = datetime.now()
        nodes = []
        braces = []
        
        parts = spec.get('parts', [])
        topic = spec.get('topic', 'Main Topic')
        
        # Step 1: Calculate each part-subpart as a small group first
        part_groups = []
        for i, part in enumerate(parts):
            subparts = part.get('subparts', [])
            subpart_heights = [self._calculate_text_width(sub['name'], theme['fontSubpart']) + 20 for sub in subparts]
            subpart_widths = [self._calculate_text_width(sub['name'], theme['fontSubpart']) + 20 for sub in subparts]
            
            part_width = self._calculate_text_width(part['name'], theme['fontPart']) + 20
            part_height = theme['fontPart'] + 20
            
            # Calculate group dimensions
            group_height = part_height
            if subpart_heights:
                group_height += sum(subpart_heights) + (len(subpart_heights) - 1) * 15 + 20
            
            part_groups.append({
                'part': part,
                'subparts': subparts,
                'part_width': part_width,
                'part_height': part_height,
                'subpart_heights': subpart_heights,
                'subpart_widths': subpart_widths,
                'group_height': group_height
            })
        
        # Step 2: Lay out groups vertically
        max_group_height = max(group['group_height'] for group in part_groups) if part_groups else 0
        group_spacing = max(60, max_group_height * 0.4)
        total_height = sum(group['group_height'] for group in part_groups) + (len(part_groups) - 1) * group_spacing
        start_y = (dimensions['height'] - total_height) / 2
        current_y = start_y
        
        for i, group in enumerate(part_groups):
            part = group['part']
            part_width = group['part_width']
            part_height = group['part_height']
            subparts = group['subparts']
            subpart_heights = group['subpart_heights']
            subpart_widths = group['subpart_widths']
            
            # Position part within its block (left-aligned)
            part_x = dimensions['padding'] + 50
            part_y = current_y + part_height / 2
            
            nodes.append(NodePosition(
                x=part_x, y=part_y,
                width=part_width, height=part_height,
                text=part['name'], node_type='part', part_index=i
            ))
            
            # Position subparts left-aligned below the part
            if subparts:
                subpart_start_x = part_x
                subpart_start_y = part_y + part_height / 2 + 20
                
                current_subpart_y = subpart_start_y
                for j, subpart in enumerate(subparts):
                    subpart_width = subpart_widths[j]
                    subpart_height = subpart_heights[j]
                    
                    subpart_x = subpart_start_x
                    subpart_y = current_subpart_y + subpart_height / 2
                    
                    nodes.append(NodePosition(
                        x=subpart_x, y=subpart_y,
                        width=subpart_width, height=subpart_height,
                        text=subpart['name'], node_type='subpart',
                        part_index=i, subpart_index=j
                    ))
                    
                    current_subpart_y += subpart_height + 15
            
            current_y += group['group_height'] + group_spacing
        
        # Step 3: Position main topic (left-center aligned, close to blocks)
        topic_width = self._calculate_text_width(topic, theme['fontTopic'])
        topic_height = theme['fontTopic'] + 20
        
        topic_x = dimensions['padding'] + 20
        topic_y = dimensions['height'] / 2
        
        nodes.append(NodePosition(
            x=topic_x, y=topic_y,
            width=topic_width, height=topic_height,
            text=topic, node_type='topic'
        ))
        
        # Validate and resolve collisions
        nodes = self._validate_and_adjust_boundaries(nodes, dimensions)
        nodes = CollisionDetector.resolve_collisions(nodes, padding=20.0)
        
        return LayoutResult(
            nodes=nodes, braces=braces, dimensions=dimensions,
            algorithm_used=LayoutAlgorithm.GROUPED_SEQUENTIAL,
            performance_metrics={'processing_time': (datetime.now() - start_time).total_seconds()}
        )

    def _calculate_main_topic_position(self, parts: List, dimensions: Dict) -> Tuple[float, float]:
        """Calculate main topic position with validation and fallback"""
        num_parts = len(parts)
        
        # Calculate position based on number of parts
        if num_parts % 2 == 0:  # Even number of parts
            main_topic_part_index = num_parts // 2 - 1
        else:  # Odd number of parts
            main_topic_part_index = num_parts // 2
        
        # Get the corresponding part position
        if 0 <= main_topic_part_index < len(parts):
            part_x = dimensions['padding'] + 50
            part_y = self._calculate_part_y_position(main_topic_part_index, parts, dimensions)
            return (part_x - 100, part_y)  # Left of the part
        
        # Fallback: center of canvas
        return (dimensions['width'] / 2, dimensions['height'] / 2)

    def _calculate_part_y_position(self, part_index: int, parts: List, dimensions: Dict) -> float:
        """Calculate Y position for a part based on its index"""
        total_parts = len(parts)
        if total_parts == 0:
            return dimensions['height'] / 2
        
        # Calculate spacing between parts
        available_height = dimensions['height'] - 2 * dimensions['padding']
        spacing = available_height / (total_parts + 1)
        
        return dimensions['padding'] + spacing * (part_index + 1)
    
    def _calculate_subpart_y_position(self, subpart_index: int, subparts: List, dimensions: Dict) -> float:
        """Calculate Y position for a subpart based on its index"""
        total_subparts = len(subparts)
        if total_subparts == 0:
            return dimensions['height'] / 2
        
        # Calculate spacing between subparts
        available_height = dimensions['height'] - 2 * dimensions['padding']
        spacing = available_height / (total_subparts + 1)
        
        return dimensions['padding'] + spacing * (subpart_index + 1)
    
    def _calculate_text_width(self, text: str, font_size: int) -> float:
        """Calculate text width based on font size and character count"""
        # Simple approximation - can be enhanced with actual font metrics
        return len(text) * font_size * 0.6

    def _validate_and_adjust_boundaries(self, nodes: List[NodePosition], dimensions: Dict) -> List[NodePosition]:
        """Validate node boundaries and adjust if necessary"""
        adjusted_nodes = []
        
        for node in nodes:
            # Check if node extends beyond canvas boundaries
            if node.x - node.width/2 < dimensions['padding']:
                node.x = dimensions['padding'] + node.width/2
            if node.x + node.width/2 > dimensions['width'] - dimensions['padding']:
                node.x = dimensions['width'] - dimensions['padding'] - node.width/2
            if node.y - node.height/2 < dimensions['padding']:
                node.y = dimensions['padding'] + node.height/2
            if node.y + node.height/2 > dimensions['height'] - dimensions['padding']:
                node.y = dimensions['height'] - dimensions['padding'] - node.height/2
            
            adjusted_nodes.append(node)
        
        return adjusted_nodes
    
    def _generate_svg_data(self, layout_result: LayoutResult, theme: Dict) -> Dict:
        """Generate SVG data for rendering"""
        svg_elements = []
        
        # Generate nodes
        for node in layout_result.nodes:
            element = {
                    'type': 'text',
                    'x': node.x,
                    'y': node.y,
                    'text': node.text,
                'font_size': self._get_font_size(node.node_type, theme),
                'fill': self._get_node_color(node.node_type, theme),
                    'text_anchor': 'middle',
                    'dominant_baseline': 'middle'
            }
            svg_elements.append(element)
        
        # Generate braces as paths
        for brace in layout_result.braces:
            # Create a simple line path for the brace
            start_x = brace['start']['x']
            start_y = brace['start']['y']
            end_x = brace['end']['x']
            end_y = brace['end']['y']
            
            # Create a path that looks like a brace (curved line)
            path_d = f"M {start_x} {start_y} Q {(start_x + end_x) / 2} {start_y} {end_x} {end_y}"
            
            element = {
                'type': 'path',
                'd': path_d,
                'stroke': theme['strokeColor'],
                'stroke_width': theme['strokeWidth'],
                'fill': 'none'
            }
            svg_elements.append(element)
        
        return {
            'elements': svg_elements,
            'width': layout_result.dimensions['width'],
            'height': layout_result.dimensions['height'],
            'background': '#ffffff'
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