"""
Async event-driven diagram generation pipeline entry point.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
from typing import Any

from agents.core.generate_events import EventEmitter
from agents.core.workflow import agent_graph_workflow_with_styles


async def run_generate_pipeline(
    user_prompt: str,
    *,
    language: str = "zh",
    forced_diagram_type: str | None = None,
    dimension_preference: str | None = None,
    model: str = "qwen",
    user_id: Any = None,
    organization_id: Any = None,
    request_type: str = "diagram_generation",
    endpoint_path: str | None = None,
    existing_analogies: list | None = None,
    fixed_dimension: str | None = None,
    dimension_only_mode: bool | None = None,
    concept_map_relationship_only: bool | None = None,
    concept_a: str | None = None,
    concept_b: str | None = None,
    concept_map_topic: str | None = None,
    link_direction: str | None = None,
    use_rag: bool = False,
    rag_top_k: int = 5,
    diagram_id: str | None = None,
    rag_document_ids: list | None = None,
    event_emit: EventEmitter | None = None,
    cancel_event: asyncio.Event | None = None,
    phase_emit=None,
) -> dict:
    """Run the full generate_graph pipeline with typed events and cancellation."""
    return await agent_graph_workflow_with_styles(
        user_prompt,
        language=language,
        forced_diagram_type=forced_diagram_type,
        dimension_preference=dimension_preference,
        model=model,
        user_id=user_id,
        organization_id=organization_id,
        request_type=request_type,
        endpoint_path=endpoint_path,
        existing_analogies=existing_analogies,
        fixed_dimension=fixed_dimension,
        dimension_only_mode=dimension_only_mode,
        concept_map_relationship_only=concept_map_relationship_only,
        concept_a=concept_a,
        concept_b=concept_b,
        concept_map_topic=concept_map_topic,
        link_direction=link_direction,
        use_rag=use_rag,
        rag_top_k=rag_top_k,
        diagram_id=diagram_id,
        rag_document_ids=rag_document_ids,
        event_emit=event_emit,
        cancel_event=cancel_event,
        phase_emit=phase_emit,
    )
