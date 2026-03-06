"""
Tree Map Palette Generator
===========================

Tree Map specific node palette generator with multi-stage workflow.

Supports 3-stage progressive generation:
1. Stage 1 (dimensions): Generate dimension options for classification
2. Stage 2 (categories): Generate categories for selected dimension
3. Stage 3 (children): Generate children for selected categories

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator
from prompts.node_palette import (
    get_tree_dimensions_prompt,
    get_tree_categories_prompt,
    get_tree_items_prompt,
)

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
        _mode: Optional[str] = None,
        _stage: Optional[str] = None,
        _stage_data: Optional[Dict[str, Any]] = None,
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
            _stage: Generation stage ('dimensions', 'categories', 'children')
            _stage_data: Stage-specific data (dimension, category_name, etc.)
        """
        stage = _stage or 'dimensions'
        stage_data = _stage_data or {}
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)

        logger.debug("[TreeMapPalette] Stage: %s | Session: %s | Topic: '%s'",
                     stage, session_id[:8], center_topic)
        if stage_data:
            logger.debug("[TreeMapPalette] Stage data: %s", stage_data)

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
            diagram_type=diagram_type,
            endpoint_path=endpoint_path
        ):
            if event.get('event') == 'node_generated':
                node = event.get('node', {})
                node_mode = (
                    stage_data.get('category_name')
                    if stage == 'children' and stage_data and stage_data.get('category_name')
                    else stage
                )
                node['mode'] = node_mode
                logger.debug(
                    "[TreeMapPalette] Node tagged with mode='%s' | ID: %s | Text: %s",
                    node_mode, node.get('id', 'unknown'), node.get('text', '')
                )

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
        language = self._detect_language(center_topic, educational_context)
        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context else 'General K12 teaching'
        )
        session_id = educational_context.get('_session_id') if educational_context else None
        stage = 'dimensions'
        stage_data = {}

        if session_id and session_id in self.session_stages:
            stage = self.session_stages[session_id].get('stage', 'dimensions')
            stage_data = self.session_stages[session_id]

        logger.debug("[TreeMapPalette-Prompt] Building prompt for stage: %s", stage)

        dimension = stage_data.get('dimension', '')
        category_name = stage_data.get('category_name', '')

        if stage == 'dimensions':
            return self._build_dimension_prompt(
                center_topic, context_desc, language, count, batch_num
            )
        if stage == 'children':
            return self._build_children_prompt(
                center_topic, dimension, category_name, context_desc,
                language, count, batch_num
            )
        return self._build_category_prompt(
            center_topic, dimension, context_desc, language, count, batch_num
        )

    def _build_dimension_prompt(
        self,
        center_topic: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for generating dimension options. Uses centralized prompts."""
        return get_tree_dimensions_prompt(
            center_topic, context_desc, language, count, batch_num
        )

    def _build_category_prompt(
        self,
        center_topic: str,
        dimension: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for generating categories (no children). Uses centralized prompts."""
        return get_tree_categories_prompt(
            center_topic, dimension, context_desc, language, count, batch_num
        )

    def _build_children_prompt(
        self,
        center_topic: str,
        dimension: str,
        category_name: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for generating children for a specific category. Uses centralized prompts."""
        return get_tree_items_prompt(
            center_topic, category_name, dimension, context_desc,
            language, count, batch_num
        )

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """
        End session and cleanup stage data.

        Overrides base class to also clean up session_stages.
        """
        # Clean up stage data
        self.session_stages.pop(session_id, None)

        # Call parent cleanup
        super().end_session(session_id, reason)


class _TreeMapPaletteHolder:
    """Holder for Tree Map palette generator singleton."""
    instance: Optional[TreeMapPaletteGenerator] = None


def get_tree_map_palette_generator() -> TreeMapPaletteGenerator:
    """Get singleton instance of Tree Map palette generator"""
    if _TreeMapPaletteHolder.instance is None:
        _TreeMapPaletteHolder.instance = TreeMapPaletteGenerator()
    return _TreeMapPaletteHolder.instance
