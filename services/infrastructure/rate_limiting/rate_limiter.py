"""
Dashscope Rate Limiter (Redis-backed)
=====================================

Rate limiting for Dashscope platform to prevent exceeding QPM and concurrent limits.
Uses Redis for global coordination across all workers.

Key Schema:
- llm:rate:qpm -> sorted set {timestamp: score} for sliding window QPM tracking
- llm:rate:concurrent -> counter for active concurrent requests
- llm:rate:stats -> hash for global statistics

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from collections import deque
from typing import Optional, Dict, Any
import asyncio
import logging
import os
import time
import uuid

from services.redis.redis_client import is_redis_available, get_redis



logger = logging.getLogger(__name__)

# Redis key prefixes
# Provider-specific keys for separate rate limiting per provider
RATE_QPM_KEY_DASHSCOPE = "llm:rate:dashscope:qpm"
RATE_CONCURRENT_KEY_DASHSCOPE = "llm:rate:dashscope:concurrent"

# Volcengine endpoint-specific keys (each endpoint has independent limits)
RATE_QPM_KEY_VOLCENGINE_DEEPSEEK = "llm:rate:volcengine:deepseek:qpm"
RATE_QPM_KEY_VOLCENGINE_KIMI = "llm:rate:volcengine:kimi:qpm"
RATE_QPM_KEY_VOLCENGINE_DOUBAO = "llm:rate:volcengine:doubao:qpm"
RATE_CONCURRENT_KEY_VOLCENGINE_DEEPSEEK = "llm:rate:volcengine:deepseek:concurrent"
RATE_CONCURRENT_KEY_VOLCENGINE_KIMI = "llm:rate:volcengine:kimi:concurrent"
RATE_CONCURRENT_KEY_VOLCENGINE_DOUBAO = "llm:rate:volcengine:doubao:concurrent"

# Legacy Volcengine keys (deprecated - use endpoint-specific keys)
RATE_QPM_KEY_VOLCENGINE = "llm:rate:volcengine:qpm"  # Deprecated: Use endpoint-specific keys
RATE_CONCURRENT_KEY_VOLCENGINE = "llm:rate:volcengine:concurrent"  # Deprecated: Use endpoint-specific keys

RATE_STATS_KEY = "llm:rate:stats"

# Legacy keys (for backward compatibility, deprecated)
RATE_QPM_KEY = "llm:rate:qpm"  # Deprecated: Use provider-specific keys
RATE_CONCURRENT_KEY = "llm:rate:concurrent"  # Deprecated: Use provider-specific keys


class DashscopeRateLimiter:
    """
    Rate limiter for Dashscope platform with Redis coordination.

    Prevents exceeding:
    - QPM (Queries Per Minute) limit - globally across all workers
    - Concurrent request limit - globally across all workers

    Uses Redis sorted sets for sliding window QPM tracking and
    Redis counters for concurrent request tracking.

    Falls back to per-worker in-memory tracking if Redis unavailable.

    Usage:
        limiter = DashscopeRateLimiter(qpm_limit=60, concurrent_limit=10)

        await limiter.acquire()  # Blocks if limits exceeded
        try:
            result = await make_api_call()
        finally:
            await limiter.release()
    """

    def __init__(
        self,
        qpm_limit: int = 200,
        concurrent_limit: int = 50,
        enabled: bool = True,
        provider: str = 'dashscope',
        endpoint: Optional[str] = None
    ):
        """
        Initialize rate limiter.

        Args:
            qpm_limit: Maximum queries per minute (default: 200)
            concurrent_limit: Maximum concurrent requests (default: 50)
            enabled: Whether rate limiting is enabled
            provider: Provider name ('dashscope' or 'volcengine') - determines Redis keys
            endpoint: Volcengine endpoint name ('ark-deepseek', 'ark-kimi', 'ark-doubao')
                     Required when provider='volcengine' to select endpoint-specific Redis keys
        """
        self.qpm_limit = qpm_limit
        self.concurrent_limit = concurrent_limit
        self.enabled = enabled
        self.provider = provider
        self.endpoint = endpoint

        # Select provider-specific Redis keys
        if provider == 'volcengine':
            # Validate endpoint parameter for Volcengine provider
            valid_endpoints = ['ark-deepseek', 'ark-kimi', 'ark-doubao']
            if not endpoint:
                raise ValueError(
                    f"Endpoint parameter is required for Volcengine provider. "
                    f"Valid endpoints: {valid_endpoints}"
                )
            if endpoint not in valid_endpoints:
                raise ValueError(
                    f"Invalid endpoint '{endpoint}' for Volcengine provider. "
                    f"Valid endpoints: {valid_endpoints}"
                )

            # Map endpoint to specific Redis keys
            if endpoint == 'ark-deepseek':
                self.qpm_key = RATE_QPM_KEY_VOLCENGINE_DEEPSEEK
                self.concurrent_key = RATE_CONCURRENT_KEY_VOLCENGINE_DEEPSEEK
            elif endpoint == 'ark-kimi':
                self.qpm_key = RATE_QPM_KEY_VOLCENGINE_KIMI
                self.concurrent_key = RATE_CONCURRENT_KEY_VOLCENGINE_KIMI
            elif endpoint == 'ark-doubao':
                self.qpm_key = RATE_QPM_KEY_VOLCENGINE_DOUBAO
                self.concurrent_key = RATE_CONCURRENT_KEY_VOLCENGINE_DOUBAO
        else:  # Default to dashscope
            self.qpm_key = RATE_QPM_KEY_DASHSCOPE
            self.concurrent_key = RATE_CONCURRENT_KEY_DASHSCOPE

        # Generate unique request ID prefix for this worker
        self._worker_id = os.getenv('WORKER_ID', str(os.getpid()))

        # In-memory fallback (kept for single-worker testing only)
        # NOTE: Redis is REQUIRED for multi-worker deployments
        self._memory_timestamps = deque()
        self._memory_active = 0
        self._lock = asyncio.Lock()

        # Local statistics
        self._local_total_requests = 0
        self._local_total_waits = 0
        self._local_total_wait_time = 0.0

        # Lua script SHA (lazy-loaded when first used)
        self._acquire_script_sha: Optional[str] = None

        # Verify Redis is available (REQUIRED for rate limiting)
        if not self._use_redis():
            raise RuntimeError(
                "Rate limiting requires Redis. Redis is unavailable. "
                "Please ensure Redis is running and configured correctly."
            )

        if endpoint:
            logger.info(
                "[RateLimiter] Initialized: Provider=%s, QPM=%s, Concurrent=%s, "
                "Enabled=%s, Redis keys: QPM=%s, Concurrent=%s, Endpoint=%s",
                provider, qpm_limit, concurrent_limit, enabled, self.qpm_key, self.concurrent_key, endpoint
            )
        else:
            logger.info(
                "[RateLimiter] Initialized: Provider=%s, QPM=%s, Concurrent=%s, "
                "Enabled=%s, Redis keys: QPM=%s, Concurrent=%s",
                provider, qpm_limit, concurrent_limit, enabled, self.qpm_key, self.concurrent_key
            )

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        Blocks if rate limits would be exceeded.

        Redis is REQUIRED - raises RuntimeError if Redis unavailable.
        """
        if not self.enabled:
            return

        # Redis is REQUIRED for rate limiting
        if not self._use_redis():
            raise RuntimeError(
                "Rate limiting requires Redis. Redis is unavailable. "
                "Please ensure Redis is running and configured correctly."
            )

        await self._redis_acquire()

    async def _redis_acquire(self) -> None:
        """
        Acquire using Redis for global coordination.

        Uses atomic Lua script to prevent race conditions between checking limits
        and incrementing counters. This ensures that concurrent requests cannot
        exceed limits even when checking simultaneously.
        """
        redis = get_redis()
        if not redis:
            raise RuntimeError(
                "Rate limiting requires Redis. Redis connection unavailable. "
                "Please ensure Redis is running and configured correctly."
            )

        wait_start = None
        last_log_time = None  # Track last periodic log time

        # Lua script for atomic check-and-increment
        # This prevents race conditions where multiple requests check limits
        # simultaneously before any increments occur
        acquire_script = """
        local concurrent_key = KEYS[1]
        local qpm_key = KEYS[2]
        local stats_key = KEYS[3]
        local concurrent_limit = tonumber(ARGV[1])
        local qpm_limit = tonumber(ARGV[2])
        local request_id = ARGV[3]
        local timestamp = tonumber(ARGV[4])
        local one_minute_ago = tonumber(ARGV[5])

        -- Clean old QPM entries
        redis.call('ZREMRANGEBYSCORE', qpm_key, 0, one_minute_ago)

        -- Check concurrent limit
        local current_concurrent = tonumber(redis.call('GET', concurrent_key) or 0)
        if current_concurrent >= concurrent_limit then
            return {0, 'concurrent_limit', current_concurrent}
        end

        -- Check QPM limit
        local current_qpm = redis.call('ZCARD', qpm_key)
        if current_qpm >= qpm_limit then
            return {0, 'qpm_limit', current_qpm}
        end

        -- All checks passed, increment atomically
        redis.call('ZADD', qpm_key, timestamp, request_id)
        redis.call('EXPIRE', qpm_key, 120)
        redis.call('INCR', concurrent_key)
        redis.call('EXPIRE', concurrent_key, 300)
        redis.call('HINCRBY', stats_key, 'total_requests', 1)

        return {1, 'success', current_concurrent + 1, current_qpm + 1}
        """

        try:
            # Register script once (idempotent)
            if self._acquire_script_sha is None:
                try:
                    self._acquire_script_sha = redis.script_load(acquire_script)
                except Exception as e:
                    logger.error("[RateLimiter] Failed to load Lua script: %s", e)
                    raise RuntimeError(
                        f"Rate limiting requires Redis. Failed to load Lua script: {e}. "
                        "Please ensure Redis is running and configured correctly."
                    ) from e

            # Loop until we successfully acquire
            while True:
                now = time.time()
                one_minute_ago = now - 60
                # Generate new request_id for each retry attempt to ensure uniqueness
                request_id = f"{self._worker_id}:{now}:{uuid.uuid4().hex[:8]}"

                # Execute atomic check-and-increment script
                try:
                    result = redis.evalsha(
                        self._acquire_script_sha,
                        3,  # Number of keys
                        self.concurrent_key,
                        self.qpm_key,
                        RATE_STATS_KEY,
                        self.concurrent_limit,
                        self.qpm_limit,
                        request_id,
                        now,
                        one_minute_ago
                    )
                except Exception as script_error:
                    # Script might not exist (Redis restart), reload it
                    if 'NOSCRIPT' in str(script_error) or 'not found' in str(script_error).lower():
                        logger.warning("[RateLimiter] Lua script not found, reloading...")
                        try:
                            self._acquire_script_sha = redis.script_load(acquire_script)
                            # Retry once
                            result = redis.evalsha(
                                self._acquire_script_sha,
                                3,
                                self.concurrent_key,
                                self.qpm_key,
                                RATE_STATS_KEY,
                                self.concurrent_limit,
                                self.qpm_limit,
                                request_id,
                                now,
                                one_minute_ago
                            )
                        except Exception as retry_error:
                            logger.error("[RateLimiter] Failed to reload Lua script: %s", retry_error)
                            raise RuntimeError(
                                f"Rate limiting requires Redis. Lua script execution failed: {retry_error}. "
                                "Please ensure Redis is running and configured correctly."
                            ) from retry_error
                    else:
                        # Other Redis errors
                        logger.error("[RateLimiter] Lua script execution failed: %s", script_error)
                        raise RuntimeError(
                            f"Rate limiting requires Redis. Lua script execution failed: {script_error}. "
                            "Please ensure Redis is running and configured correctly."
                        ) from script_error

                # Result format: {success, reason, current_value, ...}
                success = result[0] == 1

                if success:
                    # Successfully acquired
                    self._local_total_requests += 1

                    # Track wait time if we waited
                    if wait_start:
                        wait_duration = time.time() - wait_start
                        self._local_total_wait_time += wait_duration
                        try:
                            redis.hincrbyfloat(RATE_STATS_KEY, "total_wait_time", wait_duration)
                            redis.hincrby(RATE_STATS_KEY, "total_waits", 1)
                        except Exception as e:
                            logger.warning("[RateLimiter] Failed to update wait stats: %s", e)
                        # Log at INFO level if wait was significant (>1s), DEBUG otherwise
                        if wait_duration > 1.0:
                            provider_name = self.provider or 'unknown'
                            endpoint_name = self.endpoint or ''
                            logger.info(
                                "[RateLimiter] %s %s Waited %.2fs before acquiring rate limit slot",
                                provider_name, endpoint_name, wait_duration
                            )
                        else:
                            logger.debug("[RateLimiter] Waited %.2fs before acquiring", wait_duration)

                    # Get current stats for debug log
                    try:
                        current_concurrent = result[2] if len(result) > 2 else int(redis.get(self.concurrent_key) or 0)
                        current_qpm = result[3] if len(result) > 3 else redis.zcard(self.qpm_key) or 0

                        logger.debug(
                            "[RateLimiter] Acquired (Redis): %s/%s concurrent, %s/%s QPM",
                            current_concurrent, self.concurrent_limit, current_qpm, self.qpm_limit
                        )
                    except Exception as e:
                        logger.debug("[RateLimiter] Failed to get stats for logging: %s", e)

                    break  # Successfully acquired, exit loop

                else:
                    # Limit reached, wait and retry
                    limit_type = result[1] if len(result) > 1 else 'unknown'
                    current_value = result[2] if len(result) > 2 else 0

                    if wait_start is None:
                        wait_start = time.time()
                        last_log_time = wait_start
                        self._local_total_waits += 1
                        provider_name = self.provider or 'unknown'
                        endpoint_name = self.endpoint or ''
                        if limit_type == 'concurrent_limit':
                            logger.info(
                                "[RateLimiter] %s %s Concurrent limit reached (%s/%s), waiting...",
                                provider_name, endpoint_name, current_value, self.concurrent_limit
                            )
                        elif limit_type == 'qpm_limit':
                            logger.warning(
                                "[RateLimiter] %s %s QPM limit reached (%s/%s), waiting...",
                                provider_name, endpoint_name, current_value, self.qpm_limit
                            )

                    # Log periodic updates during long waits (every 5 seconds)
                    wait_duration = time.time() - wait_start
                    current_time = time.time()
                    if wait_duration > 5.0 and (last_log_time is None or current_time - last_log_time >= 5.0):
                        provider_name = self.provider or 'unknown'
                        endpoint_name = self.endpoint or ''
                        limit_value = self.concurrent_limit if limit_type == 'concurrent_limit' else self.qpm_limit
                        logger.warning(
                            "[RateLimiter] %s %s Still waiting for %s (%s/%s), waited %.1fs...",
                            provider_name, endpoint_name, limit_type, current_value, limit_value, wait_duration
                        )
                        last_log_time = current_time

                    # Wait before retrying
                    await asyncio.sleep(0.1 if limit_type == 'concurrent_limit' else 1.0)

        except Exception as e:
            logger.error("[RateLimiter] Redis acquire failed: %s", e)
            raise RuntimeError(
                f"Rate limiting requires Redis. Redis operation failed: {e}. "
                "Please ensure Redis is running and configured correctly."
            ) from e

    async def _memory_acquire(self) -> None:
        """Acquire using in-memory storage (fallback)."""
        wait_start = None

        async with self._lock:
            # 1. Wait if concurrent limit reached
            while self._memory_active >= self.concurrent_limit:
                if wait_start is None:
                    wait_start = time.time()
                    self._local_total_waits += 1
                    logger.debug(
                        "[RateLimiter] (memory) Concurrent limit reached (%s/%s), waiting...",
                        self._memory_active, self.concurrent_limit
                    )
                await asyncio.sleep(0.1)

            # 2. Clean old timestamps (older than 1 minute)
            now = time.time()
            one_minute_ago = now - 60
            while self._memory_timestamps and self._memory_timestamps[0] < one_minute_ago:
                self._memory_timestamps.popleft()

            # 3. Wait if QPM limit reached
            while len(self._memory_timestamps) >= self.qpm_limit:
                if wait_start is None:
                    wait_start = time.time()
                    self._local_total_waits += 1
                    logger.warning(
                        "[RateLimiter] (memory) QPM limit reached (%s/%s), waiting...",
                        len(self._memory_timestamps), self.qpm_limit
                    )
                await asyncio.sleep(1.0)

                # Clean old timestamps again
                now = time.time()
                one_minute_ago = now - 60
                while self._memory_timestamps and self._memory_timestamps[0] < one_minute_ago:
                    self._memory_timestamps.popleft()

            # 4. Grant permission
            self._memory_timestamps.append(now)
            self._memory_active += 1
            self._local_total_requests += 1

            # Track wait time
            if wait_start:
                wait_duration = time.time() - wait_start
                self._local_total_wait_time += wait_duration
                logger.debug("[RateLimiter] (memory) Waited %.2fs before acquiring", wait_duration)

            logger.debug(
                "[RateLimiter] Acquired (memory): %s/%s concurrent, %s/%s QPM",
                self._memory_active, self.concurrent_limit, len(self._memory_timestamps), self.qpm_limit
            )

    async def release(self) -> None:
        """Release after request completes."""
        if not self.enabled:
            return

        # Redis is REQUIRED for rate limiting
        if not self._use_redis():
            raise RuntimeError(
                "Rate limiting requires Redis. Redis is unavailable. "
                "Please ensure Redis is running and configured correctly."
            )

        await self._redis_release()

    async def _redis_release(self) -> None:
        """Release using Redis."""
        redis = get_redis()
        if not redis:
            raise RuntimeError(
                "Rate limiting requires Redis. Redis connection unavailable. "
                "Please ensure Redis is running and configured correctly."
            )

        try:
            current = redis.decr(self.concurrent_key)
            # Ensure non-negative (safety check)
            if current < 0:
                redis.set(self.concurrent_key, 0)
                current = 0

            logger.debug(
                "[RateLimiter] Released (Redis): %s/%s concurrent",
                current, self.concurrent_limit
            )

        except Exception as e:
            logger.error("[RateLimiter] Redis release failed: %s", e)
            raise

    async def _memory_release(self) -> None:
        """Release using in-memory storage."""
        async with self._lock:
            self._memory_active = max(0, self._memory_active - 1)
            logger.debug(
                "[RateLimiter] Released (memory): %s/%s concurrent",
                self._memory_active, self.concurrent_limit
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        stats = {
            'enabled': self.enabled,
            'provider': self.provider,
            'qpm_limit': self.qpm_limit,
            'concurrent_limit': self.concurrent_limit,
            'qpm_key': self.qpm_key,
            'concurrent_key': self.concurrent_key,
            'storage': 'redis' if self._use_redis() else 'memory',
            'worker_id': self._worker_id,
            # Local stats (this worker only)
            'local_total_requests': self._local_total_requests,
            'local_total_waits': self._local_total_waits,
            'local_total_wait_time': round(self._local_total_wait_time, 2),
        }

        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    now = time.time()
                    one_minute_ago = now - 60

                    # Clean and get current QPM
                    redis.zremrangebyscore(self.qpm_key, 0, one_minute_ago)
                    current_qpm = redis.zcard(self.qpm_key) or 0
                    current_concurrent = int(redis.get(self.concurrent_key) or 0)

                    # Get global stats
                    global_stats = redis.hgetall(RATE_STATS_KEY) or {}

                    stats.update({
                        'current_qpm': current_qpm,
                        'active_requests': current_concurrent,
                        'global_total_requests': int(global_stats.get('total_requests', 0)),
                        'global_total_waits': int(global_stats.get('total_waits', 0)),
                        'global_total_wait_time': float(global_stats.get('total_wait_time', 0)),
                    })

                    total_waits = stats['global_total_waits']
                    if total_waits > 0:
                        stats['avg_wait_time'] = round(
                            stats['global_total_wait_time'] / total_waits, 2
                        )
                    else:
                        stats['avg_wait_time'] = 0.0

                except Exception as e:
                    logger.warning("[RateLimiter] Failed to get Redis stats: %s", e)
                    stats['redis_stats_error'] = str(e)
        else:
            # Memory stats
            stats.update({
                'current_qpm': len(self._memory_timestamps),
                'active_requests': self._memory_active,
                'total_requests': self._local_total_requests,
                'total_waits': self._local_total_waits,
                'total_wait_time': round(self._local_total_wait_time, 2),
                'avg_wait_time': round(
                    self._local_total_wait_time / self._local_total_waits
                    if self._local_total_waits > 0 else 0, 2
                )
            })

        return stats

    def clear_state(self) -> None:
        """
        Clear rate limiter state in Redis (for testing purposes).

        WARNING: This should only be used in tests. In production, let entries
        expire naturally to maintain accurate rate limiting.
        """
        if not self._use_redis():
            return

        redis = get_redis()
        if redis:
            try:
                # Clear QPM entries
                redis.delete(self.qpm_key)
                # Clear concurrent counter
                redis.delete(self.concurrent_key)
                logger.debug("[RateLimiter] Cleared state: QPM=%s, Concurrent=%s", self.qpm_key, self.concurrent_key)
            except Exception as e:
                logger.warning("[RateLimiter] Failed to clear state: %s", e)

    async def __aenter__(self):
        """Context manager support."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, _exc_val, _exc_tb):
        """Context manager support."""
        await self.release()


# Singleton instance (will be initialized by LLMService)
class RateLimiterSingleton:
    """Singleton container for rate limiter instance."""
    _instance: Optional[DashscopeRateLimiter] = None

    @classmethod
    def get(cls) -> Optional[DashscopeRateLimiter]:
        """Get the rate limiter instance."""
        return cls._instance

    @classmethod
    def set(cls, instance: DashscopeRateLimiter) -> None:
        """Set the rate limiter instance."""
        cls._instance = instance


def get_rate_limiter() -> Optional[DashscopeRateLimiter]:
    """Get the global rate limiter instance."""
    return RateLimiterSingleton.get()


def initialize_rate_limiter(
    qpm_limit: int = 200,
    concurrent_limit: int = 50,
    enabled: bool = True
) -> DashscopeRateLimiter:
    """
    Initialize the global rate limiter.

    Args:
        qpm_limit: Maximum queries per minute (default: 200)
        concurrent_limit: Maximum concurrent requests (default: 50)
        enabled: Whether to enable rate limiting

    Returns:
        Initialized rate limiter instance
    """
    instance = DashscopeRateLimiter(
        qpm_limit=qpm_limit,
        concurrent_limit=concurrent_limit,
        enabled=enabled
    )
    RateLimiterSingleton.set(instance)
    return instance


class LoadBalancerRateLimiter:
    """
    Rate limiter for load-balanced models (DeepSeek).

    Manages separate rate limiters for each provider route:
    - Dashscope route (deepseek model)
    - Volcengine route (ark-deepseek endpoint)

    Provides provider-aware rate limiting to ensure we don't exceed
    limits on either provider when load balancing.

    Usage:
        limiter = LoadBalancerRateLimiter(
            dashscope_qpm=13500,
            dashscope_concurrent=500,
            volcengine_qpm=4500,
            volcengine_concurrent=500,
            enabled=True
        )

        # Check availability before selecting provider
        if limiter.can_acquire('dashscope'):
            provider = 'dashscope'
        elif limiter.can_acquire('volcengine'):
            provider = 'volcengine'
        else:
            # Both at capacity, wait for dashscope
            async with limiter.get_limiter('dashscope'):
                # Make request
                pass
    """

    PROVIDER_DASHSCOPE = 'dashscope'
    PROVIDER_VOLCENGINE = 'volcengine'

    def __init__(
        self,
        volcengine_qpm: int = 13500,
        volcengine_concurrent: int = 500,
        enabled: bool = True
    ):
        """
        Initialize load balancer rate limiter.

        Args:
            volcengine_qpm: QPM limit for Volcengine route
            volcengine_concurrent: Concurrent limit for Volcengine route
            enabled: Whether rate limiting is enabled

        Note:
            Dashscope route should use the shared Dashscope rate limiter
            (not managed by this class).
        """
        self.enabled = enabled

        # Only manage Volcengine route rate limiter (for DeepSeek ark-deepseek endpoint)
        # Dashscope route uses shared limiter (passed separately to load balancer)
        self.volcengine_limiter = DashscopeRateLimiter(
            qpm_limit=volcengine_qpm,
            concurrent_limit=volcengine_concurrent,
            enabled=enabled,
            provider='volcengine',
            endpoint='ark-deepseek'  # DeepSeek Volcengine endpoint
        )

        logger.info(
            "[LoadBalancerRateLimiter] Initialized: "
            "Volcengine(QPM=%s, Concurrent=%s), Enabled=%s. "
            "Note: Dashscope route uses shared Dashscope rate limiter.",
            volcengine_qpm, volcengine_concurrent, enabled
        )

    def get_limiter(self, provider: str) -> DashscopeRateLimiter:
        """
        Get rate limiter for a specific provider.

        Args:
            provider: 'volcengine' (Dashscope route uses shared limiter, not this class)

        Returns:
            Rate limiter instance for Volcengine provider

        Raises:
            ValueError: If provider is 'dashscope' (should use shared limiter instead)
            ValueError: If provider is unknown
        """
        if provider == self.PROVIDER_DASHSCOPE:
            raise ValueError(
                "Dashscope route should use the shared Dashscope rate limiter, "
                "not LoadBalancerRateLimiter. Pass the shared limiter separately."
            )
        elif provider == self.PROVIDER_VOLCENGINE:
            return self.volcengine_limiter
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def acquire(self, provider: str) -> None:
        """
        Acquire permission for a specific provider.

        Args:
            provider: 'dashscope' or 'volcengine'
        """
        if not self.enabled:
            return

        limiter = self.get_limiter(provider)
        await limiter.acquire()

    async def release(self, provider: str) -> None:
        """
        Release after request completes for a specific provider.

        Args:
            provider: 'dashscope' or 'volcengine'
        """
        if not self.enabled:
            return

        limiter = self.get_limiter(provider)
        await limiter.release()

    def can_acquire_now(self, provider: str) -> bool:
        """
        Check if a provider can accept a request immediately (non-blocking).

        This is a best-effort check. The actual acquire() may still block
        if conditions change between check and acquire.

        Args:
            provider: 'dashscope' or 'volcengine'

        Returns:
            True if provider likely has capacity, False otherwise
        """
        if not self.enabled:
            return True

        limiter = self.get_limiter(provider)
        stats = limiter.get_stats()

        # Check concurrent limit
        # FIXED: Removed incorrect 'or' operator - use active_requests directly
        active = stats.get('active_requests', 0)
        concurrent_limit = stats.get('concurrent_limit', 0)

        if active >= concurrent_limit:
            return False

        # Check QPM limit (approximate)
        current_qpm = stats.get('current_qpm', 0)
        qpm_limit = stats.get('qpm_limit', 0)

        if current_qpm >= qpm_limit:
            return False

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for Volcengine provider."""
        return {
            'enabled': self.enabled,
            'volcengine': self.volcengine_limiter.get_stats(),
            'note': 'Dashscope route uses shared Dashscope rate limiter (not included here)'
        }

    async def __aenter__(self):
        """Context manager support - not used directly, use get_limiter()."""
        raise NotImplementedError("Use get_limiter(provider) to get provider-specific limiter")

    async def __aexit__(self, exc_type, _exc_val, _exc_tb):
        """Context manager support."""
        pass
