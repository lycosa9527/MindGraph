"""Build admin / school-dashboard user list rows with usage and entitlement fields."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sa_count

from models.domain.auth import Organization, User
from models.domain.diagrams import Diagram
from models.domain.markets import MarketEntitlement, MarketSubscription
from routers.auth.helpers import utc_to_beijing_iso
from utils.auth.org_subscription import effective_school_tier_for_org
from utils.auth.role_constants import normalize_role
from utils.auth.school_tier import (
    is_unlimited_diagram_limit,
    max_diagrams_for_tier,
    SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED,
)

_ACTIVE_SUBSCRIPTION_STATUSES = ("pending", "active", "past_due")


def _paid_benefit_from_organization(org: Organization) -> dict[str, Any]:
    """School B2B subscription end; null org expires_at means no expiry date set (permanent)."""
    expires_at = getattr(org, "expires_at", None)
    if expires_at is None:
        return {"expires_at": None, "permanent": True}
    return {"expires_at": expires_at, "permanent": False}


def _resolve_paid_benefit(
    user: User,
    org: Optional[Organization],
    market_paid_benefit: dict[str, Any],
) -> dict[str, Any]:
    """Org service subscription for affiliated users; consumer market rows otherwise."""
    if user.organization_id:
        if org is not None:
            return _paid_benefit_from_organization(org)
        return {"expires_at": None, "permanent": False}
    return market_paid_benefit


def _mask_phone(phone: Optional[str]) -> Optional[str]:
    if phone and len(phone) == 11:
        return phone[:3] + "****" + phone[-4:]
    return phone


def _max_diagrams_for_user(user: User, org: Optional[Organization]) -> int:
    if org is None:
        return SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED
    tier = effective_school_tier_for_org(org)
    return max_diagrams_for_tier(tier)


def diagram_quota_from_count(
    diagram_count: int,
    max_diagrams: int = SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED,
) -> dict[str, int]:
    """Diagram slot usage for one user (admin detail / list enrichment)."""
    if is_unlimited_diagram_limit(max_diagrams):
        return {
            "diagram_count": diagram_count,
            "diagram_quota_max": SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED,
            "diagram_remaining": SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED,
        }
    remaining = max(0, max_diagrams - diagram_count)
    return {
        "diagram_count": diagram_count,
        "diagram_quota_max": max_diagrams,
        "diagram_remaining": remaining,
    }


async def diagram_quota_for_user(db: AsyncSession, user_id: int) -> dict[str, int]:
    counts = await _diagram_counts_by_user(db, [user_id])
    return diagram_quota_from_count(counts.get(user_id, 0))


def build_admin_user_detail_payload(
    user: User,
    org: Optional[Organization],
    diagram_count: int,
) -> dict[str, Any]:
    """Serialize one user for admin edit modal (full phone/email, quota fields)."""
    quota = diagram_quota_from_count(diagram_count, _max_diagrams_for_user(user, org))
    return {
        "id": user.id,
        "phone": user.phone,
        "email": getattr(user, "email", None),
        "name": user.name,
        "role": normalize_role(getattr(user, "role", None)),
        "organization_id": user.organization_id,
        "organization_code": org.code if org else None,
        "organization_name": org.name if org else None,
        "school_tier": effective_school_tier_for_org(org) if org else None,
        "locked_until": utc_to_beijing_iso(user.locked_until),
        "created_at": utc_to_beijing_iso(user.created_at),
        "email_login_whitelisted_from_cn": getattr(user, "email_login_whitelisted_from_cn", False),
        **quota,
    }


async def _diagram_counts_by_user(
    db: AsyncSession,
    user_ids: Sequence[int],
) -> dict[int, int]:
    if not user_ids:
        return {}
    stmt = (
        select(Diagram.user_id, sa_count(Diagram.id))
        .where(
            Diagram.user_id.in_(tuple(user_ids)),
            Diagram.is_deleted.is_(False),
        )
        .group_by(Diagram.user_id)
    )
    rows = (await db.execute(stmt)).all()
    return {int(row.user_id): int(row[1] or 0) for row in rows}


async def _paid_benefit_by_user(
    db: AsyncSession,
    user_ids: Sequence[int],
) -> dict[int, dict[str, Any]]:
    """Per user: furthest benefit end time; permanent if any active row has null expiry."""
    if not user_ids:
        return {}
    now = datetime.now(UTC).replace(tzinfo=None)
    result: dict[int, dict[str, Any]] = {int(uid): {"expires_at": None, "permanent": False} for uid in user_ids}

    ent_stmt = select(MarketEntitlement.user_id, MarketEntitlement.expires_at).where(
        MarketEntitlement.user_id.in_(tuple(user_ids)),
        or_(MarketEntitlement.expires_at.is_(None), MarketEntitlement.expires_at > now),
    )
    for row in (await db.execute(ent_stmt)).all():
        uid = int(row.user_id)
        entry = result[uid]
        exp = row.expires_at
        if exp is None:
            entry["permanent"] = True
            entry["expires_at"] = None
            continue
        current = entry.get("expires_at")
        if current is None and not entry["permanent"]:
            entry["expires_at"] = exp
        elif current is not None and exp > current:
            entry["expires_at"] = exp

    sub_stmt = select(
        MarketSubscription.user_id,
        MarketSubscription.current_period_end,
    ).where(
        MarketSubscription.user_id.in_(tuple(user_ids)),
        MarketSubscription.status.in_(_ACTIVE_SUBSCRIPTION_STATUSES),
        MarketSubscription.current_period_end.isnot(None),
        MarketSubscription.current_period_end > now,
    )
    for row in (await db.execute(sub_stmt)).all():
        uid = int(row.user_id)
        entry = result[uid]
        if entry["permanent"]:
            continue
        period_end = row.current_period_end
        current = entry.get("expires_at")
        if current is None or period_end > current:
            entry["expires_at"] = period_end

    return result


def build_admin_user_list_row(
    user: User,
    org: Optional[Organization],
    token_stats: dict[str, int],
    diagram_count: int,
    paid_benefit: dict[str, Any],
) -> dict[str, Any]:
    """Serialize one user for admin user-management tables."""
    max_diagrams = _max_diagrams_for_user(user, org)
    if is_unlimited_diagram_limit(max_diagrams):
        remaining = SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED
    else:
        remaining = max(0, max_diagrams - diagram_count)
    effective_benefit = _resolve_paid_benefit(user, org, paid_benefit)
    permanent = bool(effective_benefit.get("permanent"))
    benefit_dt = effective_benefit.get("expires_at")
    return {
        "id": user.id,
        "phone": _mask_phone(user.phone),
        "name": user.name,
        "role": normalize_role(getattr(user, "role", None)),
        "organization_id": user.organization_id,
        "organization_code": org.code if org else None,
        "organization_name": org.name if org else None,
        "school_tier": effective_school_tier_for_org(org) if org else None,
        "locked_until": utc_to_beijing_iso(user.locked_until),
        "created_at": utc_to_beijing_iso(user.created_at),
        "token_stats": token_stats,
        "diagram_count": diagram_count,
        "diagram_quota_max": max_diagrams,
        "diagram_remaining": remaining,
        "paid_benefit_permanent": permanent,
        "paid_benefit_expires_at": None if permanent else utc_to_beijing_iso(benefit_dt),
        "email_login_whitelisted_from_cn": getattr(user, "email_login_whitelisted_from_cn", False),
    }


async def enrich_admin_user_list_rows(
    db: AsyncSession,
    users: Sequence[User],
    organizations_by_id: dict[int, Organization],
    token_stats_by_user: dict[int, dict[str, int]],
) -> list[dict[str, Any]]:
    """Attach diagram quota and paid-benefit fields for a page of users."""
    user_ids = [int(user.id) for user in users]
    diagram_counts = await _diagram_counts_by_user(db, user_ids)
    paid_benefits = await _paid_benefit_by_user(db, user_ids)
    rows: list[dict[str, Any]] = []
    for user in users:
        uid = int(user.id)
        org = organizations_by_id.get(user.organization_id) if user.organization_id else None
        token_stats = token_stats_by_user.get(
            uid,
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        rows.append(
            build_admin_user_list_row(
                user,
                org,
                token_stats,
                diagram_counts.get(uid, 0),
                paid_benefits.get(uid, {"expires_at": None, "permanent": False}),
            )
        )
    return rows
