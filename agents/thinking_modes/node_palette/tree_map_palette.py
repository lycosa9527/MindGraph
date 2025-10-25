"""
Tree Map Palette Generator
===========================

Tree Map specific node palette generator with multi-stage workflow.

Supports 3-stage progressive generation:
1. Stage 1 (dimensions): Generate dimension options for classification
2. Stage 2 (categories): Generate categories for selected dimension
3. Stage 3 (children): Generate children for selected categories

Author: lycosa9527
Made by: MindSpring Team
"""

import re
import logging
from typing import Optional, Dict, Any, AsyncGenerator

from agents.thinking_modes.node_palette.base_palette_generator import BasePaletteGenerator

logger = logging.getLogger(__name__)


class TreeMapPaletteGenerator(BasePaletteGenerator):
    """
    Tree Map specific palette generator with multi-stage workflow.
    
    Stages:
    - dimensions: Generate dimension options (if user hasn't selected one)
    - categories: Generate categories for selected dimension (no children)
    - children: Generate children for specific category
    """
    
    def __init__(self):
        """Initialize tree map palette generator"""
        super().__init__()
        # Track stage data per session
        self.session_stages = {}  # session_id -> {'stage': str, 'dimension': str, 'categories': []}
    
    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        stage: str = 'categories',  # NEW: stage parameter
        stage_data: Optional[Dict[str, Any]] = None  # NEW: stage-specific data
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with stage-specific logic.
        
        Args:
            session_id: Session identifier
            center_topic: Main topic
            educational_context: Educational context
            nodes_per_llm: Nodes to request per LLM
            stage: Generation stage ('dimensions', 'categories', 'children')
            stage_data: Stage-specific data (dimension, category_name, etc.)
        """
        # Store stage info
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)
        
        logger.info("[TreeMapPalette] Stage: %s | Session: %s | Topic: '%s'", 
                   stage, session_id[:8], center_topic)
        if stage_data:
            logger.info("[TreeMapPalette] Stage data: %s", stage_data)
        
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
            # Add mode field to every node for explicit tracking (like Double Bubble and Multi Flow)
            if event.get('event') == 'node_generated':
                node = event.get('node', {})
                
                # For children stage, use category_name as mode (for dynamic tab routing)
                # For other stages, use stage name
                if stage == 'children' and stage_data and stage_data.get('category_name'):
                    node_mode = stage_data['category_name']
                    logger.info(f"[TreeMapPalette] Node tagged with category mode='{node_mode}' | ID: {node.get('id', 'unknown')} | Text: {node.get('text', '')}")
                else:
                    node_mode = stage
                    logger.info(f"[TreeMapPalette] Node tagged with stage mode='{node_mode}' | ID: {node.get('id', 'unknown')} | Text: {node.get('text', '')}")
                
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
        Build stage-specific prompt for Tree Map node generation.
        
        Checks session_stages to determine current stage and builds appropriate prompt.
        
        Args:
            center_topic: Main topic to classify
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
        # Since we're in instance method, we need session_id - but base class doesn't pass it
        # Workaround: Store in educational_context during generate_batch call
        session_id = educational_context.get('_session_id') if educational_context else None
        stage = 'categories'  # default
        stage_data = {}
        
        if session_id and session_id in self.session_stages:
            stage = self.session_stages[session_id].get('stage', 'categories')
            stage_data = self.session_stages[session_id]
        
        logger.info("[TreeMapPalette-Prompt] Building prompt for stage: %s", stage)
        
        # Build stage-specific prompt
        if stage == 'dimensions':
            return self._build_dimension_prompt(center_topic, context_desc, language, count, batch_num)
        elif stage == 'categories':
            dimension = stage_data.get('dimension', '')
            return self._build_category_prompt(center_topic, dimension, context_desc, language, count, batch_num)
        elif stage == 'children':
            dimension = stage_data.get('dimension', '')
            category_name = stage_data.get('category_name', '')
            return self._build_children_prompt(center_topic, dimension, category_name, context_desc, language, count, batch_num)
        else:
            # Fallback to categories
            return self._build_category_prompt(center_topic, '', context_desc, language, count, batch_num)
    
    def _build_dimension_prompt(self, center_topic: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
        """Build prompt for generating dimension options"""
        if language == 'zh':
            prompt = f"""为主题"{center_topic}"生成{count}个可能的分类维度。

教学背景：{context_desc}

树状图可以使用不同的维度来分类主题。请思考这个主题可以用哪些维度进行分类。

