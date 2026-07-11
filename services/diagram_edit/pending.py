"""Pending mutation ack registry (mutation_id → asyncio.Future).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.diagram_edit.types import ToolResult


@dataclass(slots=True)
class MutationAckPayload:
    """Inbound ack from owning canvas."""

    mutation_id: str
    verified: bool
    revision: Optional[int] = None
    hub_revision: Optional[int] = None
    hub_persist_ok: Optional[bool] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    created_node_ids: Optional[list[str]] = None


@dataclass(slots=True)
class _PendingEntry:
    future: asyncio.Future
    created_at: float
    voice_session_id: str
    idempotency_key: Optional[str]


_pending: Dict[str, _PendingEntry] = {}
_idempotency_cache: Dict[str, ToolResult] = {}


def new_mutation_id() -> str:
    """Generate a unique mutation id."""
    return str(uuid.uuid4())


def register_pending(
    mutation_id: str,
    voice_session_id: str,
    *,
    idempotency_key: Optional[str] = None,
) -> asyncio.Future:
    """Register a pending ack future for mutation_id."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _pending[mutation_id] = _PendingEntry(
        future=fut,
        created_at=time.monotonic(),
        voice_session_id=voice_session_id,
        idempotency_key=idempotency_key,
    )
    return fut


def get_cached_result(idempotency_key: str) -> Optional[ToolResult]:
    """Return cached ToolResult for idempotent retry."""
    return _idempotency_cache.get(idempotency_key)


def cache_result(idempotency_key: str, result: ToolResult) -> None:
    """Cache ToolResult for idempotent retry."""
    _idempotency_cache[idempotency_key] = result


def complete_pending(ack: MutationAckPayload) -> bool:
    """
    Complete a pending future from inbound ack.

    Returns True when the ack matched a pending entry; late acks are ignored.
    """
    entry = _pending.pop(ack.mutation_id, None)
    if entry is None:
        return False
    if entry.future.done():
        return False
    entry.future.set_result(ack)
    return True


async def wait_for_ack(
    mutation_id: str,
    *,
    timeout_sec: float = 8.0,
) -> Optional[MutationAckPayload]:
    """Await verified ack or return None on timeout."""
    entry = _pending.get(mutation_id)
    if entry is None:
        return None
    try:
        result = await asyncio.wait_for(entry.future, timeout=timeout_sec)
        return result if isinstance(result, MutationAckPayload) else None
    except asyncio.TimeoutError:
        _pending.pop(mutation_id, None)
        if not entry.future.done():
            entry.future.cancel()
        return None


def clear_pending_for_session(voice_session_id: str) -> None:
    """Cancel pending acks when a voice session ends."""
    to_remove = [mid for mid, ent in _pending.items() if ent.voice_session_id == voice_session_id]
    for mid in to_remove:
        entry = _pending.pop(mid, None)
        if entry is not None and not entry.future.done():
            entry.future.cancel()


def reset_pending_state_for_tests() -> None:
    """Clear all pending state (tests only)."""
    for entry in _pending.values():
        if not entry.future.done():
            entry.future.cancel()
    _pending.clear()
    _idempotency_cache.clear()
