"""
Integration Tests for API Endpoints
====================================

Tests API endpoint functionality and error handling.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import pytest
import asyncio
import aiohttp
from typing import Optional, Dict, Any


class TestAPIEndpoints:
    """Test suite for API endpoints."""
    
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
    async def test_health_check(self, session, base_url):
        """Test health check endpoint."""
        async with session.get(f"{base_url}/health") as response:
            assert response.status == 200
            data = await response.json()
            assert 'status' in data
            assert data['status'] == 'ok'
            assert 'version' in data
    
    @pytest.mark.asyncio
    async def test_health_redis(self, session, base_url):
        """Test Redis health check."""
        async with session.get(f"{base_url}/health/redis") as response:
            assert response.status in [200, 503]  # 200 if healthy, 503 if unavailable
            data = await response.json()
            assert 'status' in data
    
    @pytest.mark.asyncio
    async def test_health_database(self, session, base_url):
        """Test database health check."""
        async with session.get(f"{base_url}/health/database") as response:
            assert response.status in [200, 503]  # 200 if healthy, 503 if unhealthy
            data = await response.json()
            assert 'status' in data
            assert 'database_healthy' in data
    
    @pytest.mark.asyncio
    async def test_health_all(self, session, base_url):
        """Test comprehensive health check."""
        async with session.get(f"{base_url}/health/all") as response:
            assert response.status in [200, 503]
            data = await response.json()
            assert 'status' in data
            assert 'checks' in data
            assert 'application' in data['checks']
            assert 'redis' in data['checks']
            assert 'database' in data['checks']
    
    @pytest.mark.asyncio
    async def test_generate_graph_validation(self, session, base_url):
        """Test generate_graph endpoint validation."""
        # Test with empty prompt
        async with session.post(
            f"{base_url}/api/generate_graph",
            json={"prompt": "", "language": "en", "llm": "qwen"}
        ) as response:
            assert response.status == 400  # Bad request
    
    @pytest.mark.asyncio
    async def test_export_png_validation(self, session, base_url):
        """Test export_png endpoint validation."""
        # Test with missing diagram_data
        async with session.post(
            f"{base_url}/api/export_png",
            json={"diagram_type": "circle_map"}
        ) as response:
            assert response.status in [400, 401]  # Bad request or unauthorized
    
    @pytest.mark.asyncio
    async def test_frontend_log_validation(self, session, base_url):
        """Test frontend_log endpoint validation."""
        # Test with valid request
        async with session.post(
            f"{base_url}/api/frontend_log",
            json={"level": "info", "message": "Test message"}
        ) as response:
            assert response.status == 200
            data = await response.json()
            assert data.get('status') == 'logged'
    
    @pytest.mark.asyncio
    async def test_frontend_log_batch_validation(self, session, base_url):
        """Test frontend_log_batch endpoint validation."""
        # Test with valid batch
        async with session.post(
            f"{base_url}/api/frontend_log_batch",
            json={
                "batch_size": 2,
                "logs": [
                    {"level": "info", "message": "Test 1"},
                    {"level": "debug", "message": "Test 2"}
                ]
            }
        ) as response:
            assert response.status == 200
            data = await response.json()
            assert data.get('status') == 'logged'
            assert data.get('count') == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

