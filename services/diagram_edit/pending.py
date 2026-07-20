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
    scope: Optional[str]


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
    scope: Optional[str] = None,
) -> asyncio.Future:
    """Register a pending ack future for mutation_id."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    scope_key = scope.strip() if isinstance(scope, str) and scope.strip() else None
    _pending[mutation_id] = _PendingEntry(
        future=fut,
        created_at=time.monotonic(),
        voice_session_id=voice_session_id,
        idempotency_key=idempotency_key,
        scope=scope_key,
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


def fail_pending_for_scope(
    scope: str,
    *,
    error_code: str = "no_owner",
    message: str = "Desktop canvas owner disconnected",
) -> int:
    """Fail pending acks for ``scope`` when the canvas owner drops mid-flight.

    Completes waiters with a verified=False ack so mobile fails fast with
    ``no_owner`` instead of waiting for ``ack_timeout``.
    """
    want = scope.strip() if isinstance(scope, str) else ""
    if not want:
        return 0
    matched = 0
    for mid, ent in list(_pending.items()):
        if ent.scope != want:
            continue
        if complete_pending(
            MutationAckPayload(
                mutation_id=mid,
                verified=False,
                error_code=error_code,
                message=message,
            )
        ):
            matched += 1
    return matched


def clear_pending_for_session(voice_session_id: str) -> None:
    """Fail pending acks when a voice session ends (no cancel — waiters get a result)."""
    to_remove = [mid for mid, ent in _pending.items() if ent.voice_session_id == voice_session_id]
    for mid in to_remove:
        complete_pending(
            MutationAckPayload(
                mutation_id=mid,
                verified=False,
                error_code="no_owner",
                message="Voice session ended before canvas ack",
            )
        )


def detach_pending_for_tests(mutation_id: str) -> Optional[asyncio.Future]:
    """
    Remove a pending entry without completing it (multi-worker test isolation).

    Returns the future so the test can reattach via ``reattach_pending_for_tests``.
    """
    entry = _pending.pop(mutation_id, None)
    if entry is None:
        return None
    return entry.future


def reattach_pending_for_tests(
    mutation_id: str,
    future: asyncio.Future,
    *,
    voice_session_id: str = "test",
) -> None:
    """Restore a previously detached pending future (multi-worker tests)."""
    _pending[mutation_id] = _PendingEntry(
        future=future,
        created_at=time.monotonic(),
        voice_session_id=voice_session_id,
        idempotency_key=None,
        scope=None,
    )


def reset_pending_state_for_tests() -> None:
    """Clear all pending state (tests only)."""
    for entry in _pending.values():
        if not entry.future.done():
            entry.future.cancel()
    _pending.clear()
    _idempotency_cache.clear()
