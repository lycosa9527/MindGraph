"""Regression tests for redis-py SCH connection kwargs (sync vs async)."""

from __future__ import annotations

import inspect

from redis.asyncio.connection import AbstractConnection

from services.redis.redis_connection_options import (
    async_maint_notifications_supported,
    redis_async_connection_options,
    redis_connection_options,
)


def test_sync_options_disable_sch() -> None:
    """Sync clients always disable Smart Client Handoffs probing."""
    opts = redis_connection_options()
    assert "maint_notifications_config" in opts
    assert opts["maint_notifications_config"].enabled is False


def test_async_options_match_redis_py_capability() -> None:
    """Async options must not include unsupported kwargs on the installed redis-py."""
    opts = redis_async_connection_options()
    supported = async_maint_notifications_supported()
    if supported:
        assert opts["maint_notifications_config"].enabled is False
    else:
        assert not opts


def test_async_sch_kwargs_compatible_with_abstract_connection() -> None:
    """Every async SCH kwarg must be accepted by redis.asyncio AbstractConnection."""
    allowed = set(inspect.signature(AbstractConnection.__init__).parameters)
    for key in redis_async_connection_options():
        assert key in allowed
