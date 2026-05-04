"""
Best-effort persistence of Redis live workshop specs during process shutdown.

Scans ``workshop:live_spec:*`` and flushes each distinct workshop code to
PostgreSQL while the async engine is still open.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import List, Set

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis
from services.online_collab.redis.online_collab_redis_keys import (
    code_to_diagram_key,
    live_last_db_flush_key,
    room_last_collab_activity_key,
)
from services.online_collab.spec.online_collab_live_flush import (
    LIVE_FLUSH_MAX_INTERVAL_SEC,
)
from services.online_collab.spec.online_collab_live_spec_ops import (
    flush_live_spec_to_db,
)

logger = logging.getLogger(__name__)

_LIVE_SPEC_PREFIX = "workshop:live_spec:"
_STALE_LAG_MULT = 3
_STALE_HEALTH_MAX_KEYS = 80


def workshop_code_from_live_spec_key(raw: str | bytes) -> str | None:
    """
    Parse workshop ``code`` from a Redis key ``workshop:live_spec:{code}``.

    Supports cluster hash-tag form ``workshop:live_spec:{ABC}`` and plain
    ``workshop:live_spec:ABC``.
    """
    key = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    if not key.startswith(_LIVE_SPEC_PREFIX):
        return None
    rest = key[len(_LIVE_SPEC_PREFIX) :]
    if len(rest) >= 2 and rest[0] == "{" and rest[-1] == "}":
        rest = rest[1:-1]
    return rest or None


async def flush_all_live_specs_on_shutdown(
    *,
    max_concurrency: int = 8,
    scan_count: int = 128,
) -> int:
    """
    Flush every live spec found in Redis to Postgres (best-effort).

    Returns the number of ``flush_live_spec_to_db`` calls attempted (including
    failures); skips codes with no ``code_to_diagram`` mapping.
    """
    redis = get_async_redis()
    if redis is None:
        return 0

    try:
        parsed_max = int(os.environ.get("LIVE_SPEC_SHUTDOWN_FLUSH_CONCURRENCY", ""))
    except ValueError:
        parsed_max = 0
    if parsed_max > 0:
        max_concurrency = max(1, min(parsed_max, 64))

    seen: Set[str] = set()
    attempts = 0
    count_lock = asyncio.Lock()
    sem = asyncio.Semaphore(max_concurrency)

    async def _maybe_flush(code: str) -> None:
        nonlocal attempts
        try:
            raw_did = await redis.get(code_to_diagram_key(code))
        except (RedisError, OSError, RuntimeError, TypeError) as exc:
            logger.debug("[LiveSpec] shutdown: diagram id read failed code=%s: %s", code, exc)
            return
        if not raw_did:
            return
        diagram_id = raw_did if isinstance(raw_did, str) else raw_did.decode("utf-8")
        async with sem:
            async with count_lock:
                attempts += 1
            try:
                await flush_live_spec_to_db(code, diagram_id)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "[LiveSpec] shutdown flush failed code=%s diagram=%s: %s",
                    code,
                    diagram_id,
                    exc,
                )

    tasks: List[asyncio.Task[None]] = []
    try:
        async for raw_key in redis.scan_iter(
            match=f"{_LIVE_SPEC_PREFIX}*",
            count=scan_count,
        ):
            code = workshop_code_from_live_spec_key(raw_key)
            if code is None or code in seen:
                continue
            seen.add(code)
            tasks.append(asyncio.create_task(_maybe_flush(code)))
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.warning("[LiveSpec] shutdown scan failed: %s", exc)
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return attempts

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    if seen:
        logger.info(
            "[LiveSpec] shutdown: flushed live_spec scan distinct_codes=%s attempts=%s",
            len(seen),
            attempts,
        )
    return attempts


async def collab_live_spec_durability_alerts() -> list[str]:
    """
    Sample Redis for rooms where last collaborative activity is ahead of DB flush.

    Intended for log-based alerting on ``/health/websocket``: returns tokens
    such as ``live_spec_db_flush_lag_detected`` when any sampled room looks
    dangerously far behind (configuration / Redis issues).
    """
    redis = get_async_redis()
    if redis is None:
        return []

    lag_seconds = LIVE_FLUSH_MAX_INTERVAL_SEC * _STALE_LAG_MULT
    max_sample = _STALE_HEALTH_MAX_KEYS
    try:
        env_sample = int(os.environ.get("LIVE_SPEC_HEALTH_STALE_SAMPLE", ""))
    except ValueError:
        env_sample = 0
    if env_sample > 0:
        max_sample = max(10, min(env_sample, 500))

    examined = 0
    try:
        async for raw_key in redis.scan_iter(
            match=f"{_LIVE_SPEC_PREFIX}*",
            count=64,
        ):
            if examined >= max_sample:
                break
            code = workshop_code_from_live_spec_key(raw_key)
            if code is None:
                continue
            examined += 1
            try:
                async with redis.pipeline(transaction=False) as pipe:
                    pipe.get(room_last_collab_activity_key(code))
                    pipe.get(live_last_db_flush_key(code))
                    collab_raw, flush_raw = await pipe.execute()
            except (RedisError, OSError, RuntimeError, TypeError) as exc:
                logger.debug("[LiveSpec] health stale sample failed code=%s: %s", code, exc)
                continue

            if not collab_raw:
                continue
            try:
                collab_ts = float(
                    collab_raw if isinstance(collab_raw, str) else collab_raw.decode("utf-8")
                )
            except (TypeError, ValueError):
                continue
            flush_ts = 0.0
            if flush_raw is not None:
                try:
                    flush_ts = float(
                        flush_raw if isinstance(flush_raw, str) else flush_raw.decode("utf-8")
                    )
                except (TypeError, ValueError):
                    flush_ts = 0.0
            if collab_ts > flush_ts and (time.time() - flush_ts) > lag_seconds:
                return ["live_spec_db_flush_lag_detected"]
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.debug("[LiveSpec] durability alert scan failed: %s", exc)

    return []
