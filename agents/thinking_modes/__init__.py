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

__all__ = [
    'BaseThinkingAgent',
    'ThinkingAgentFactory',
    'CircleMapThinkingAgent',
    'BubbleMapThinkingAgent',
    'DoubleBubbleMapThinkingAgent',
]
