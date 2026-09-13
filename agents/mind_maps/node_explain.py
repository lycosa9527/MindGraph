"""
Mind map node explain — a short gloss for one selected node.

Voice, length, and depth follow canvas 专业程度. The canvas streams the
meaning facet into a bubble beside the node. Conflict and questions
facets remain available on the API.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from agents.mind_maps.node_explain_prompts import (
    build_facet_prompt,
    max_tokens_for_audience,
    normalize_facet,
)
from services.llm import llm_service


class _GeneratorHolder:
    """Holds singleton instance to avoid global mutable state."""

    instance: Optional["MindMapNodeExplainGenerator"] = None


class MindMapNodeExplainGenerator:
    """Streams one educational facet for a selected diagram node."""

    def __init__(self) -> None:
        self.llm_service = llm_service

    async def stream_explain(
        self,
        *,
        node_label: str,
        topic: str,
        diagram_type: str = "mindmap",
        top_level_branches: Optional[List[str]] = None,
        ancestor_path: Optional[List[str]] = None,
        sibling_branches: Optional[List[str]] = None,
        child_branches: Optional[List[str]] = None,
        language: str = "en",
        facet: str = "meaning",
        audience_level: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        endpoint_path: str = "/thinking_mode/mindmap/explain_node",
        diagram_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_token: Optional[str] = None,
        generation_instructions: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield SSE-friendly event dicts: token chunks and end."""
        resolved_facet = normalize_facet(facet)
        branches = top_level_branches or []
        ancestors = ancestor_path or []
        siblings = sibling_branches or []
        children = child_branches or []
        token = (request_token or "req").strip() or "req"
        user_part = str(user_id) if user_id is not None else "anon"
        base_session = (session_id or "").strip() or f"explain_{diagram_id or 'anon'}_{user_part}"
        # Per-facet stream id keeps token rows distinct while sharing the client session prefix.
        stream_session_id = f"{base_session}:{resolved_facet}:{token}"
        saw_token = False

        prompt = build_facet_prompt(
            facet=resolved_facet,
            node_label=node_label,
            topic=topic,
            diagram_type=diagram_type,
            top_level_branches=branches,
            ancestor_path=ancestors,
            sibling_branches=siblings,
            child_branches=children,
            language=language,
            audience_level=audience_level,
            generation_instructions=generation_instructions,
        )

        async for chunk in self.llm_service.chat_stream(
            prompt=prompt,
            model="qwen",
            max_tokens=max_tokens_for_audience(audience_level or "general"),
            temperature=0.6,
            user_id=user_id,
            organization_id=organization_id,
            request_type="mindmap_node_explain",
            diagram_type=diagram_type or "mindmap",
            endpoint_path=endpoint_path,
            session_id=stream_session_id,
            use_knowledge_base=False,
            yield_structured=True,
        ):
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") != "token":
                continue
            content = chunk.get("content") or ""
            if not content:
                continue
            saw_token = True
            yield {"event": "token", "text": content, "facet": resolved_facet}

        if not saw_token:
            # Router emits a localized empty-response error when no chunks arrive.
            return
        yield {"event": "end", "facet": resolved_facet}


def get_mind_map_node_explain_generator() -> MindMapNodeExplainGenerator:
    """Return shared generator instance."""
    if _GeneratorHolder.instance is None:
        _GeneratorHolder.instance = MindMapNodeExplainGenerator()
    return _GeneratorHolder.instance
