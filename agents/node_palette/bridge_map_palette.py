"""
Bridge Map Palette Generator
=============================

Bridge Map specific node palette generator.
Generates analogy pair nodes for Bridge Maps with paired left/right format.
Similar to double bubble map's differences, but for analogies.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from functools import lru_cache
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator
from prompts.node_palette import (
    get_bridge_pairs_prompt,
    get_bridge_dimensions_prompt,
)

logger = logging.getLogger(__name__)


def _parse_analogy_node(node: Dict[str, Any]) -> bool:
    """
    Parse pipe-separated analogy in node text. Mutates node in place.
    Returns True if valid, False if should skip.
    """
    text = node.get('text', '')
    if '|' not in text:
        logger.warning("[BridgeMap] Skipping node without pipe separator: '%s'", text)
        return False
    parts = text.split('|')
    if len(parts) < 2:
        logger.warning("[BridgeMap] Skipping malformed node: '%s'", text)
        return False
    left_text = parts[0].strip()
    right_text = parts[1].strip()
    dimension = parts[2].strip() if len(parts) >= 3 else None
    if len(left_text) < 2 or len(right_text) < 2:
        logger.debug("[BridgeMap] Skipping too short: '%s | %s'", left_text, right_text)
        return False
    if left_text.startswith('-') or right_text.startswith('-'):
        logger.debug("[BridgeMap] Skipping markdown separator: '%s | %s'", left_text, right_text)
        return False
    if 'as' in left_text.lower() and 'as' in right_text.lower():
        logger.debug("[BridgeMap] Skipping header pattern: '%s | %s'", left_text, right_text)
        return False
    node['left'] = left_text
    node['right'] = right_text
    if dimension:
        node['dimension'] = dimension
    node['text'] = text
    dim_info = f" | dimension='{dimension}'" if dimension else ""
    logger.debug(
        "[BridgeMap] Parsed pair successfully: left='%s' | right='%s'%s",
        left_text, right_text, dim_info
    )
    logger.debug("[BridgeMap] Node now has: %s", list(node.keys()))
    return True


class BridgeMapPaletteGenerator(BasePaletteGenerator):
    """
    Bridge Map specific palette generator.

    Generates analogy pair nodes for Bridge Maps.
    Uses pipe-separated format: "left | right | dimension"
    similar to double bubble differences.
    """

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
        Generate batch with stage support: dimensions or pairs.

        Stage 'dimensions': Generate relationship dimension options (one per line).
        Stage 'pairs': Generate analogy pairs for selected dimension.
        """
        if educational_context is None:
            educational_context = {}
        educational_context = {
            **educational_context,
            '_stage': _stage or 'dimensions',
            '_stage_data': _stage_data or {},
        }
        async for chunk in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm,
            _mode=_mode,
            _stage=_stage,
            _stage_data=_stage_data,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path
        ):
            if chunk.get('event') == 'node_generated':
                node = chunk.get('node', {})
                if _stage == 'dimensions':
                    node['mode'] = 'dimensions'
                else:
                    logger.debug(
                        "[BridgeMap] Processing node with text: '%s'",
                        node.get('text', '')
                    )
                    if not _parse_analogy_node(node):
                        continue
            yield chunk

    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build Bridge Map prompt: dimensions (stage 1) or pairs (stage 2).

        Stage 'dimensions': Generate relationship dimension options.
        Stage 'pairs': Generate analogy pairs (use dimension from stage_data if set).
        """
        stage = (
            educational_context.get('_stage', 'dimensions')
            if educational_context else 'dimensions'
        )
        stage_data = (
            educational_context.get('_stage_data', {})
            if educational_context else {}
        )
        language = self._detect_language(center_topic, educational_context)
        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context else 'General K12 teaching'
        )

        if stage == 'dimensions':
            return self._build_dimensions_prompt(
                center_topic, context_desc, language, count, batch_num
            )

        dimension = stage_data.get('dimension', '') or center_topic
        is_specific_relationship = bool(dimension and str(dimension).strip())
        logger.debug(
            "[BridgeMap-Prompt] Stage: %s | Dimension: '%s'",
            stage, dimension
        )

        dim_for_prompt = dimension if is_specific_relationship else None
        return get_bridge_pairs_prompt(
            center_topic, dim_for_prompt, context_desc, language, count, batch_num
        )

    def _build_dimensions_prompt(
        self,
        center_topic: str,
        context_desc: str,
        language: str,
        count: int,
        batch_num: int
    ) -> str:
        """Build prompt for generating relationship dimension options (stage 1). Uses centralized prompts."""
        return get_bridge_dimensions_prompt(
            center_topic, context_desc, language, count, batch_num
        )


@lru_cache(maxsize=1)
def get_bridge_map_palette_generator() -> BridgeMapPaletteGenerator:
    """Get singleton instance of Bridge Map palette generator."""
    return BridgeMapPaletteGenerator()
