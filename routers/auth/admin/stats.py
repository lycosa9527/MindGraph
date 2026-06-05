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
from sqlalchemy.sql.functions import (
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
from utils.auth import get_current_user, get_user_role, is_admin, is_management_panel_user
from utils.auth.admin_panel_permissions import (
    CAP_PANEL_ACCESS,
    user_panel_capabilities,
)
from utils.auth.admin_scope import AdminScope, assert_panel_org_readable, panel_read_only_for_user
from utils.auth.mindbot_token_stats import (
    add_service_period,
    add_token_period,
    aggregate_mindbot_token_totals,
    aggregate_mindbot_tokens_by_org_today,
    merge_org_token_stats,
)
from utils.auth.school_tier import school_dashboard_quotas_payload

from ..dependencies import (
    get_language_dependency,
    require_admin_stats_read,
    require_school_dashboard_read,
)
from ..helpers import get_beijing_now, get_beijing_today_start_utc

from .stats_helpers import (
    sql_count_column as _sql_count,
    token_stats_by_org_today as _token_stats_by_org_today,
    top_users_by_tokens_all_time,
    top_users_by_tokens_today as _top_users_by_tokens_today,
)

from .school_scope import resolve_school_dashboard_org_id_scoped

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/status")
async def get_admin_status(current_user: User = Depends(get_current_user)) -> Dict[str, bool]:
    """
    Lightweight endpoint to check if current user is admin.

    This endpoint does NOT require admin access - it returns admin status for any authenticated user.
    Used by frontend to check admin status without making expensive stats queries.

    Returns:
        {"is_admin": true/false, "is_management_panel_user": true/false}
    """
    return {
        "is_admin": is_admin(current_user),
        "is_management_panel_user": is_management_panel_user(current_user),
    }


@router.get("/admin/capabilities")
async def get_admin_capabilities(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Management panel capabilities for the current user.

    Always returns 200 for authenticated users. Roles without panel access get
    empty capabilities and panel_access=false.
    """
    role = get_user_role(current_user)
    caps = user_panel_capabilities(current_user)
    org_id = getattr(current_user, "organization_id", None)
    panel_access = CAP_PANEL_ACCESS in caps or is_management_panel_user(current_user)
    read_only = panel_read_only_for_user(current_user) if panel_access else False
    return {
        "role": role,
        "capabilities": sorted(caps),
        "org_ids": [int(org_id)] if org_id is not None and caps else None,
        "read_only": read_only,
        "default_org_id": int(org_id) if org_id is not None else None,
        "panel_access": panel_access,
    }


@router.get("/admin/stats", dependencies=[Depends(require_admin_stats_read)])
async def get_stats_admin(
    _request: Request,
    _scope: AdminScope = Depends(require_admin_stats_read),
    db: AsyncSession = Depends(get_async_db),
    _lang: str = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """Get system statistics (ADMIN ONLY)"""
    total_users = (await db.execute(select(_sql_count(User.id)))).scalar_one()
    total_orgs = (await db.execute(select(_sql_count(Organization.id)))).scalar_one()

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

    # Per-organization token usage (Beijing today) for dashboard ranking
    token_stats_by_org: Dict[str, Dict[str, Any]] = {}
    token_stats_by_org_mindgraph: Dict[str, Dict[str, Any]] = {}
    token_stats_by_org_mindmate: Dict[str, Dict[str, Any]] = {}
    top_users_by_tokens_today: list[Dict[str, Any]] = []

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

        mindbot_week = await aggregate_mindbot_token_totals(db, created_since=week_ago)
        token_stats = add_token_period(token_stats, mindbot_week)

        token_stats_by_org = await _token_stats_by_org_today(db, today_start)
        token_stats_by_org_mindgraph = await _token_stats_by_org_today(db, today_start, "mindgraph")
        token_stats_by_org_mindmate = await _token_stats_by_org_today(db, today_start, "mindmate")
        mindbot_orgs_today = await aggregate_mindbot_tokens_by_org_today(db, today_start)
        token_stats_by_org = merge_org_token_stats(token_stats_by_org, mindbot_orgs_today)
        token_stats_by_org_mindmate = merge_org_token_stats(
            token_stats_by_org_mindmate,
            mindbot_orgs_today,
        )

        top_users_by_tokens_today = await _top_users_by_tokens_today(
            db,
            today_start,
            mask_phone=True,
            include_org_name=True,
        )

    except (ImportError, Exception) as e:
        logger.debug("TokenUsage dashboard stats not available: %s", e)

    return {
        "total_users": total_users,
        "total_organizations": total_orgs,
        "recent_registrations": recent_registrations,
        "token_stats": token_stats,  # Global token stats
        "token_stats_by_org": token_stats_by_org,
        "token_stats_by_org_mindgraph": token_stats_by_org_mindgraph,
        "token_stats_by_org_mindmate": token_stats_by_org_mindmate,
        "top_users_by_tokens_today": top_users_by_tokens_today,
    }


@router.get("/admin/stats/school")
async def get_school_stats(
    organization_id: Optional[int] = None,
    scope: AdminScope = Depends(require_school_dashboard_read),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """
    Get school-scoped statistics (ADMIN or MANAGER).

    Managers: organization_id must be their own org (or omitted to use their org).
    Admins: organization_id required to select which school to view.
    """
    effective_org_id = await resolve_school_dashboard_org_id_scoped(
        scope, organization_id, db, lang
    )

    org = (await db.execute(select(Organization).where(Organization.id == effective_org_id))).scalars().first()
    if not org:
        logger.warning(
            "[SchoolDashboard] organization missing for school stats",
            extra=school_dashboard_extra(
                event="school_stats_org_not_found",
                actor_id=scope.actor.id,
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

        mindbot_week = await aggregate_mindbot_token_totals(
            db,
            created_since=week_ago,
            organization_id=effective_org_id,
        )
        token_stats = add_token_period(token_stats, mindbot_week)

        org_today_stats = (
            await db.execute(
                select(
                    sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                    sa_coalesce(_sql_count(TokenUsage.id), 0).label("request_count"),
                ).where(
                    TokenUsage.organization_id == effective_org_id,
                    TokenUsage.success,
                    TokenUsage.created_at >= today_start,
                )
            )
        ).first()

        org_bucket = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "request_count": 0,
        }
        if org_today_stats:
            org_bucket = {
                "input_tokens": int(org_today_stats.input_tokens or 0),
                "output_tokens": int(org_today_stats.output_tokens or 0),
                "total_tokens": int(org_today_stats.total_tokens or 0),
                "request_count": int(org_today_stats.request_count or 0),
            }
        mindbot_org_today = await aggregate_mindbot_token_totals(
            db,
            created_since=today_start,
            organization_id=effective_org_id,
        )
        org_bucket = add_token_period(org_bucket, mindbot_org_today)
        if org_bucket.get("total_tokens", 0) > 0:
            token_stats_by_org[org.name] = {
                "org_id": org.id,
                **org_bucket,
            }

        top_users = await _top_users_by_tokens_today(
            db,
            today_start,
            organization_id=effective_org_id,
            mask_phone=True,
        )
    except (ImportError, Exception) as e:
        logger.debug("TokenUsage not available: %s", e)

    quotas = await school_dashboard_quotas_payload(db, org)

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
        "quotas": quotas,
    }


@router.get("/admin/stats/school/token-stats")
async def get_school_token_stats(
    request: Request,
    organization_id: Optional[int] = None,
    scope: AdminScope = Depends(require_school_dashboard_read),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """
    Get token stats for a school (ADMIN or MANAGER).
    Same structure as /admin/token-stats with organization_id filter.
    """
    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    return await get_token_stats_admin(
        _request=request,
        organization_id=org_id,
        scope=scope,
        db=db,
        lang=lang,
    )


@router.get("/admin/token-stats")
async def get_token_stats_admin(
    _request: Request,
    organization_id: Optional[int] = None,
    scope: AdminScope = Depends(require_admin_stats_read),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """Get detailed token usage statistics (ADMIN ONLY)

    If organization_id is provided, returns stats for that organization only.
    Otherwise returns global stats.

    Returns separate stats for:
    - mindgraph: Diagram generation and related features
    - mindmate: Web MindMate (Dify) plus DingTalk bot (MindBot / Dify) token usage
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
                    actor_id=scope.actor.id,
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
            await assert_panel_org_readable(scope, int(organization_id), db, lang)
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

        mindbot_org_id = organization_id if organization_id else None
        mindbot_today = await aggregate_mindbot_token_totals(
            db,
            created_since=today_start,
            organization_id=mindbot_org_id,
        )
        today_stats = add_token_period(today_stats, mindbot_today)
        mindbot_week = await aggregate_mindbot_token_totals(
            db,
            created_since=week_ago,
            organization_id=mindbot_org_id,
        )
        week_stats = add_token_period(week_stats, mindbot_week)
        mindbot_month = await aggregate_mindbot_token_totals(
            db,
            created_since=month_ago,
            organization_id=mindbot_org_id,
        )
        month_stats = add_token_period(month_stats, mindbot_month)
        mindbot_total = await aggregate_mindbot_token_totals(
            db,
            organization_id=mindbot_org_id,
        )
        total_stats = add_token_period(total_stats, mindbot_total)

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

            mindbot_period = await aggregate_mindbot_token_totals(
                db,
                created_since=date_filter,
                organization_id=mindbot_org_id,
            )
            by_service["mindmate"][period] = add_service_period(
                by_service["mindmate"][period],
                mindbot_period,
            )

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

        top_users = await top_users_by_tokens_all_time(
            db,
            organization_id=organization_id,
            mask_phone=True,
        )

        top_users_today = await _top_users_by_tokens_today(
            db,
            today_start,
            organization_id=organization_id,
            mask_phone=True,
            include_org_name=True,
            include_io_tokens=True,
        )

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
