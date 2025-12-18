"""
Common Pydantic Models and Enums
=================================

Shared models and enumerations used across requests and responses.

Author: lycosa9527
Made by: MindSpring Team
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class DiagramType(str, Enum):
    """Supported diagram types"""
    BUBBLE_MAP = "bubble_map"
    BRIDGE_MAP = "bridge_map"
    TREE_MAP = "tree_map"
    CIRCLE_MAP = "circle_map"
    DOUBLE_BUBBLE_MAP = "double_bubble_map"
    MULTI_FLOW_MAP = "multi_flow_map"
    FLOW_MAP = "flow_map"
    BRACE_MAP = "brace_map"
    CONCEPT_MAP = "concept_map"
    MIND_MAP = "mind_map"
    # Thinking Tools
    FACTOR_ANALYSIS = "factor_analysis"
    THREE_POSITION_ANALYSIS = "three_position_analysis"
    PERSPECTIVE_ANALYSIS = "perspective_analysis"
    GOAL_ANALYSIS = "goal_analysis"
    POSSIBILITY_ANALYSIS = "possibility_analysis"
    RESULT_ANALYSIS = "result_analysis"
    FIVE_W_ONE_H = "five_w_one_h"
    WHWM_ANALYSIS = "whwm_analysis"
    FOUR_QUADRANT = "four_quadrant"


class LLMModel(str, Enum):
    """Supported LLM models"""
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    HUNYUAN = "hunyuan"
    DOUBAO = "doubao"


class Language(str, Enum):
    """Supported languages"""
    ZH = "zh"
    EN = "en"

