"""
Node Palette Generators - Modular Architecture
===============================================

Base class + diagram-specific generators for node palette.

Author: lycosa9527
Made by: MindSpring Team
"""

from agents.thinking_modes.node_palette.base_palette_generator import BasePaletteGenerator
from agents.thinking_modes.node_palette.circle_map_palette import CircleMapPaletteGenerator
from agents.thinking_modes.node_palette.double_bubble_palette import DoubleBubblePaletteGenerator

__all__ = ['BasePaletteGenerator', 'CircleMapPaletteGenerator', 'DoubleBubblePaletteGenerator']

