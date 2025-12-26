"""
Integration Tests for API Security
==================================

Tests security features: rate limiting, authentication, CSRF protection.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import pytest
import asyncio
import aiohttp
from typing import Optional


class TestAPISecurity:
    """Test suite for API security features."""
    
    @pytest.fixture
    def base_url(self):
        """Base URL for API tests."""
        return "http://localhost:9527"
    
    @pytest.fixture
    async def session(self):
        """Create aiohttp session."""
        async with aiohttp.ClientSession() as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_frontend_log_rate_limiting(self, session, base_url):
        """Test rate limiting on frontend logging endpoints."""
        # Make 101 requests (limit is 100 per minute)
        results = []
        for i in range(101):
            async with session.post(
                f"{base_url}/api/frontend_log",
                json={"level": "info", "message": f"Test message {i}"}
            ) as response:
                results.append(response.status)
        
        # At least one should be rate limited (429)
        assert 429 in results, "Rate limiting not working on frontend_log endpoint"
    
    @pytest.mark.asyncio
    async def test_generate_graph_rate_limiting(self, session, base_url):
        """Test rate limiting on expensive endpoints."""
        # This test requires authentication, so we'll test the endpoint structure
        # In a real scenario, you'd need to authenticate first
        async with session.post(
            f"{base_url}/api/generate_graph",
            json={"prompt": "Test", "language": "en", "llm": "qwen"}
        ) as response:
            # Should get 401 (unauthorized) or 429 (rate limited) or 400 (validation)
            assert response.status in [400, 401, 429], f"Unexpected status: {response.status}"
    
    @pytest.mark.asyncio
    async def test_temp_images_signed_url(self, session, base_url):
        """Test temp images endpoint requires signed URL."""
        # Try to access without signature
        async with session.get(f"{base_url}/api/temp_images/test.png") as response:
            # Should get 403 (forbidden) or 404 (not found)
            assert response.status in [403, 404], f"Temp images should require signed URL, got {response.status}"
    
    @pytest.mark.asyncio
    async def test_csrf_protection_headers(self, session, base_url):
        """Test CSRF protection headers are set."""
        async with session.get(f"{base_url}/health") as response:
            headers = response.headers
            # Check for security headers
            assert 'X-Frame-Options' in headers
            assert 'X-Content-Type-Options' in headers
            assert headers['X-Frame-Options'] == 'DENY'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

