"""
HTTP Client Manager for LLM Providers

Manages shared httpx AsyncClient instances for LLM providers.
Provides HTTP/2 multiplexing, connection pooling, and proper cleanup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

import httpx

from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


class HTTPXClientManager:
    """
    Manages shared httpx AsyncClient instances for LLM providers.

    Benefits:
    - HTTP/2 multiplexing for concurrent requests
    - Connection pooling across requests
    - Lazy initialization (clients created on first use)
    - Proper cleanup on shutdown
    - Recreates clients when the asyncio event loop changes (pytest)
    """

    _instance: Optional["HTTPXClientManager"] = None

    def __init__(self) -> None:
        """init."""
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._loop_id: Optional[int] = None

    @classmethod
    def get_instance(cls) -> "HTTPXClientManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_loop_affinity(self) -> None:
        """Drop clients bound to a closed/previous event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop_id = id(loop)
        if self._loop_id is None:
            self._loop_id = loop_id
            self._lock = asyncio.Lock()
            return
        if self._loop_id == loop_id:
            if self._lock is None:
                self._lock = asyncio.Lock()
            return
        # New event loop (common under pytest-asyncio): abandon old clients.
        self._clients.clear()
        self._loop_id = loop_id
        self._lock = asyncio.Lock()
        logger.debug("[HTTPXClientManager] Reset clients for new event loop")

    async def get_client(
        self,
        provider: str,
        base_url: str,
        timeout: float = 60.0,
        stream_timeout: float = 120.0,
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
        self._ensure_loop_affinity()
        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            existing = self._clients.get(provider)
            if existing is not None and not existing.is_closed:
                return existing

            self._clients[provider] = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(
                    timeout,
                    connect=30.0,
                    read=stream_timeout,
                ),
                http2=True,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0,
                ),
            )
            logger.debug("[HTTPXClientManager] Created client for %s", provider)
            return self._clients[provider]

    async def close_all(self) -> None:
        """Close all client connections. Call on app shutdown."""
        self._ensure_loop_affinity()
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            for provider, client in list(self._clients.items()):
                if not client.is_closed:
                    try:
                        await client.aclose()
                    except BACKGROUND_INFRA_ERRORS as exc:
                        logger.debug(
                            "[HTTPXClientManager] Close %s ignored: %s",
                            provider,
                            exc,
                        )
                    logger.debug("[HTTPXClientManager] Closed client for %s", provider)
            self._clients.clear()

    def reset_for_tests(self) -> None:
        """Drop cached clients without awaiting (pytest between loops)."""
        self._clients.clear()
        self._lock = None
        self._loop_id = None


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


def reset_httpx_clients_for_tests() -> None:
    """Clear shared httpx clients between pytest event loops."""
    manager = _get_manager_for_close_func()
    if manager is not None:
        manager.reset_for_tests()
    singleton = HTTPXClientManager.get_instance()
    singleton.reset_for_tests()
