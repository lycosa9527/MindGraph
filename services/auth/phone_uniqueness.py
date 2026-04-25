"""
Authoritative phone uniqueness checks on the current database session.

Use these helpers so the check runs in the same transaction as the insert or update
(unlike user_cache lookups, which use a separate session).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User


async def any_user_id_with_phone(
    db: AsyncSession,
    phone: str,
) -> Optional[int]:
    """
    If any user has this phone, return that user's id; otherwise None.
    """
    row = (
        await db.execute(select(User.id).where(User.phone == phone).limit(1))
    ).scalar_one_or_none()
    if row is None:
        return None
    return int(row)


async def other_user_id_with_phone(
    db: AsyncSession,
    phone: str,
    exclude_user_id: int,
) -> Optional[int]:
    """
    If another user already has this phone, return that user's id; otherwise None.
    """
    row = (
        await db.execute(
            select(User.id)
            .where(User.phone == phone, User.id != exclude_user_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return int(row)
