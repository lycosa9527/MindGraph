"""
Brace Map Palette Generator
============================

Brace Map specific node palette generator.

Generates part/component nodes for Brace Maps using auto-complete style prompts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator
from prompts.node_palette import (
    get_brace_dimensions_prompt,
    get_brace_parts_prompt,
    get_brace_subparts_prompt,
)
from utils.placeholder import filter_for_prompt

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
            center_topic: Main topic (whole)
            educational_context: Educational context
            nodes_per_llm: Nodes to request per LLM
            _stage: Generation stage ('dimensions', 'parts', 'subparts')
            _stage_data: Stage-specific data (dimension, part_name, parts, etc.)
        """
        stage = _stage or 'dimensions'
        stage_data = _stage_data or {}
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)

        logger.debug("[BraceMapPalette] Stage: %s | Session: %s | Topic: '%s'",
                     stage, session_id[:8], center_topic)
        if stage_data:
            logger.debug("[BraceMapPalette] Stage data: %s", stage_data)

        if educational_context is None:
            educational_context = {}
        educational_context = {**educational_context,
                              '_session_id': session_id,
                              '_stage': stage,
                              '_stage_data': stage_data}

        async for event in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm,
            _mode=_mode,
            _stage=stage,
            _stage_data=stage_data,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path
        ):
            if event.get('event') == 'node_generated':
                self._tag_brace_node_with_mode(event, stage, stage_data)
            yield event

    def _tag_brace_node_with_mode(
        self,
        event: Dict[str, Any],
        stage: str,
        stage_data: Dict[str, Any]
    ) -> None:
        """Set node mode and parent_id from stage. parent_id is stable; mode is display fallback."""
        node = event.get('node', {})
        if stage == 'subparts' and stage_data and stage_data.get('part_name'):
            node_mode = stage_data['part_name']
            if stage_data.get('part_id'):
                node['parent_id'] = stage_data['part_id']
        else:
            node_mode = stage
        node['mode'] = node_mode
        logger.debug(
            "[BraceMapPalette] Node tagged with mode='%s' parent_id=%s | ID: %s | Text: %s",
            node_mode,
            node.get('parent_id', ''),
            node.get('id', 'unknown'),
            node.get('text', ''),
        )

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
        language = self._detect_language(center_topic, educational_context)
        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context else 'General K12 teaching'
        )

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

        logger.debug(
            "[BraceMapPalette-Prompt] Building prompt for stage: %s | Stage data: %s",
            stage, stage_data
        )

        # Build stage-specific prompt
        if stage == 'dimensions':
            return self._build_dimensions_prompt(
                center_topic, context_desc, language, count, batch_num
            )
        if stage == 'parts':
            dimension = stage_data.get('dimension', '')
            return self._build_parts_prompt(
                center_topic, dimension, context_desc, language, count, batch_num
            )
        if stage == 'subparts':
            raw_part = stage_data.get('part_name', '')
            raw_dim = stage_data.get('dimension', '')
            part_name = filter_for_prompt(
                raw_part,
                fallback_zh='该部分',
                fallback_en='the selected part',
                language=language
            )
            dimension = (raw_dim or '').strip()
            return self._build_subparts_prompt(
                center_topic, part_name, dimension, context_desc,
                language, count, batch_num
            )
        return self._build_dimensions_prompt(
            center_topic, context_desc, language, count, batch_num
        )

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
        Uses centralized prompts aligned with thinking_maps.py.
        """
        return get_brace_dimensions_prompt(
            center_topic, context_desc, language, count, batch_num
        )

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
        Uses centralized prompts aligned with thinking_maps.py.
        """
        return get_brace_parts_prompt(
            center_topic, dimension, context_desc, language, count, batch_num
        )

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
        Uses centralized prompts aligned with thinking_maps.py.
        """
        return get_brace_subparts_prompt(
            center_topic, part_name, dimension, context_desc,
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


class _BraceMapPaletteHolder:
    """Holder for Brace Map palette generator singleton."""
    instance: Optional[BraceMapPaletteGenerator] = None


def get_brace_map_palette_generator() -> BraceMapPaletteGenerator:
    """Get singleton instance of Brace Map palette generator"""
    if _BraceMapPaletteHolder.instance is None:
        _BraceMapPaletteHolder.instance = BraceMapPaletteGenerator()
    return _BraceMapPaletteHolder.instance
