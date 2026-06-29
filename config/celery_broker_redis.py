"""
Celery/kombu Redis broker pool defaults.
=======================================

Celery uses kombu, which builds ``redis.ConnectionPool`` without MindGraph's
:func:`services.redis.redis_connection_options.redis_connection_options`.
redis-py 8 defaults to RESP3 and probes ``CLIENT MAINT_NOTIFICATIONS`` (Redis
Cloud SCH).  The broker only needs basic list/pub-sub commands, so we force
RESP2 and avoid that probe entirely.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

try:
    from kombu.transport import redis as kombu_redis
except ImportError:
    kombu_redis = None

KOMBU_BROKER_POOL_OPTS: dict[str, Any] = {"protocol": 2}


def patch_kombu_redis_connection_pool() -> None:
    """Force RESP2 on kombu ``ConnectionPool`` construction (Celery broker)."""
    if kombu_redis is None:
        return

    channel_cls = kombu_redis.Channel
    if getattr(channel_cls, "_mindgraph_kombu_pool_patch_applied", False):
        return

    original_connparams = getattr(channel_cls, "_connparams")

    def get_pool_with_resp2(self, asynchronous=False):
        params = original_connparams(self, asynchronous=asynchronous)
        params.update(KOMBU_BROKER_POOL_OPTS)
        self.keyprefix_fanout = self.keyprefix_fanout.format(db=params["db"])
        return kombu_redis.redis.ConnectionPool(**params)

    setattr(channel_cls, "_get_pool", get_pool_with_resp2)
    setattr(channel_cls, "_mindgraph_kombu_pool_patch_applied", True)
