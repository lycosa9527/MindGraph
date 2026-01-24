"""
Common Pydantic Models and Enums
=================================

Shared models and enumerations used across requests and responses.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from enum import Enum



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
