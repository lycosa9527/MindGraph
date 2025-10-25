"""
Unit Tests for Rate Limiter
============================

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
import asyncio
import time
from services.rate_limiter import DashscopeRateLimiter


class TestRateLimiter:
    """Test suite for DashscopeRateLimiter."""
    
    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        """Test concurrent request limiting."""
        limiter = DashscopeRateLimiter(
            qpm_limit=100,
            concurrent_limit=2,
            enabled=True
        )
        
        active_count = 0
        max_active = 0
        
        async def task():
            nonlocal active_count, max_active
            await limiter.acquire()
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.1)
            active_count -= 1
            await limiter.release()
        
        # Start 5 tasks concurrently
        await asyncio.gather(*[task() for _ in range(5)])
        
        # Max concurrent should not exceed limit
        assert max_active <= 2
        print(f"Max concurrent: {max_active}")
    
    @pytest.mark.asyncio
    async def test_qpm_limit(self):
        """Test QPM limiting."""
        limiter = DashscopeRateLimiter(
            qpm_limit=5,
            concurrent_limit=10,
            enabled=True
        )
        
        start_time = time.time()
        
        # Make 10 requests (should trigger QPM wait after 5)
        for i in range(10):
            await limiter.acquire()
            await limiter.release()
        
        elapsed = time.time() - start_time
        
        # Should have waited for rate limit
        assert elapsed > 0.5  # Some waiting occurred
        print(f"Completed 10 requests in {elapsed:.2f}s")
        
        stats = limiter.get_stats()
        print(f"Stats: {stats}")
    
    @pytest.mark.asyncio
    async def test_disabled_limiter(self):
        """Test that disabled limiter doesn't block."""
        limiter = DashscopeRateLimiter(
            qpm_limit=1,
            concurrent_limit=1,
            enabled=False
        )
        
        start_time = time.time()
        
        # Make 10 requests quickly
        for i in range(10):
            await limiter.acquire()
            await limiter.release()
        
        elapsed = time.time() - start_time
        
        # Should be very fast (no limiting)
        assert elapsed < 0.5
        print(f"Completed 10 requests in {elapsed:.2f}s (disabled)")
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test rate limiter as context manager."""
        limiter = DashscopeRateLimiter(
            qpm_limit=100,
            concurrent_limit=5,
            enabled=True
        )
        
        async with limiter:
            # Rate limiter acquired
            pass
        # Rate limiter released
        
        stats = limiter.get_stats()
        assert stats['total_requests'] == 1
        assert stats['active_requests'] == 0
        print(f"Context manager test passed: {stats}")
    
    def test_get_stats(self):
        """Test getting statistics."""
        limiter = DashscopeRateLimiter(
            qpm_limit=60,
            concurrent_limit=10,
            enabled=True
        )
        
        stats = limiter.get_stats()
        assert stats['enabled'] is True
        assert stats['qpm_limit'] == 60
        assert stats['concurrent_limit'] == 10
        assert stats['total_requests'] == 0
        print(f"Initial stats: {stats}")


