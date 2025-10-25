"""
Brace Map Palette Generator
============================

Brace Map specific node palette generator.

Generates part/component nodes for Brace Maps using auto-complete style prompts.

Author: lycosa9527
Made by: MindSpring Team
"""

import re
import logging
from typing import Optional, Dict, Any, AsyncGenerator

from agents.thinking_modes.node_palette.base_palette_generator import BasePaletteGenerator

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
        stage_data: Optional[Dict[str, Any]] = None  # NEW: stage-specific data
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
        # Store stage info
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)
        
        logger.info("[BraceMapPalette] Stage: %s | Session: %s | Topic: '%s'", 
                   stage, session_id[:8], center_topic)
        if stage_data:
            logger.info("[BraceMapPalette] Stage data: %s", stage_data)
        
        # Pass session_id through educational_context so _build_prompt can access it
        if educational_context is None:
            educational_context = {}
        educational_context = {**educational_context, '_session_id': session_id}
        
        # Call base class generate_batch which will use our _build_prompt
        async for event in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm
        ):
            # Add mode field to every node for explicit tracking (like Tree Map)
            if event.get('event') == 'node_generated':
                node = event.get('node', {})
                
                # For subparts stage, use part_name as mode (for dynamic tab routing)
                # For parts stage, use stage name
                if stage == 'subparts' and stage_data and stage_data.get('part_name'):
                    node_mode = stage_data['part_name']
                    logger.info(f"[BraceMapPalette] Node tagged with part mode='{node_mode}' | ID: {node.get('id', 'unknown')} | Text: {node.get('text', '')}")
                else:
                    node_mode = stage
                    logger.info(f"[BraceMapPalette] Node tagged with stage mode='{node_mode}' | ID: {node.get('id', 'unknown')} | Text: {node.get('text', '')}")
                
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
        # Get language from educational context
        language = educational_context.get('language', 'en') if educational_context else 'en'
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'
        
        # Determine current stage from session_stages
        # Get session_id from educational_context (passed through during generate_batch)
        session_id = educational_context.get('_session_id') if educational_context else None
        stage = 'dimensions'  # default (start from dimensions selection)
        stage_data = {}
        
        if session_id and session_id in self.session_stages:
            stage = self.session_stages[session_id].get('stage', 'dimensions')
            stage_data = self.session_stages[session_id]
        
        logger.info("[BraceMapPalette-Prompt] Building prompt for stage: %s", stage)
        
        # Build stage-specific prompt
        if stage == 'dimensions':
            return self._build_dimensions_prompt(center_topic, context_desc, language, count, batch_num)
        elif stage == 'parts':
            dimension = stage_data.get('dimension', '')
            return self._build_parts_prompt(center_topic, dimension, context_desc, language, count, batch_num)
        elif stage == 'subparts':
            part_name = stage_data.get('part_name', '')
            return self._build_subparts_prompt(center_topic, part_name, context_desc, language, count, batch_num)
        else:
            # Fallback to dimensions
            return self._build_dimensions_prompt(center_topic, context_desc, language, count, batch_num)
    
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
                prompt = f"""为以下整体生成{count}个组成部分：{center_topic}

教学背景：{context_desc}
拆解维度：{dimension}

你能够绘制括号图，对整体进行拆解，展示整体与部分的关系。
思维方式：拆解、分解
1. 必须按照"{dimension}"这个维度进行拆解
2. 部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语
4. 每个部分要简洁明了

要求：每个部分要简洁明了，可以超过4个字，但不要太长，避免完整句子。只输出部分文本，每行一个，不要编号。

按照"{dimension}"维度生成{count}个组成部分："""
            else:
                prompt = f"""为以下整体生成{count}个组成部分：{center_topic}

教学背景：{context_desc}

你能够绘制括号图，对整体进行拆解，展示整体与部分的关系。
思维方式：拆解、分解
1. 从同一个拆解维度进行拆解（例如：按物理部件、按功能模块、按生命周期等）
2. 部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语
4. 每个部分要简洁明了

要求：每个部分要简洁明了，可以超过4个字，但不要太长，避免完整句子。只输出部分文本，每行一个，不要编号。

生成{count}个组成部分："""
        else:
            if dimension:
                prompt = f"""Generate {count} Brace Map parts/components for: {center_topic}

Educational Context: {context_desc}
Decomposition Dimension: {dimension}

You can draw a brace map to decompose the whole and show the relationship between whole and parts.
Thinking approach: Decomposition, Breaking down
1. MUST decompose using the "{dimension}" dimension
2. Parts should be clear, mutually exclusive, and collectively exhaustive (MECE principle)
3. Use nouns or noun phrases
4. Each part should be concise and clear

Requirements: Each part should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences. Output only the part text, one per line, no numbering.

Generate {count} parts using "{dimension}" dimension:"""
            else:
                prompt = f"""Generate {count} Brace Map parts/components for: {center_topic}

Educational Context: {context_desc}

You can draw a brace map to decompose the whole and show the relationship between whole and parts.
Thinking approach: Decomposition, Breaking down
1. Decompose using a consistent dimension (e.g., by physical parts, by functional modules, by life cycle, etc.)
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
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """
        Build prompt for generating sub-parts for a specific part.
        
        This is for Stage 2: generating finer components for each selected part.
        """
        if language == 'zh':
            prompt = f"""为整体"{center_topic}"的部分"{part_name}"生成{count}个子部件或组成成分

教学背景：{context_desc}

你能够绘制括号图，进一步分解"{part_name}"这个部分，展示它的更细致的组成。

要求：
1. 所有子部件必须属于"{part_name}"这个部分
2. 子部件要具体、清晰、有代表性
3. 使用名词或名词短语，2-8个字
4. 只输出子部件名称，每行一个，不要编号

为"{part_name}"生成{count}个子部件："""
        else:
            prompt = f"""Generate {count} sub-components for part "{part_name}" of whole: {center_topic}

Educational Context: {context_desc}

You can draw a brace map to further decompose the part "{part_name}" and show its finer components.

Requirements:
1. All sub-components MUST belong to the part "{part_name}"
2. Sub-components should be specific, clear, and representative
3. Use nouns or noun phrases, 2-8 words
4. Output only sub-component names, one per line, no numbering

Generate {count} sub-components for "{part_name}":"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。提供更多不同的子部件，避免重复。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Provide more diverse sub-components, avoid repetition."
        
        return prompt
    
    def _get_system_message(self, educational_context: Optional[Dict[str, Any]]) -> str:
        """
        Get system message for Brace Map node generation.
        
        Args:
            educational_context: Educational context dict
            
        Returns:
            System message string (EN or ZH based on context)
        """
        has_chinese = False
        if educational_context and educational_context.get('raw_message'):
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', educational_context['raw_message']))
        
        return '你是一个有帮助的K12教育助手。' if has_chinese else 'You are a helpful K12 education assistant.'
    
    def end_session(self, session_id: str, reason: str = "complete"):
        """
        End session and cleanup stage data.
        
        Overrides base class to also clean up session_stages.
        """
        # Clean up stage data
        self.session_stages.pop(session_id, None)
        
        # Call parent cleanup
        super().end_session(session_id, reason)


# Global singleton instance for Brace Map
_brace_map_palette_generator = None

def get_brace_map_palette_generator() -> BraceMapPaletteGenerator:
    """Get singleton instance of Brace Map palette generator"""
    global _brace_map_palette_generator
    if _brace_map_palette_generator is None:
        _brace_map_palette_generator = BraceMapPaletteGenerator()
    return _brace_map_palette_generator

