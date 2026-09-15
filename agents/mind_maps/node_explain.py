"""
Mind map node explain — a 250–400 character gloss for one selected node.

Meaning facet writes after web search; images run on a parallel Responses call.
Conflict and questions stay on chat completions.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from agents.mind_maps.node_explain_prompts import (
    RESEARCH_IMAGE_MAX_OUTPUT_TOKENS,
    RESEARCH_IMAGE_TOOLS,
    RESEARCH_MAX_OUTPUT_TOKENS,
    RESEARCH_TOOLS,
    build_facet_prompt,
    build_research_image_prompt,
    build_research_meaning_prompt,
    max_tokens_for_audience,
    normalize_facet,
)
from agents.mind_maps.node_explain_research import merge_research_streams
from services.infrastructure.http.error_handler import (
    LLMInvalidParameterError,
    LLMModelNotFoundError,
)
from services.llm import llm_service
from services.llm.responses.service import get_responses_service


class _GeneratorHolder:
    """Holds singleton instance to avoid global mutable state."""

    instance: Optional["MindMapNodeExplainGenerator"] = None


def _should_fallback_to_chat(exc: Exception) -> bool:
    if isinstance(exc, LLMModelNotFoundError):
        return True
    if not isinstance(exc, LLMInvalidParameterError):
        return False
    text = str(exc).lower()
    return "does not support" in text or "not support" in text


class MindMapNodeExplainGenerator:
    """Streams one educational facet for a selected diagram node."""

    def __init__(self) -> None:
        self.llm_service = llm_service
        self.responses_service = get_responses_service()

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
        """Yield SSE-friendly event dicts for one facet."""
        resolved_facet = normalize_facet(facet)
        branches = top_level_branches or []
        ancestors = ancestor_path or []
        siblings = sibling_branches or []
        children = child_branches or []
        token = (request_token or "req").strip() or "req"
        user_part = str(user_id) if user_id is not None else "anon"
        base_session = (session_id or "").strip() or f"explain_{diagram_id or 'anon'}_{user_part}"
        stream_session_id = f"{base_session}:{resolved_facet}:{token}"

        if resolved_facet == "meaning":
            async for event in self._stream_research_meaning(
                node_label=node_label,
                topic=topic,
                diagram_type=diagram_type,
                top_level_branches=branches,
                ancestor_path=ancestors,
                sibling_branches=siblings,
                child_branches=children,
                language=language,
                audience_level=audience_level,
                user_id=user_id,
                organization_id=organization_id,
                endpoint_path=endpoint_path,
                stream_session_id=stream_session_id,
                generation_instructions=generation_instructions,
            ):
                yield event
            return

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
        async for event in self._stream_chat_tokens(
            prompt=prompt,
            resolved_facet=resolved_facet,
            audience_level=audience_level,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path,
            stream_session_id=stream_session_id,
        ):
            yield event

    async def _stream_research_meaning(
        self,
        *,
        node_label: str,
        topic: str,
        diagram_type: str,
        top_level_branches: List[str],
        ancestor_path: List[str],
        sibling_branches: List[str],
        child_branches: List[str],
        language: str,
        audience_level: Optional[str],
        user_id: Optional[int],
        organization_id: Optional[int],
        endpoint_path: str,
        stream_session_id: str,
        generation_instructions: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        prompt = build_research_meaning_prompt(
            node_label=node_label,
            topic=topic,
            diagram_type=diagram_type,
            top_level_branches=top_level_branches,
            ancestor_path=ancestor_path,
            sibling_branches=sibling_branches,
            child_branches=child_branches,
            language=language,
            audience_level=audience_level,
            generation_instructions=generation_instructions,
        )
        image_prompt = build_research_image_prompt(
            node_label=node_label,
            topic=topic,
            language=language,
        )
        write_stream = self.responses_service.stream(
            prompt=prompt,
            tools=list(RESEARCH_TOOLS),
            enable_thinking=True,
            max_output_tokens=RESEARCH_MAX_OUTPUT_TOKENS,
            temperature=0.6,
            user_id=user_id,
            organization_id=organization_id,
            request_type="mindmap_node_explain",
            diagram_type=diagram_type or "mindmap",
            endpoint_path=endpoint_path,
            session_id=stream_session_id,
        )
        image_stream = self.responses_service.stream(
            prompt=image_prompt,
            tools=list(RESEARCH_IMAGE_TOOLS),
            enable_thinking=True,
            max_output_tokens=RESEARCH_IMAGE_MAX_OUTPUT_TOKENS,
            temperature=0.6,
            user_id=user_id,
            organization_id=organization_id,
            request_type="mindmap_node_explain",
            diagram_type=diagram_type or "mindmap",
            endpoint_path=endpoint_path,
            session_id=f"{stream_session_id}:images",
            bill_usage=False,
        )
        saw_event = False
        yielded_error = False
        try:
            async for chunk in merge_research_streams(write_stream, image_stream):
                mapped = self._map_research_chunk(chunk)
                if mapped is None:
                    continue
                saw_event = True
                if mapped.get("event") == "error":
                    yielded_error = True
                yield mapped
            if not yielded_error:
                yield {"event": "end", "facet": "meaning"}
            return
        except (LLMModelNotFoundError, LLMInvalidParameterError) as exc:
            if saw_event or not _should_fallback_to_chat(exc):
                raise
        async for event in self._stream_chat_tokens(
            prompt=prompt,
            resolved_facet="meaning",
            audience_level=audience_level,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path,
            stream_session_id=stream_session_id,
        ):
            yield event

    def _map_research_chunk(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        kind = chunk.get("type")
        if kind == "status":
            return {
                "event": "status",
                "phase": chunk.get("phase") or "",
                "query": chunk.get("query") or "",
                "urls": chunk.get("urls") or [],
                "facet": "meaning",
            }
        if kind == "search_source":
            return {
                "event": "search_source",
                "query": chunk.get("query") or "",
                "sources": chunk.get("sources") or [],
                "facet": "meaning",
            }
        if kind == "extract":
            return {
                "event": "extract",
                "goal": chunk.get("goal") or "",
                "urls": chunk.get("urls") or [],
                "facet": "meaning",
            }
        if kind == "image":
            return {
                "event": "image",
                "images": chunk.get("images") or [],
                "facet": "meaning",
            }
        if kind == "thinking":
            content = chunk.get("content") or ""
            if not content:
                return None
            return {"event": "thinking", "text": content, "facet": "meaning"}
        if kind == "token":
            content = chunk.get("content") or ""
            if not content:
                return None
            return {"event": "token", "text": content, "facet": "meaning"}
        if kind == "error":
            message = chunk.get("content") or ""
            if not message:
                return None
            return {"event": "error", "message": message, "facet": "meaning"}
        return None

    async def _stream_chat_tokens(
        self,
        *,
        prompt: str,
        resolved_facet: str,
        audience_level: Optional[str],
        user_id: Optional[int],
        organization_id: Optional[int],
        diagram_type: str,
        endpoint_path: str,
        stream_session_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        saw_token = False
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
        if saw_token:
            yield {"event": "end", "facet": resolved_facet}


def get_mind_map_node_explain_generator() -> MindMapNodeExplainGenerator:
    """Return shared generator instance."""
    if _GeneratorHolder.instance is None:
        _GeneratorHolder.instance = MindMapNodeExplainGenerator()
    return _GeneratorHolder.instance
