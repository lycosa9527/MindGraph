"""
mindmap palette module.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator

"""
Mind Map Palette Generator
==========================

Mind Map specific node palette generator with multi-stage workflow.

Supports 2-stage progressive generation:
1. Stage 1 (branches): Generate main branches from central topic
2. Stage 2 (children): Generate sub-branches for selected branch

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class MindMapPaletteGenerator(BasePaletteGenerator):
    """
    Mind Map specific palette generator with multi-stage workflow.

    Stages:
    - branches: Generate main branches from central topic (default)
    - children: Generate sub-branches for specific branch
    """

    def __init__(self):
        """Initialize mind map palette generator"""
        super().__init__()
        # Track stage data per session
        self.session_stages = {}  # session_id -> {'stage': str, 'branch_name': str}

    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        stage: str = 'branches',  # NEW: stage parameter
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
            center_topic: Main topic
            educational_context: Educational context
            nodes_per_llm: Nodes to request per LLM
            stage: Generation stage ('branches', 'children')
            stage_data: Stage-specific data (branch_name, etc.)
        """
        # Store stage info (for backward compatibility and state tracking)
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)

        logger.debug("[MindMapPalette] Stage: %s | Session: %s | Topic: '%s'",
                   stage, session_id[:8], center_topic)
        if stage_data:
            logger.debug("[MindMapPalette] Stage data: %s", stage_data)

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
            # Add mode field to every node for explicit tracking
            if event.get('event') == 'node_generated':
                node = event.get('node', {})

                # For children stage, use branch_name as mode (for dynamic tab routing)
                # For branches stage, use 'branches' as mode
                if stage == 'children' and stage_data and stage_data.get('branch_name'):
                    node_mode = stage_data['branch_name']
                    node_id = node.get('id', 'unknown')
                    node_text = node.get('text', '')
                    logger.debug("[MindMapPalette] Node tagged with branch mode='%s' | ID: %s | Text: %s", node_mode, node_id, node_text)
                else:
                    node_mode = stage
                    node_id = node.get('id', 'unknown')
                    node_text = node.get('text', '')
                    logger.debug("[MindMapPalette] Node tagged with stage mode='%s' | ID: %s | Text: %s", node_mode, node_id, node_text)

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
        Build stage-specific prompt for Mind Map node generation.

        Checks session_stages to determine current stage and builds appropriate prompt.

        Args:
            center_topic: Central topic
            educational_context: Educational context dict
            count: Number of ideas/branches to request
            batch_num: Current batch number

        Returns:
            Stage-specific formatted prompt for Mind Map idea generation
        """
        # Detect language from content (Chinese topic = Chinese prompt)

        # Use same context extraction as auto-complete
        educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'

        # Determine current stage from session_stages
        session_id = educational_context.get('_session_id') if educational_context else None
        stage = 'branches'  # default
        stage_data = {}

        if session_id and session_id in self.session_stages:
            stage = self.session_stages[session_id].get('stage', 'branches')
            stage_data = self.session_stages[session_id]

        logger.debug("[MindMapPalette-Prompt] Building prompt for stage: %s", stage)

        # Build stage-specific prompt
        if stage == 'children':
            stage_data.get('branch_name', '')
            return self._build_children_prompt  # pylint: disable=protected-access(center_topic, branch_name, context_desc, language, count, batch_num)
        else:  # branches
            return self._build_branches_prompt  # pylint: disable=protected-access(center_topic, context_desc, language, count, batch_num)

    def _build_branches_prompt(self, center_topic: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
        """Build prompt for generating main branches from central topic"""

        # Build prompt based on language (derived from MIND_MAP_GENERATION prompts)
        if language == 'zh':
            prompt = f"""为以下主题生成{count}个思维导图分支想法：{center_topic}

教学背景：{context_desc}

你能够绘制思维导图，进行发散思维和头脑风暴。
思维方式：发散、联想、创造
1. 从多个角度对中心主题进行联想
2. 分支要覆盖不同的维度和方面
3. 每个分支要简洁明了，使用名词或名词短语
4. 鼓励创造性和多样性思考

要求：每个分支想法要简洁明了（1-5个词），不要使用完整句子，不要编号。只输出分支文本，每行一个。

生成{count}个分支想法："""
        else:
            prompt = f"""Generate {count} Mind Map branch ideas for: {center_topic}

Educational Context: {context_desc}

You can draw a mind map for divergent thinking and brainstorming.
Thinking approach: Divergent, Associative, Creative
1. Associate from multiple angles around the central topic
2. Branches should cover different dimensions and aspects
3. Each branch should be concise, using nouns or noun phrases
4. Encourage creative and diverse thinking

Requirements: Each branch idea should be concise (1-5 words), avoid full sentences, no numbering. Output only the branch text, one per line.

Generate {count} branch ideas:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性和创造性，从新的维度和角度思考，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity and creativity from new dimensions and angles, avoid any repetition from previous batches."

        return prompt

    def _build_children_prompt(self, center_topic: str, branch_name: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
        """Build prompt for generating sub-branches/children for a specific branch"""

        if language == 'zh':
            prompt = f"""为思维导图分支"{branch_name}"生成{count}个子分支想法：

主题：{center_topic}
上级分支：{branch_name}
教学背景：{context_desc}

你能够为思维导图分支生成子想法，进一步细化和展开这个分支。
思维方式：深入、细化、展开
1. 围绕"{branch_name}"这个分支进行更深入的思考
2. 子分支应该是该分支的具体展开或细节
3. 每个子分支要简洁明了，使用名词或名词短语
4. 保持与上级分支的逻辑关联性

要求：每个子分支想法要简洁明了（1-5个词），不要使用完整句子，不要编号。只输出子分支文本，每行一个。

生成{count}个子分支想法："""
        else:
            prompt = f"""Generate {count} sub-branch ideas for the branch "{branch_name}":

Main Topic: {center_topic}
Parent Branch: {branch_name}
Educational Context: {context_desc}

You can generate sub-ideas for a mind map branch, further refining and expanding this branch.
Thinking approach: Deepen, Refine, Expand
1. Think more deeply around the branch "{branch_name}"
2. Sub-branches should be specific expansions or details of this branch
3. Each sub-branch should be concise, using nouns or noun phrases
4. Maintain logical connection with the parent branch

Requirements: Each sub-branch idea should be concise (1-5 words), avoid full sentences, no numbering. Output only the sub-branch text, one per line.

Generate {count} sub-branch ideas:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保提供不同角度的子想法，避免重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Provide different perspectives for sub-ideas, avoid repetition."

        return prompt

# Global singleton  # pylint: disable=global-statement instance for Mind Map
_mindmap_palette_generator = None

def get_mindmap_palette_generator() -> MindMapPaletteGenerator:
    """Get singleton instance of Mind Map palette generator"""
    global _mindmap_palette_generator  # pylint: disable=global-statement
    if _mindmap_palette_generator is None:
        _mindmap_palette_generator = MindMapPaletteGenerator()
    return _mindmap_palette_generator

