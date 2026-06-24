"""
Typed events for the diagram generation pipeline.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

GenerateGraphEventName = Literal[
    "accepted",
    "detecting",
    "requirements",
    "progress",
    "waiting",
    "streaming",
    "complete",
    "error",
]

LegacyPhaseName = Literal["accepted", "waiting", "streaming", "requirements"]


EventEmitter = Callable[["GenerateGraphEvent"], Awaitable[None]]
PhaseEmitter = Callable[[str], Awaitable[None]]


@dataclass
class GenerateGraphEvent:
    """Single event emitted during diagram generation."""

    event: GenerateGraphEventName
    model: Optional[str] = None
    topic: Optional[str] = None
    diagram_type: Optional[str] = None
    message: Optional[str] = None
    error_type: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_sse_dict(self) -> dict[str, Any]:
        """Serialize for SSE/JSON consumers."""
        data = asdict(self)
        extra = data.pop("extra", None) or {}
        payload = data.pop("payload", None)
        out = {key: value for key, value in data.items() if value is not None}
        out.update(extra)
        if payload is not None:
            out.update(payload)
        return out


def event_emitter_from_phase_emitter(phase_emit: PhaseEmitter | None) -> EventEmitter | None:
    """Adapt legacy string phase emitter to typed events."""
    if phase_emit is None:
        return None

    async def emit(event: GenerateGraphEvent) -> None:
        if event.event in ("waiting", "streaming", "requirements"):
            await phase_emit(event.event)

    return emit


def phase_emitter_from_event_emitter(event_emit: EventEmitter | None) -> PhaseEmitter | None:
    """Adapt typed event emitter for agents using legacy phase strings."""
    if event_emit is None:
        return None

    async def phase_emit(phase: str) -> None:
        if phase in ("waiting", "streaming", "requirements"):
            await event_emit(GenerateGraphEvent(event=phase))

    return phase_emit


async def emit_progress(
    event_emit: EventEmitter | None,
    *,
    topic: str,
    diagram_type: str,
    model: str | None = None,
) -> None:
    """Emit progress metadata for UI topic/diagram-type toasts."""
    if event_emit is None:
        return
    await event_emit(
        GenerateGraphEvent(
            event="progress",
            topic=topic,
            diagram_type=diagram_type,
            model=model,
        )
    )
