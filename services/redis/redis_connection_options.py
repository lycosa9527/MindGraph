"""
Shared redis-py connection options for MindGraph.
=================================================

MindGraph targets standard OSS Redis. redis-py 8 treats an unset protocol as
RESP3-capable and, by default, probes ``CLIENT MAINT_NOTIFICATIONS`` (Smart
Client Handoffs for Redis Cloud / Redis Software). OSS servers do not
implement that command, so we disable the probe on sync clients we create.

redis-py 8.0.0 accepts ``maint_notifications_config`` on sync
``redis.connection.AbstractConnection`` but not yet on
``redis.asyncio.connection.AbstractConnection``; async pools must omit the
kwarg until upstream adds parity.
"""

from __future__ import annotations

import inspect
from typing import Any

from redis.asyncio.connection import AbstractConnection as AsyncAbstractConnection
from redis.maint_notifications import MaintNotificationsConfig

_DISABLED_MAINT_NOTIFICATIONS = MaintNotificationsConfig(enabled=False)

_ASYNC_MAINT_NOTIFICATIONS_SUPPORTED = (
    "maint_notifications_config" in inspect.signature(AsyncAbstractConnection.__init__).parameters
)


def async_maint_notifications_supported() -> bool:
    """Return True when redis.asyncio connections accept SCH disable kwargs."""
    return _ASYNC_MAINT_NOTIFICATIONS_SUPPORTED


def redis_connection_options() -> dict[str, Any]:
    """Return kwargs for sync ``Redis()`` / ``from_url()`` that skip SCH probing."""
    return {"maint_notifications_config": _DISABLED_MAINT_NOTIFICATIONS}


def redis_async_connection_options() -> dict[str, Any]:
    """Return kwargs for ``redis.asyncio.from_url()`` when supported by redis-py."""
    if _ASYNC_MAINT_NOTIFICATIONS_SUPPORTED:
        return {"maint_notifications_config": _DISABLED_MAINT_NOTIFICATIONS}
    return {}
