"""
Redis and WebSocket fan-out listener wiring for application lifespan.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os

from services.features.ws_redis_fanout_listener import (
    await_ws_fanout_listener_stopped,
    start_ws_fanout_listener,
    stop_ws_fanout_listener,
)
from services.infrastructure.monitoring.critical_alert import CriticalAlertService
from services.infrastructure.security.abuseipdb_service import (
    warm_sismember_cache_ttl_snapshot,
)
from services.infrastructure.security.ip_reputation_env_snapshot import (
    log_ip_reputation_startup_summary,
    warm_ip_reputation_env_snapshot,
)
from services.redis.redis_client import RedisStartupError, close_redis_sync, init_redis_sync

logger = logging.getLogger(__name__)


class CollabProductionGuardError(RuntimeError):
    """Raised when required production collab security settings are missing."""


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _validate_collab_production_guards() -> None:
    if os.getenv("ENVIRONMENT", "production").strip().lower() != "production":
        return

    required = {
        "COLLAB_WS_ALLOWED_ORIGINS": os.getenv("COLLAB_WS_ALLOWED_ORIGINS", ""),
        "COLLAB_FANOUT_ORIGIN_SECRET": os.getenv("COLLAB_FANOUT_ORIGIN_SECRET", ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if not missing:
        return

    message = (
        "Missing required production collaboration settings: "
        + ", ".join(missing)
    )
    logger.critical("[LIFESPAN] %s", message)
    if _env_truthy("COLLAB_STRICT_PROD_GUARDS", "1"):
        raise CollabProductionGuardError(message)


async def lifespan_init_redis_phase(is_main_worker: bool) -> None:
    """Initialize Redis and start the WS fan-out subscriber in the running loop."""
    if is_main_worker:
        logger.debug("[LIFESPAN] Initializing Redis...")
    try:
        init_redis_sync()
        _validate_collab_production_guards()
        warm_ip_reputation_env_snapshot()
        warm_sismember_cache_ttl_snapshot()
        if is_main_worker:
            log_ip_reputation_startup_summary()
        if is_main_worker:
            logger.debug("Redis initialized successfully")
        try:
            loop = asyncio.get_running_loop()
            start_ws_fanout_listener(loop)
        except Exception as ws_fan_exc:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning(
                    "[LIFESPAN] WebSocket Redis fan-out listener: %s",
                    ws_fan_exc,
                )
        if is_main_worker:
            try:
                from services.redis.redis_async_client import get_async_redis  # pylint: disable=import-outside-toplevel
                from services.online_collab.redis.online_collab_redis_health import (  # pylint: disable=import-outside-toplevel
                    check_online_collab_redis_durability,
                    check_online_collab_redis_version,
                )

                redis_async = get_async_redis()
                await check_online_collab_redis_version(redis_async)
                await check_online_collab_redis_durability(redis_async)
            except Exception as health_exc:  # pylint: disable=broad-except
                logger.warning(
                    "[LIFESPAN] Workshop Redis durability check skipped: %s",
                    health_exc,
                )
    except (RedisStartupError, CollabProductionGuardError) as exc:
        component = "CollabConfig" if isinstance(exc, CollabProductionGuardError) else "Redis"
        try:
            CriticalAlertService.send_startup_failure_alert_sync(
                component=component,
                error_message=f"{component} startup failed: {str(exc)}",
                details=(
                    "Application cannot start until required production "
                    "configuration is present."
                    if isinstance(exc, CollabProductionGuardError)
                    else "Application cannot start without Redis. Check Redis "
                    "connection and configuration."
                ),
            )
        except Exception as alert_error:  # pylint: disable=broad-except
            logger.error("Failed to send startup failure alert: %s", alert_error)
        logger.error("Application startup failed. Exiting.")
        os._exit(1)  # pylint: disable=protected-access


async def stop_fanout_listeners(is_main_worker: bool) -> None:
    """Stop Redis pub/sub and PG NOTIFY fanout listeners during shutdown."""
    try:
        stop_ws_fanout_listener()
        await await_ws_fanout_listener_stopped(timeout=5.0)
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to stop WebSocket fan-out listener: %s", exc)
    try:
        from services.features.ws_pg_notify_fanout import (  # pylint: disable=import-outside-toplevel
            stop_pg_notify_listener,
        )

        stop_pg_notify_listener()
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to stop PG NOTIFY listener: %s", exc)


def close_redis_connection(is_main_worker: bool) -> None:
    """Close the global sync Redis client."""
    try:
        close_redis_sync()
        if is_main_worker:
            logger.info("Redis connection closed")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to close Redis: %s", exc)
