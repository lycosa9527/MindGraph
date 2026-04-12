"""Redis single-flight gate: first callback binds Dify conversation per DingTalk chat."""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional

from services.redis.redis_client import RedisOperations, is_redis_available
from utils.env_helpers import env_bool, env_int

CONV_GATE_PREFIX = "mindbot:conv_gate:"
_DEFAULT_GATE_TTL = 120
_DEFAULT_POLL_TOTAL_MS = 3000
_DEFAULT_POLL_STEP_MS = 50


def conv_gate_ttl_seconds() -> int:
    return max(30, min(600, env_int("MINDBOT_CONV_GATE_TTL_SECONDS", _DEFAULT_GATE_TTL)))


def conv_gate_poll_total_ms() -> int:
    return max(100, min(120_000, env_int("MINDBOT_CONV_GATE_POLL_MS", _DEFAULT_POLL_TOTAL_MS)))


def conv_gate_poll_step_ms() -> int:
    return max(10, min(500, env_int("MINDBOT_CONV_GATE_POLL_STEP_MS", _DEFAULT_POLL_STEP_MS)))


def conv_gate_enabled() -> bool:
    return env_bool("MINDBOT_CONV_GATE_ENABLED", True)


def gate_key_for(org_id: int, dingtalk_conversation_id: str) -> str:
    return f"{CONV_GATE_PREFIX}{org_id}:{dingtalk_conversation_id}"


async def redis_acquire_conv_gate_async(org_id: int, dingtalk_conversation_id: str) -> bool:
    """Return True if this process holds the gate (SET NX won)."""
    if not is_redis_available():
        return False
    key = gate_key_for(org_id, dingtalk_conversation_id)
    ttl = conv_gate_ttl_seconds()
    return await asyncio.to_thread(
        RedisOperations.set_with_ttl_if_not_exists,
        key,
        "1",
        ttl,
    )


async def redis_release_conv_gate_async(org_id: int, dingtalk_conversation_id: str) -> None:
    if not is_redis_available():
        return
    key = gate_key_for(org_id, dingtalk_conversation_id)
    await asyncio.to_thread(RedisOperations.delete, key)


async def poll_dify_conv_key_async(
    redis_get_async: Callable[[str], Awaitable[Optional[str]]],
    conv_key: str,
) -> Optional[str]:
    """
    Wait until ``conv_key`` appears or poll budget expires.

    ``redis_get_async`` is ``_redis_get_async`` from the callback module (injected for tests).
    """
    total_ms = conv_gate_poll_total_ms()
    step_ms = conv_gate_poll_step_ms()
    deadline = time.monotonic() + total_ms / 1000.0
    while time.monotonic() < deadline:
        val = await redis_get_async(conv_key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        await asyncio.sleep(step_ms / 1000.0)
    return None
