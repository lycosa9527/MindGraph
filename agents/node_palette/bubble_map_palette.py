"""
bubble map palette module.
"""
from typing import Optional, Dict, Any

from agents.node_palette.base_palette_generator import BasePaletteGenerator

"""
Bubble Map Palette Generator
==============================

Bubble Map specific node palette generator.

Generates attribute/adjective nodes for Bubble Maps using centralized prompt system.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""




class BubbleMapPaletteGenerator(BasePaletteGenerator):
    """
    Bubble Map specific palette generator.

    Generates adjective/attribute nodes for Bubble Maps.
    """

    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build Bubble Map prompt using existing generation logic.

        Args:
            center_topic: Center topic from Bubble Map
            educational_context: Educational context dict
            count: Number of attribute nodes to request
            batch_num: Current batch number

        Returns:
            Formatted prompt for Bubble Map attribute node generation
        """
        # Detect language from content (Chinese topic = Chinese prompt)
        language = self._detect_language  # pylint: disable=protected-access(center_topic, educational_context)

        # Use same context extraction as auto-complete
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'

        # Build prompt based on language
        if language == 'zh':
            prompt = f"""为以下主题生成{count}个气泡图属性词：{center_topic}

教学背景：{context_desc}

你能够生成气泡图属性，使用形容词或描述性短语来描述核心主题的属性。
思维方式：使用形容词进行描述、说明特质。
1. 使用形容词或形容词短语
2. 从多个维度对中心词进行描述
3. 能够从多个角度进行发散、联想，角度越广越好
4. 特征词要尽可能简洁

要求：每个特征要简洁明了，使用形容词或形容词短语对中心词进行描述，可以超过4个字，但不要太长，避免完整句子。

只输出属性词文本，每行一个，不要编号。

生成{count}个属性词："""
        else:
            prompt = f"""Generate {count} Bubble Map attribute words for: {center_topic}

Educational Context: {context_desc}

You can generate bubble map attributes using adjectives or descriptive phrases to describe the attributes of the core topic.
Thinking approach: Use adjectives for description and explanation of characteristics.
1. Use adjectives or adjectival phrases
2. Describe the central topic from multiple dimensions
3. Be able to diverge and associate from multiple angles, the wider the angle the better
4. Feature words should be as concise as possible

Requirements: Each characteristic should be concise and clear. Use adjectives or adjectival phrases to describe the central topic. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

Output only the attribute text, one per line, no numbering.

Generate {count} attributes:"""

        # Add diversity note for later batches (node palette specific)
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的维度和角度描述，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity from new dimensions and angles, avoid any repetition from previous batches."

        return prompt

# Global singleton  # pylint: disable=global-statement instance for Bubble Map
_bubble_map_palette_generator = None

def get_bubble_map_palette_generator() -> BubbleMapPaletteGenerator:
    """Get singleton instance of Bubble Map palette generator"""
    global _bubble_map_palette_generator  # pylint: disable=global-statement
    if _bubble_map_palette_generator is None:
        _bubble_map_palette_generator = BubbleMapPaletteGenerator()
    return _bubble_map_palette_generator

