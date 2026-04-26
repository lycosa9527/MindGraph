"""Admin Statistics Endpoints.

Admin-only statistics endpoints:
- GET /admin/stats - Get system statistics
- GET /admin/token-stats - Get detailed token usage statistics

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import timedelta, timezone
from typing import Optional, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import (
    count as sql_count,
    sum as sa_sum,
    coalesce as sa_coalesce,
)

from config.database import get_async_db
from models.domain.auth import User, Organization
from models.domain.messages import Language, Messages
from models.domain.token_usage import TokenUsage
from services.auth.school_dashboard_logger import (
    get_school_dashboard_logger,
    school_dashboard_extra,
)
from utils.auth import get_current_user, is_admin

from ..dependencies import (
    get_language_dependency,
    require_admin,
    require_admin_or_manager,
)
from ..helpers import get_beijing_now, get_beijing_today_start_utc
from .school_scope import resolve_school_dashboard_org_id

logger = logging.getLogger(__name__)

router = APIRouter()


def _sql_count(column: Any) -> ColumnElement:
    """Helper function to call count for SQLAlchemy queries."""
    return sql_count(column)


@router.get("/admin/status")
async def get_admin_status(current_user: User = Depends(get_current_user)) -> Dict[str, bool]:
    """
    Lightweight endpoint to check if current user is admin.

    This endpoint does NOT require admin access - it returns admin status for any authenticated user.
    Used by frontend to check admin status without making expensive stats queries.

    Returns:
        {"is_admin": true/false}
    """
    return {"is_admin": is_admin(current_user)}


@router.get("/admin/stats", dependencies=[Depends(require_admin)])
async def get_stats_admin(
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    _lang: str = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """Get system statistics (ADMIN ONLY)"""
    total_users = (await db.execute(select(_sql_count(User.id)))).scalar_one()
    total_orgs = (await db.execute(select(_sql_count(Organization.id)))).scalar_one()

    # Performance optimization: Get user counts for all organizations in one GROUP BY query
    # instead of N+1 queries (one per organization)
    users_by_org = {}
    user_counts_query = (
        await db.execute(
            select(Organization.id, Organization.name, _sql_count(User.id).label("user_count"))
            .outerjoin(User, Organization.id == User.organization_id)
            .group_by(Organization.id, Organization.name)
        )
    ).all()

    # Build dictionary with organization name as key
    for count_result in user_counts_query:
        users_by_org[count_result.name] = count_result.user_count

    # Sort by count (highest first)
    users_by_org = dict(sorted(users_by_org.items(), key=lambda x: x[1], reverse=True))

    # Use Beijing time for "today" calculations
    # Convert to UTC for database queries since timestamps are stored in UTC
    beijing_now = get_beijing_now()
    today_start = get_beijing_today_start_utc()
    # Calculate week_ago from today start (00:00:00) to match token-stats endpoint behavior
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = (beijing_today_start - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
    recent_registrations = (
        await db.execute(select(_sql_count(User.id)).where(User.created_at >= today_start))
    ).scalar_one()

    # Token usage stats (this week) - PER USER and PER ORGANIZATION tracking!
    token_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    # Per-organization token usage (for school-level reporting)
    token_stats_by_org = {}

    try:
        # Global token stats for past week
        week_token_stats = (
            await db.execute(
                select(
                    sa_sum(TokenUsage.input_tokens).label("input_tokens"),
                    sa_sum(TokenUsage.output_tokens).label("output_tokens"),
                    sa_sum(TokenUsage.total_tokens).label("total_tokens"),
                ).where(TokenUsage.created_at >= week_ago, TokenUsage.success)
            )
        ).first()

        if week_token_stats:
            token_stats = {
                "input_tokens": int(week_token_stats.input_tokens or 0),
                "output_tokens": int(week_token_stats.output_tokens or 0),
                "total_tokens": int(week_token_stats.total_tokens or 0),
            }

        # Per-organization TOTAL token usage (all time, for active school ranking)
        # Use LEFT JOIN to include organizations with no token usage
        org_token_stats = (
            await db.execute(
                select(
                    Organization.id,
                    Organization.name,
                    sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                    sa_coalesce(_sql_count(TokenUsage.id), 0).label("request_count"),
                )
                .outerjoin(
                    TokenUsage,
                    and_(Organization.id == TokenUsage.organization_id, TokenUsage.success),
                )
                .group_by(Organization.id, Organization.name)
            )
        ).all()

        # Build per-organization stats dictionary
        # Only include organizations that actually have token usage
        for org_stat in org_token_stats:
            if org_stat.request_count and org_stat.request_count > 0:
                token_stats_by_org[org_stat.name] = {
                    "org_id": org_stat.id,
                    "input_tokens": int(org_stat.input_tokens or 0),
                    "output_tokens": int(org_stat.output_tokens or 0),
                    "total_tokens": int(org_stat.total_tokens or 0),
                    "request_count": int(org_stat.request_count or 0),
                }

    except (ImportError, Exception) as e:
        # TokenUsage model doesn't exist yet or table not created - return zeros
        logger.debug("TokenUsage not available yet: %s", e)

    return {
        "total_users": total_users,
        "total_organizations": total_orgs,
        "users_by_org": users_by_org,
        "recent_registrations": recent_registrations,
        "token_stats": token_stats,  # Global token stats
        "token_stats_by_org": token_stats_by_org,  # Per-organization TOTAL token stats (all time)
    }


@router.get("/admin/stats/school", dependencies=[Depends(require_admin_or_manager)])
async def get_school_stats(
    organization_id: Optional[int] = None,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """
    Get school-scoped statistics (ADMIN or MANAGER).

    Managers: organization_id must be their own org (or omitted to use their org).
    Admins: organization_id required to select which school to view.
    """
    effective_org_id = resolve_school_dashboard_org_id(organization_id, current_user, lang)

    org = (
        await db.execute(select(Organization).where(Organization.id == effective_org_id))
    ).scalars().first()
    if not org:
        logger.warning(
            "[SchoolDashboard] organization missing for school stats",
            extra=school_dashboard_extra(
                event="school_stats_org_not_found",
                actor_id=current_user.id,
                org_id=effective_org_id,
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", lang, effective_org_id),
        )

    today_start = get_beijing_today_start_utc()
    beijing_now = get_beijing_now()
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = (beijing_today_start - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)

    total_users = (
        await db.execute(select(_sql_count(User.id)).where(User.organization_id == effective_org_id))
    ).scalar_one()
    recent_registrations = (
        await db.execute(
            select(_sql_count(User.id)).where(
                User.organization_id == effective_org_id,
                User.created_at >= today_start,
            )
        )
    ).scalar_one()

    token_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    token_stats_by_org = {}
    users_by_org = {org.name: total_users}
    top_users = []

    try:
        week_token_stats = (
            await db.execute(
                select(
                    sa_sum(TokenUsage.input_tokens).label("input_tokens"),
                    sa_sum(TokenUsage.output_tokens).label("output_tokens"),
                    sa_sum(TokenUsage.total_tokens).label("total_tokens"),
                ).where(
                    TokenUsage.organization_id == effective_org_id,
                    TokenUsage.created_at >= week_ago,
                    TokenUsage.success,
                )
            )
        ).first()

        if week_token_stats:
            token_stats = {
                "input_tokens": int(week_token_stats.input_tokens or 0),
                "output_tokens": int(week_token_stats.output_tokens or 0),
                "total_tokens": int(week_token_stats.total_tokens or 0),
            }

        org_token_stats = (
            await db.execute(
                select(
                    sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                ).where(TokenUsage.organization_id == effective_org_id, TokenUsage.success)
            )
        ).first()

        if org_token_stats:
            token_stats_by_org[org.name] = {
                "org_id": org.id,
                "input_tokens": int(org_token_stats.input_tokens or 0),
                "output_tokens": int(org_token_stats.output_tokens or 0),
                "total_tokens": int(org_token_stats.total_tokens or 0),
                "request_count": 0,
            }

        top_users_query = (
            await db.execute(
                select(
                    User.id,
                    User.phone,
                    User.name,
                    sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                )
                .outerjoin(TokenUsage, and_(User.id == TokenUsage.user_id, TokenUsage.success))
                .where(User.organization_id == effective_org_id)
                .group_by(User.id, User.phone, User.name)
                .order_by(sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).desc())
                .limit(10)
            )
        ).all()

        top_users = []
        for u in top_users_query:
            masked_phone = u.phone
            if u.phone and len(u.phone) == 11:
                masked_phone = u.phone[:3] + "****" + u.phone[-4:]
            top_users.append(
                {
                    "id": u.id,
                    "phone": masked_phone,
                    "name": u.name or u.phone,
                    "total_tokens": int(u.total_tokens or 0),
                }
            )
    except (ImportError, Exception) as e:
        logger.debug("TokenUsage not available: %s", e)

    return {
        "organization": {
            "id": org.id,
            "name": org.name,
            "code": org.code,
            "invitation_code": org.invitation_code or "",
        },
        "total_users": total_users,
        "recent_registrations": recent_registrations,
        "token_stats": token_stats,
        "token_stats_by_org": token_stats_by_org,
        "users_by_org": users_by_org,
        "top_users": top_users,
    }


@router.get("/admin/stats/school/token-stats", dependencies=[Depends(require_admin_or_manager)])
async def get_school_token_stats(
    request: Request,
    organization_id: Optional[int] = None,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """
    Get token stats for a school (ADMIN or MANAGER).
    Same structure as /admin/token-stats with organization_id filter.
    """
    org_id = resolve_school_dashboard_org_id(organization_id, current_user, lang)
    return await get_token_stats_admin(
        _request=request,
        organization_id=org_id,
        _current_user=current_user,
        db=db,
        lang=lang,
    )


@router.get("/admin/token-stats", dependencies=[Depends(require_admin)])
async def get_token_stats_admin(
    _request: Request,
    organization_id: Optional[int] = None,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """Get detailed token usage statistics (ADMIN ONLY)

    If organization_id is provided, returns stats for that organization only.
    Otherwise returns global stats.

    Returns separate stats for:
    - mindgraph: Diagram generation and related features
    - mindmate: AI assistant (Dify) conversations
    - dingtalk_generations: Counts of successful /api/generate_dingtalk (PNG + markdown) calls
    """
    # Use Beijing time for "today" calculations
    # Convert to UTC for database queries since timestamps are stored in UTC
    beijing_now = get_beijing_now()
    today_start = get_beijing_today_start_utc()
    # Calculate week_ago and month_ago from today start (00:00:00) to match trends endpoint behavior
    # This ensures status cards match graph sums:
    # - "Past Week" = last 7 days from today 00:00:00 (includes today)
    # - "Past Month" = last 30 days from today 00:00:00 (includes today)
    # Example: If today is Jan 15 00:00:00:
    #   - week_ago = Jan 8 00:00:00 UTC
    #   - Query includes: Jan 8, 9, 10, 11, 12, 13, 14, 15 (8 days, including today)
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = (beijing_today_start - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
    month_ago = (beijing_today_start - timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None)

    # Initialize default stats
    today_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    week_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    month_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    total_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    top_users = []

    # Initialize breakdown by service type
    empty_breakdown = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "request_count": 0,
    }
    by_service = {
        "mindgraph": {
            "today": empty_breakdown.copy(),
            "week": empty_breakdown.copy(),
            "month": empty_breakdown.copy(),
            "total": empty_breakdown.copy(),
        },
        "mindmate": {
            "today": empty_breakdown.copy(),
            "week": empty_breakdown.copy(),
            "month": empty_breakdown.copy(),
            "total": empty_breakdown.copy(),
        },
    }
    # Successful POST /api/generate_dingtalk rows (DingTalk PNG + markdown image flow)
    dingtalk_generations = {
        "today": 0,
        "week": 0,
        "month": 0,
        "total": 0,
    }

    # Build base filter for organization if specified
    try:
        org_filter = []
        if organization_id:
            org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalars().first()
            if not org:
                sd_log = get_school_dashboard_logger(
                    logger,
                    actor_id=_current_user.id,
                    org_id=organization_id,
                )
                sd_log.warning(
                    "[SchoolDashboard] organization not found for token stats",
                    extra={"sd_event": "token_stats_org_not_found"},
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=Messages.error("organization_not_found", lang, organization_id),
                )
            org_filter.append(TokenUsage.organization_id == organization_id)

        # Today stats - sum all token usage today (including records with user_id=NULL)
        # Note: This includes API key usage without user_id, so it may be larger than sum of top users
        today_stmt = select(
            sa_sum(TokenUsage.input_tokens).label("input_tokens"),
            sa_sum(TokenUsage.output_tokens).label("output_tokens"),
            sa_sum(TokenUsage.total_tokens).label("total_tokens"),
        ).where(TokenUsage.created_at >= today_start, TokenUsage.success)
        if org_filter:
            today_stmt = today_stmt.where(*org_filter)
        today_token_stats = (await db.execute(today_stmt)).first()

        # Also calculate today stats for authenticated users only (for comparison)
        today_user_stmt = select(
            sa_sum(TokenUsage.input_tokens).label("input_tokens"),
            sa_sum(TokenUsage.output_tokens).label("output_tokens"),
            sa_sum(TokenUsage.total_tokens).label("total_tokens"),
        ).where(
            TokenUsage.created_at >= today_start,
            TokenUsage.success,
            TokenUsage.user_id.isnot(None),
        )
        if org_filter:
            today_user_stmt = today_user_stmt.where(*org_filter)
        today_user_token_stats = (await db.execute(today_user_stmt)).first()

        if today_token_stats:
            today_stats = {
                "input_tokens": int(today_token_stats.input_tokens or 0),
                "output_tokens": int(today_token_stats.output_tokens or 0),
                "total_tokens": int(today_token_stats.total_tokens or 0),
            }

        # Verify consistency: sum of top users should not exceed authenticated user total
        if today_user_token_stats:
            authenticated_total = int(today_user_token_stats.total_tokens or 0)
            all_total = today_stats.get("total_tokens", 0)
            logger.debug(
                "Today token stats - All: %s, Authenticated users only: %s",
                all_total,
                authenticated_total,
            )

            if authenticated_total > all_total:
                logger.warning(
                    "Token count mismatch: Authenticated users (%s) > All users (%s)",
                    authenticated_total,
                    all_total,
                )

        # Past week stats
        week_stmt = select(
            sa_sum(TokenUsage.input_tokens).label("input_tokens"),
            sa_sum(TokenUsage.output_tokens).label("output_tokens"),
            sa_sum(TokenUsage.total_tokens).label("total_tokens"),
        ).where(TokenUsage.created_at >= week_ago, TokenUsage.success)
        if org_filter:
            week_stmt = week_stmt.where(*org_filter)
        week_token_stats = (await db.execute(week_stmt)).first()

        if week_token_stats:
            week_stats = {
                "input_tokens": int(week_token_stats.input_tokens or 0),
                "output_tokens": int(week_token_stats.output_tokens or 0),
                "total_tokens": int(week_token_stats.total_tokens or 0),
            }

        # Past month stats
        month_stmt = select(
            sa_sum(TokenUsage.input_tokens).label("input_tokens"),
            sa_sum(TokenUsage.output_tokens).label("output_tokens"),
            sa_sum(TokenUsage.total_tokens).label("total_tokens"),
        ).where(TokenUsage.created_at >= month_ago, TokenUsage.success)
        if org_filter:
            month_stmt = month_stmt.where(*org_filter)
        month_token_stats = (await db.execute(month_stmt)).first()

        if month_token_stats:
            month_stats = {
                "input_tokens": int(month_token_stats.input_tokens or 0),
                "output_tokens": int(month_token_stats.output_tokens or 0),
                "total_tokens": int(month_token_stats.total_tokens or 0),
            }

        # Total stats (all time)
        total_stmt = select(
            sa_sum(TokenUsage.input_tokens).label("input_tokens"),
            sa_sum(TokenUsage.output_tokens).label("output_tokens"),
            sa_sum(TokenUsage.total_tokens).label("total_tokens"),
        ).where(TokenUsage.success)
        if org_filter:
            total_stmt = total_stmt.where(*org_filter)
        total_token_stats = (await db.execute(total_stmt)).first()

        if total_token_stats:
            total_stats = {
                "input_tokens": int(total_token_stats.input_tokens or 0),
                "output_tokens": int(total_token_stats.output_tokens or 0),
                "total_tokens": int(total_token_stats.total_tokens or 0),
            }

        # Service breakdown: MindGraph vs MindMate
        # Query stats grouped by request_type for different time periods
        async def get_service_stats(date_filter=None):
            """Get stats grouped by service type (mindgraph vs mindmate)"""
            stmt = select(
                TokenUsage.request_type,
                sa_sum(TokenUsage.input_tokens).label("input_tokens"),
                sa_sum(TokenUsage.output_tokens).label("output_tokens"),
                sa_sum(TokenUsage.total_tokens).label("total_tokens"),
                _sql_count(TokenUsage.id).label("request_count"),
            ).where(TokenUsage.success)

            if date_filter is not None:
                stmt = stmt.where(TokenUsage.created_at >= date_filter)
            if org_filter:
                stmt = stmt.where(*org_filter)

            return (await db.execute(stmt.group_by(TokenUsage.request_type))).all()

        # Get breakdown for each time period
        for period, date_filter in [
            ("today", today_start),
            ("week", week_ago),
            ("month", month_ago),
            ("total", None),
        ]:
            service_results = await get_service_stats(date_filter)
            for result in service_results:
                request_type = result.request_type or "unknown"
                # Map request_type to service category
                if request_type == "mindmate":
                    service = "mindmate"
                else:
                    service = "mindgraph"

                by_service[service][period]["input_tokens"] += int(result.input_tokens or 0)
                by_service[service][period]["output_tokens"] += int(result.output_tokens or 0)
                by_service[service][period]["total_tokens"] += int(result.total_tokens or 0)
                by_service[service][period]["request_count"] += int(result.request_count or 0)

        _dingtalk_path = and_(
            TokenUsage.endpoint_path == "/api/generate_dingtalk",
            TokenUsage.success,
        )
        for d_key, d_since in (
            ("today", today_start),
            ("week", week_ago),
            ("month", month_ago),
            ("total", None),
        ):
            d_stmt = select(_sql_count(TokenUsage.id)).where(_dingtalk_path)
            if d_since is not None:
                d_stmt = d_stmt.where(TokenUsage.created_at >= d_since)
            if org_filter:
                d_stmt = d_stmt.where(*org_filter)
            d_row = (await db.execute(d_stmt)).scalar()
            dingtalk_generations[d_key] = int(d_row or 0)

        # Top 10 users by total tokens (all time), including organization name
        # Group by Organization.id (not name) to avoid issues with duplicate organization names
        top_users_stmt = (
            select(
                User.id,
                User.phone,
                User.name,
                Organization.id.label("organization_id"),
                Organization.name.label("organization_name"),
                sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
            )
            .outerjoin(Organization, User.organization_id == Organization.id)
            .outerjoin(TokenUsage, and_(User.id == TokenUsage.user_id, TokenUsage.success))
        )
        if org_filter:
            top_users_stmt = top_users_stmt.where(*org_filter)
        top_users_query = (
            await db.execute(
                top_users_stmt.group_by(User.id, User.phone, User.name, Organization.id, Organization.name)
                .order_by(sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).desc())
                .limit(10)
            )
        ).all()

        top_users = [
            {
                "id": user.id,
                "phone": user.phone,
                "name": user.name or user.phone,
                "organization_name": user.organization_name or "",
                "input_tokens": int(user.input_tokens or 0),
                "output_tokens": int(user.output_tokens or 0),
                "total_tokens": int(user.total_tokens or 0),
            }
            for user in top_users_query
        ]

        # Top 10 users by today's token usage, including organization name
        # Use inner join to only include users with actual token usage today
        # Group by Organization.id (not name) to avoid issues with duplicate organization names
        top_users_today_stmt = (
            select(
                User.id,
                User.phone,
                User.name,
                Organization.id.label("organization_id"),
                Organization.name.label("organization_name"),
                sa_sum(TokenUsage.total_tokens).label("total_tokens"),
                sa_sum(TokenUsage.input_tokens).label("input_tokens"),
                sa_sum(TokenUsage.output_tokens).label("output_tokens"),
            )
            .outerjoin(Organization, User.organization_id == Organization.id)
            .join(
                TokenUsage,
                and_(
                    User.id == TokenUsage.user_id,
                    TokenUsage.created_at >= today_start,
                    TokenUsage.success,
                ),
            )
        )
        if org_filter:
            top_users_today_stmt = top_users_today_stmt.where(*org_filter)
        top_users_today_query = (
            await db.execute(
                top_users_today_stmt.group_by(User.id, User.phone, User.name, Organization.id, Organization.name)
                .having(sa_sum(TokenUsage.total_tokens) > 0)
                .order_by(sa_sum(TokenUsage.total_tokens).desc())
                .limit(10)
            )
        ).all()

        top_users_today = [
            {
                "id": user.id,
                "phone": user.phone,
                "name": user.name or user.phone,
                "organization_name": user.organization_name or "",
                "input_tokens": int(user.input_tokens or 0),
                "output_tokens": int(user.output_tokens or 0),
                "total_tokens": int(user.total_tokens or 0),
            }
            for user in top_users_today_query
        ]

        # Verify consistency: sum of top 10 users today should not exceed authenticated user total
        if today_user_token_stats and top_users_today:
            authenticated_total = int(today_user_token_stats.total_tokens or 0)
            top10_sum = sum(user["total_tokens"] for user in top_users_today)
            all_total = today_stats.get("total_tokens", 0)

            logger.debug(
                "Today token verification - All: %s, Authenticated: %s, Top 10 sum: %s",
                all_total,
                authenticated_total,
                top10_sum,
            )

            if top10_sum > authenticated_total:
                logger.warning(
                    "Token count mismatch: Top 10 users sum (%s) > Authenticated users total (%s)",
                    top10_sum,
                    authenticated_total,
                )
            if authenticated_total > all_total:
                logger.warning(
                    "Token count mismatch: Authenticated users (%s) > All users (%s)",
                    authenticated_total,
                    all_total,
                )

    except HTTPException:
        raise
    except (ImportError, Exception) as e:
        logger.error("Error loading token stats: %s", e, exc_info=True)

    return {
        "today": today_stats,
        "past_week": week_stats,
        "past_month": month_stats,
        "total": total_stats,
        "top_users": top_users,
        "top_users_today": top_users_today if "top_users_today" in locals() else [],
        "by_service": by_service,  # MindGraph vs MindMate breakdown
        "dingtalk_generations": dingtalk_generations,
    }
