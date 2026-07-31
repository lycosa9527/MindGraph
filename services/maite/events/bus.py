"""
Per-session asyncio event bus for Maite learning sessions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

from services.infrastructure.http.error_handler import LLMServiceError
from services.maite.events.kinds import MaiteEventKind
from services.utils.error_types import DATABASE_ERRORS, LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

MaiteEventHandler = Callable[["MaiteEvent"], Awaitable[None]]


@dataclass(slots=True)
class MaiteEvent:
    """Single event on the per-session Maite bus."""

    kind: MaiteEventKind
    session_key: str
    payload: Dict[str, Any] = field(default_factory=dict)


class MaiteSessionEventBus:
    """One ``asyncio.Queue`` per Maite session with a single consumer task."""

    def __init__(self, session_key: str, *, maxsize: int = 64) -> None:
        self.session_key = session_key
        self._queue: asyncio.Queue[MaiteEvent] = asyncio.Queue(maxsize=maxsize)
        self._consumer_task: Optional[asyncio.Task[None]] = None
        self._handlers: list[MaiteEventHandler] = []
        self._closed = False

    def add_handler(self, handler: MaiteEventHandler) -> None:
        """Register an async handler invoked for each emitted event."""
        self._handlers.append(handler)

    async def emit(self, event: MaiteEvent) -> None:
        """Enqueue an event; drop oldest when the queue is full."""
        if self._closed:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Maite event queue full for session %s; dropping oldest",
                self.session_key,
            )
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            await self._queue.put(event)

    async def start(self) -> None:
        """Start the background consumer loop."""
        if self._consumer_task is not None:
            return
        self._consumer_task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Stop the consumer and emit a terminal ``stop`` event."""
        self._closed = True
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        await self.emit(MaiteEvent(kind="stop", session_key=self.session_key, payload={}))

    async def _consume_loop(self) -> None:
        while not self._closed:
            event = await self._queue.get()
            if event.kind == "stop":
                break
            for handler in self._handlers:
                try:
                    await handler(event)
                except (
                    *DATABASE_ERRORS,
                    *LLM_PIPELINE_ERRORS,
                    LLMServiceError,
                    RuntimeError,
                    ValueError,
                    KeyError,
                    AttributeError,
                    TypeError,
                    OSError,
                ) as exc:
                    logger.error(
                        "Maite event handler error kind=%s session=%s: %s",
                        event.kind,
                        self.session_key,
                        exc,
                        exc_info=True,
                    )


_buses: Dict[str, MaiteSessionEventBus] = {}


def get_maite_session_event_bus(session_key: str) -> MaiteSessionEventBus:
    """Return or create the event bus for ``session_key``."""
    bus = _buses.get(session_key)
    if bus is None:
        bus = MaiteSessionEventBus(session_key)
        _buses[session_key] = bus
    return bus


def remove_maite_session_event_bus(session_key: str) -> None:
    """Remove a session bus from the registry."""
    _buses.pop(session_key, None)


async def emit_maite_session_event(
    session_key: str,
    kind: MaiteEventKind,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Enqueue one event on the session bus (no-op if bus was torn down)."""
    bus = _buses.get(session_key)
    if bus is None:
        return
    await bus.emit(
        MaiteEvent(
            kind=kind,
            session_key=session_key,
            payload=dict(payload) if payload else {},
        )
    )
