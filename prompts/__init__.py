"""
Centralized Prompt Registry for MindGraph

This module provides a unified interface for all diagram prompts,
organizing them by diagram type and language.
"""

from typing import Dict, Any
from .thinking_maps import THINKING_MAP_PROMPTS
from .concept_maps import CONCEPT_MAP_PROMPTS
from .mind_maps import MIND_MAP_PROMPTS
from .main_agent import MAIN_AGENT_PROMPTS
from .thinking_tools import THINKING_TOOLS_PROMPTS


# Unified prompt registry
PROMPT_REGISTRY = {
    **THINKING_MAP_PROMPTS,
    **CONCEPT_MAP_PROMPTS,
    **MIND_MAP_PROMPTS,
    **MAIN_AGENT_PROMPTS,
    **THINKING_TOOLS_PROMPTS,
}

def get_prompt(diagram_type: str, language: str = 'en', prompt_type: str = 'generation') -> str:
    """
    Get a prompt for a specific diagram type and language.
    
    Args:
        diagram_type: Type of diagram (e.g., 'bridge_map', 'bubble_map')
        language: Language code ('en' or 'zh')
        prompt_type: Type of prompt ('generation', 'classification', 'extraction')
    
    Returns:
        str: The prompt template
    """
    key = f"{diagram_type}_{prompt_type}_{language}"
    return PROMPT_REGISTRY.get(key, "")

def get_available_diagram_types() -> list:
    """Get list of all available diagram types that the application supports."""
    # Return all supported diagram types including the new thinking tools
    supported_types = [
        'bubble_map',
        'bridge_map', 
        'tree_map',
        'circle_map',
        'double_bubble_map',
        'flow_map',
        'brace_map',
        'multi_flow_map',
        'concept_map',
        'mindmap',
        'mind_map',  # Note: both mindmap and mind_map are supported for compatibility
        # Thinking Tools
        'factor_analysis',
        'three_position_analysis',
        'perspective_analysis',
        'goal_analysis',
        'possibility_analysis',
        'result_analysis',
        'five_w_one_h',
        'whwm_analysis',
        'four_quadrant'
    ]
    
    # Filter to only include types that have prompts in the registry
    available_types = []
    for diagram_type in supported_types:
        # Check if we have at least one prompt for this diagram type
        has_prompt = any(key.startswith(f"{diagram_type}_") for key in PROMPT_REGISTRY.keys())
        if has_prompt:
            available_types.append(diagram_type)
    
    return sorted(available_types)

def get_prompt_metadata(diagram_type: str) -> Dict[str, Any]:
    """Get metadata about a diagram type's prompts."""
    metadata = {
        'has_generation': False,
        'has_classification': False,
        'has_extraction': False,
        'languages': []
    }
    
    for key in PROMPT_REGISTRY.keys():
        # Check if key starts with diagram_type followed by underscore
        if key.startswith(f"{diagram_type}_"):
            if 'generation' in key:
                metadata['has_generation'] = True
            elif 'classification' in key:
                metadata['has_classification'] = True
            elif 'extraction' in key:
                metadata['has_extraction'] = True
            
            if '_en' in key:
                metadata['languages'].append('en')
            elif '_zh' in key:
                metadata['languages'].append('zh')
    
    metadata['languages'] = list(set(metadata['languages']))
    return metadata 