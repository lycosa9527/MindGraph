"""
Flow Map Palette Generator
===========================

Flow Map specific node palette generator.
Generates step/process nodes for Flow Maps using auto-complete style prompts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator
from prompts.node_palette import (
    get_flow_dimensions_prompt,
    get_flow_steps_prompt,
    get_flow_substeps_prompt,
)

logger = logging.getLogger(__name__)


class FlowMapPaletteGenerator(BasePaletteGenerator):
    """
    Flow Map specific palette generator with multi-stage workflow and step sequencing.

    Stages:
    1. steps: Generate main steps (no dimensions needed)
    2. substeps: Generate substeps for a specific step

    Key feature: Sequence numbers are assigned when user selects steps (based on selection order),
    not during generation. This allows users to see steps without numbers first, then numbers
    appear after selection.
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
        _mode: Optional[str] = None,
        _stage: Optional[str] = None,
        _stage_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with multi-stage workflow and step sequencing.

        Args:
            session_id: Session identifier
            center_topic: Main process/event
            educational_context: Educational context
            nodes_per_llm: Nodes to request per LLM
            _stage: Generation stage ('dimensions', 'steps', 'substeps')
            _stage_data: Stage-specific data (dimension, step_name, etc.)
        """
        stage = _stage or 'steps'
        stage_data = _stage_data
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
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
            diagram_type=diagram_type,
            endpoint_path=endpoint_path
        ):
            if event.get('event') == 'node_generated':
                self._tag_node_with_mode(event, stage, stage_data)
            yield event

    def _tag_node_with_mode(
        self,
        event: Dict[str, Any],
        stage: str,
        stage_data: Optional[Dict[str, Any]]
    ) -> None:
        """Set node mode from stage; use step_name for substeps, else stage name."""
        node = event.get('node', {})
        if not node:
            return
        if stage == 'substeps' and stage_data and stage_data.get('step_name'):
            node['mode'] = stage_data['step_name']
        else:
            node['mode'] = stage
        logger.debug(
            "[FlowMapPalette] Node tagged with mode='%s' | ID: %s | Text: %s",
            node['mode'], node.get('id', 'unknown'), node.get('text', ''))

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
        language = self._detect_language(center_topic, educational_context)
        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context else 'General K12 teaching'
        )

        # Get session_id from educational_context (passed through from generate_batch)
        session_id = educational_context.get('_session_id', '') if educational_context else ''

        # Get current stage and stage_data
        stage_info = self.session_stages.get(session_id, {})
        stage = stage_info.get('stage', 'steps')  # Default to 'steps' (dimensions stage removed)

        logger.debug("[FlowMapPalette-Prompt] Building prompt for stage: %s", stage)

        # Build stage-specific prompt
        if stage == 'steps':
            return self._build_steps_prompt(
                center_topic, context_desc, language, count, batch_num
            )
        if stage == 'substeps':
            step_name = stage_info.get('step_name', '')
            return self._build_substeps_prompt(
                center_topic, step_name, context_desc, language, count, batch_num
            )
        # Fallback to steps (default stage for flow maps)
        logger.warning(
            "[FlowMapPalette] Unknown stage '%s', defaulting to 'steps'", stage
        )
        return self._build_steps_prompt(
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
        """Build prompt for Stage 1: Dimensions. Uses centralized prompts."""
        return get_flow_dimensions_prompt(
            center_topic, context_desc, language, count, batch_num
        )

    def _build_steps_prompt(
        self,
        center_topic: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for Stage 1: Steps. Uses centralized prompts."""
        return get_flow_steps_prompt(
            center_topic, context_desc, language, count, batch_num
        )

    def _build_substeps_prompt(
        self,
        center_topic: str,
        step_name: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for Stage 2: Substeps (for a specific step). Uses centralized prompts."""
        return get_flow_substeps_prompt(
            center_topic, step_name, context_desc, language, count, batch_num
        )

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """
        End session and cleanup stage data and sequence tracking.

        Overrides base class to also clean up session_stages and step_sequences.
        """
        # Clean up stage data and sequence tracking
        self.session_stages.pop(session_id, None)
        self.step_sequences.pop(session_id, None)

        # Call parent cleanup
        super().end_session(session_id, reason)


class _FlowMapPaletteHolder:
    """Holder for Flow Map palette generator singleton instance."""

    instance: Optional[FlowMapPaletteGenerator] = None


def get_flow_map_palette_generator() -> FlowMapPaletteGenerator:
    """Get singleton instance of Flow Map palette generator"""
    if _FlowMapPaletteHolder.instance is None:
        _FlowMapPaletteHolder.instance = FlowMapPaletteGenerator()
    return _FlowMapPaletteHolder.instance
