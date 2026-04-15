"""Tests for Dify aiohttp session pooling (no live API calls)."""

from __future__ import annotations

import pytest

from clients.dify import _DifySharedHttpPool


@pytest.mark.asyncio
async def test_blocking_pool_replaces_closed_session() -> None:
    await _DifySharedHttpPool.close_all()
    api_url = "https://example.com/v1"
    timeout = 30
    first = await _DifySharedHttpPool.session_blocking(api_url, timeout)
    await first.close()
    assert first.closed
    second = await _DifySharedHttpPool.session_blocking(api_url, timeout)
    try:
        assert second is not first
        assert not second.closed
    finally:
        await _DifySharedHttpPool.close_all()


@pytest.mark.asyncio
async def test_streaming_pool_replaces_closed_session() -> None:
    await _DifySharedHttpPool.close_all()
    api_url = "https://example.com/v1"
    sock_read = 120
    first = await _DifySharedHttpPool.session_streaming(api_url, sock_read)
    await first.close()
    assert first.closed
    second = await _DifySharedHttpPool.session_streaming(api_url, sock_read)
    try:
        assert second is not first
        assert not second.closed
    finally:
        await _DifySharedHttpPool.close_all()
