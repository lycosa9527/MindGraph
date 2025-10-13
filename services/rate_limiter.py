"""
Dashscope Rate Limiter
======================

Rate limiting for Dashscope platform to prevent exceeding QPM and concurrent limits.

@author lycosa9527
@made_by MindSpring Team
"""

import asyncio
import logging
from datetime import datetime, timedelta
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class DashscopeRateLimiter:
    """
    Rate limiter for Dashscope platform.
    
    Prevents exceeding:
    - QPM (Queries Per Minute) limit
    - Concurrent request limit
    
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
        
        # Track recent requests (last minute)
        self._request_timestamps = deque()
        self._active_requests = 0
        self._lock = asyncio.Lock()
        
        # Statistics
        self._total_requests = 0
        self._total_waits = 0
        self._total_wait_time = 0.0
        
        logger.info(
            f"[RateLimiter] Initialized: "
            f"QPM={qpm_limit}, Concurrent={concurrent_limit}, Enabled={enabled}"
        )
    
    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        Blocks if rate limits would be exceeded.
        """
        if not self.enabled:
            return
        
        wait_start = None
        async with self._lock:
            # 1. Wait if concurrent limit reached
            while self._active_requests >= self.concurrent_limit:
                if wait_start is None:
                    wait_start = datetime.now()
                    self._total_waits += 1
                    logger.debug(
                        f"[RateLimiter] Concurrent limit reached "
                        f"({self._active_requests}/{self.concurrent_limit}), waiting..."
                    )
                await asyncio.sleep(0.1)
            
            # 2. Clean old timestamps (older than 1 minute)
            now = datetime.now()
            one_minute_ago = now - timedelta(minutes=1)
            while self._request_timestamps and self._request_timestamps[0] < one_minute_ago:
                self._request_timestamps.popleft()
            
            # 3. Wait if QPM limit reached
            while len(self._request_timestamps) >= self.qpm_limit:
                if wait_start is None:
                    wait_start = datetime.now()
                    self._total_waits += 1
                    logger.warning(
                        f"[RateLimiter] QPM limit reached "
                        f"({len(self._request_timestamps)}/{self.qpm_limit}), waiting..."
                    )
                await asyncio.sleep(1.0)
                
                # Clean old timestamps again
                now = datetime.now()
                one_minute_ago = now - timedelta(minutes=1)
                while self._request_timestamps and self._request_timestamps[0] < one_minute_ago:
                    self._request_timestamps.popleft()
            
            # 4. Grant permission
            self._request_timestamps.append(now)
            self._active_requests += 1
            self._total_requests += 1
            
            # Track wait time
            if wait_start:
                wait_duration = (datetime.now() - wait_start).total_seconds()
                self._total_wait_time += wait_duration
                logger.debug(f"[RateLimiter] Waited {wait_duration:.2f}s before acquiring")
            
            logger.debug(
                f"[RateLimiter] Acquired: "
                f"{self._active_requests}/{self.concurrent_limit} concurrent, "
                f"{len(self._request_timestamps)}/{self.qpm_limit} QPM"
            )
    
    async def release(self) -> None:
        """Release after request completes."""
        if not self.enabled:
            return
        
        async with self._lock:
            self._active_requests -= 1
            logger.debug(
                f"[RateLimiter] Released: "
                f"{self._active_requests}/{self.concurrent_limit} concurrent"
            )
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        return {
            'enabled': self.enabled,
            'qpm_limit': self.qpm_limit,
            'concurrent_limit': self.concurrent_limit,
            'current_qpm': len(self._request_timestamps),
            'active_requests': self._active_requests,
            'total_requests': self._total_requests,
            'total_waits': self._total_waits,
            'total_wait_time': round(self._total_wait_time, 2),
            'avg_wait_time': round(
                self._total_wait_time / self._total_waits if self._total_waits > 0 else 0,
                2
            )
        }
    
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


