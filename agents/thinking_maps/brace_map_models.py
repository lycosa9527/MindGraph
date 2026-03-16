"""
Brace map models and data structures.

Contains enums, dataclasses, and configuration constants used by the brace map agent.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


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


class LayoutAlgorithm(Enum):
    """Available layout algorithms for brace maps"""
    FLEXIBLE_DYNAMIC = "flexible_dynamic"


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
    layout_data: Dict[str, Any]


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
    parent_block_id: Optional[str] = None


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
