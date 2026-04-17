"""Redis token buffer module.

Shared token usage buffer using Redis Streams. Collects token usage records
from all workers and flushes to database periodically. Features: shared stream
across all workers (no data loss on worker crash), consumer-group delivery for
at-least-once processing, periodic batch flush to database, graceful fallback
to per-worker memory buffer. Key schema: tokens:stream -> Redis Stream,
tokens:stats -> hash of total_written, total_dropped, batches.
"""

from datetime import UTC, datetime
from typing import Optional, Dict, Any, List, Tuple
import asyncio
import logging
import os
import threading
import time

import orjson
from redis.exceptions import ResponseError as RedisResponseError
from sqlalchemy import insert as sa_insert

from config.database import AsyncSessionLocal, check_disk_space
from models.domain.token_usage import TokenUsage
from services.redis import keys as _keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import _RedisCapabilities, is_redis_available
from services.teacher_usage_stats import compute_and_upsert_user_usage_stats_async

logger = logging.getLogger(__name__)

# Redis keys sourced from central registry.
STREAM_KEY = _keys.TOKENS_STREAM
STATS_KEY = _keys.TOKENS_STATS
CONSUMER_GROUP = "token_flush_workers"
CONSUMER_NAME = f"worker_{os.getpid()}"

# Configuration from environment
BATCH_SIZE = int(os.getenv("TOKEN_TRACKER_BATCH_SIZE", "1000"))
BATCH_INTERVAL = float(os.getenv("TOKEN_TRACKER_BATCH_INTERVAL", "300"))  # 5 minutes
MAX_BUFFER_SIZE = int(os.getenv("TOKEN_TRACKER_MAX_BUFFER_SIZE", "10000"))
WORKER_CHECK_INTERVAL = 30.0  # Check every 30 seconds
# Stream entries delivered more than this many times are considered poison pills
# and are acknowledged + dropped to prevent infinite retry loops.
MAX_STREAM_DELIVERY_COUNT = int(os.getenv("TOKEN_TRACKER_MAX_DELIVERY_COUNT", "5"))
# Hard cap on the underlying Redis Stream so a long DB outage cannot grow Redis
# memory unbounded. ``MAXLEN ~`` (approximate trimming) keeps the cost O(1).
STREAM_HARD_CAP = MAX_BUFFER_SIZE * 5


