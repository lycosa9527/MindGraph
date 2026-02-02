"""
Workshop Cleanup Scheduler
==========================

Periodic cleanup of expired workshop sessions.
Removes workshop codes from database when Redis keys expire.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
from datetime import datetime

from services.workshop import workshop_service

logger = logging.getLogger(__name__)

# Cleanup interval: every 6 hours
CLEANUP_INTERVAL_HOURS = 6
CLEANUP_INTERVAL_SECONDS = CLEANUP_INTERVAL_HOURS * 3600


async def start_workshop_cleanup_scheduler(interval_hours: float = CLEANUP_INTERVAL_HOURS) -> None:
    """
    Start periodic cleanup of expired workshop sessions.

    Args:
        interval_hours: Hours between cleanup runs (default: 6 hours)
    """
    interval_seconds = interval_hours * 3600

    logger.info(
        "[WorkshopCleanup] Starting workshop cleanup scheduler "
        "(interval: %s hours)",
        interval_hours,
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            logger.info("[WorkshopCleanup] Running cleanup of expired workshops...")
            start_time = datetime.utcnow()

            cleaned_count = await workshop_service.cleanup_expired_workshops()

            duration = (datetime.utcnow() - start_time).total_seconds()

            if cleaned_count > 0:
                logger.info(
                    "[WorkshopCleanup] Cleanup completed: removed %d expired workshop(s) "
                    "in %.2f seconds",
                    cleaned_count,
                    duration,
                )
            else:
                logger.debug(
                    "[WorkshopCleanup] Cleanup completed: no expired workshops found "
                    "(took %.2f seconds)",
                    duration,
                )

        except asyncio.CancelledError:
            logger.info("[WorkshopCleanup] Cleanup scheduler cancelled")
            break
        except Exception as e:
            logger.error(
                "[WorkshopCleanup] Error in cleanup scheduler: %s",
                e,
                exc_info=True,
            )
            # Continue running even if one cleanup fails
            await asyncio.sleep(60)  # Wait 1 minute before retrying
