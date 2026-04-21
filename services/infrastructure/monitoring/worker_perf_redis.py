"""Redis storage for per-uvicorn-worker performance snapshots (admin merge).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

WORKER_PERF_KEY_PREFIX = "mg:admin:perf:worker:"
WORKER_PERF_SCAN_MATCH = f"{WORKER_PERF_KEY_PREFIX}*"


async def store_worker_perf_snapshot(payload: Dict[str, Any], ttl_seconds: int) -> None:
    """Persist one worker JSON blob (SETEX)."""
    pid = payload.get("pid")
    if not isinstance(pid, int):
        return
    redis_client = get_async_redis()
    if redis_client is None:
        return
    key = f"{WORKER_PERF_KEY_PREFIX}{pid}"
    try:
        raw = json.dumps(payload, separators=(",", ":"), default=str)
        await redis_client.set(key, raw, ex=int(ttl_seconds))
    except (TypeError, ValueError, OSError, RuntimeError) as exc:
        logger.debug("[WorkerPerf] store failed: %s", exc)


async def load_all_worker_perf_snapshots() -> List[Dict[str, Any]]:
    """Load all recently published worker snapshots (SCAN + GET)."""
    redis_client = get_async_redis()
    if redis_client is None:
        return []
    rows: List[Dict[str, Any]] = []
    try:
        async for key in redis_client.scan_iter(match=WORKER_PERF_SCAN_MATCH, count=32):
            raw = await redis_client.get(key)
            if raw is None:
                continue
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.debug("[WorkerPerf] load_all failed: %s", exc)
    return rows
