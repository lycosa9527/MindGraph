"""Background publish of per-worker metrics to Redis for admin performance merge.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging

from redis.exceptions import RedisError

from routers.auth.admin.performance import build_worker_perf_payload_async
from services.infrastructure.monitoring.worker_perf_redis import store_worker_perf_snapshot
from services.redis.redis_client import is_redis_available

logger = logging.getLogger(__name__)

_INTERVAL_S = 4.0
_TTL_S = 14


async def _build_and_store() -> None:
    if not is_redis_available():
        return
    try:
        payload = await build_worker_perf_payload_async()
        await store_worker_perf_snapshot(payload, _TTL_S)
    except (
        TypeError,
        ValueError,
        OSError,
        RuntimeError,
        asyncio.TimeoutError,
        ConnectionError,
        RedisError,
    ) as exc:
        logger.debug("[WorkerPerf] heartbeat tick failed: %s", exc)


async def run_worker_perf_heartbeat(stop: asyncio.Event) -> None:
    """Loop until ``stop`` is set; tolerates Redis outages."""
    while not stop.is_set():
        await _build_and_store()
        try:
            await asyncio.wait_for(stop.wait(), timeout=_INTERVAL_S)
        except asyncio.TimeoutError:
            pass


def start_worker_perf_heartbeat() -> tuple[asyncio.Task[None], asyncio.Event]:
    """Return (task, stop_event). Set the event and cancel the task on shutdown."""
    stop = asyncio.Event()
    task = asyncio.create_task(run_worker_perf_heartbeat(stop), name="worker_perf_heartbeat")
    return task, stop
