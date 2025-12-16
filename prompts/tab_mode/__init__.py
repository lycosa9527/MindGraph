"""
Tab Mode Prompts - Centralized Registry
========================================

Unified prompt registry for Tab Mode feature.
Organizes prompts by function: autocomplete, expansion, colors.

@author MindGraph Team
"""

from .autocomplete import TAB_MODE_AUTOCOMPLETE_PROMPTS
from .expansion import TAB_MODE_EXPANSION_PROMPTS
from .colors import TAB_MODE_COLOR_PROMPTS

# Unified registry
TAB_MODE_PROMPTS = {
    **TAB_MODE_AUTOCOMPLETE_PROMPTS,
    **TAB_MODE_EXPANSION_PROMPTS,
    **TAB_MODE_COLOR_PROMPTS,
}

__all__ = [
    'TAB_MODE_PROMPTS',
    'TAB_MODE_AUTOCOMPLETE_PROMPTS',
    'TAB_MODE_EXPANSION_PROMPTS',
    'TAB_MODE_COLOR_PROMPTS',
]

