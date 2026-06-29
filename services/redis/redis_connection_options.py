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

Celery/kombu broker pools use RESP2 only (see ``config.celery_broker_redis``);
the broker does not need RESP3 and RESP2 avoids the SCH probe entirely.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import inspect
import os
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


def enable_resp3_default() -> bool:
    """RESP3 is on unless explicitly disabled (Redis 6+ required for HELLO)."""
    return os.getenv("REDIS_RESP3", "true").strip().lower() in {"1", "true", "yes", "on"}


def redis_connection_options() -> dict[str, Any]:
    """Return kwargs for sync ``Redis()`` / ``from_url()`` that skip SCH probing."""
    opts: dict[str, Any] = {"maint_notifications_config": _DISABLED_MAINT_NOTIFICATIONS}
    if enable_resp3_default():
        opts["protocol"] = 3
    else:
        opts["protocol"] = 2
    return opts


def redis_async_connection_options() -> dict[str, Any]:
    """Return kwargs for ``redis.asyncio.from_url()`` when supported by redis-py."""
    if _ASYNC_MAINT_NOTIFICATIONS_SUPPORTED:
        return {"maint_notifications_config": _DISABLED_MAINT_NOTIFICATIONS}
    return {}
