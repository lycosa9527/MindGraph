"""
brace map palette module.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator

"""
Brace Map Palette Generator
============================

Brace Map specific node palette generator.

Generates part/component nodes for Brace Maps using auto-complete style prompts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class BraceMapPaletteGenerator(BasePaletteGenerator):
    """
    Brace Map specific palette generator with multi-stage workflow.

    Stages:
    - dimensions: Generate dimension options for decomposition (Stage 1)
    - parts: Generate main parts based on selected dimension (Stage 2)
    - subparts: Generate sub-parts for specific part (Stage 3)
    """

    def __init__(self):
        """Initialize brace map palette generator"""
        super().__init__()
        # Track stage data per session
        self.session_stages = {}  # session_id -> {'stage': str, 'dimension': str, 'part_name': str, 'parts': []}

    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        stage: str = 'dimensions',  # NEW: stage parameter (default to dimensions)
        stage_data: Optional[Dict[str, Any]] = None,  # NEW: stage-specific data
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with stage-specific logic.

        Args:
            session_id: Session identifier
            center_topic: Main topic (whole)
            educational_context: Educational context
            nodes_per_llm: Nodes to request per LLM
            stage: Generation stage ('dimensions', 'parts', 'subparts')
            stage_data: Stage-specific data (dimension, part_name, parts, etc.)
        """
        # Store stage info (for backward compatibility and state tracking)
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)

        logger.debug("[BraceMapPalette] Stage: %s | Session: %s | Topic: '%s'",
                   stage, session_id[:8], center_topic)
        if stage_data:
            logger.debug("[BraceMapPalette] Stage data: %s", stage_data)

        # Pass session_id and stage_data through educational_context so _build_prompt can access them directly
        # This is better than relying on session_stages lookup (avoids timing/state sync issues)
        if educational_context is None:
            educational_context = {}
        educational_context = {**educational_context,
                              '_session_id': session_id,
                              '_stage': stage,
                              '_stage_data': stage_data or {}}

        # Call base class generate_batch which will use our _build_prompt
        async for event in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path
        ):
            # Add mode field to every node for explicit tracking (like Tree Map)
            if event.get('event') == 'node_generated':
                node = event.get('node', {})

                # For subparts stage, use part_name as mode (for dynamic tab routing)
                # For parts stage, use stage name
                if stage == 'subparts' and stage_data and stage_data.get('part_name'):
                    node_mode = stage_data['part_name']
                    node_id = node.get('id', 'unknown')
                    node_text = node.get('text', '')
                    logger.debug("[BraceMapPalette] Node tagged with part mode='%s' | ID: %s | Text: %s", node_mode, node_id, node_text)
                else:
                    node_mode = stage
                    node_id = node.get('id', 'unknown')
                    node_text = node.get('text', '')
                    logger.debug("[BraceMapPalette] Node tagged with stage mode='%s' | ID: %s | Text: %s", node_mode, node_id, node_text)

                node['mode'] = node_mode

            yield event

    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build stage-specific prompt for Brace Map node generation.

        Checks session_stages to determine current stage and builds appropriate prompt.

        Args:
            center_topic: The whole to be decomposed
            educational_context: Educational context dict
            count: Number of items to request
            batch_num: Current batch number

        Returns:
            Stage-specific formatted prompt
        """
        # Detect language from content (Chinese topic = Chinese prompt)
        educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'

        # Get stage and stage_data directly from educational_context (passed through in generate_batch)
        # This is more reliable than session_stages lookup - avoids state sync issues
        stage = educational_context.get('_stage', 'dimensions') if educational_context else 'dimensions'
        stage_data = educational_context.get('_stage_data', {}) if educational_context else {}

        # Fallback to session_stages for backward compatibility (if not in educational_context)
        if stage == 'dimensions' and not stage_data:
            session_id = educational_context.get('_session_id') if educational_context else None
            if session_id and session_id in self.session_stages:
                stage = self.session_stages[session_id].get('stage', 'dimensions')
                stage_data = self.session_stages[session_id]

        logger.debug("[BraceMapPalette-Prompt] Building prompt for stage: %s | Stage data: %s", stage, stage_data)

        # Build stage-specific prompt
        if stage == 'dimensions':
            return self._build_dimensions_prompt  # pylint: disable=protected-access(center_topic, context_desc, language, count, batch_num)
        elif stage == 'parts':
            stage_data.get('dimension', '')
            return self._build_parts_prompt  # pylint: disable=protected-access(center_topic, dimension, context_desc, language, count, batch_num)
        elif stage == 'subparts':
            stage_data.get('part_name', '')
            stage_data.get('dimension', '')  # Get dimension for subparts prompt
            return self._build_subparts_prompt  # pylint: disable=protected-access(center_topic, part_name, dimension, context_desc, language, count, batch_num)
        else:
            # Fallback to dimensions
            return self._build_dimensions_prompt  # pylint: disable=protected-access(center_topic, context_desc, language, count, batch_num)

    def _build_dimensions_prompt(
        self,
        center_topic: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """
        Build prompt for generating dimension options for decomposition.

        This is Stage 1: User selects how they want to decompose the whole.
        """
        if language == 'zh':
            prompt = f"""为主题"{center_topic}"生成{count}个可能的拆解维度。

教学背景：{context_desc}

括号图可以使用不同的维度来拆解整体。请思考这个整体可以用哪些维度进行拆解。

常见拆解维度类型（参考）：
- 物理部件（按实体组成）
- 功能模块（按功能划分）
- 时间阶段（按时间顺序）
- 空间区域（按空间位置）
- 类型分类（按种类划分）
- 属性特征（按特性划分）
- 层次结构（按层级划分）

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地拆解这个整体
4. 只输出维度名称，每行一个，不要编号

生成{count}个拆解维度："""
        else:
            prompt = f"""Generate {count} possible decomposition dimensions for: {center_topic}

Educational Context: {context_desc}

A brace map can decompose a whole using DIFFERENT DIMENSIONS. Think about what dimensions could be used to break down this whole.

Common dimension types (reference):
- Physical Components (by physical parts)
- Functional Modules (by function)
- Time Stages (by temporal sequence)
- Spatial Regions (by location)
- Type Classification (by category)
- Attribute Features (by characteristics)
- Hierarchical Structure (by levels)

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should be valid for decomposing this whole
4. Output only dimension names, one per line, no numbering

Generate {count} dimensions:"""

        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保提供不同角度的维度，避免重复。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."

        return prompt

    def _build_parts_prompt(
        self,
        center_topic: str,
        dimension: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """
        Build prompt for generating main parts based on selected dimension.

        This is Stage 2: Generate parts using the user's selected dimension.
        """
        # Build prompt based on language (derived from BRACE_MAP_GENERATION prompts)
        if language == 'zh':
            if dimension:
                prompt = f"""需要从"{dimension}"这个视角来拆解整体"{center_topic}"。

教学背景：{context_desc}
用户选择的拆解视角：{dimension}

核心任务：从"{dimension}"这个视角，将"{center_topic}"拆解成{count}个组成部分。

核心要求：
1. 始终从"{dimension}"视角拆解"{center_topic}"
2. 部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 生成3-6个部分（理想数量）
4. 使用名词或名词短语，2-8个字
5. 只输出部分名称，每行一个，不要编号，不要解释

从"{dimension}"视角拆解"{center_topic}"，生成{count}个组成部分："""
            else:
                prompt = f"""为以下整体生成{count}个组成部分：{center_topic}

教学背景：{context_desc}

你能够绘制括号图，对整体进行拆解，展示整体与部分的关系。
思维方式：拆解、分解
1. 从同一个拆解维度进行拆解
2. 部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语
4. 每个部分要简洁明了

要求：每个部分要简洁明了，可以超过4个字，但不要太长，避免完整句子。只输出部分文本，每行一个，不要编号。

生成{count}个组成部分："""
        else:
            if dimension:
                prompt = f"""Decompose the whole "{center_topic}" from the "{dimension}" perspective.

Educational Context: {context_desc}
User-selected decomposition perspective: {dimension}

Core Task: From the "{dimension}" perspective, break down "{center_topic}" into {count} component parts.

Core Requirements:
1. ALWAYS decompose "{center_topic}" from the "{dimension}" perspective
2. Parts should be clear, mutually exclusive, and collectively exhaustive (MECE principle)
3. Generate 3-6 parts (ideal range)
4. Use nouns or noun phrases, 2-8 words
5. Output only part names, one per line, no numbering, no explanations

Decompose "{center_topic}" from the "{dimension}" perspective, generate {count} component parts:"""
            else:
                prompt = f"""Generate {count} Brace Map parts/components for: {center_topic}

Educational Context: {context_desc}

You can draw a brace map to decompose the whole and show the relationship between whole and parts.
Thinking approach: Decomposition, Breaking down
1. Decompose using a consistent dimension
2. Parts should be clear, mutually exclusive, and collectively exhaustive (MECE principle)
3. Use nouns or noun phrases
4. Each part should be concise and clear

Requirements: Each part should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences. Output only the part text, one per line, no numbering.

Generate {count} parts:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的拆解角度思考，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity from new decomposition angles, avoid any repetition from previous batches."

        return prompt

    def _build_subparts_prompt(
        self,
        center_topic: str,
        part_name: str,
        dimension: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """
        Build prompt for generating sub-parts for a specific part.

        This is for Stage 3: generating physical/structural/functional components of the selected part.
        """
        if language == 'zh':
            if dimension:
                prompt = f"""为部分"{part_name}"生成{count}个子部件，该部分属于整体"{center_topic}"，拆解维度为"{dimension}"

教学背景：{context_desc}
整体主题：{center_topic}
拆解维度：{dimension}
选中的部分：{part_name}

核心要求：
1. 所有子部件必须属于部分"{part_name}"，且与整体主题"{center_topic}"相关
2. 子部件必须符合拆解维度"{dimension}"的视角
3. 子部件应该是"{part_name}"的组成部分、子元素或具体实例（2-6个，理想数量）
4. 子部件要具体、详细、有代表性
5. 使用名词或名词短语，2-8个字
6. 只输出子部件名称，每行一个，不要编号，不要解释

为部分"{part_name}"（属于"{center_topic}"，维度"{dimension}"）生成{count}个子部件："""
            else:
                prompt = f"""为整体"{center_topic}"的部分"{part_name}"生成{count}个子部件或组成成分

教学背景：{context_desc}

核心要求：
1. 所有子部件必须属于部分"{part_name}"，且与整体主题"{center_topic}"相关
2. 子部件应该是"{part_name}"的组成部分、子元素或具体实例
3. 子部件要具体、详细、有代表性
4. 使用名词或名词短语，2-8个字
5. 只输出子部件名称，每行一个，不要编号

为部分"{part_name}"（属于整体"{center_topic}"）生成{count}个子部件："""
        else:
            if dimension:
                prompt = f"""Generate {count} sub-components for part "{part_name}" of whole "{center_topic}" using dimension "{dimension}"

Educational Context: {context_desc}
Whole Topic: {center_topic}
Decomposition Dimension: {dimension}
Selected Part: {part_name}

Requirements:
1. ALL sub-components MUST belong to part "{part_name}" and be relevant to the whole topic "{center_topic}"
2. Sub-components MUST align with the decomposition dimension "{dimension}"
3. Sub-components should be components, sub-elements, or specific instances of "{part_name}" (2-6 items, ideal range)
4. Sub-components should be specific, detailed, and representative
5. Use nouns or noun phrases, 2-8 words
6. Output only sub-component names, one per line, no numbering, no explanations

Generate {count} sub-components for "{part_name}" (part of "{center_topic}", dimension "{dimension}"):"""
            else:
                prompt = f"""Generate {count} sub-components for part "{part_name}" of whole: {center_topic}

Educational Context: {context_desc}

Requirements:
1. ALL sub-components MUST belong to part "{part_name}" and be relevant to the whole topic "{center_topic}"
2. Sub-components should be components, sub-elements, or specific instances of "{part_name}"
3. Sub-components should be specific, detailed, and representative
4. Use nouns or noun phrases, 2-8 words
5. Output only sub-component names, one per line, no numbering

Generate {count} sub-components for "{part_name}" (part of "{center_topic}"):"""

        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。提供更多不同的子部件，避免重复。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Provide more diverse sub-components, avoid repetition."

        return prompt

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """
        End session and cleanup stage data.

        Overrides base class to also clean up session_stages.
        """
        # Clean up stage data
        self.session_stages.pop(session_id, None)

        # Call parent cleanup
        super().end_session(session_id, reason)


# Global singleton  # pylint: disable=global-statement instance for Brace Map
_brace_map_palette_generator = None

def get_brace_map_palette_generator() -> BraceMapPaletteGenerator:
    """Get singleton instance of Brace Map palette generator"""
    global _brace_map_palette_generator  # pylint: disable=global-statement
    if _brace_map_palette_generator is None:
        _brace_map_palette_generator = BraceMapPaletteGenerator()
    return _brace_map_palette_generator

