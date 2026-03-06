"""
Concept map palette module.

Concept Map specific node palette generator.
Generates concept nodes from the main topic for free-form concept maps.
"""
from typing import Any, Dict, List, Optional

from agents.node_palette.base_palette_generator import BasePaletteGenerator


class ConceptMapPaletteGenerator(BasePaletteGenerator):
    """Concept Map palette generator for concept node generation from topic."""

    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build Concept Map prompt for concept generation.

        Args:
            center_topic: Main topic from Concept Map
            educational_context: Educational context dict
            count: Number of concepts to request
            batch_num: Current batch number

        Returns:
            Formatted prompt for Concept Map concept generation
        """
        language = self._detect_language(center_topic, educational_context)

        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context
            else 'General K12 teaching'
        )

        if language == 'zh':
            prompt = (
                f"""为概念图主题"{center_topic}"生成{count}个相关概念。

教学背景：{context_desc}

面向K12教育，生成适合学生学习的核心概念。
1. 优先选择学科内的主要概念、重要概念
2. 适当加入跨学科概念，帮助学生建立知识联系
3. 每个概念用名词或名词短语，2-4个字
4. 概念应与主题强相关，可形成有意义的关系
5. 避免重复和长句

只输出概念文本，每行一个，不要编号。

生成{count}个概念："""
            )
        else:
            prompt = (
                f"""Generate {count} concepts for the concept map topic: {center_topic}

Educational Context: {context_desc}

K12 education focused. Generate important, core concepts for student learning.
1. Prioritize main concepts and key concepts within the subject
2. Include some cross-discipline concepts to help students build connections
3. Each concept: noun or noun phrase, 1-4 words
4. Concepts should be strongly related to the topic and form meaningful links
5. Avoid duplicates and long sentences

Output only concept text, one per line, no numbering.

Generate {count} concepts:"""
            )

        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，避免与之前批次重复。"
            else:
                prompt += (
                    f"\n\nNote: This is batch {batch_num}. "
                    "Ensure MAXIMUM diversity and avoid any repetition from previous batches."
                )

        return prompt


_PALETTE_GENERATOR_CACHE: List[Optional[ConceptMapPaletteGenerator]] = [None]


def get_concept_map_palette_generator() -> ConceptMapPaletteGenerator:
    """Get singleton instance of Concept Map palette generator."""
    if _PALETTE_GENERATOR_CACHE[0] is None:
        _PALETTE_GENERATOR_CACHE[0] = ConceptMapPaletteGenerator()
    return _PALETTE_GENERATOR_CACHE[0]
