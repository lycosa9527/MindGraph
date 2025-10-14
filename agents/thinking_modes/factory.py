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

logger = logging.getLogger(__name__)


class ThinkingAgentFactory:
    """
    Factory to create diagram-specific ThinkGuide agents.
    
    Each diagram type has unique ThinkGuide behavior:
    - Circle Map: Socratic refinement of observations (define topic in context)
    - Bubble Map: Attribute-focused descriptive thinking (describe with adjectives)
    - Tree Map: Hierarchical categorization (classify and group)
    - Mind Map: Branch organization (explore connections)
    - Flow Map: Sequential reasoning (analyze processes)
    
    Usage:
        agent = ThinkingAgentFactory.create_agent('circle_map')
        agent = ThinkingAgentFactory.create_agent('bubble_map')
    """
    
    # Registry of diagram type -> agent class
    _agents = {
        'circle_map': CircleMapThinkingAgent,
        'bubble_map': BubbleMapThinkingAgent,
        # Future diagram types will be added here as we implement them:
        # 'double_bubble_map': DoubleBubbleMapThinkingAgent,
        # 'mind_map': MindMapThinkingAgent,
        # 'tree_map': TreeMapThinkingAgent,
        # 'flow_map': FlowMapThinkingAgent,
        # 'bridge_map': BridgeMapThinkingAgent,
        # 'multi_flow_map': MultiFlowMapThinkingAgent,
        # 'brace_map': BraceMapThinkingAgent,
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
            logger.error(f"[ThinkingAgentFactory] No agent found for diagram type: {diagram_type}")
            raise ValueError(
                f"ThinkGuide not yet available for diagram type: {diagram_type}. "
                f"Supported types: {', '.join(cls._agents.keys())}"
            )
        
        logger.info(f"[ThinkingAgentFactory] Creating {agent_class.__name__} for {diagram_type}")
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
