"""
circle map palette module.
"""
from typing import Optional, Dict, Any

from agents.node_palette.base_palette_generator import BasePaletteGenerator

"""
Circle Map Palette Generator
=============================

Circle Map specific node palette generator.

Generates context nodes for Circle Maps.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""




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
        Build Circle Map prompt for node generation.

        Args:
            center_topic: Center topic from Circle Map
            educational_context: Educational context dict
            count: Number of context nodes to request
            batch_num: Current batch number

        Returns:
            Formatted prompt for Circle Map context node generation
        """
        # Detect language from content (Chinese topic = Chinese prompt)
        language = self._detect_language  # pylint: disable=protected-access(center_topic, educational_context)

        # Use same context extraction as auto-complete
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'

        # Build prompt based on language
        if language == 'zh':
            prompt = f"""为以下主题生成{count}个圆圈图观察点：{center_topic}

教学背景：{context_desc}

你能对中心词进行头脑风暴，联想出与之相关的信息或背景知识。
思维方式：关联、发散
1. 能够从多个角度进行发散、联想，角度越广越好
2. 特征词要尽可能简洁

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。

只输出观察点文本，每行一个，不要编号。

生成{count}个观察点："""
        else:
            prompt = f"""Generate {count} Circle Map observations for: {center_topic}

Educational Context: {context_desc}

You can brainstorm the central topic and associate it with related information or background knowledge.
Thinking approach: Association, Divergence
1. Be able to diverge and associate from multiple angles, the wider the angle the better
2. Feature words should be as concise as possible

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

Output only the observation text, one per line, no numbering.

Generate {count} observations:"""

        # Add diversity note for later batches (node palette specific)
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity and avoid any repetition from previous batches."

        return prompt

# Global singleton  # pylint: disable=global-statement instance for Circle Map
_circle_map_palette_generator = None

def get_circle_map_palette_generator() -> CircleMapPaletteGenerator:
    """Get singleton instance of Circle Map palette generator"""
    global _circle_map_palette_generator  # pylint: disable=global-statement
    if _circle_map_palette_generator is None:
        _circle_map_palette_generator = CircleMapPaletteGenerator()
    return _circle_map_palette_generator

