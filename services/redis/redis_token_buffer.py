"""Redis token buffer module.

Shared token usage buffer using Redis. Collects token usage records from all
workers and flushes to database periodically. Features: shared buffer across
all workers (no data loss on worker crash), atomic list operations for thread
safety, periodic batch flush to database for persistence, graceful fallback
to per-worker memory buffer. Key schema: tokens:buffer -> list of record_json,
tokens:stats -> hash of total_written, total_dropped, batches.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import asyncio
import json
import logging
import os
import threading
import time

from sqlalchemy import inspect as sa_inspect

from services.redis.redis_client import is_redis_available, get_redis
from config.database import SessionLocal, check_disk_space
from models.domain.token_usage import TokenUsage
from services.teacher_usage_stats import compute_and_upsert_user_usage_stats

logger = logging.getLogger(__name__)

# Redis keys
BUFFER_KEY = "tokens:buffer"
STATS_KEY = "tokens:stats"

# Configuration from environment
BATCH_SIZE = int(os.getenv('TOKEN_TRACKER_BATCH_SIZE', '1000'))
BATCH_INTERVAL = float(os.getenv('TOKEN_TRACKER_BATCH_INTERVAL', '300'))  # 5 minutes
MAX_BUFFER_SIZE = int(os.getenv('TOKEN_TRACKER_MAX_BUFFER_SIZE', '10000'))
WORKER_CHECK_INTERVAL = 30.0  # Check every 30 seconds


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
        'qwen': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
        'qwen-turbo': {'input': 0.3, 'output': 0.6, 'provider': 'dashscope'},
        'qwen-plus': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
        'deepseek': {'input': 0.4, 'output': 2.0, 'provider': 'dashscope'},
        'kimi': {'input': 2.0, 'output': 6.0, 'provider': 'dashscope'},
        'hunyuan': {'input': 0.45, 'output': 0.5, 'provider': 'tencent'},
        'doubao': {'input': 0.8, 'output': 2.0, 'provider': 'volcengine'},
        # Dify MindMate - uses Dify's hosted models (pricing estimated based on typical usage)
        'dify': {'input': 0.5, 'output': 1.5, 'provider': 'dify'},
    }

    # Model name mapping
    MODEL_NAME_MAP = {
        'qwen': 'qwen-plus-latest',
        'qwen-turbo': 'qwen-turbo-latest',
        'qwen-plus': 'qwen-plus-latest',
        'deepseek': 'deepseek-v3.1',
        'kimi': 'moonshot-v1-32k',
        'hunyuan': 'hunyuan-turbo',
        'doubao': 'doubao-1-5-pro-32k',
        'dify': 'dify-mindmate',
    }

    def __init__(self):
        self._enabled = os.getenv('TOKEN_TRACKER_ENABLED', 'true').lower() == 'true'
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
                BATCH_SIZE, BATCH_INTERVAL, MAX_BUFFER_SIZE
            )
        else:
            logger.info("[TokenBuffer] Disabled via TOKEN_TRACKER_ENABLED=false")

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def _ensure_worker_started(self):
        """Start background flush worker if not already running."""
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

        while not self._shutting_down:
            try:
                await asyncio.sleep(WORKER_CHECK_INTERVAL)

                if self._shutting_down:
                    break

                # Check flush conditions
                buffer_size = self._get_buffer_size()
                time_since_flush = time.time() - self._last_flush_time

                should_flush = False
                flush_reason = ""

                if buffer_size >= MAX_BUFFER_SIZE:
                    should_flush = True
                    flush_reason = "max buffer (%s >= %s)" % (buffer_size, MAX_BUFFER_SIZE)
                elif buffer_size >= BATCH_SIZE:
                    should_flush = True
                    flush_reason = "batch size (%s >= %s)" % (buffer_size, BATCH_SIZE)
                elif time_since_flush >= BATCH_INTERVAL and buffer_size > 0:
                    should_flush = True
                    flush_reason = "interval (%.0fs >= %ss)" % (time_since_flush, BATCH_INTERVAL)

                if should_flush:
                    logger.debug("[TokenBuffer] Flush triggered: %s", flush_reason)
                    await self._flush_buffer()

            except asyncio.CancelledError:
                logger.debug("[TokenBuffer] Flush worker cancelled")
                break
            except Exception as e:
                logger.error("[TokenBuffer] Flush worker error: %s", e, exc_info=True)
                await asyncio.sleep(5)

        # Final flush on shutdown
        if self._get_buffer_size() > 0:
            buffer_size = self._get_buffer_size()
            logger.info("[TokenBuffer] Final flush: %s records", buffer_size)
            await self._flush_buffer()

        logger.debug("[TokenBuffer] Flush worker stopped")

    def _get_buffer_size(self) -> int:
        """Get current buffer size."""
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    return redis.llen(BUFFER_KEY) or 0
                except Exception:
                    pass

        with self._memory_lock:
            return len(self._memory_buffer)

    async def _flush_buffer(self):
        """Flush buffer to database."""
        if not self._enabled:
            return

        # Get records from buffer
        records = self._pop_records(BATCH_SIZE)
        if not records:
            return

        record_count = len(records)
        start_time = time.time()

        try:
            # Check disk space
            try:
                if not check_disk_space(required_mb=50):
                    logger.error("[TokenBuffer] Insufficient disk space - records dropped")
                    self._total_dropped += record_count
                    return
            except Exception:
                pass

            db = SessionLocal()
            try:
                # Bulk insert
                db.bulk_insert_mappings(sa_inspect(TokenUsage), records)
                db.commit()

                write_time = time.time() - start_time
                self._total_written += record_count
                self._total_batches += 1
                self._last_flush_time = time.time()

                # Update Redis stats
                self._update_stats(record_count)

                total_tokens = sum(r.get('total_tokens', 0) for r in records)
                write_time_ms = write_time * 1000
                logger.info(
                    "[TokenBuffer] Wrote %s records (%s tokens) in %.1fms | Total: %s",
                    record_count, total_tokens, write_time_ms, self._total_written
                )

                user_ids = {
                    uid for r in records
                    for uid in (r.get("user_id"),)
                    if isinstance(uid, int)
                }
                for uid in user_ids:
                    try:
                        compute_and_upsert_user_usage_stats(uid, db)
                    except Exception as stats_err:
                        logger.debug(
                            "[TokenBuffer] Stats compute failed for user %s: %s",
                            uid, stats_err
                        )

            except Exception as e:
                db.rollback()
                self._total_dropped += record_count
                logger.error("[TokenBuffer] Database write failed: %s", e)
            finally:
                db.close()

        except Exception as e:
            self._total_dropped += record_count
            logger.error("[TokenBuffer] Flush failed: %s", e)

    def _pop_records(self, count: int) -> List[Dict]:
        """Pop up to count records from buffer."""
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    # Atomic pop: get and remove in one pipeline
                    pipe = redis.pipeline()
                    pipe.lrange(BUFFER_KEY, 0, count - 1)
                    pipe.ltrim(BUFFER_KEY, count, -1)
                    results = pipe.execute()

                    records = []
                    for item in (results[0] or []):
                        try:
                            record = json.loads(item)
                            # Convert created_at back to datetime
                            if 'created_at' in record and isinstance(record['created_at'], str):
                                record['created_at'] = datetime.fromisoformat(record['created_at'])
                            records.append(record)
                        except Exception:
                            pass
                    return records
                except Exception as e:
                    logger.error("[TokenBuffer] Redis pop failed: %s", e)

        # Fallback to memory
        with self._memory_lock:
            records = self._memory_buffer[:count]
            self._memory_buffer = self._memory_buffer[count:]
            return records

    def _update_stats(self, count: int):
        """Update Redis stats."""
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    pipe = redis.pipeline()
                    pipe.hincrby(STATS_KEY, "total_written", count)
                    pipe.hincrby(STATS_KEY, "total_batches", 1)
                    pipe.execute()
                except Exception:
                    pass

    async def track_usage(
        self,
        model_alias: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: Optional[int] = None,
        request_type: str = 'diagram_generation',
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
            pricing = self.MODEL_PRICING.get(model_alias, {
                'input': 0.4,
                'output': 1.2,
                'provider': 'unknown'
            })

            # Calculate cost
            input_cost = input_tokens * pricing['input'] / 1_000_000
            output_cost = output_tokens * pricing['output'] / 1_000_000
            total_cost = input_cost + output_cost

            model_name = self.MODEL_NAME_MAP.get(model_alias, model_alias)

            # Build record
            if kwargs:
                logger.debug("[TokenBuffer] Extra kwargs ignored: %s", list(kwargs.keys()))
            record = {
                'user_id': user_id,
                'organization_id': organization_id,
                'api_key_id': api_key_id,
                'session_id': session_id or f"session_{os.urandom(8).hex()}",
                'conversation_id': conversation_id,
                'model_provider': pricing['provider'],
                'model_name': model_name,
                'model_alias': model_alias,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'input_cost': round(input_cost, 6),
                'output_cost': round(output_cost, 6),
                'total_cost': round(total_cost, 6),
                'request_type': request_type,
                'diagram_type': diagram_type,
                'endpoint_path': endpoint_path,
                'success': success,
                'response_time': response_time,
                'created_at': datetime.utcnow().isoformat()
            }

            # Add to buffer
            return self._push_record(record)

        except Exception as e:
            logger.error("[TokenBuffer] Failed to buffer record: %s", e)
            return False

    def _push_record(self, record: Dict) -> bool:
        """Push record to buffer."""
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    # Check buffer size
                    current_size = redis.llen(BUFFER_KEY) or 0
                    if current_size >= MAX_BUFFER_SIZE:
                        self._total_dropped += 1
                        logger.warning("[TokenBuffer] Buffer overflow! Dropping record.")
                        return False

                    redis.rpush(BUFFER_KEY, json.dumps(record))
                    return True
                except Exception as e:
                    logger.error("[TokenBuffer] Redis push failed: %s", e)

        # Fallback to memory
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

        # Final flush
        while self._get_buffer_size() > 0:
            await self._flush_buffer()

        logger.info(
            "[TokenBuffer] Shutdown complete. Total written: %s, dropped: %s",
            self._total_written, self._total_dropped
        )

    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID."""
        return f"session_{os.urandom(8).hex()}"

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        stats = {
            'enabled': self._enabled,
            'buffer_size': self._get_buffer_size(),
            'total_written': self._total_written,
            'total_dropped': self._total_dropped,
            'total_batches': self._total_batches,
            'storage': 'redis' if self._use_redis() else 'memory',
            'config': {
                'batch_size': BATCH_SIZE,
                'batch_interval': BATCH_INTERVAL,
                'max_buffer_size': MAX_BUFFER_SIZE,
            }
        }

        # Add Redis global stats
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    redis_stats = redis.hgetall(STATS_KEY)
                    if redis_stats:
                        stats['redis_total_written'] = int(redis_stats.get('total_written', 0))
                        stats['redis_total_batches'] = int(redis_stats.get('total_batches', 0))
                except Exception:
                    pass

        return stats


class _TokenBufferHolder:
    """Holder for singleton token buffer instance."""

    _instance: Optional[RedisTokenBuffer] = None


def get_token_buffer() -> RedisTokenBuffer:
    """Get or create global token buffer instance."""
    if _TokenBufferHolder._instance is None:
        _TokenBufferHolder._instance = RedisTokenBuffer()
    return _TokenBufferHolder._instance


# Alias for backwards compatibility
def get_token_tracker() -> RedisTokenBuffer:
    """Alias for get_token_buffer (backwards compatibility)."""
    return get_token_buffer()
