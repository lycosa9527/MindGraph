"""Celery tasks for Showcase teaching-design cover generation."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

from config.celery import celery_app
from services.monitoring.error_reporting import record_exception_from_celery
from services.showcase.covers.events import publish_showcase_cover_event_sync
from services.showcase.covers.generate import generate_showcase_cover
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

# LO convert ≤120s; leave headroom for PNG shrink + COS put + DB.
_SOFT_TIME_LIMIT_SECONDS = 180
_HARD_TIME_LIMIT_SECONDS = 210


@celery_app.task(
    bind=True,
    name="showcase.generate_cover",
    queue="default",
    soft_time_limit=_SOFT_TIME_LIMIT_SECONDS,
    time_limit=_HARD_TIME_LIMIT_SECONDS,
)
def generate_cover_task(
    self,
    post_id: str,
    user_id: int,
    attachment_key: str,
    organization_id: Optional[int] = None,
    author_id: Optional[int] = None,
) -> bool:
    """Render and persist a teaching-design cover for ``post_id``."""
    logger.info(
        "[ShowcaseCoverTask] dispatch post=%s user=%s task=%s",
        post_id[:8] if post_id else "",
        user_id,
        self.request.id,
    )
    try:
        return asyncio.run(
            generate_showcase_cover(
                post_id=post_id,
                user_id=int(user_id),
                attachment_key=attachment_key,
                organization_id=organization_id,
                author_id=int(author_id) if author_id is not None else int(user_id),
            )
        )
    except SoftTimeLimitExceeded as exc:
        logger.error(
            "[ShowcaseCoverTask] post=%s soft time limit: %s",
            post_id[:8] if post_id else "",
            exc,
            exc_info=True,
        )
        publish_showcase_cover_event_sync(
            post_id,
            "cover_fail",
            reason="soft_time_limit",
        )
        record_exception_from_celery(
            source="background",
            component="ShowcaseCoverTask",
            exc=exc,
            tags={"post_id": post_id, "user_id": user_id},
        )
        return False
    except TimeLimitExceeded as exc:
        logger.error(
            "[ShowcaseCoverTask] post=%s hard time limit: %s",
            post_id[:8] if post_id else "",
            exc,
            exc_info=True,
        )
        publish_showcase_cover_event_sync(
            post_id,
            "cover_fail",
            reason="hard_time_limit",
        )
        record_exception_from_celery(
            source="background",
            component="ShowcaseCoverTask",
            exc=exc,
            tags={"post_id": post_id, "user_id": user_id},
        )
        raise
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error(
            "[ShowcaseCoverTask] post=%s failed: %s",
            post_id[:8] if post_id else "",
            exc,
            exc_info=True,
        )
        publish_showcase_cover_event_sync(
            post_id,
            "cover_fail",
            reason=str(exc)[:200],
        )
        record_exception_from_celery(
            source="background",
            component="ShowcaseCoverTask",
            exc=exc,
            tags={"post_id": post_id, "user_id": user_id},
        )
        raise
