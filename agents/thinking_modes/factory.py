"""
Thinking Mode Agent Factory
============================

Factory to create the correct ThinkGuide agent based on diagram type.
Uses ReAct pattern for diagram-specific behavior.

@author lycosa9527
@made_by MindSpring Team
"""

import logging
from typing import Optional

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent
from agents.thinking_modes.circle_map_agent_react import CircleMapThinkingAgent
from agents.thinking_modes.bubble_map_agent_react import BubbleMapThinkingAgent
from agents.thinking_modes.double_bubble_map_agent_react import DoubleBubbleMapThinkingAgent
from agents.thinking_modes.tree_map_agent_react import TreeMapThinkingAgent
from agents.thinking_modes.flow_map_agent_react import FlowMapThinkingAgent
from agents.thinking_modes.multi_flow_map_agent_react import MultiFlowMapThinkingAgent
from agents.thinking_modes.brace_map_agent_react import BraceMapThinkingAgent
from agents.thinking_modes.bridge_map_agent_react import BridgeMapThinkingAgent
from agents.thinking_modes.mindmap_agent_react import MindMapThinkingAgent

logger = logging.getLogger(__name__)


class ThinkingAgentFactory:
    """
    Factory to create diagram-specific ThinkGuide agents.
    
    Each diagram type has unique ThinkGuide behavior:
    - Circle Map: Socratic refinement of observations (define topic in context)
    - Bubble Map: Attribute-focused descriptive thinking (describe with adjectives)
    - Double Bubble Map: Compare and contrast thinking
    - Tree Map: Hierarchical categorization (classify and group)
    - Flow Map: Sequential reasoning (analyze processes)
    - Multi Flow Map: Cause-effect analysis
    - Brace Map: Part-whole relationships
    - Bridge Map: Analogical reasoning
    - Mind Map: Associative and divergent thinking
    
    Usage:
        agent = ThinkingAgentFactory.create_agent('circle_map')
        agent = ThinkingAgentFactory.create_agent('bubble_map')
    """
    
    # Registry of diagram type -> agent class
    _agents = {
        'circle_map': CircleMapThinkingAgent,
        'bubble_map': BubbleMapThinkingAgent,
        'double_bubble_map': DoubleBubbleMapThinkingAgent,
        'tree_map': TreeMapThinkingAgent,
        'flow_map': FlowMapThinkingAgent,
        'multi_flow_map': MultiFlowMapThinkingAgent,
        'brace_map': BraceMapThinkingAgent,
        'bridge_map': BridgeMapThinkingAgent,
        'mindmap': MindMapThinkingAgent,
    }
    
    # Singleton instances (one agent per diagram type)
    _instances = {}
    
    @classmethod
    def get_agent(cls, diagram_type: str) -> BaseThinkingAgent:
        """
        Get (or create) the appropriate ThinkGuide agent for a diagram type.
        Uses singleton pattern - one agent instance per diagram type.
        
        Args:
            diagram_type: Type of diagram ('circle_map', 'bubble_map', etc.)
            
        Returns:
            Diagram-specific thinking agent
            
        Raises:
            ValueError: If diagram type is not supported
        """
        # Return existing instance if available
        if diagram_type in cls._instances:
            return cls._instances[diagram_type]
        
        # Create new instance
        agent_class = cls._agents.get(diagram_type)
        
        if not agent_class:
            # Use CircleMapThinkingAgent as fallback for unsupported diagram types
            logger.warning(f"[ThinkingAgentFactory] No specialized agent for {diagram_type}, using CircleMapThinkingAgent as fallback")
            agent_class = CircleMapThinkingAgent
        
        logger.debug(f"[ThinkingAgentFactory] Creating {agent_class.__name__} for {diagram_type}")
        instance = agent_class()
        cls._instances[diagram_type] = instance
        return instance
    
    @classmethod
    def create_agent(cls, diagram_type: str) -> BaseThinkingAgent:
        """
        Alias for get_agent() for backward compatibility.
        
        Args:
            diagram_type: Type of diagram ('circle_map', 'bubble_map', etc.)
            
        Returns:
            Diagram-specific thinking agent
        """
        return cls.get_agent(diagram_type)
    
    @classmethod
    def is_supported(cls, diagram_type: str) -> bool:
        """
        Check if a diagram type is supported by ThinkGuide.
        
        Args:
            diagram_type: Type of diagram to check
            
        Returns:
            True if supported, False otherwise
        """
        return diagram_type in cls._agents
    
    @classmethod
    def get_supported_types(cls) -> list:
        """
        Get list of all supported diagram types.
        
        Returns:
            List of diagram type strings
        """
        return list(cls._agents.keys())