class RedisTokenBuffer:
    """
    Redis-based token usage buffer.

    Collects token usage records in Redis (shared across all workers)
    and flushes them to database in batches for persistent storage.

    This solves the per-worker buffer problem where worker crashes
    could lose buffered data.
    """

    # Model pricing (per 1M tokens in CNY)
    MODEL_PRICING = {
        "qwen": {"input": 0.4, "output": 1.2, "provider": "dashscope"},
        "qwen-turbo": {"input": 0.3, "output": 0.6, "provider": "dashscope"},
        "qwen-plus": {"input": 0.4, "output": 1.2, "provider": "dashscope"},
        "deepseek": {"input": 0.4, "output": 2.0, "provider": "dashscope"},
        "kimi": {"input": 2.0, "output": 6.0, "provider": "dashscope"},
        "hunyuan": {"input": 0.45, "output": 0.5, "provider": "tencent"},
        "doubao": {"input": 0.8, "output": 2.0, "provider": "volcengine"},
        # Dify MindMate - uses Dify's hosted models (pricing estimated based on typical usage)
        "dify": {"input": 0.5, "output": 1.5, "provider": "dify"},
    }

    # Model name mapping
    MODEL_NAME_MAP = {
        "qwen": "qwen-plus-latest",
        "qwen-turbo": "qwen-turbo-latest",
        "qwen-plus": "qwen-plus-latest",
        "deepseek": "deepseek-v3.1",
        "kimi": "moonshot-v1-32k",
        "hunyuan": "hunyuan-turbo",
        "doubao": "doubao-1-5-pro-32k",
        "dify": "dify-mindmate",
    }

    def __init__(self):
        self._enabled = os.getenv("TOKEN_TRACKER_ENABLED", "true").lower() == "true"
        self._worker_task: Optional[asyncio.Task] = None
        self._initialized = False
        self._shutting_down = False
        self._last_flush_time = time.time()

        # In-memory fallback buffer
        self._memory_buffer: List[Dict[str, Any]] = []
        self._memory_lock = threading.Lock()

        # Local stats
        self._total_written = 0
        self._total_dropped = 0
        self._total_batches = 0

        if self._enabled:
            logger.info(
                "[TokenBuffer] Initialized: batch_size=%s, interval=%s s, max_buffer=%s",
                BATCH_SIZE,
                BATCH_INTERVAL,
                MAX_BUFFER_SIZE,
            )
        else:
            logger.info("[TokenBuffer] Disabled via TOKEN_TRACKER_ENABLED=false")

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    async def _ensure_stream_group(self) -> bool:
        """Create the consumer group on the stream if it does not exist yet."""
        if not self._use_redis():
            return False
        try:
            redis = get_async_redis()
            await redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
            logger.debug(
                "[TokenBuffer] Consumer group '%s' created on stream '%s'",
                CONSUMER_GROUP,
                STREAM_KEY,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                logger.warning("[TokenBuffer] Could not create consumer group: %s", exc)
        return True

    def _ensure_worker_started(self) -> None:
        """Start background flush worker if not already running.

        The consumer-group bootstrap is awaited inside the worker coroutine so
        we do not need to block the caller while the first XGROUP CREATE goes
        out on the wire.
        """
        if self._initialized or not self._enabled:
            return

        try:
            loop = asyncio.get_running_loop()
            self._worker_task = loop.create_task(self._flush_worker())
            self._initialized = True
            self._last_flush_time = time.time()
            logger.debug("[TokenBuffer] Background flush worker started")
        except RuntimeError:
            pass

    async def _flush_worker(self):
        """Background worker that periodically flushes buffer to database."""
        logger.debug("[TokenBuffer] Flush worker started")

        if self._use_redis():
            await self._ensure_stream_group()

        while not self._shutting_down:
            try:
                await asyncio.sleep(WORKER_CHECK_INTERVAL)

                if self._shutting_down:
                    break

                buffer_size = await self._get_buffer_size()
                time_since_flush = time.time() - self._last_flush_time

                should_flush = False
                flush_reason = ""

                if buffer_size >= MAX_BUFFER_SIZE:
                    should_flush = True
                    flush_reason = f"max buffer ({buffer_size} >= {MAX_BUFFER_SIZE})"
                elif buffer_size >= BATCH_SIZE:
                    should_flush = True
                    flush_reason = f"batch size ({buffer_size} >= {BATCH_SIZE})"
                elif time_since_flush >= BATCH_INTERVAL and buffer_size > 0:
                    should_flush = True
                    flush_reason = f"interval ({time_since_flush:.0f}s >= {BATCH_INTERVAL}s)"

                if should_flush:
                    logger.debug("[TokenBuffer] Flush triggered: %s", flush_reason)
                    await self._flush_buffer()

            except asyncio.CancelledError:
                logger.debug("[TokenBuffer] Flush worker cancelled")
                break
            except Exception as e:
                logger.error("[TokenBuffer] Flush worker error: %s", e, exc_info=True)
                await asyncio.sleep(5)

        remaining = await self._get_buffer_size()
        if remaining > 0:
            logger.info("[TokenBuffer] Final flush: %s records", remaining)
            await self._flush_buffer()

        logger.debug("[TokenBuffer] Flush worker stopped")

    async def _get_buffer_size(self) -> int:
        """Get current buffer size (stream length + unacked pending entries)."""
        if self._use_redis():
            try:
                redis = get_async_redis()
                return int(await redis.xlen(STREAM_KEY) or 0)
            except Exception as exc:
                logger.debug("Token buffer stream length check failed: %s", exc)

        with self._memory_lock:
            return len(self._memory_buffer)

    async def _flush_buffer(self):
        """Flush buffer to database, then acknowledge processed stream entries."""
        if not self._enabled:
            return

        tuples = await self._pop_records(BATCH_SIZE)
        if not tuples:
            return

        entry_ids = [eid for eid, _ in tuples if eid is not None]
        records = [r for _, r in tuples]
        record_count = len(records)
        start_time = time.time()

        try:
            try:
                if not check_disk_space(required_mb=50):
                    logger.error("[TokenBuffer] Insufficient disk space - records dropped")
                    self._total_dropped += record_count
                    return
            except Exception as exc:
                logger.debug("Token buffer disk space check failed: %s", exc)

            async with AsyncSessionLocal() as db:
                try:
                    await db.execute(sa_insert(TokenUsage), records)
                    await db.commit()

                    await self._ack_records(entry_ids)

                    write_time = time.time() - start_time
                    self._total_written += record_count
                    self._total_batches += 1
                    self._last_flush_time = time.time()

                    await self._update_stats(record_count)

                    total_tokens = sum(r.get("total_tokens", 0) for r in records)
                    write_time_ms = write_time * 1000
                    logger.info(
                        "[TokenBuffer] Wrote %s records (%s tokens) in %.1fms | Total: %s",
                        record_count,
                        total_tokens,
                        write_time_ms,
                        self._total_written,
                    )

                    user_ids = {uid for r in records for uid in (r.get("user_id"),) if isinstance(uid, int)}
                    for uid in user_ids:
                        try:
                            await compute_and_upsert_user_usage_stats_async(uid, db)
                        except Exception as stats_err:
                            logger.debug(
                                "[TokenBuffer] Stats compute failed for user %s: %s",
                                uid,
                                stats_err,
                            )
                    try:
                        await db.commit()
                    except Exception as commit_err:
                        await db.rollback()
                        logger.warning("[TokenBuffer] Stats commit failed: %s", commit_err)

                except Exception as exc:
                    await db.rollback()
                    self._total_dropped += record_count
                    logger.error("[TokenBuffer] Database write failed: %s", exc)

        except Exception as exc:
            self._total_dropped += record_count
            logger.error("[TokenBuffer] Flush failed: %s", exc)

    async def _pop_records(self, count: int) -> List[Tuple]:
        """
        Read up to count records from the stream via consumer group.

        Returns a list of (entry_id, parsed_record) tuples so that the caller
        can acknowledge after a successful DB write.  The plain-list fallback
        path returns tuples of (None, record) for a uniform interface.

        block=None means non-blocking: if there are no new entries we get an
        empty result immediately.  Using block=0 would block the thread
        indefinitely when the stream is empty, freezing the flush worker.
        """
        if self._use_redis():
            try:
                redis = get_async_redis()
                try:
                    pending = await redis.xautoclaim(
                        STREAM_KEY,
                        CONSUMER_GROUP,
                        CONSUMER_NAME,
                        min_idle_time=60000,
                        start_id="0-0",
                        count=count,
                    )
                    raw_entries = pending[1] if pending and len(pending) > 1 else []
                except Exception:
                    raw_entries = []

                if raw_entries:
                    try:
                        pending_info = await redis.xpending_range(
                            STREAM_KEY,
                            CONSUMER_GROUP,
                            min="-",
                            max="+",
                            count=len(raw_entries),
                        )
                        delivery_counts = {entry["message_id"]: entry["times_delivered"] for entry in pending_info}
                        dead_letters = [
                            eid for eid, _ in raw_entries if delivery_counts.get(eid, 0) > MAX_STREAM_DELIVERY_COUNT
                        ]
                        if dead_letters:
                            logger.error(
                                "[TokenBuffer] Dropping %s poison stream entries (delivery count > %s)",
                                len(dead_letters),
                                MAX_STREAM_DELIVERY_COUNT,
                            )
                            await self._ack_records(dead_letters)
                            dead_set = set(dead_letters)
                            raw_entries = [(eid, fields) for eid, fields in raw_entries if eid not in dead_set]
                    except Exception as dlq_exc:
                        logger.debug("[TokenBuffer] Dead-letter check failed: %s", dlq_exc)

                remaining = count - len(raw_entries)
                if remaining > 0:
                    new_entries = await redis.xreadgroup(
                        CONSUMER_GROUP,
                        CONSUMER_NAME,
                        {STREAM_KEY: ">"},
                        count=remaining,
                        block=None,
                    )
                    if new_entries:
                        raw_entries.extend(new_entries[0][1])

                records = []
                poison_ids = []
                for entry_id, fields in raw_entries:
                    try:
                        record = orjson.loads(fields.get("data") or b"{}")
                        if "created_at" in record and isinstance(record["created_at"], str):
                            record["created_at"] = datetime.fromisoformat(record["created_at"])
                        records.append((entry_id, record))
                    except Exception as exc:
                        logger.warning(
                            "[TokenBuffer] Dropping unparseable stream entry %s: %s",
                            entry_id,
                            exc,
                        )
                        poison_ids.append(entry_id)

                if poison_ids:
                    await self._ack_records(poison_ids)

                return records
            except Exception as exc:
                logger.error("[TokenBuffer] Redis stream read failed: %s", exc)

        with self._memory_lock:
            batch = self._memory_buffer[:count]
            self._memory_buffer = self._memory_buffer[count:]
            return [(None, r) for r in batch]

    async def _ack_records(self, entry_ids: List[str]) -> None:
        """Acknowledge successfully processed stream entries so they are removed."""
        if not entry_ids:
            return
        try:
            redis = get_async_redis()
            await redis.xack(STREAM_KEY, CONSUMER_GROUP, *entry_ids)
            await redis.xdel(STREAM_KEY, *entry_ids)
        except Exception as exc:
            logger.warning("[TokenBuffer] Stream ack failed: %s", exc)

    async def _update_stats(self, count: int) -> None:
        """Update Redis stats (HINCRBY in a pipeline)."""
        if not self._use_redis():
            return
        try:
            redis = get_async_redis()
            async with redis.pipeline(transaction=False) as pipe:
                pipe.hincrby(STATS_KEY, "total_written", count)
                pipe.hincrby(STATS_KEY, "total_batches", 1)
                await pipe.execute()
        except Exception as exc:
            logger.debug("Token buffer stats update failed: %s", exc)

    async def track_usage(
        self,
        model_alias: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: Optional[int] = None,
        request_type: str = "diagram_generation",
        diagram_type: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        response_time: Optional[float] = None,
        success: bool = True,
        **kwargs: Any,
    ) -> bool:
        """
        Track token usage (non-blocking, batched).

        Records are added to a shared Redis buffer and flushed to
        database periodically.

        Returns:
            True if added to buffer, False if disabled or overflow
        """
        if not self._enabled:
            return False

        try:
            self._ensure_worker_started()

            # Calculate total tokens if not provided
            if total_tokens is None:
                total_tokens = input_tokens + output_tokens

            # Get pricing info
            pricing = self.MODEL_PRICING.get(model_alias, {"input": 0.4, "output": 1.2, "provider": "unknown"})

            # Calculate cost
            input_cost = input_tokens * pricing["input"] / 1_000_000
            output_cost = output_tokens * pricing["output"] / 1_000_000
            total_cost = input_cost + output_cost

            model_name = self.MODEL_NAME_MAP.get(model_alias, model_alias)

            # Build record
            if kwargs:
                logger.debug("[TokenBuffer] Extra kwargs ignored: %s", list(kwargs.keys()))
            record = {
                "user_id": user_id,
                "organization_id": organization_id,
                "api_key_id": api_key_id,
                "session_id": session_id or f"session_{os.urandom(8).hex()}",
                "conversation_id": conversation_id,
                "model_provider": pricing["provider"],
                "model_name": model_name,
                "model_alias": model_alias,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "input_cost": round(input_cost, 6),
                "output_cost": round(output_cost, 6),
                "total_cost": round(total_cost, 6),
                "request_type": request_type,
                "diagram_type": diagram_type,
                "endpoint_path": endpoint_path,
                "success": success,
                "response_time": response_time,
                "created_at": datetime.now(UTC).isoformat(),
            }

            return await self._push_record(record)

        except Exception as e:
            logger.error("[TokenBuffer] Failed to buffer record: %s", e)
            return False

    async def _push_record(self, record: Dict) -> bool:
        """Push record to stream buffer using XADD (with IDMPAUTO when supported).

        Caps the underlying stream at ``STREAM_HARD_CAP`` via ``MAXLEN ~`` so a
        long DB outage cannot grow Redis memory without bound. The
        approximate variant keeps trimming O(1). IDMPAUTO support is detected
        once at startup by ``_apply_redis_startup_config``; we still guard
        against a stale capability marker by catching ``ResponseError``.
        """
        if self._use_redis():
            try:
                redis = get_async_redis()
                current_size = int(await redis.xlen(STREAM_KEY) or 0)
                if current_size >= MAX_BUFFER_SIZE:
                    self._total_dropped += 1
                    logger.warning("[TokenBuffer] Buffer overflow! Dropping record.")
                    return False

                payload = {"data": orjson.dumps(record)}
                if _RedisCapabilities.idmpauto:
                    try:
                        await redis.xadd(
                            STREAM_KEY,
                            payload,
                            id="IDMPAUTO",
                            maxlen=STREAM_HARD_CAP,
                            approximate=True,
                        )
                        return True
                    except RedisResponseError as resp_err:
                        err_str = str(resp_err)
                        if "IDMPAUTO" in err_str or "Invalid stream ID" in err_str:
                            _RedisCapabilities.idmpauto = False
                            logger.warning(
                                "[TokenBuffer] IDMPAUTO rejected by server; falling back to auto-generated ids"
                            )
                        else:
                            raise

                await redis.xadd(
                    STREAM_KEY,
                    payload,
                    maxlen=STREAM_HARD_CAP,
                    approximate=True,
                )
                return True
            except Exception as exc:
                logger.error("[TokenBuffer] Redis push failed: %s", exc)

        with self._memory_lock:
            if len(self._memory_buffer) >= MAX_BUFFER_SIZE:
                self._total_dropped += 1
                return False
            self._memory_buffer.append(record)
            return True

    async def flush(self):
        """Manually flush pending records (called on shutdown)."""
        if not self._enabled:
            return

        self._shutting_down = True

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        while await self._get_buffer_size() > 0:
            await self._flush_buffer()

        logger.info(
            "[TokenBuffer] Shutdown complete. Total written: %s, dropped: %s",
            self._total_written,
            self._total_dropped,
        )

    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID."""
        return f"session_{os.urandom(8).hex()}"

    async def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        stats = {
            "enabled": self._enabled,
            "buffer_size": await self._get_buffer_size(),
            "total_written": self._total_written,
            "total_dropped": self._total_dropped,
            "total_batches": self._total_batches,
            "storage": "redis_stream" if self._use_redis() else "memory",
            "config": {
                "batch_size": BATCH_SIZE,
                "batch_interval": BATCH_INTERVAL,
                "max_buffer_size": MAX_BUFFER_SIZE,
            },
        }

        if self._use_redis():
            try:
                redis = get_async_redis()
                redis_stats = await redis.hgetall(STATS_KEY)
                if redis_stats:
                    stats["redis_total_written"] = int(redis_stats.get("total_written", 0))
                    stats["redis_total_batches"] = int(redis_stats.get("total_batches", 0))
                stats["stream_length"] = int(await redis.xlen(STREAM_KEY) or 0)
            except Exception as exc:
                logger.debug("Token buffer stats retrieval failed: %s", exc)

        return stats


class _TokenBufferHolder:
    """Holder for singleton token buffer instance."""

    _instance: Optional[RedisTokenBuffer] = None

    @classmethod
    def get_instance(cls) -> RedisTokenBuffer:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = RedisTokenBuffer()
        return cls._instance


def get_token_buffer() -> RedisTokenBuffer:
    """Get or create global token buffer instance."""
    return _TokenBufferHolder.get_instance()


# Alias for backwards compatibility
def get_token_tracker() -> RedisTokenBuffer:
    """Alias for get_token_buffer (backwards compatibility)."""
    return get_token_buffer()
