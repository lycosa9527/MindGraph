"""
Circle Map Palette Generator
=============================

Circle Map specific node palette generator.

Generates context nodes for Circle Maps using centralized prompt system.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import re
from typing import Optional, Dict, Any

from agents.thinking_modes.node_palette.base_palette_generator import BasePaletteGenerator
from prompts.thinking_modes.circle_map import get_prompt


class CircleMapPaletteGenerator(BasePaletteGenerator):
    """
    Circle Map specific palette generator.
    
    Generates context nodes for Circle Maps.
    """
    
    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build Circle Map prompt using CENTRALIZED prompt system.
        
        Args:
            center_topic: Center topic from Circle Map
            educational_context: Educational context dict
            count: Number of context nodes to request
            batch_num: Current batch number
            
        Returns:
            Formatted prompt for Circle Map context node generation
        """
        # Detect language
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', center_topic))
        language = 'zh' if has_chinese else 'en'
        
        # Use same context extraction as auto-complete
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'
        
        # Get prompt from centralized system
        prompt_template = get_prompt('NODE_GENERATION', language)
        
        # Format the template
        prompt = prompt_template.format(
            count=count,
            center_topic=center_topic,
            educational_context=context_desc
        )
        
        # Add diversity note for later batches (node palette specific)
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity and avoid any repetition from previous batches."
        
        return prompt
    
    def _get_system_message(self, educational_context: Optional[Dict[str, Any]]) -> str:
        """
        Get system message for Circle Map node generation.
        
        Args:
            educational_context: Educational context dict
            
        Returns:
            System message string (EN or ZH based on context)
        """
        has_chinese = False
        if educational_context and educational_context.get('raw_message'):
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', educational_context['raw_message']))
        
        return '你是一个有帮助的K12教育助手。' if has_chinese else 'You are a helpful K12 education assistant.'


# Global singleton instance for Circle Map
_circle_map_palette_generator = None

def get_circle_map_palette_generator() -> CircleMapPaletteGenerator:
    """Get singleton instance of Circle Map palette generator"""
    global _circle_map_palette_generator
    if _circle_map_palette_generator is None:
        _circle_map_palette_generator = CircleMapPaletteGenerator()
    return _circle_map_palette_generator

