"""
Centralized Prompt Registry for MindGraph

This module provides a unified interface for all diagram prompts,
organizing them by diagram type and language.
"""

from typing import Dict, Any
from .thinking_maps import THINKING_MAP_PROMPTS
from .concept_maps import CONCEPT_MAP_PROMPTS
from .mind_maps import MIND_MAP_PROMPTS
from .common_diagrams import COMMON_DIAGRAM_PROMPTS

# Unified prompt registry
PROMPT_REGISTRY = {
    **THINKING_MAP_PROMPTS,
    **CONCEPT_MAP_PROMPTS,
    **MIND_MAP_PROMPTS,
    **COMMON_DIAGRAM_PROMPTS
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
    """Get list of all available diagram types."""
    types = set()
    for key in PROMPT_REGISTRY.keys():
        if '_en' in key or '_zh' in key:
            # Extract diagram type from keys like "bridge_map_generation_en"
            parts = key.split('_')
            if len(parts) >= 3:
                # For keys like "bridge_map_generation_en", take "bridge_map"
                diagram_type = '_'.join(parts[:-2])
                types.add(diagram_type)
    return sorted(list(types))

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