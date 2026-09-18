"""Admin helpers: search teachers and enrich pilot/class list rows.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from models.domain.auth import Organization, User
from models.domain.learning_space import LearningPilotTeacher
from utils.auth.role_constants import ROLE_STUDENT, db_roles_for_canonical_filter
from utils.auth.roles import is_student
from utils.db.session_open import system_rls_session


def assert_teacher_eligible_for_pilot(teacher: User, organization_id: int) -> None:
    """Raise ValueError when the user cannot be granted Learning Space.

    Product rule: anyone except Learning Space students can be a pilot, as long as
    they belong to the given school organization. Platform role is unrelated.
    """
    if is_student(teacher):
        raise ValueError("Students cannot be pilot teachers")
    if teacher.organization_id is None:
        raise ValueError("Teacher has no organization")
    if int(teacher.organization_id) != int(organization_id):
        raise ValueError("Organization does not match teacher")


async def search_teachers_for_pilot(
    db: AsyncSession,
    *,
    query: str,
    organization_id: int | None,
    limit: int = 20,
) -> list[dict]:
    """Find non-student accounts by name/phone/email for pilot onboarding."""
    q = (query or "").strip()
    if not q and organization_id is None:
        return []

    student_roles = tuple(db_roles_for_canonical_filter(ROLE_STUDENT))
    conditions: list[ColumnElement[bool]] = [
        User.role.notin_(student_roles),
        User.organization_id.isnot(None),
    ]
    if organization_id is not None:
        conditions.append(User.organization_id == organization_id)
    if q:
        term = f"%{q}%"
        conditions.append((User.name.like(term)) | (User.phone.like(term)) | (User.email.like(term)))

    result = await db.execute(select(User).where(*conditions).order_by(User.id.desc()).limit(max(1, min(limit, 50))))
    users = list(result.scalars().all())
    if not users:
        return []

    org_ids = {int(u.organization_id) for u in users if u.organization_id is not None}
    org_names = await organization_display_map(org_ids)

    pilot_result = await db.execute(
        select(LearningPilotTeacher.teacher_user_id).where(
            LearningPilotTeacher.teacher_user_id.in_([int(u.id) for u in users])
        )
    )
    already_pilot = {int(uid) for (uid,) in pilot_result.all()}

    items: list[dict] = []
    for user in users:
        org_id = int(user.organization_id) if user.organization_id is not None else None
        items.append(
            {
                "id": int(user.id),
                "name": user.name or "",
                "phone": user.phone,
                "email": user.email,
                "role": user.role,
                "organization_id": org_id,
                "organization_name": org_names.get(org_id, "") if org_id is not None else "",
                "already_pilot": int(user.id) in already_pilot,
            }
        )
    return items


def _user_label(name: str | None, phone: str | None, email: str | None) -> str:
    return (name or "").strip() or (phone or "").strip() or (email or "").strip()


def _org_label(name: str | None, display_name: str | None) -> str:
    return (display_name or "").strip() or (name or "").strip()


async def user_display_map(user_ids: set[int]) -> dict[int, str]:
    """Map user id → display label via system RLS (admin label enrichment)."""
    if not user_ids:
        return {}
    async with system_rls_session() as db:
        result = await db.execute(
            select(User.id, User.name, User.phone, User.email).where(User.id.in_(tuple(user_ids)))
        )
        return {int(uid): _user_label(name, phone, email) for uid, name, phone, email in result.all()}


async def organization_display_map(org_ids: set[int]) -> dict[int, str]:
    """Map organization id → name via system RLS (admin label enrichment)."""
    if not org_ids:
        return {}
    async with system_rls_session() as db:
        result = await db.execute(
            select(Organization.id, Organization.name, Organization.display_name).where(
                Organization.id.in_(tuple(org_ids))
            )
        )
        return {int(oid): _org_label(name, display_name) for oid, name, display_name in result.all()}
