"""
Inline Recommendations Generator - Catapult-style multi-LLM streaming.

Fires 3 LLMs (qwen, deepseek, doubao) concurrently to generate node text
recommendations for mindmap, flow_map, tree_map, brace_map.
Streams recommendations progressively, deduplicates across LLMs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import re
import time
from difflib import SequenceMatcher
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from agents.inline_recommendations.context_extractors import (
    extract_diagram_context,
    get_diagram_existing_texts,
)
from agents.inline_recommendations.prompts import build_prompt
from agents.inline_recommendations.prompts._common import get_context_desc
from services.llm import llm_service

logger = logging.getLogger(__name__)


def _strip_parenthetical(text: str) -> str:
    """Remove parenthetical notes (Chinese （） or English ())."""
    if not text:
        return text
    for sep in ("（", "("):
        idx = text.find(sep)
        if idx >= 0:
            text = text[:idx]
    return text.strip()


class _GeneratorHolder:
    """Holds singleton instance to avoid global mutable state."""

    instance: Optional["InlineRecommendationsGenerator"] = None


class InlineRecommendationsGenerator:
    """
    Catapult-style generator for inline node recommendations.

    Fires 3 LLMs concurrently, streams recommendations as they arrive, deduplicates.
    """

    def __init__(self) -> None:
        self.llm_service = llm_service
        self.llm_models = ["qwen", "deepseek", "doubao"]
        self.seen_texts: Dict[str, Set[str]] = {}
        self.generated: Dict[str, List[str]] = {}
        self.batch_counts: Dict[str, int] = {}
        self.session_start_times: Dict[str, float] = {}

    def _normalize(self, text: str) -> str:
        """Normalize text for deduplication."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _seed_diagram_texts(self, session_id: str, context: Dict[str, Any]) -> None:
        """Seed seen_texts with diagram content so we don't recommend duplicates."""
        diagram_texts = get_diagram_existing_texts(context)
        if session_id not in self.seen_texts:
            self.seen_texts[session_id] = set()
        for txt in diagram_texts:
            norm = self._normalize(txt)
            if norm:
                self.seen_texts[session_id].add(norm)

    def _deduplicate(self, text: str, session_id: str) -> Tuple[bool, str, float]:
        """Check if text is unique. Returns (is_unique, match_type, similarity)."""
        normalized = self._normalize(text)
        if session_id not in self.seen_texts:
            self.seen_texts[session_id] = set()
        seen = self.seen_texts[session_id]
        if normalized in seen:
            return (False, "exact", 1.0)
        for seen_text in seen:
            similarity = SequenceMatcher(None, normalized, seen_text).ratio()
            if similarity > 0.85:
                return (False, "fuzzy", similarity)
        seen.add(normalized)
        return (True, "unique", 0.0)

    def _try_parse_line(self, line: str, session_id: str) -> Optional[str]:
        """Parse and deduplicate a line. Returns text if unique else None."""
        raw = line
        line = line.strip().lstrip("0123456789.-、）) ").strip()
        if not line or len(line) < 2:
            logger.debug("[InlineRec] Parse reject (empty/short): raw=%r", raw[:80])
            return None
        cleaned = _strip_parenthetical(line)
        if not cleaned:
            logger.debug("[InlineRec] Parse reject (parenthetical): raw=%r", raw[:80])
            return None
        is_unique, match_type, sim = self._deduplicate(cleaned, session_id)
        if not is_unique:
            logger.debug(
                "[InlineRec] Parse reject (dup %s %.2f): %r",
                match_type,
                sim,
                cleaned[:50],
            )
            return None
        return cleaned

    def _store_recommendation(self, session_id: str, text: str, llm_name: str) -> Dict[str, Any]:
        """Store recommendation and return event dict."""
        if session_id not in self.generated:
            self.generated[session_id] = []
        self.generated[session_id].append(text)
        logger.debug("[InlineRec] Yield recommendation: %r (from %s)", text[:50], llm_name)
        return {
            "event": "recommendation_generated",
            "text": text,
            "source_llm": llm_name,
        }

    def _parse_lines_to_events(self, lines: List[str], session_id: str, llm_name: str) -> List[Dict[str, Any]]:
        """Parse lines into recommendation events."""
        events: List[Dict[str, Any]] = []
        for line in lines:
            text = self._try_parse_line(line, session_id)
            if text:
                events.append(self._store_recommendation(session_id, text, llm_name))
        return events

    async def _process_stream_chunk(
        self,
        chunk: Dict[str, Any],
        session_id: str,
        state: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process one stream chunk, yield recommendation events."""
        evt_type = chunk.get("event")
        llm = chunk.get("llm", "")
        curr = state["current_lines"]
        pend = state["pending"]
        order = state["llm_order"]
        nidx = state["next_idx"]

        if evt_type == "token":
            tok = chunk.get("token", "")
            curr[llm] += tok
            if "\n" in curr[llm]:
                parts = curr[llm].split("\n")
                curr[llm] = parts[-1]
                logger.debug(
                    "[InlineRec] Split on newline: %d parts from %s, lines=%r",
                    len(parts) - 1,
                    llm,
                    [p[:40] for p in parts[:-1]],
                )
                for evt in self._parse_lines_to_events(parts[:-1], session_id, llm):
                    pend[llm].append(evt)
                    for _ in range(len(state["llm_order"])):
                        mdl = order[nidx % len(order)]
                        nidx += 1
                        if pend[mdl]:
                            yield pend[mdl].pop(0)
                            await asyncio.sleep(0)
                state["next_idx"] = nidx

        elif evt_type == "complete":
            remainder = curr[llm].lstrip("0123456789.-、）) ")
            logger.debug(
                "[InlineRec] Complete from %s: remainder=%r (len=%d)",
                llm,
                remainder[:200],
                len(remainder),
            )
            for evt in self._parse_lines_to_events([remainder], session_id, llm):
                pend[llm].append(evt)
            while pend[llm]:
                yield pend[llm].pop(0)
                await asyncio.sleep(0)

    def _resolve_models(self, models: Optional[List[str]]) -> List[str]:
        """Resolve requested models to active list; fallback to all if empty."""
        active = [m for m in models if m in self.llm_models] if models else self.llm_models.copy()
        return active if active else self.llm_models.copy()

    async def _stream_recommendations(
        self,
        session_id: str,
        prompt: str,
        language: str,
        batch_num: int,
        diagram_type: str,
        models: Optional[List[str]] = None,
        stream_opts: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream recommendations from LLMs. models: which models to use (default: all 3)."""
        opts = stream_opts or {}
        active_models = self._resolve_models(models)
        state: Dict[str, Any] = {
            "current_lines": {m: "" for m in active_models},
            "pending": {m: [] for m in active_models},
            "llm_order": active_models.copy(),
            "next_idx": 0,
        }
        async for chunk in self.llm_service.stream_progressive(
            prompt=prompt,
            models=active_models,
            temperature=min(0.7 + (batch_num - 1) * 0.1, 1.0),
            max_tokens=500,
            timeout=20.0,
            system_message=(
                "你是一个有帮助的K12教育助手。" if language == "zh" else "You are a helpful K12 education assistant."
            ),
            user_id=opts.get("user_id"),
            organization_id=opts.get("organization_id"),
            request_type="inline_recommendations",
            diagram_type=diagram_type,
            endpoint_path=opts.get("endpoint_path") or "/thinking_mode/inline_recommendations/start",
            session_id=session_id,
        ):
            async for evt in self._process_stream_chunk(chunk, session_id, state):
                yield evt

    def _prepare_batch(
        self,
        session_id: str,
        diagram_type: str,
        stage: str,
        nodes: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, Any]]],
        current_node_id: Optional[str],
        language: str,
        count: int,
        educational_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Prepare batch: init session, build prompt. Returns prep dict or None."""
        context = extract_diagram_context(diagram_type, nodes, connections, current_node_id)
        context["context_desc"] = get_context_desc(educational_context)

        if session_id not in self.session_start_times:
            self.session_start_times[session_id] = time.time()
            self.batch_counts[session_id] = 0

        self._seed_diagram_texts(session_id, context)

        batch_num = self.batch_counts[session_id] + 1
        self.batch_counts[session_id] = batch_num
        existing = self.generated.get(session_id, [])
        total_before = len(existing)
        prompt = build_prompt(
            diagram_type,
            stage,
            context,
            language=language,
            count=count,
            batch_num=batch_num,
            existing=existing,
        )

        if not prompt:
            return None

        return {
            "batch_num": batch_num,
            "total_before": total_before,
            "prompt": prompt,
        }

    def _batch_complete_event(
        self,
        session_id: str,
        prep: Dict[str, Any],
        batch_start: float,
    ) -> Dict[str, Any]:
        """Build batch_complete event dict."""
        generated = self.generated.get(session_id, [])
        return {
            "event": "batch_complete",
            "batch_number": prep["batch_num"],
            "batch_duration": round(time.time() - batch_start, 2),
            "new_unique": len(generated) - prep["total_before"],
            "total": len(generated),
        }

    async def _run_batch_stream(
        self,
        session_id: str,
        prep: Dict[str, Any],
        diagram_type: str,
        language: str,
        models: Optional[List[str]],
        opts: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Run stream and yield events; yields error event on exception."""
        try:
            async for evt in self._stream_recommendations(
                session_id=session_id,
                prompt=prep["prompt"],
                language=language,
                batch_num=prep["batch_num"],
                diagram_type=diagram_type,
                models=models,
                stream_opts=opts,
            ):
                yield evt
        except Exception as exc:
            logger.error("[InlineRec] Stream error: %s", str(exc), exc_info=True)
            yield {
                "event": "error",
                "message": str(exc) if str(exc) else "Request failed",
            }

    async def generate_batch(
        self,
        session_id: str,
        diagram_type: str,
        stage: str,
        nodes: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, Any]]] = None,
        current_node_id: Optional[str] = None,
        language: str = "en",
        count: int = 15,
        models: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate batch of recommendations using selected LLMs concurrently.

        models: which models to use (default: all). options: user_id, org_id, etc.

        Yields:
            - {'event': 'batch_start', 'batch_number': N, 'llm_count': N}
            - {'event': 'recommendation_generated', 'text': str, 'source_llm': str}
            - {'event': 'batch_complete', 'total_unique': N}
            - {'event': 'error', 'message': str}
        """
        opts = options or {}
        prep = self._prepare_batch(
            session_id,
            diagram_type,
            stage,
            nodes,
            connections,
            current_node_id,
            language,
            count,
            opts.get("educational_context"),
        )
        if prep is None:
            yield {"event": "error", "message": "Failed to build prompt"}
            return

        logger.debug(
            "[InlineRec] Batch %d | Session: %s | Type: %s | Stage: %s",
            prep["batch_num"],
            session_id[:8],
            diagram_type,
            stage,
        )

        yield {
            "event": "batch_start",
            "batch_number": prep["batch_num"],
            "llm_count": len(self._resolve_models(models)),
        }

        batch_start = time.time()
        async for evt in self._run_batch_stream(session_id, prep, diagram_type, language, models, opts):
            yield evt
            if evt.get("event") == "error":
                return

        yield self._batch_complete_event(session_id, prep, batch_start)

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """Clean up session state."""
        logger.debug(
            "[InlineRec] Session ended: %s (reason: %s)",
            session_id[:8],
            reason,
        )
        self.session_start_times.pop(session_id, None)
        self.generated.pop(session_id, None)
        self.seen_texts.pop(session_id, None)
        self.batch_counts.pop(session_id, None)

    def prune_stale_sessions(self, max_age_seconds: int = 1800) -> int:
        """Remove sessions older than max_age_seconds. Returns count pruned."""
        now = time.time()
        threshold = now - max_age_seconds
        stale = [sid for sid, start in self.session_start_times.items() if start < threshold]
        for sid in stale:
            self.session_start_times.pop(sid, None)
            self.generated.pop(sid, None)
            self.seen_texts.pop(sid, None)
            self.batch_counts.pop(sid, None)
        if stale:
            logger.debug("[InlineRec] Pruned %d stale session(s)", len(stale))
        return len(stale)


def get_inline_recommendations_generator() -> InlineRecommendationsGenerator:
    """Return singleton inline recommendations generator."""
    if _GeneratorHolder.instance is None:
        _GeneratorHolder.instance = InlineRecommendationsGenerator()
    return _GeneratorHolder.instance
