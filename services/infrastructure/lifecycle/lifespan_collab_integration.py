"""
Online collaboration / workshop background tasks wired from application lifespan.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

from services.online_collab import start_online_collab_cleanup_scheduler
from services.online_collab.core.online_collab_manager import start_online_collab_manager
from services.online_collab.redis.online_collab_redis_scripts import (
    load_scripts_if_available as load_collab_scripts,
)

logger = logging.getLogger(__name__)


async def start_online_collab_subsystem_async(
    is_main_worker: bool,
) -> Tuple[Optional[asyncio.Task], Optional[asyncio.Task]]:
    """
    Start online-collab background tasks and return handles for shutdown.

    Returns (workshop_cleanup_task, session_manager_task).
    """
    workshop_cleanup_task: Optional[asyncio.Task] = None
    try:
        workshop_cleanup_task = asyncio.create_task(
            start_online_collab_cleanup_scheduler(interval_hours=6),
        )
        if is_main_worker:
            logger.debug("Workshop cleanup scheduler started")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start workshop cleanup scheduler: %s", exc)

    await load_collab_scripts()

    try:
        from services.online_collab.redis.online_collab_redis_locks import (  # pylint: disable=import-outside-toplevel
            ensure_online_collab_functions_loaded,
        )
        from services.redis.redis_async_client import get_async_redis  # pylint: disable=import-outside-toplevel

        await ensure_online_collab_functions_loaded(get_async_redis())
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.debug("Redis workshop FUNCTION preload skipped: %s", exc)

    try:
        from services.online_collab.redis.redis8_features import (  # pylint: disable=import-outside-toplevel
            enable_client_tracking,
        )
        from services.redis.redis_async_client import get_async_redis  # pylint: disable=import-outside-toplevel

        await enable_client_tracking(get_async_redis())
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.debug("CLIENT TRACKING opt-in skipped: %s", exc)

    session_manager_task: Optional[asyncio.Task] = None
    try:
        session_manager_task = start_online_collab_manager()
        if is_main_worker:
            logger.debug("Workshop session manager idle monitor started")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start workshop session manager: %s", exc)

    try:
        from services.features.ws_pg_notify_fanout import (  # pylint: disable=import-outside-toplevel
            start_pg_notify_listener,
        )

        start_pg_notify_listener()
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start PG NOTIFY listener: %s", exc)

    return workshop_cleanup_task, session_manager_task
