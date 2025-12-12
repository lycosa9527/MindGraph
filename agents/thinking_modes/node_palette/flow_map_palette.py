"""
Flow Map Palette Generator
===========================

Flow Map specific node palette generator.

Generates step/process nodes for Flow Maps using auto-complete style prompts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import re
import logging
from typing import Optional, Dict, Any, AsyncGenerator

from agents.thinking_modes.node_palette.base_palette_generator import BasePaletteGenerator

logger = logging.getLogger(__name__)


class FlowMapPaletteGenerator(BasePaletteGenerator):
    """
    Flow Map specific palette generator with multi-stage workflow and step sequencing.
    
    Stages:
    1. dimensions: Generate decomposition dimensions for the flow
    2. steps: Generate main steps based on selected dimension
    3. substeps: Generate substeps for a specific step
    
    Key feature: Each generated step gets a sequence number for ordering.
    """
    
    def __init__(self):
        """Initialize flow map palette generator"""
        super().__init__()
        # Track stage data per session
        self.session_stages = {}  # session_id -> {'stage': str, 'dimension': str, 'step_name': str}
        # Track step sequence numbers per session
        self.step_sequences = {}  # session_id -> next_sequence_number
    
    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        stage: str = 'dimensions',  # NEW: stage parameter (dimensions -> steps -> substeps)
        stage_data: Optional[Dict[str, Any]] = None,  # NEW: stage-specific data
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with multi-stage workflow and step sequencing.
        
        Args:
            session_id: Session identifier
            center_topic: Main process/event
            educational_context: Educational context
            nodes_per_llm: Nodes to request per LLM
            stage: Generation stage ('dimensions', 'steps', 'substeps')
            stage_data: Stage-specific data (dimension, step_name, etc.)
        """
        # Store stage info
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
            # Initialize sequence counter (start at 1)
            self.step_sequences[session_id] = 1
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)
        
        logger.info("[FlowMapPalette] Stage: %s | Session: %s | Topic: '%s'", 
                   stage, session_id[:8], center_topic)
        if stage_data:
            logger.info("[FlowMapPalette] Stage data: %s", stage_data)
        
        # Pass session_id through educational_context so _build_prompt can access it
        if educational_context is None:
            educational_context = {}
        educational_context = {**educational_context, '_session_id': session_id}
        
        # Call base class generate_batch which will use our _build_prompt
        async for event in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type
        ):
            # Add mode and sequence fields to every node
            if event.get('event') == 'node_generated':
                node = event.get('node', {})
                
                # For substeps stage, use step_name as mode (for dynamic tab routing)
                # For other stages, use stage name as mode
                if stage == 'substeps' and stage_data and stage_data.get('step_name'):
                    node_mode = stage_data['step_name']
                    logger.debug(f"[FlowMapPalette] Node tagged with step mode='{node_mode}' | ID: {node.get('id', 'unknown')} | Text: {node.get('text', '')}")
                else:
                    node_mode = stage
                    logger.debug(f"[FlowMapPalette] Node tagged with stage mode='{node_mode}' | ID: {node.get('id', 'unknown')} | Text: {node.get('text', '')}")
                
                node['mode'] = node_mode
                
                # CRITICAL: Add sequence number for steps
                if stage == 'steps':
                    node['sequence'] = self.step_sequences[session_id]
                    self.step_sequences[session_id] += 1
                    logger.info(f"[FlowMapPalette] Step node tagged with sequence={node['sequence']} | ID: {node.get('id', 'unknown')}")
            
            yield event
    
    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build Flow Map prompt (routes to stage-specific prompts).
        
        Args:
            center_topic: Main process/event title
            educational_context: Educational context dict
            count: Number of items to request
            batch_num: Current batch number
            
        Returns:
            Formatted prompt for current stage
        """
        # Get language from educational context
        language = educational_context.get('language', 'en') if educational_context else 'en'
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'
        
        # Get session_id from educational_context (passed through from generate_batch)
        session_id = educational_context.get('_session_id', '') if educational_context else ''
        
        # Get current stage and stage_data
        stage_info = self.session_stages.get(session_id, {})
        stage = stage_info.get('stage', 'dimensions')
        
        logger.debug(f"[FlowMapPalette-Prompt] Building prompt for stage: {stage}")
        
        # Build stage-specific prompt
        if stage == 'dimensions':
            return self._build_dimensions_prompt(center_topic, context_desc, language, count, batch_num)
        elif stage == 'steps':
            dimension = stage_info.get('dimension', '')
            return self._build_steps_prompt(center_topic, dimension, context_desc, language, count, batch_num)
        elif stage == 'substeps':
            step_name = stage_info.get('step_name', '')
            return self._build_substeps_prompt(center_topic, step_name, context_desc, language, count, batch_num)
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
        """Build prompt for Stage 1: Dimensions"""
        if language == 'zh':
            prompt = f"""为主题"{center_topic}"生成{count}个可能的拆解维度。

教学背景：{context_desc}

流程图可以使用不同的维度来拆解流程。请思考这个流程可以用哪些维度进行拆解。

