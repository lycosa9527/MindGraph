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

import asyncio
import logging
import time
import os
import uuid
from datetime import datetime
from collections import deque
from typing import Optional, Dict, Any

from services.redis_client import is_redis_available, get_redis

logger = logging.getLogger(__name__)

# Redis key prefixes
RATE_QPM_KEY = "llm:rate:qpm"
RATE_CONCURRENT_KEY = "llm:rate:concurrent"
RATE_STATS_KEY = "llm:rate:stats"


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
        enabled: bool = True
    ):
        """
        Initialize rate limiter.
        
        Args:
            qpm_limit: Maximum queries per minute (default: 200)
            concurrent_limit: Maximum concurrent requests (default: 50)
            enabled: Whether rate limiting is enabled
        """
        self.qpm_limit = qpm_limit
        self.concurrent_limit = concurrent_limit
        self.enabled = enabled
        
        # Generate unique request ID prefix for this worker
        self._worker_id = os.getenv('WORKER_ID', str(os.getpid()))
        
        # In-memory fallback (used when Redis unavailable)
        self._memory_timestamps = deque()
        self._memory_active = 0
        self._lock = asyncio.Lock()
        
        # Local statistics
        self._local_total_requests = 0
        self._local_total_waits = 0
        self._local_total_wait_time = 0.0
        
        storage = "Redis" if self._use_redis() else "memory"
        logger.info(
            f"[RateLimiter] Initialized: "
            f"QPM={qpm_limit}, Concurrent={concurrent_limit}, "
            f"Enabled={enabled}, Storage={storage}"
        )
    
    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()
    
    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        Blocks if rate limits would be exceeded.
        """
        if not self.enabled:
            return
        
        if self._use_redis():
            await self._redis_acquire()
        else:
            await self._memory_acquire()
    
    async def _redis_acquire(self) -> None:
        """Acquire using Redis for global coordination."""
        redis = get_redis()
        if not redis:
            await self._memory_acquire()
            return
        
        wait_start = None
        request_id = f"{self._worker_id}:{time.time()}:{uuid.uuid4().hex[:8]}"
        
        try:
            # 1. Wait if concurrent limit reached
            while True:
                current_concurrent = int(redis.get(RATE_CONCURRENT_KEY) or 0)
                if current_concurrent < self.concurrent_limit:
                    break
                
                if wait_start is None:
                    wait_start = time.time()
                    self._local_total_waits += 1
                    logger.debug(
                        f"[RateLimiter] Concurrent limit reached "
                        f"({current_concurrent}/{self.concurrent_limit}), waiting..."
                    )
                await asyncio.sleep(0.1)
            
            # 2. Wait if QPM limit reached
            while True:
                now = time.time()
                one_minute_ago = now - 60
                
                # Atomic: clean old entries and count
                pipe = redis.pipeline()
                pipe.zremrangebyscore(RATE_QPM_KEY, 0, one_minute_ago)
                pipe.zcard(RATE_QPM_KEY)
                results = pipe.execute()
                
                current_qpm = results[1] or 0
                if current_qpm < self.qpm_limit:
                    break
                
                if wait_start is None:
                    wait_start = time.time()
                    self._local_total_waits += 1
                    logger.warning(
                        f"[RateLimiter] QPM limit reached "
                        f"({current_qpm}/{self.qpm_limit}), waiting..."
                    )
                await asyncio.sleep(1.0)
            
            # 3. Grant permission - atomic add to QPM and increment concurrent
            now = time.time()
            pipe = redis.pipeline()
            pipe.zadd(RATE_QPM_KEY, {request_id: now})
            pipe.expire(RATE_QPM_KEY, 120)  # 2 minute TTL for cleanup
            pipe.incr(RATE_CONCURRENT_KEY)
            pipe.expire(RATE_CONCURRENT_KEY, 300)  # 5 minute TTL as safety
            pipe.hincrby(RATE_STATS_KEY, "total_requests", 1)
            pipe.execute()
            
            self._local_total_requests += 1
            
            # Track wait time
            if wait_start:
                wait_duration = time.time() - wait_start
                self._local_total_wait_time += wait_duration
                redis.hincrbyfloat(RATE_STATS_KEY, "total_wait_time", wait_duration)
                redis.hincrby(RATE_STATS_KEY, "total_waits", 1)
                logger.debug(f"[RateLimiter] Waited {wait_duration:.2f}s before acquiring")
            
            # Get current stats for debug log
            current_concurrent = int(redis.get(RATE_CONCURRENT_KEY) or 0)
            current_qpm = redis.zcard(RATE_QPM_KEY) or 0
            
            logger.debug(
                f"[RateLimiter] Acquired (Redis): "
                f"{current_concurrent}/{self.concurrent_limit} concurrent, "
                f"{current_qpm}/{self.qpm_limit} QPM"
            )
            
        except Exception as e:
            logger.warning(f"[RateLimiter] Redis acquire failed: {e}, falling back to memory")
            await self._memory_acquire()
    
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
                        f"[RateLimiter] (memory) Concurrent limit reached "
                        f"({self._memory_active}/{self.concurrent_limit}), waiting..."
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
                        f"[RateLimiter] (memory) QPM limit reached "
                        f"({len(self._memory_timestamps)}/{self.qpm_limit}), waiting..."
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
                logger.debug(f"[RateLimiter] (memory) Waited {wait_duration:.2f}s before acquiring")
            
            logger.debug(
                f"[RateLimiter] Acquired (memory): "
                f"{self._memory_active}/{self.concurrent_limit} concurrent, "
                f"{len(self._memory_timestamps)}/{self.qpm_limit} QPM"
            )
    
    async def release(self) -> None:
        """Release after request completes."""
        if not self.enabled:
            return
        
        if self._use_redis():
            await self._redis_release()
        else:
            await self._memory_release()
    
    async def _redis_release(self) -> None:
        """Release using Redis."""
        redis = get_redis()
        if not redis:
            await self._memory_release()
            return
        
        try:
            current = redis.decr(RATE_CONCURRENT_KEY)
            # Ensure non-negative (safety check)
            if current < 0:
                redis.set(RATE_CONCURRENT_KEY, 0)
                current = 0
            
            logger.debug(
                f"[RateLimiter] Released (Redis): "
                f"{current}/{self.concurrent_limit} concurrent"
            )
            
        except Exception as e:
            logger.warning(f"[RateLimiter] Redis release failed: {e}")
            await self._memory_release()
    
    async def _memory_release(self) -> None:
        """Release using in-memory storage."""
        async with self._lock:
            self._memory_active = max(0, self._memory_active - 1)
            logger.debug(
                f"[RateLimiter] Released (memory): "
                f"{self._memory_active}/{self.concurrent_limit} concurrent"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        stats = {
            'enabled': self.enabled,
            'qpm_limit': self.qpm_limit,
            'concurrent_limit': self.concurrent_limit,
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
                    redis.zremrangebyscore(RATE_QPM_KEY, 0, one_minute_ago)
                    current_qpm = redis.zcard(RATE_QPM_KEY) or 0
                    current_concurrent = int(redis.get(RATE_CONCURRENT_KEY) or 0)
                    
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
                    logger.warning(f"[RateLimiter] Failed to get Redis stats: {e}")
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
    
    async def __aenter__(self):
        """Context manager support."""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager support."""
        await self.release()


# Singleton instance (will be initialized by LLMService)
_rate_limiter: Optional[DashscopeRateLimiter] = None


def get_rate_limiter() -> Optional[DashscopeRateLimiter]:
    """Get the global rate limiter instance."""
    return _rate_limiter


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
    global _rate_limiter
    _rate_limiter = DashscopeRateLimiter(
        qpm_limit=qpm_limit,
        concurrent_limit=concurrent_limit,
        enabled=enabled
    )
    return _rate_limiter