常见分类维度类型（参考）：
- 生物分类（科学性）
- 栖息地（环境性）
- 食性（营养性）
- 体型（物理性）
- 功能（功能性）
- 时间阶段（时间性）
- 地理区域（空间性）

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地分类这个主题
4. 只输出维度名称，每行一个，不要编号

生成{count}个分类维度："""
        else:
            prompt = f"""Generate {count} possible classification dimensions for topic: {center_topic}

Educational Context: {context_desc}

A tree map can classify a topic using DIFFERENT DIMENSIONS. Think about what dimensions could be used to classify this topic.

Common dimension types (reference):
- Biological Taxonomy (Scientific)
- Habitat (Environmental)
- Diet (Nutritional)
- Size (Physical)
- Function (Functional)
- Time Stages (Temporal)
- Geographic Region (Spatial)

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should be valid for classifying this topic
4. Output only dimension names, one per line, no numbering

Generate {count} dimensions:"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保提供不同角度的维度，避免重复。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        
        return prompt
    
    def _build_category_prompt(self, center_topic: str, dimension: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
        """Build prompt for generating categories (no children)"""
        if language == 'zh':
            if dimension:
                prompt = f"""为主题"{center_topic}"生成{count}个分类类别，使用分类维度：{dimension}

教学背景：{context_desc}

要求：
1. 所有类别必须遵循"{dimension}"这个分类维度
2. 类别要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语，2-8个字
4. 只输出类别名称，每行一个，不要编号
5. 不要生成具体的子项目，只生成类别名称

生成{count}个类别："""
            else:
                prompt = f"""为主题"{center_topic}"生成{count}个树状图分类类别

教学背景：{context_desc}

要求：
1. 从同一个分类维度进行分类
2. 类别要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语，2-8个字
4. 只输出类别名称，每行一个，不要编号
5. 不要生成具体的子项目，只生成类别名称

生成{count}个类别："""
        else:
            if dimension:
                prompt = f"""Generate {count} classification categories for: {center_topic}, using dimension: {dimension}

Educational Context: {context_desc}

Requirements:
1. ALL categories MUST follow the "{dimension}" dimension
2. Categories should be clear, mutually exclusive, and collectively exhaustive (MECE)
3. Use nouns or noun phrases, 2-8 words
4. Output only category names, one per line, no numbering
5. Do NOT generate specific items, only category names

Generate {count} categories:"""
            else:
                prompt = f"""Generate {count} Tree Map classification categories for: {center_topic}

Educational Context: {context_desc}

Requirements:
1. Classify using a consistent dimension
2. Categories should be clear, mutually exclusive, and collectively exhaustive (MECE)
3. Use nouns or noun phrases, 2-8 words
4. Output only category names, one per line, no numbering
5. Do NOT generate specific items, only category names

Generate {count} categories:"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。提供不同的类别，避免重复。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Provide different categories, avoid repetition."
        
        return prompt
    
    def _build_children_prompt(self, center_topic: str, dimension: str, category_name: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
        """Build prompt for generating children for a specific category"""
        if language == 'zh':
            prompt = f"""为主题"{center_topic}"的类别"{category_name}"生成{count}个具体项目

教学背景：{context_desc}
分类维度：{dimension}

要求：
1. 所有项目必须属于"{category_name}"这个类别
2. 项目要具体、详细、有代表性
3. 使用名词或名词短语，2-10个字
4. 只输出项目名称，每行一个，不要编号

为"{category_name}"生成{count}个项目："""
        else:
            prompt = f"""Generate {count} specific items for category "{category_name}" under topic: {center_topic}

Educational Context: {context_desc}
Classification Dimension: {dimension}

Requirements:
1. ALL items MUST belong to the "{category_name}" category
2. Items should be specific, detailed, and representative
3. Use nouns or noun phrases, 2-10 words
4. Output only item names, one per line, no numbering

Generate {count} items for "{category_name}":"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。提供更多不同的项目，避免重复。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Provide more diverse items, avoid repetition."
        
        return prompt
    
    def _get_system_message(self, educational_context: Optional[Dict[str, Any]]) -> str:
        """
        Get system message for Tree Map node generation.
        
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


# Global singleton instance for Tree Map
_tree_map_palette_generator = None

def get_tree_map_palette_generator() -> TreeMapPaletteGenerator:
    """Get singleton instance of Tree Map palette generator"""
    global _tree_map_palette_generator
    if _tree_map_palette_generator is None:
        _tree_map_palette_generator = TreeMapPaletteGenerator()
    return _tree_map_palette_generator

