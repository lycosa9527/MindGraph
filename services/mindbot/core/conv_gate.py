"""Redis single-flight gate: first callback binds Dify conversation per DingTalk chat.

Sentinel design
---------------
When the gate is acquired, ``CONV_GATE_SENTINEL`` is written to ``conv_key``
immediately.  Second-arrival messages that poll for ``conv_key`` skip the sentinel
value and keep waiting — this ensures they do not use ``"__pending__"`` as a Dify
conversation ID.  When the first-arrival message succeeds, the real conversation ID
overwrites the sentinel.  If the first-arrival fails (Dify error, timeout, etc.) the
gate is released; the sentinel remains but is ignored by subsequent pollers.

Exponential backoff
-------------------
``poll_dify_conv_key_async`` starts at ``step_initial_ms`` and doubles on every miss
(capped at ``POLL_STEP_MAX_MS``).  This drastically reduces Redis GET traffic compared
to a fixed 50 ms step — at most ~8 calls over a 3-second window vs up to 60.
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Awaitable, Callable, Optional

from services.mindbot.infra.redis_async import redis_delete, redis_set_ttl, redis_setnx_ttl
from utils.env_helpers import env_bool, env_int

CONV_GATE_PREFIX = "mindbot:conv_gate:"
CONV_GATE_SENTINEL = "__pending__"

_DEFAULT_GATE_TTL = 120
# Dify median first-token latency under load is ~12–20 s; 30 s covers the
# common case without permanently blocking follow-up messages.  Override via
# MINDBOT_CONV_GATE_POLL_MS.
_DEFAULT_POLL_TOTAL_MS = 30000
_DEFAULT_POLL_STEP_INITIAL_MS = 50
_POLL_STEP_MAX_MS = 400


@functools.cache
def _conv_gate_ttl_seconds() -> int:
    return max(30, min(600, env_int("MINDBOT_CONV_GATE_TTL_SECONDS", _DEFAULT_GATE_TTL)))


@functools.cache
def _conv_gate_poll_total_ms() -> int:
    return max(100, min(120_000, env_int("MINDBOT_CONV_GATE_POLL_MS", _DEFAULT_POLL_TOTAL_MS)))


@functools.cache
def _conv_gate_poll_step_initial_ms() -> int:
    return max(10, min(500, env_int("MINDBOT_CONV_GATE_POLL_STEP_MS", _DEFAULT_POLL_STEP_INITIAL_MS)))


def conv_gate_ttl_seconds() -> int:
    return _conv_gate_ttl_seconds()


def conv_gate_poll_total_ms() -> int:
    return _conv_gate_poll_total_ms()


def conv_gate_poll_step_ms() -> int:
    return _conv_gate_poll_step_initial_ms()


def conv_gate_enabled() -> bool:
    return env_bool("MINDBOT_CONV_GATE_ENABLED", True)


def normalize_dify_conversation_id_from_redis(val: Optional[str]) -> Optional[str]:
    """
    Map Redis conv binding to a value safe to pass to Dify.

    While the first in-flight message holds the conv gate, ``conv_key`` may hold
    ``CONV_GATE_SENTINEL``. That string must not be sent as ``conversation_id``
    (Dify validates UUIDs). Empty or whitespace-only values are treated as missing.
    """
    if val is None:
        return None
    if not isinstance(val, str):
        return None
    stripped = val.strip()
    if not stripped or stripped == CONV_GATE_SENTINEL:
        return None
    return stripped


def gate_key_for(org_id: int, dingtalk_conversation_id: str) -> str:
    return f"{CONV_GATE_PREFIX}{org_id}:{dingtalk_conversation_id}"


async def redis_acquire_conv_gate_async(
    org_id: int,
    dingtalk_conversation_id: str,
    *,
    conv_key: Optional[str] = None,
) -> bool:
    """
    Return True if this process holds the gate (SET NX won).

    When ``conv_key`` is supplied and the gate is acquired, writes
    ``CONV_GATE_SENTINEL`` to ``conv_key`` so that second-arrival pollers know a
    binding is in progress and do not time out immediately.  The sentinel is
    overwritten by the real Dify conversation ID once the first-arrival message
    completes successfully.
    """
    key = gate_key_for(org_id, dingtalk_conversation_id)
    ttl = conv_gate_ttl_seconds()
    result = await redis_setnx_ttl(key, "1", ttl)
    won = result is True
    if won and conv_key:
        sentinel_ok = await redis_set_ttl(conv_key, CONV_GATE_SENTINEL, ttl)
        if not sentinel_ok:
            await redis_delete(key)
            return False
    return won


async def redis_release_conv_gate_async(org_id: int, dingtalk_conversation_id: str) -> None:
    key = gate_key_for(org_id, dingtalk_conversation_id)
    await redis_delete(key)


async def poll_dify_conv_key_async(
    redis_get_async: Callable[[str], Awaitable[Optional[str]]],
    conv_key: str,
) -> Optional[str]:
    """
    Wait until ``conv_key`` holds a real Dify conversation ID or poll budget expires.

    Skips ``CONV_GATE_SENTINEL`` values — those indicate the first-arrival message is
    still running but has not yet received a conversation ID from Dify.

    Uses exponential backoff starting at the configured initial step (default 50 ms),
    doubling each miss up to ``_POLL_STEP_MAX_MS`` (400 ms).  This keeps Redis GET
    traffic low: at most ~8 calls over a 3-second window vs up to 60 with a fixed step.

    ``redis_get_async`` is ``_redis_get_async`` from the callback module (injected for tests).
    """
    total_ms = conv_gate_poll_total_ms()
    step_ms = float(_conv_gate_poll_step_initial_ms())
    deadline = time.monotonic() + total_ms / 1000.0
    while time.monotonic() < deadline:
        val = await redis_get_async(conv_key)
        if isinstance(val, str) and val.strip() and val.strip() != CONV_GATE_SENTINEL:
            return val.strip()
        remaining_ms = (deadline - time.monotonic()) * 1000.0
        sleep_ms = min(step_ms, remaining_ms, _POLL_STEP_MAX_MS)
        if sleep_ms <= 0:
            break
        await asyncio.sleep(sleep_ms / 1000.0)
        step_ms = min(step_ms * 2.0, _POLL_STEP_MAX_MS)
    return None
