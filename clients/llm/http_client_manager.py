"""
HTTP Client Manager for LLM Providers

Manages shared httpx AsyncClient instances for LLM providers.
Provides HTTP/2 multiplexing, connection pooling, and proper cleanup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Optional
import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class HTTPXClientManager:
    """
    Manages shared httpx AsyncClient instances for LLM providers.

    Benefits:
    - HTTP/2 multiplexing for concurrent requests
    - Connection pooling across requests
    - Lazy initialization (clients created on first use)
    - Proper cleanup on shutdown
    """

    _instance: Optional['HTTPXClientManager'] = None

    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> 'HTTPXClientManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_client(
        self,
        provider: str,
        base_url: str,
        timeout: float = 60.0,
        stream_timeout: float = 120.0
    ) -> httpx.AsyncClient:
        """
        Get or create an httpx AsyncClient for a provider.

        Args:
            provider: Provider identifier (e.g., 'dashscope', 'volcengine')
            base_url: Base URL for the provider API
            timeout: Default timeout for non-streaming requests
            stream_timeout: Timeout for streaming requests (longer for thinking models)

        Returns:
            Shared httpx.AsyncClient instance
        """
        async with self._lock:
            if provider not in self._clients or self._clients[provider].is_closed:
                self._clients[provider] = httpx.AsyncClient(
                    base_url=base_url,
                    timeout=httpx.Timeout(
                        timeout,
                        connect=10.0,
                        read=stream_timeout  # Longer read timeout for streaming
                    ),
                    http2=True,  # Enable HTTP/2 for better multiplexing
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                        keepalive_expiry=30.0
                    )
                )
                logger.debug('[HTTPXClientManager] Created client for %s', provider)
            return self._clients[provider]

    async def close_all(self) -> None:
        """Close all client connections. Call on app shutdown."""
        async with self._lock:
            for provider, client in self._clients.items():
                if not client.is_closed:
                    await client.aclose()
                    logger.debug('[HTTPXClientManager] Closed client for %s', provider)
            self._clients.clear()


# Global httpx client manager instance
# Using closure to avoid global statements and protected member access
def _create_manager_functions():
    """Create closure functions to manage httpx manager instance."""
    manager_instance: Optional[HTTPXClientManager] = None

    def get_manager() -> HTTPXClientManager:
        nonlocal manager_instance
        if manager_instance is None:
            manager_instance = HTTPXClientManager.get_instance()
        return manager_instance

    def get_manager_for_close() -> Optional[HTTPXClientManager]:
        return manager_instance

    return get_manager, get_manager_for_close


_get_manager_func, _get_manager_for_close_func = _create_manager_functions()


def get_httpx_manager() -> HTTPXClientManager:
    """Get the global httpx client manager."""
    return _get_manager_func()


async def close_httpx_clients() -> None:
    """Close all httpx clients. Call on app shutdown."""
    manager = _get_manager_for_close_func()
    if manager is not None:
        await manager.close_all()
