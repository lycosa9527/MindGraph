"""
MindGraph Agents Package

Central registry for all diagram generation agents.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .concept_maps import ConceptMapAgent
from .mind_maps import MindMapAgent
from .thinking_maps import (
    FlowMapAgent,
    TreeMapAgent,
    BraceMapAgent,
    MultiFlowMapAgent,
    BubbleMapAgent,
    DoubleBubbleMapAgent,
    CircleMapAgent,
    BridgeMapAgent
)

# Agent Registry - Maps diagram types to their agent classes
AGENT_REGISTRY = {
    # Concept Maps
    'concept_map': ConceptMapAgent,

    # Mind Maps
    'mindmap': MindMapAgent,

    # Thinking Maps
    'flow_map': FlowMapAgent,
    'tree_map': TreeMapAgent,
    'brace_map': BraceMapAgent,
    'multi_flow_map': MultiFlowMapAgent,
    'bubble_map': BubbleMapAgent,
    'double_bubble_map': DoubleBubbleMapAgent,
    'circle_map': CircleMapAgent,
    'bridge_map': BridgeMapAgent,
}

def get_agent(diagram_type: str):
    """
    Get an agent instance for the specified diagram type.

    Args:
        diagram_type: Type of diagram to generate

    Returns:
        Agent instance or None if not found
    """
    agent_class = AGENT_REGISTRY.get(diagram_type)
    if agent_class:
        return agent_class()
    return None

def get_available_diagram_types():
    """
    Get list of all available diagram types.

    Returns:
        List of diagram type strings
    """
    return list(AGENT_REGISTRY.keys())

def is_agent_available(diagram_type: str) -> bool:
    """
    Check if an agent is available for the specified diagram type.

    Args:
        diagram_type: Type of diagram to check

    Returns:
        True if agent is available, False otherwise
    """
    return diagram_type in AGENT_REGISTRY

__all__ = [
    'ConceptMapAgent',
    'MindMapAgent',
    'FlowMapAgent',
    'TreeMapAgent',
    'BraceMapAgent',
    'MultiFlowMapAgent',
    'BubbleMapAgent',
    'DoubleBubbleMapAgent',
    'CircleMapAgent',
    'BridgeMapAgent',
    'AGENT_REGISTRY',
    'get_agent',
    'get_available_diagram_types',
    'is_agent_available'
]
