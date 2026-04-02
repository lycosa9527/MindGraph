"""
DB + Redis cleanup for expired workshop sessions (called by scheduler).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from sqlalchemy import select

from config.database import AsyncSessionLocal
from models.domain.diagrams import Diagram
from services.redis.redis_client import get_redis
from services.workshop.workshop_expiry import is_workshop_expired
from services.workshop.workshop_redis_keys import purge_workshop_redis_keys
from services.workshop.workshop_session_fields import (
    backfill_workshop_expiry_if_needed,
    clear_workshop_session_fields,
)

logger = logging.getLogger(__name__)


async def cleanup_expired_workshops_impl() -> int:
    """
    Clear diagrams whose ``workshop_expires_at`` is in the past.
    """
    redis = get_redis()
    if not redis:
        logger.error("[WorkshopCleanup] Redis client not available")
        return 0

    cleaned_count = 0
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Diagram).filter(
                    Diagram.workshop_code.isnot(None),
                    ~Diagram.is_deleted,
                )
            )
            diagrams_with_workshop = result.scalars().all()

            for diagram in diagrams_with_workshop:
                code = diagram.workshop_code
                if code is None:
                    continue
                await backfill_workshop_expiry_if_needed(diagram, db)
                if not diagram.workshop_expires_at or not is_workshop_expired(diagram.workshop_expires_at):
                    continue
                purge_workshop_redis_keys(redis, code)
                clear_workshop_session_fields(diagram)
                cleaned_count += 1
                logger.info(
                    "[WorkshopCleanup] Cleaned up expired workshop %s for diagram %s",
                    code,
                    diagram.id,
                )

            if cleaned_count > 0:
                await db.commit()
                logger.info(
                    "[WorkshopCleanup] Cleaned up %d expired workshop(s)",
                    cleaned_count,
                )

        except Exception as exc:
            logger.error(
                "[WorkshopCleanup] Error cleaning up expired workshops: %s",
                exc,
                exc_info=True,
            )
            await db.rollback()

    return cleaned_count