常见拆解维度类型（参考）：
- 时间阶段（按时间顺序）
- 功能模块（按功能划分）
- 层次结构（按层级划分）
- 空间位置（按位置划分）
- 角色视角（按参与者划分）
- 类型分类（按种类划分）

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地拆解这个流程
4. 只输出维度名称，每行一个，不要编号

生成{count}个拆解维度："""
        else:
            prompt = f"""Generate {count} possible decomposition dimensions for: {center_topic}

Educational Context: {context_desc}

Flow maps can use different dimensions to break down a process. Think about what dimensions can be used to decompose this flow.

Common dimension types (reference):
- Time phases (chronological order)
- Functional modules (by function)
- Hierarchical structure (by level)
- Spatial location (by position)
- Role perspective (by participant)
- Type classification (by category)

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should effectively decompose this flow
4. Output only the dimension name, one per line, no numbering

Generate {count} decomposition dimensions:"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保提供不同角度的维度，避免重复。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Ensure different perspectives, avoid duplication."
        
        return prompt
    
    def _build_steps_prompt(
        self,
        center_topic: str,
        dimension: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for Stage 2: Steps (based on selected dimension)"""
        if language == 'zh':
            prompt = f"""为流程"{center_topic}"生成{count}个按时间顺序排列的步骤

拆解维度：{dimension}

教学背景：{context_desc}

你能够绘制流程图，展示过程的各个步骤。
思维方式：顺序、流程
1. 步骤要按照"{dimension}"这个维度进行拆解
2. 步骤要按时间顺序排列（从早到晚，从开始到结束）
3. 每个步骤要简洁明了，不要使用完整句子
4. 使用动宾短语或名词短语描述步骤
5. 步骤之间要有逻辑关联

要求：每个步骤要简洁明了（1-6个词），不要标点符号，不要编号前缀。只输出步骤文本，每行一个。**请按照时间顺序从早到晚排列步骤**。

生成{count}个按顺序的步骤："""
        else:
            prompt = f"""Generate {count} chronologically ordered steps for: {center_topic}

Decomposition dimension: {dimension}

Educational Context: {context_desc}

You can draw a flow map to show the steps of a process.
Thinking approach: Sequential, Procedural
1. Steps should follow the "{dimension}" dimension
2. Steps should be in chronological order (from beginning to end)
3. Each step should be concise and clear, avoid full sentences
4. Use action phrases or noun phrases to describe steps
5. Steps should be logically connected

Requirements: Each step should be concise (1-6 words), no punctuation, no numbering prefixes. Output only the step text, one per line. **Please arrange steps in chronological order from earliest to latest**.

Generate {count} ordered steps:"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保步骤仍然按照时间顺序排列，提供新的角度或细节。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Ensure steps remain in chronological order with new angles or details."
        
        return prompt
    
    def _build_substeps_prompt(
        self,
        center_topic: str,
        step_name: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for Stage 3: Substeps (for a specific step)"""
        if language == 'zh':
            prompt = f"""为步骤"{step_name}"生成{count}个子步骤

整体流程：{center_topic}

教学背景：{context_desc}

你能够将一个步骤进一步细化为多个子步骤。
思维方式：细化、分解
1. 子步骤要详细展开"{step_name}"这个步骤
2. 子步骤要按时间顺序排列
3. 每个子步骤要简洁明了，不要使用完整句子
4. 使用动宾短语或名词短语描述子步骤

要求：每个子步骤要简洁明了（1-8个词），不要标点符号，不要编号前缀。只输出子步骤文本，每行一个。

生成{count}个子步骤："""
        else:
            prompt = f"""Generate {count} substeps for: {step_name}

Overall process: {center_topic}

Educational Context: {context_desc}

You can break down a step into multiple substeps.
Thinking approach: Refinement, Decomposition
1. Substeps should detail out the "{step_name}" step
2. Substeps should be in chronological order
3. Each substep should be concise and clear, avoid full sentences
4. Use action phrases or noun phrases to describe substeps

Requirements: Each substep should be concise (1-8 words), no punctuation, no numbering prefixes. Output only the substep text, one per line.

Generate {count} substeps:"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保子步骤仍然按照时间顺序排列，提供新的角度或细节。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Ensure substeps remain in chronological order with new angles or details."
        
        return prompt
    
    def _get_system_message(self, educational_context: Optional[Dict[str, Any]]) -> str:
        """
        Get system message for Flow Map node generation.
        
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
        End session and cleanup stage data and sequence tracking.
        
        Overrides base class to also clean up session_stages and step_sequences.
        """
        # Clean up stage data and sequence tracking
        self.session_stages.pop(session_id, None)
        self.step_sequences.pop(session_id, None)
        
        # Call parent cleanup
        super().end_session(session_id, reason)


# Global singleton instance for Flow Map
_flow_map_palette_generator = None

def get_flow_map_palette_generator() -> FlowMapPaletteGenerator:
    """Get singleton instance of Flow Map palette generator"""
    global _flow_map_palette_generator
    if _flow_map_palette_generator is None:
        _flow_map_palette_generator = FlowMapPaletteGenerator()
    return _flow_map_palette_generator

