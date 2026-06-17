"""Per-session asyncio event bus for Kitty voice."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Literal, Optional

logger = logging.getLogger(__name__)

KittyEventKind = Literal[
    "transcription",
    "text_inbound",
    "diagram_mutated",
    "assistant_text",
    "assistant_done",
    "context_update",
    "function_call",
    "image_paragraph",
    "stop",
]

KittyEventHandler = Callable[["KittyEvent"], Awaitable[None]]


@dataclass(slots=True)
class KittyEvent:
    """Single event on the per-session Kitty bus."""

    kind: KittyEventKind
    voice_session_id: str
    payload: Dict[str, Any] = field(default_factory=dict)


class SessionEventBus:
    """One ``asyncio.Queue`` per voice session with a single consumer task."""

    def __init__(self, voice_session_id: str, *, maxsize: int = 64) -> None:
        """init  ."""
        self.voice_session_id = voice_session_id
        self._queue: asyncio.Queue[KittyEvent] = asyncio.Queue(maxsize=maxsize)
        self._consumer_task: Optional[asyncio.Task] = None
        self._handlers: list[KittyEventHandler] = []
        self._closed = False

    def add_handler(self, handler: KittyEventHandler) -> None:
        """Add handler."""
        self._handlers.append(handler)

    async def emit(self, event: KittyEvent) -> None:
        """Emit."""
        if self._closed:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Kitty event queue full for session %s; dropping oldest",
                self.voice_session_id,
            )
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            await self._queue.put(event)

    async def start(self) -> None:
        """Start."""
        if self._consumer_task is not None:
            return
        self._consumer_task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Stop."""
        self._closed = True
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        await self.emit(KittyEvent(kind="stop", voice_session_id=self.voice_session_id, payload={}))

    async def _consume_loop(self) -> None:
        """Consume loop."""
        while not self._closed:
            event = await self._queue.get()
            if event.kind == "stop":
                break
            for handler in self._handlers:
                try:
                    await handler(event)
                except (RuntimeError, ValueError, KeyError, AttributeError, TypeError, OSError) as exc:
                    logger.error(
                        "Kitty event handler error kind=%s session=%s: %s",
                        event.kind,
                        self.voice_session_id,
                        exc,
                        exc_info=True,
                    )


_buses: Dict[str, SessionEventBus] = {}


def get_session_event_bus(voice_session_id: str) -> SessionEventBus:
    """Get session event bus."""
    bus = _buses.get(voice_session_id)
    if bus is None:
        bus = SessionEventBus(voice_session_id)
        _buses[voice_session_id] = bus
    return bus


def remove_session_event_bus(voice_session_id: str) -> None:
    """Remove session event bus."""
    _buses.pop(voice_session_id, None)


async def emit_kitty_session_event(
    voice_session_id: str,
    kind: KittyEventKind,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Enqueue one event on the session bus (no-op if bus was torn down)."""
    bus = _buses.get(voice_session_id)
    if bus is None:
        return
    await bus.emit(
        KittyEvent(
            kind=kind,
            voice_session_id=voice_session_id,
            payload=dict(payload) if payload else {},
        )
    )


async def emit_diagram_mutated(
    voice_session_id: str,
    *,
    action: str,
    delta: Optional[str] = None,
) -> None:
    """Notify the session bus that diagram state changed (handler schedules Omni refresh)."""
    await emit_kitty_session_event(
        voice_session_id,
        "diagram_mutated",
        {"action": action, "delta": delta or action},
    )
