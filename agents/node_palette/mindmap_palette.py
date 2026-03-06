"""Mind Map Palette Generator.

Mind Map specific node palette generator with multi-stage workflow.
Supports 2-stage progressive generation:
1. Stage 1 (branches): Generate main branches from central topic
2. Stage 2 (children): Generate sub-branches for selected branch
"""

from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator
from prompts.node_palette import (
    get_mindmap_branches_prompt,
    get_mindmap_children_prompt,
)

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
        _mode: Optional[str] = None,
        _stage: Optional[str] = None,
        _stage_data: Optional[Dict[str, Any]] = None,
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
            _stage: Generation stage ('branches', 'children')
            _stage_data: Stage-specific data (branch_name, etc.)
        """
        stage = _stage or 'branches'
        stage_data = _stage_data or {}

        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)

        logger.debug("[MindMapPalette] Stage: %s | Session: %s | Topic: '%s'",
                     stage, session_id[:8], center_topic)
        if stage_data:
            logger.debug("[MindMapPalette] Stage data: %s", stage_data)

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
                self._tag_node_with_mode(event, stage, stage_data)
            yield event

    def _tag_node_with_mode(
        self,
        event: Dict[str, Any],
        stage: str,
        stage_data: Dict[str, Any]
    ) -> None:
        """Add mode field to node for explicit tracking."""
        node = event.get('node', {})
        if stage == 'children' and stage_data.get('branch_name'):
            node_mode = stage_data['branch_name']
        else:
            node_mode = stage
        node['mode'] = node_mode
        logger.debug(
            "[MindMapPalette] Node tagged with mode='%s' | ID: %s | Text: %s",
            node_mode,
            node.get('id', 'unknown'),
            node.get('text', '')
        )

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
        language = self._detect_language(center_topic, educational_context)
        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context
            else 'General K12 teaching'
        )

        session_id = (
            educational_context.get('_session_id') if educational_context
            else None
        )
        stage = 'branches'
        stage_data = {}

        if session_id and session_id in self.session_stages:
            stage = self.session_stages[session_id].get('stage', 'branches')
            stage_data = self.session_stages[session_id]

        logger.debug(
            "[MindMapPalette-Prompt] Building prompt for stage: %s", stage
        )

        if stage == 'children':
            branch_name = stage_data.get('branch_name', '')
            return self._build_children_prompt(
                center_topic,
                branch_name,
                context_desc,
                language,
                count,
                batch_num
            )
        return self._build_branches_prompt(
            center_topic, context_desc, language, count, batch_num
        )

    def _build_branches_prompt(
        self,
        center_topic: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for generating main branches from central topic. Uses centralized prompts."""
        return get_mindmap_branches_prompt(
            center_topic, context_desc, language, count, batch_num
        )

    def _build_children_prompt(
        self,
        center_topic: str,
        branch_name: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for generating sub-branches/children for a specific branch. Uses centralized prompts."""
        return get_mindmap_children_prompt(
            center_topic, branch_name, context_desc, language, count, batch_num
        )


class _MindMapPaletteHolder:
    """Holder for Mind Map palette generator singleton instance."""

    instance: Optional[MindMapPaletteGenerator] = None


def get_mindmap_palette_generator() -> MindMapPaletteGenerator:
    """Get singleton instance of Mind Map palette generator"""
    if _MindMapPaletteHolder.instance is None:
        _MindMapPaletteHolder.instance = MindMapPaletteGenerator()
    return _MindMapPaletteHolder.instance
