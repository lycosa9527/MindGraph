"""
Thinking Mode Agent Factory
============================

Routes diagram types to appropriate ThinkGuide agents.
ONE ENDPOINT FOR ALL DIAGRAM TYPES!

@author lycosa9527
@made_by MindSpring Team
"""

from agents.thinking_modes.circle_map_agent import CircleMapThinkingAgent


class ThinkingAgentFactory:
    """
    Factory pattern for creating diagram-specific thinking agents.
    
    Benefits:
    - Single endpoint handles all diagram types
    - Easy to add new diagram types (just add elif!)
    - Centralized routing logic
    - All agents share same workflow, different prompts
    """
    
    @staticmethod
    def get_agent(diagram_type: str):
        """
        Get the appropriate agent for the diagram type.
        
        Args:
            diagram_type: One of the thinking map types
        
        Returns:
            Agent instance for that diagram type
        
        Raises:
            ValueError: If diagram type is unknown
        """
        
        # Currently supported: Circle Map (more coming soon!)
        if diagram_type == 'circle_map':
            return CircleMapThinkingAgent()
        
        # TODO: Add remaining 7 thinking maps:
        # elif diagram_type == 'bubble_map':
        #     return BubbleMapThinkingAgent()
        # elif diagram_type == 'double_bubble_map':
        #     return DoubleBubbleMapThinkingAgent()
        # elif diagram_type == 'tree_map':
        #     return TreeMapThinkingAgent()
        # elif diagram_type == 'brace_map':
        #     return BraceMapThinkingAgent()
        # elif diagram_type == 'flow_map':
        #     return FlowMapThinkingAgent()
        # elif diagram_type == 'multi_flow_map':
        #     return MultiFlowMapThinkingAgent()
        # elif diagram_type == 'bridge_map':
        #     return BridgeMapThinkingAgent()
        
        else:
            supported = ThinkingAgentFactory.get_supported_types()
            raise ValueError(
                f"Unknown diagram type: {diagram_type}. "
                f"Supported types: {', '.join(supported)}"
            )
    
    @staticmethod
    def get_supported_types():
        """Get list of all supported diagram types"""
        return [
            'circle_map',  # Brainstorming & Defining
            # Coming soon:
            # 'bubble_map',           # Describing with Adjectives
            # 'double_bubble_map',    # Comparing & Contrasting
            # 'tree_map',             # Classifying & Categorizing
            # 'brace_map',            # Whole-to-Part Analysis
            # 'flow_map',             # Sequencing & Steps
            # 'multi_flow_map',       # Cause & Effect
            # 'bridge_map'            # Seeing Analogies
        ]


