"""
Celery/kombu Redis pool defaults.
=================================

Celery uses kombu (broker) and ``celery.backends.redis`` (result store), both
of which build ``redis.ConnectionPool`` without MindGraph's
:func:`services.redis.redis_connection_options.redis_connection_options`.
redis-py 8 treats an unset protocol as RESP3 and probes
``CLIENT MAINT_NOTIFICATIONS`` (Redis Cloud SCH). OSS Redis does not implement
that command, so we force RESP2 and disable the probe on both pools.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.redis.redis_connection_options import celery_redis_pool_options

try:
    from kombu.transport import redis as kombu_redis
except ImportError:
    kombu_redis = None

try:
    from celery.backends.redis import RedisBackend as CeleryRedisBackend
except ImportError:
    CeleryRedisBackend = None


def patch_kombu_redis_connection_pool() -> None:
    """Force RESP2 and disable SCH on kombu ``ConnectionPool`` (Celery broker)."""
    if kombu_redis is None:
        return

    broker_redis = kombu_redis.redis
    channel_cls = kombu_redis.Channel
    if getattr(channel_cls, "_mindgraph_kombu_pool_patch_applied", False):
        return

    original_connparams = getattr(channel_cls, "_connparams")

    def get_pool_with_resp2(self, asynchronous=False):
        params = original_connparams(self, asynchronous=asynchronous)
        params.update(celery_redis_pool_options())
        self.keyprefix_fanout = self.keyprefix_fanout.format(db=params["db"])
        return broker_redis.ConnectionPool(**params)

    setattr(channel_cls, "_get_pool", get_pool_with_resp2)
    setattr(channel_cls, "_mindgraph_kombu_pool_patch_applied", True)


def patch_celery_redis_result_backend() -> None:
    """Force RESP2 and disable SCH on Celery Redis result-backend pools."""
    if CeleryRedisBackend is None:
        return
    if getattr(CeleryRedisBackend, "_mindgraph_result_pool_patch_applied", False):
        return

    original_get_pool = getattr(CeleryRedisBackend, "_get_pool")

    def get_pool_with_oss_opts(self, **params):
        params.update(celery_redis_pool_options())
        return original_get_pool(self, **params)

    setattr(CeleryRedisBackend, "_get_pool", get_pool_with_oss_opts)
    setattr(CeleryRedisBackend, "_mindgraph_result_pool_patch_applied", True)


def patch_celery_redis_pools() -> None:
    """Apply OSS Redis pool defaults to Celery broker and result backend."""
    patch_kombu_redis_connection_pool()
    patch_celery_redis_result_backend()
