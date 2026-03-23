"""
Persist workshop chat org-presence disconnect time for org roster / last-seen.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.domain.auth import User as UserModel

logger = logging.getLogger(__name__)


def record_workshop_last_seen(db: Session, user_id: int) -> None:
    """Set workshop_last_seen_at to now (UTC) for the given user."""
    try:
        row = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not row:
            return
        row.workshop_last_seen_at = datetime.utcnow()
        db.commit()
    except SQLAlchemyError as exc:
        logger.debug("[WorkshopLastSeen] record failed user_id=%s: %s", user_id, exc)
        db.rollback()
