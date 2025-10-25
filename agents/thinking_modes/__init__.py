"""
ThinkGuide Agents - Thinking Mode
==================================

Socratic guided thinking agents for all 8 thinking map types.

@author lycosa9527
@made_by MindSpring Team
"""

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent
from agents.thinking_modes.factory import ThinkingAgentFactory
from agents.thinking_modes.circle_map_agent_react import CircleMapThinkingAgent
from agents.thinking_modes.bubble_map_agent_react import BubbleMapThinkingAgent
from agents.thinking_modes.double_bubble_map_agent_react import DoubleBubbleMapThinkingAgent
from agents.thinking_modes.tree_map_agent_react import TreeMapThinkingAgent
from agents.thinking_modes.flow_map_agent_react import FlowMapThinkingAgent
from agents.thinking_modes.multi_flow_map_agent_react import MultiFlowMapThinkingAgent
from agents.thinking_modes.brace_map_agent_react import BraceMapThinkingAgent
from agents.thinking_modes.bridge_map_agent_react import BridgeMapThinkingAgent
from agents.thinking_modes.mindmap_agent_react import MindMapThinkingAgent

__all__ = [
    'BaseThinkingAgent',
    'ThinkingAgentFactory',
    'CircleMapThinkingAgent',
    'BubbleMapThinkingAgent',
    'DoubleBubbleMapThinkingAgent',
    'TreeMapThinkingAgent',
    'FlowMapThinkingAgent',
    'MultiFlowMapThinkingAgent',
    'BraceMapThinkingAgent',
    'BridgeMapThinkingAgent',
    'MindMapThinkingAgent',
]
