"""
Workshop Cleanup Scheduler

Periodic cleanup of expired workshop sessions.
Removes workshop codes from database when Redis keys expire.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from services.online_collab.core.online_collab_manager import (
    get_online_collab_manager,
)

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_HOURS = 6
CLEANUP_INTERVAL_SECONDS = CLEANUP_INTERVAL_HOURS * 3600


async def start_online_collab_cleanup_scheduler(
    interval_hours: float = CLEANUP_INTERVAL_HOURS,
) -> None:
    """Start periodic cleanup of expired workshop sessions.

    Args:
        interval_hours: Hours between cleanup runs (default: 6 hours)
    """
    interval_seconds = interval_hours * 3600

    logger.info(
        "[OnlineCollabCleanup] Starting workshop cleanup scheduler (interval: %s hours)",
        interval_hours,
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            logger.info("[OnlineCollabCleanup] Running cleanup of expired workshops...")
            start_time = datetime.now(tz=UTC)
            cleaned_count = await (
                get_online_collab_manager().cleanup_expired_online_collabs()
            )

            duration = (datetime.now(tz=UTC) - start_time).total_seconds()

            if cleaned_count > 0:
                logger.info(
                    "[OnlineCollabCleanup] Cleanup completed: removed %d expired workshop(s) in %.2f seconds",
                    cleaned_count,
                    duration,
                )
            else:
                logger.debug(
                    "[OnlineCollabCleanup] Cleanup completed: no expired workshops found (took %.2f seconds)",
                    duration,
                )

        except asyncio.CancelledError:
            logger.info("[OnlineCollabCleanup] Cleanup scheduler cancelled")
            break
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as exc:
            logger.error(
                "[OnlineCollabCleanup] Error in cleanup scheduler: %s",
                exc,
                exc_info=True,
            )
            await asyncio.sleep(60)
