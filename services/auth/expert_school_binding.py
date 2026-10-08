"""
Bind platform experts to schools.

A binding is a row in ``organization_expert_bindings``. One expert may be
bound to many schools at once. Saving one school only changes that school's
rows. Schools an expert creates are bound in the same transaction.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, OrganizationExpertBinding, User
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.role_constants import ROLE_EXPERT
from utils.auth.roles import is_expert

logger = logging.getLogger(__name__)

MAX_EXPERT_BINDINGS = 200


class ExpertBindingError(Exception):
    """Binding request that should become an HTTP error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def creator_should_auto_bind(role: str | None) -> bool:
    """Schools created by an expert are bound to that expert."""
    return role == ROLE_EXPERT


def binding_user_ids_to_add(current: set[int], desired: set[int]) -> list[int]:
    """Expert ids to insert for this school. Other schools are not in ``current``."""
    return sorted(desired - current)


def binding_user_ids_to_remove(current: set[int], desired: set[int]) -> list[int]:
    """Expert ids to drop from this school only."""
    return sorted(current - desired)


def _dedupe_user_ids(user_ids: list[int]) -> list[int]:
    """Drop non-positive and repeated ids, preserving order."""
    ordered: list[int] = []
    seen: set[int] = set()
    for raw in user_ids:
        user_id = int(raw)
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        ordered.append(user_id)
    return ordered


async def bound_org_ids_for_user(db: AsyncSession, user: User) -> list[int]:
    """Schools this user is bound to. Non-experts have none."""
    if not is_expert(user):
        return []
    return await list_bound_org_ids(db, int(user.id))


async def list_bound_org_ids(db: AsyncSession, user_id: int) -> list[int]:
    """School ids this user is bound to, lowest id first."""
    rows = await db.execute(
        select(OrganizationExpertBinding.organization_id)
        .where(OrganizationExpertBinding.user_id == int(user_id))
        .order_by(OrganizationExpertBinding.organization_id)
    )
    return [int(org_id) for org_id in rows.scalars().all()]


async def user_is_bound_to_org(db: AsyncSession, user_id: int, org_id: int) -> bool:
    """True when this user has a binding row for the school."""
    row = await db.execute(
        select(OrganizationExpertBinding.user_id).where(
            OrganizationExpertBinding.user_id == int(user_id),
            OrganizationExpertBinding.organization_id == int(org_id),
        )
    )
    return row.scalar_one_or_none() is not None


async def users_linked_by_expert_binding(db: AsyncSession, left: User, right: User) -> bool:
    """True when an expert binding puts these two users in one school.

    Returns immediately when neither user is an expert, so same-org checks
    for teachers do not issue a second query.
    """
    if not is_expert(left) and not is_expert(right):
        return False
    left_org = int(left.organization_id) if left.organization_id is not None else None
    right_org = int(right.organization_id) if right.organization_id is not None else None
    if is_expert(left) and right_org is not None and await user_is_bound_to_org(db, int(left.id), right_org):
        return True
    if is_expert(right) and left_org is not None and await user_is_bound_to_org(db, int(right.id), left_org):
        return True
    if is_expert(left) and is_expert(right):
        left_orgs = set(await list_bound_org_ids(db, int(left.id)))
        if not left_orgs:
            return False
        right_orgs = set(await list_bound_org_ids(db, int(right.id)))
        return bool(left_orgs & right_orgs)
    return False


async def bind_creating_expert(db: AsyncSession, org: Organization, user: User) -> None:
    """Attach the creating expert to the new school. Does not commit."""
    if not creator_should_auto_bind(getattr(user, "role", None)):
        return
    db.add(
        OrganizationExpertBinding(
            organization_id=int(org.id),
            user_id=int(user.id),
        )
    )


async def list_expert_school_binding(
    db: AsyncSession,
    org_id: int,
    *,
    include_all_experts: bool,
) -> dict:
    """Bound expert ids plus picker rows.

    Editors receive every expert account. Other readers only see experts
    already bound to this school.
    """
    org = (await db.execute(select(Organization.id).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise ExpertBindingError("organization_not_found")

    bound_rows = await db.execute(
        select(OrganizationExpertBinding.user_id).where(OrganizationExpertBinding.organization_id == org_id)
    )
    bound_user_ids = [int(user_id) for user_id in bound_rows.scalars().all()]

    stmt = select(
        User.id,
        User.name,
        User.phone,
        User.email,
    ).where(User.role == ROLE_EXPERT)
    if not include_all_experts:
        if not bound_user_ids:
            return {"bound_user_ids": [], "experts": []}
        stmt = stmt.where(User.id.in_(bound_user_ids))
    stmt = stmt.order_by(User.name, User.id)
    rows = (await db.execute(stmt)).all()

    experts: list[dict] = []
    bound_set = set(bound_user_ids)
    for row in rows:
        experts.append(
            {
                "id": int(row.id),
                "name": row.name,
                "phone": row.phone,
                "email": row.email,
            }
        )
    ordered_bound = [int(row.id) for row in rows if int(row.id) in bound_set]
    return {"bound_user_ids": ordered_bound, "experts": experts}


async def apply_expert_school_binding(
    db: AsyncSession,
    org_id: int,
    user_ids: list[int],
) -> list[int]:
    """Replace this school's expert bindings. Other schools stay as they are."""
    desired = _dedupe_user_ids(user_ids)
    if len(desired) > MAX_EXPERT_BINDINGS:
        raise ExpertBindingError("too_many")

    org_row = (await db.execute(select(Organization.id).where(Organization.id == org_id))).scalar_one_or_none()
    if org_row is None:
        raise ExpertBindingError("organization_not_found")

    if desired:
        found = {
            int(user_id)
            for user_id in (
                await db.execute(
                    select(User.id).where(User.role == ROLE_EXPERT, User.id.in_(desired)),
                )
            ).scalars()
        }
        if any(user_id not in found for user_id in desired):
            raise ExpertBindingError("not_expert")

    current = {
        int(user_id)
        for user_id in (
            await db.execute(
                select(OrganizationExpertBinding.user_id).where(OrganizationExpertBinding.organization_id == org_id)
            )
        ).scalars()
    }
    desired_set = set(desired)
    to_remove = binding_user_ids_to_remove(current, desired_set)
    to_add = binding_user_ids_to_add(current, desired_set)
    if to_remove:
        await db.execute(
            delete(OrganizationExpertBinding).where(
                OrganizationExpertBinding.organization_id == org_id,
                OrganizationExpertBinding.user_id.in_(to_remove),
            )
        )
    for user_id in to_add:
        db.add(
            OrganizationExpertBinding(
                organization_id=org_id,
                user_id=user_id,
            )
        )

    try:
        await db.commit()
    except DATABASE_ERRORS:
        await db.rollback()
        raise

    logger.info(
        "[ExpertBinding] School %s bindings added %s removed %s",
        org_id,
        to_add,
        to_remove,
    )
    return to_add + to_remove
