"""
Node-explain stream stats for backend logs, Redis tracker, and usage timeline.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from models.domain.auth import User
from services.admin.user_usage_activity import clip_activity_preview
from services.monitoring.module_activity import schedule_module_activity
from utils.auth.connection_types import HttpOrWebSocket

logger = logging.getLogger(__name__)

_LOG_PREFIX = "[MindMapExplain]"
_INTERNAL_EVENTS = frozenset({"usage"})


def is_internal_explain_event(event: str) -> bool:
    """True when the chunk is for logs/tracker only (do not SSE)."""
    return event in _INTERNAL_EVENTS


def _as_token_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


@dataclass
class LaneTokenTotals:
    """Prompt / completion / billed totals for one Responses lane."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add(self, input_tokens: int, output_tokens: int, total_tokens: int) -> None:
        """Accumulate one Responses usage event into this lane."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += total_tokens


@dataclass
class ExplainStreamStats:
    """Search / image / token totals for one explain facet stream."""

    searches: int = 0
    sources: int = 0
    images: int = 0
    write: LaneTokenTotals = field(default_factory=LaneTokenTotals)
    image: LaneTokenTotals = field(default_factory=LaneTokenTotals)
    queries: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        """Write plus image billed tokens."""
        return int(self.write.total_tokens) + int(self.image.total_tokens)

    @property
    def write_tokens(self) -> int:
        """Billed tokens for the search-then-write lane."""
        return int(self.write.total_tokens)

    @property
    def image_tokens(self) -> int:
        """Billed tokens for the parallel image-search lane."""
        return int(self.image.total_tokens)

    def observe(self, chunk: Mapping[str, Any]) -> None:
        """Fold one generator event into the running totals."""
        event = str(chunk.get("event") or "")
        if event == "status" and str(chunk.get("phase") or "") == "searching":
            self.searches += 1
            self._remember_query(chunk.get("query"))
            return
        if event == "search_source":
            sources = chunk.get("sources")
            if isinstance(sources, list):
                self.sources += len(sources)
            self._remember_query(chunk.get("query"))
            return
        if event == "image":
            images = chunk.get("images")
            if isinstance(images, list):
                self.images += len(images)
            else:
                self.images += 1
            return
        if event == "usage":
            self._observe_usage(chunk)

    def _remember_query(self, raw: Any) -> None:
        query = str(raw or "").strip()
        if query and query not in self.queries:
            self.queries.append(query)

    def _observe_usage(self, chunk: Mapping[str, Any]) -> None:
        usage = chunk.get("usage")
        if not isinstance(usage, Mapping):
            return
        input_tokens = _as_token_count(usage.get("input_tokens") or usage.get("prompt_tokens"))
        output_tokens = _as_token_count(usage.get("output_tokens") or usage.get("completion_tokens"))
        total = _as_token_count(usage.get("total_tokens"))
        if total <= 0:
            total = input_tokens + output_tokens
        lane = str(chunk.get("lane") or "write")
        target = self.image if lane == "image" else self.write
        target.add(input_tokens, output_tokens, total)


@dataclass(frozen=True)
class ExplainActivityContext:
    """Identity + node fields for a completion tracker write."""

    user: Optional[User]
    request: Optional[HttpOrWebSocket]
    diagram_type: str
    diagram_id: Optional[str]
    session_id: str
    facet: str
    node_label: str
    topic: str


def log_explain_complete(
    *,
    session_short: str,
    facet: str,
    node_label: str,
    chunk_count: int,
    stats: ExplainStreamStats,
    success: bool,
    extra: str = "",
) -> None:
    """INFO line with related-activity counts and token totals."""
    node = clip_activity_preview(node_label, max_len=24) or "-"
    outcome = "complete" if success else "failed"
    extra_text = f" {extra}" if extra else ""
    logger.info(
        "%s Stream %s | session=%s facet=%s node=%s chunks=%d "
        "searches=%d sources=%d images=%d tokens=%d "
        "write=%d/%d/%d image=%d/%d/%d%s",
        _LOG_PREFIX,
        outcome,
        session_short,
        facet,
        node,
        chunk_count,
        stats.searches,
        stats.sources,
        stats.images,
        stats.total_tokens,
        stats.write.input_tokens,
        stats.write.output_tokens,
        stats.write.total_tokens,
        stats.image.input_tokens,
        stats.image.output_tokens,
        stats.image.total_tokens,
        extra_text,
    )


def schedule_explain_completion_activity(
    ctx: ExplainActivityContext,
    stats: ExplainStreamStats,
    *,
    success: bool,
) -> None:
    """Redis tracker + usage timeline with token counts (no gloss text)."""
    if ctx.user is None or not hasattr(ctx.user, "id"):
        return
    queries = ", ".join(stats.queries[:4])
    node = (ctx.node_label or "").strip()
    schedule_module_activity(
        user=ctx.user,
        module="canvas",
        redis_activity_type="mindmap_node_explain",
        request=ctx.request,
        details={
            "diagram_type": ctx.diagram_type,
            "session_id": ctx.session_id,
            "facet": ctx.facet,
            "node_label": node[:80],
            "searches": stats.searches,
            "sources": stats.sources,
            "images": stats.images,
            "write_tokens": stats.write_tokens,
            "image_tokens": stats.image_tokens,
            "total_tokens": stats.total_tokens,
            "queries": queries,
        },
        detail=(
            f"{ctx.facet} node={node[:24]} tokens={stats.total_tokens} search={stats.searches} images={stats.images}"
        ),
        usage_source="mindgraph",
        usage_action="mindmap_node_explain",
        title=node or ctx.facet,
        prompt_preview=(ctx.topic or node)[:120],
        diagram_type=ctx.diagram_type,
        diagram_id=ctx.diagram_id,
        conversation_id=ctx.session_id,
        total_tokens=stats.total_tokens or None,
        success=success,
        persist_usage=True,
    )
