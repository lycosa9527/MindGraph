"""
Database initialization and post-migration warmup for application lifespan.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from config.database import init_db
from services.auth.ip_geolocation import get_geolocation_service
from services.infrastructure.monitoring.critical_alert import CriticalAlertService
from services.infrastructure.recovery.recovery_startup import (
    check_database_on_startup,
    cleanup_incomplete_chunk_operations,
)
from services.redis.cache.redis_cache_loader import reload_cache_from_database
from services.redis.redis_bayi_whitelist import get_bayi_whitelist
from utils.auth import AUTH_MODE, display_demo_info

logger = logging.getLogger(__name__)


async def lifespan_startup_database_phase(is_main_worker: bool) -> None:
    """
    Run DB integrity checks, migrations, chunk recovery, cache preload.

    Mirrors the former inlined block in lifespan.py before LLM initialization.
    """
    if is_main_worker:
        logger.debug("[LIFESPAN] Initializing database...")
    if is_main_worker:
        logger.debug("[LIFESPAN] Checking database integrity...")
    if not await check_database_on_startup():
        if is_main_worker:
            logger.critical("Database recovery failed or was aborted. Shutting down.")
        try:
            CriticalAlertService.send_startup_failure_alert_sync(
                component="Database",
                error_message="Database recovery failed or was aborted",
                details=(
                    "Database integrity check failed and recovery was not successful. "
                    "Manual intervention required."
                ),
            )
        except Exception as alert_error:  # pylint: disable=broad-except
            if is_main_worker:
                logger.error("Failed to send startup failure alert: %s", alert_error)
        raise SystemExit(1)
    if is_main_worker:
        logger.debug("Database integrity verified")

    try:
        init_db()
    except Exception as init_exc:
        logger.critical(
            "[LIFESPAN] Database schema initialization failed (init_db): %s",
            init_exc,
            exc_info=True,
        )
        try:
            CriticalAlertService.send_startup_failure_alert_sync(
                component="Database",
                error_message=f"init_db failed: {init_exc}",
                details=(
                    "Table creation or migrations failed. Verify the PostgreSQL user can "
                    "CREATE tables on the database and DATABASE_URL points at the "
                    "intended database."
                ),
            )
        except Exception as alert_error:  # pylint: disable=broad-except
            if is_main_worker:
                logger.error("Failed to send startup failure alert: %s", alert_error)
        raise SystemExit(1) from init_exc

    logger.debug("[LIFESPAN] Cleaning up incomplete chunk test operations (post-migration)...")
    cleaned_chunk = await cleanup_incomplete_chunk_operations()
    if cleaned_chunk > 0 and is_main_worker:
        logger.info(
            "[Recovery] Cleaned up %d incomplete chunk operation(s) from kill -9",
            cleaned_chunk,
        )

    if is_main_worker:
        logger.debug("Database initialized successfully")
        display_demo_info()

    try:
        try:
            library_dir = Path(os.getenv("LIBRARY_STORAGE_DIR", "./storage/library"))
            library_dir.mkdir(parents=True, exist_ok=True)
            (library_dir / "covers").mkdir(parents=True, exist_ok=True)
            if is_main_worker:
                logger.debug("[LIFESPAN] Library storage ready: %s", library_dir.resolve())
        except Exception as lib_dir_exc:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning(
                    "[LIFESPAN] Could not create library storage directory: %s",
                    lib_dir_exc,
                )

        if is_main_worker:
            logger.debug("[LIFESPAN] Loading cache and IP database...")

        preload_auth_cache = os.getenv("PRELOAD_USER_AUTH_CACHE", "true").lower() in (
            "1",
            "true",
            "yes",
        )

        async def load_user_cache():
            if not preload_auth_cache:
                if is_main_worker:
                    logger.info(
                        "[CacheLoader] User auth cache preloading skipped "
                        "(PRELOAD_USER_AUTH_CACHE disabled)",
                    )
                return True

            try:
                result = await reload_cache_from_database()
                return result
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Failed to load cache from database: %s", exc, exc_info=True)
                return False

        def load_ip_database():
            try:
                geolocation_service = get_geolocation_service()
                if geolocation_service.is_ready():
                    if is_main_worker:
                        logger.info("IP Geolocation Service initialized successfully")
                    return True
                if is_main_worker:
                    logger.warning(
                        "IP Geolocation database not available (database file missing or failed to load)"
                    )
                return False
            except Exception as exc:  # pylint: disable=broad-except
                if is_main_worker:
                    logger.warning("Failed to initialize IP Geolocation Service: %s", exc)
                return False

        cache_result, ip_db_result = await asyncio.gather(
            load_user_cache(),
            asyncio.to_thread(load_ip_database),
            return_exceptions=True,
        )

        if isinstance(cache_result, Exception):
            if is_main_worker:
                logger.error(
                    "Failed to load cache from database: %s",
                    cache_result,
                    exc_info=True,
                )
        elif cache_result:
            if preload_auth_cache and is_main_worker:
                logger.info("[CacheLoader] User cache loading completed successfully")
        elif preload_auth_cache:
            if is_main_worker:
                logger.warning("[CacheLoader] Cache loading returned False - cache may not be preloaded")
                logger.warning(
                    "[CacheLoader] WARNING: User authentication data may not be preloaded into Redis cache"
                )

        if isinstance(ip_db_result, Exception):
            if is_main_worker:
                logger.warning("Failed to initialize IP Geolocation Service: %s", ip_db_result)

        try:
            if AUTH_MODE == "bayi":
                whitelist = get_bayi_whitelist()
                count = await whitelist.load_from_env()
                if count > 0 and is_main_worker:
                    logger.info("Loaded %s IP(s) from BAYI_IP_WHITELIST into Redis", count)
        except Exception as exc:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to load IP whitelist into Redis: %s", exc)
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.error(
                "Failed during post-DB startup (library dirs, cache preload, etc.): %s",
                exc,
                exc_info=True,
            )
