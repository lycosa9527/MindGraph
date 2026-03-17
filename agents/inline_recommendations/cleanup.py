"""
Inline Recommendations Cleanup Scheduler
========================================

Periodic cleanup of stale inline recommendation sessions.
Removes session state older than TTL when client never called cleanup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import asyncio
import logging

from agents.inline_recommendations.generator import get_inline_recommendations_generator

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 1800
CLEANUP_INTERVAL_MINUTES = 30


async def start_inline_rec_cleanup_scheduler(
    interval_minutes: int = CLEANUP_INTERVAL_MINUTES,
) -> None:
    """
    Start periodic cleanup of stale inline recommendation sessions.

    Args:
        interval_minutes: Minutes between cleanup runs (default: 30)
    """
    interval_seconds = interval_minutes * 60

    logger.info(
        "[InlineRecCleanup] Starting cleanup scheduler (interval: %s min)",
        interval_minutes,
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            generator = get_inline_recommendations_generator()
            pruned = generator.prune_stale_sessions(max_age_seconds=SESSION_TTL_SECONDS)

            if pruned > 0:
                logger.info(
                    "[InlineRecCleanup] Pruned %d stale session(s)",
                    pruned,
                )
            else:
                logger.debug("[InlineRecCleanup] No stale sessions found")

        except asyncio.CancelledError:
            logger.info("[InlineRecCleanup] Cleanup scheduler cancelled")
            break
        except Exception as e:
            logger.error(
                "[InlineRecCleanup] Error in cleanup scheduler: %s",
                e,
                exc_info=True,
            )
            await asyncio.sleep(60)
