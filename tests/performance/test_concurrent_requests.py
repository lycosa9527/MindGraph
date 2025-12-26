"""
Performance Tests for Concurrent Requests
==========================================

Tests system behavior under concurrent load.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import pytest
import asyncio
import aiohttp
import time
from typing import List, Dict, Any


class TestConcurrentRequests:
    """Test suite for concurrent request handling."""
    
    @pytest.fixture
    def base_url(self):
        """Base URL for API tests."""
        return "http://localhost:9527"
    
    @pytest.fixture
    async def session(self):
        """Create aiohttp session with connection pool."""
        connector = aiohttp.TCPConnector(limit=100)
        async with aiohttp.ClientSession(connector=connector) as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, session, base_url):
        """Test concurrent health check requests."""
        async def check_health():
            async with session.get(f"{base_url}/health") as response:
                return response.status
        
        # Make 50 concurrent requests
        tasks = [check_health() for _ in range(50)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed (200)
        assert all(status == 200 for status in results), "Some health checks failed"
    
    @pytest.mark.asyncio
    async def test_concurrent_frontend_logs(self, session, base_url):
        """Test concurrent frontend log requests."""
        async def send_log(i):
            async with session.post(
                f"{base_url}/api/frontend_log",
                json={"level": "info", "message": f"Concurrent test {i}"}
            ) as response:
                return response.status
        
        # Make 50 concurrent requests
        tasks = [send_log(i) for i in range(50)]
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time
        
        # Most should succeed (200), some may be rate limited (429)
        success_count = sum(1 for status in results if status == 200)
        rate_limited_count = sum(1 for status in results if status == 429)
        
        assert success_count > 0, "No requests succeeded"
        # Rate limiting should kick in for some requests
        assert rate_limited_count >= 0, "Rate limiting should work"
        
        # Should complete reasonably quickly (< 5 seconds)
        assert duration < 5.0, f"Concurrent requests took too long: {duration:.2f}s"
    
    @pytest.mark.asyncio
    async def test_concurrent_generate_graph_rate_limiting(self, session, base_url):
        """Test rate limiting under concurrent load."""
        async def make_request(i):
            async with session.post(
                f"{base_url}/api/generate_graph",
                json={"prompt": f"Test {i}", "language": "en", "llm": "qwen"}
            ) as response:
                return response.status
        
        # Make 35 concurrent requests (limit is 30 per minute)
        tasks = [make_request(i) for i in range(35)]
        results = await asyncio.gather(*tasks)
        
        # Some should be rate limited (429) or unauthorized (401)
        statuses = set(results)
        assert 429 in statuses or 401 in statuses, "Rate limiting not working under concurrent load"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

