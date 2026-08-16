"""Regression tests for redis-py SCH connection kwargs (sync vs async)."""

from __future__ import annotations

import inspect
import sys
from types import SimpleNamespace

from redis.asyncio.connection import AbstractConnection

from config.celery_broker_redis import (
    patch_celery_redis_pools,
    patch_celery_redis_result_backend,
    patch_kombu_redis_connection_pool,
)
from services.redis.redis_connection_options import (
    async_maint_notifications_supported,
    celery_redis_pool_options,
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


def test_kombu_pool_patch_uses_resp2(monkeypatch) -> None:
    """Kombu ConnectionPool must use RESP2 so redis-py skips SCH probing."""
    calls: list[dict] = []

    class FakeChannel:
        """Stand-in for kombu.transport.redis.Channel."""

        _mindgraph_kombu_pool_patch_applied = False
        keyprefix_fanout = "/{db}."

        def _connparams(self, asynchronous=False):
            _ = asynchronous
            return {"db": 1}

    fake_module = SimpleNamespace(
        Channel=FakeChannel,
        redis=SimpleNamespace(
            ConnectionPool=lambda **kwargs: calls.append(kwargs) or "pool",
        ),
    )
    monkeypatch.setitem(sys.modules, "kombu.transport.redis", fake_module)
    monkeypatch.setattr("config.celery_broker_redis.kombu_redis", fake_module)

    patch_kombu_redis_connection_pool()
    pool = getattr(FakeChannel(), "_get_pool")()

    assert pool == "pool"
    assert calls[0]["protocol"] == 2
    assert calls[0]["maint_notifications_config"].enabled is False
    assert getattr(FakeChannel, "_mindgraph_kombu_pool_patch_applied") is True


def test_kombu_pool_patch_is_idempotent(monkeypatch) -> None:
    """Repeated patch calls must not wrap _get_pool multiple times."""

    class FakeChannel:
        """Stand-in for kombu.transport.redis.Channel."""

        _mindgraph_kombu_pool_patch_applied = False
        keyprefix_fanout = "/{db}."

        def _connparams(self, asynchronous=False):
            _ = asynchronous
            return {"db": 0}

        def _get_pool(self, asynchronous=False):
            _ = asynchronous
            return "original"

    fake_module = SimpleNamespace(
        Channel=FakeChannel,
        redis=SimpleNamespace(ConnectionPool=lambda **kwargs: "pool"),
    )
    monkeypatch.setitem(sys.modules, "kombu.transport.redis", fake_module)
    monkeypatch.setattr("config.celery_broker_redis.kombu_redis", fake_module)

    patch_kombu_redis_connection_pool()
    patched = getattr(FakeChannel, "_get_pool")
    patch_kombu_redis_connection_pool()
    assert getattr(FakeChannel, "_get_pool") is patched


def test_celery_redis_pool_options_disable_sch() -> None:
    """Celery/kombu pools must use RESP2 and disable Smart Client Handoffs."""
    opts = celery_redis_pool_options()
    assert opts["protocol"] == 2
    assert opts["maint_notifications_config"].enabled is False


def test_celery_result_backend_pool_uses_resp2(monkeypatch) -> None:
    """Celery result-backend ConnectionPool must skip SCH probing."""
    calls: list[dict] = []

    class FakeBackend:
        """Stand-in for celery.backends.redis.RedisBackend."""

        _mindgraph_result_pool_patch_applied = False

        def _get_pool(self, **params):
            calls.append(params)
            return "pool"

    monkeypatch.setattr("config.celery_broker_redis.CeleryRedisBackend", FakeBackend)

    patch_celery_redis_result_backend()
    pool = getattr(FakeBackend(), "_get_pool")(host="localhost")

    assert pool == "pool"
    assert calls[0]["host"] == "localhost"
    assert calls[0]["protocol"] == 2
    assert calls[0]["maint_notifications_config"].enabled is False
    assert getattr(FakeBackend, "_mindgraph_result_pool_patch_applied") is True


def test_celery_result_backend_pool_patch_is_idempotent(monkeypatch) -> None:
    """Repeated result-backend patch calls must not wrap _get_pool multiple times."""

    class FakeBackend:
        """Stand-in for celery.backends.redis.RedisBackend."""

        _mindgraph_result_pool_patch_applied = False

        def _get_pool(self, **params):
            _ = params
            return "original"

    monkeypatch.setattr("config.celery_broker_redis.CeleryRedisBackend", FakeBackend)

    patch_celery_redis_result_backend()
    patched = getattr(FakeBackend, "_get_pool")
    patch_celery_redis_result_backend()
    assert getattr(FakeBackend, "_get_pool") is patched


def test_patch_celery_redis_pools_applies_both(monkeypatch) -> None:
    """Combined patch must cover broker and result-backend pools."""

    class FakeChannel:
        """Stand-in for kombu.transport.redis.Channel."""

        _mindgraph_kombu_pool_patch_applied = False
        keyprefix_fanout = "/{db}."

        def _connparams(self, asynchronous=False):
            _ = asynchronous
            return {"db": 0}

    class FakeBackend:
        """Stand-in for celery.backends.redis.RedisBackend."""

        _mindgraph_result_pool_patch_applied = False

        def _get_pool(self, **params):
            _ = params
            return "original"

    fake_module = SimpleNamespace(
        Channel=FakeChannel,
        redis=SimpleNamespace(ConnectionPool=lambda **kwargs: "pool"),
    )
    monkeypatch.setitem(sys.modules, "kombu.transport.redis", fake_module)
    monkeypatch.setattr("config.celery_broker_redis.kombu_redis", fake_module)
    monkeypatch.setattr("config.celery_broker_redis.CeleryRedisBackend", FakeBackend)

    patch_celery_redis_pools()
    assert getattr(FakeChannel, "_mindgraph_kombu_pool_patch_applied") is True
    assert getattr(FakeBackend, "_mindgraph_result_pool_patch_applied") is True
