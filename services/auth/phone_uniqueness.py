"""
Authoritative phone and email uniqueness checks (global scope).

Uses a short-lived system RLS session so lookups see all users regardless of
the caller's authenticated or panel session mode.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from models.domain.auth import User
from utils.auth.bayi_mode import canonical_bayi_subject
from utils.db.session_open import system_rls_session


def _stored_phone_clause(phone: str) -> ColumnElement[bool]:
    """Match the stored account key. A 小致 userId matches every spelling of that UUID."""
    key = canonical_bayi_subject(phone)
    exact = User.phone == key
    try:
        UUID(key)
    except (ValueError, AttributeError, TypeError):
        return exact
    return or_(exact, func.lower(User.phone) == key)


async def any_user_id_with_phone(phone: str) -> Optional[int]:
    """
    If any user has this phone, return that user's id; otherwise None.
    """
    async with system_rls_session() as db:
        row = (await db.execute(select(User.id).where(_stored_phone_clause(phone)).limit(1))).scalar_one_or_none()
    if row is None:
        return None
    return int(row)


async def other_user_id_with_phone(phone: str, exclude_user_id: int) -> Optional[int]:
    """
    If another user already has this phone, return that user's id; otherwise None.
    """
    async with system_rls_session() as db:
        row = (
            await db.execute(select(User.id).where(_stored_phone_clause(phone), User.id != exclude_user_id).limit(1))
        ).scalar_one_or_none()
    if row is None:
        return None
    return int(row)


async def other_user_id_with_email(email: str, exclude_user_id: int) -> Optional[int]:
    """If another user already has this email, return that user's id; otherwise None."""
    async with system_rls_session() as db:
        row = (
            await db.execute(select(User.id).where(User.email == email, User.id != exclude_user_id).limit(1))
        ).scalar_one_or_none()
    if row is None:
        return None
    return int(row)


async def any_user_id_with_email(email: str) -> Optional[int]:
    """If any user has this email, return that user's id; otherwise None."""
    async with system_rls_session() as db:
        row = (await db.execute(select(User.id).where(User.email == email).limit(1))).scalar_one_or_none()
    if row is None:
        return None
    return int(row)
