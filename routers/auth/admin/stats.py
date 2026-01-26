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
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from config.database import get_db
from models.domain.auth import User, Organization
from models.domain.token_usage import TokenUsage
from utils.auth import get_current_user, is_admin

from ..dependencies import get_language_dependency, require_admin
from ..helpers import get_beijing_now, get_beijing_today_start_utc

logger = logging.getLogger(__name__)

router = APIRouter()


def _sql_count(column: Any) -> ColumnElement:
    """Helper function to call func.count for SQLAlchemy queries."""
    count_func = getattr(func, 'count')
    return count_func(column)


@router.get("/admin/status")
async def get_admin_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, bool]:
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
    db: Session = Depends(get_db),
    _lang: str = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """Get system statistics (ADMIN ONLY)"""
    total_users = db.query(User).count()
    total_orgs = db.query(Organization).count()

    # Performance optimization: Get user counts for all organizations in one GROUP BY query
    # instead of N+1 queries (one per organization)
    users_by_org = {}
    user_counts_query = db.query(
        Organization.id,
        Organization.name,
        _sql_count(User.id).label('user_count')
    ).outerjoin(
        User,
        Organization.id == User.organization_id
    ).group_by(
        Organization.id,
        Organization.name
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
    recent_registrations = db.query(User).filter(User.created_at >= today_start).count()

    # Token usage stats (this week) - PER USER and PER ORGANIZATION tracking!
    token_stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0
    }

    # Per-organization token usage (for school-level reporting)
    token_stats_by_org = {}

    try:
        # Global token stats for past week
        week_token_stats = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= week_ago,
            TokenUsage.success
        ).first()

        if week_token_stats:
            token_stats = {
                "input_tokens": int(week_token_stats.input_tokens or 0),
                "output_tokens": int(week_token_stats.output_tokens or 0),
                "total_tokens": int(week_token_stats.total_tokens or 0)
            }

        # Per-organization TOTAL token usage (all time, for active school ranking)
        # Use LEFT JOIN to include organizations with no token usage
        org_token_stats = db.query(
            Organization.id,
            Organization.name,
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('input_tokens'),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('output_tokens'),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label('total_tokens'),
            func.coalesce(_sql_count(TokenUsage.id), 0).label('request_count')
        ).outerjoin(
            TokenUsage,
            and_(
                Organization.id == TokenUsage.organization_id,
                TokenUsage.success
            )
        ).group_by(
            Organization.id,
            Organization.name
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
                    "request_count": int(org_stat.request_count or 0)
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
        "token_stats_by_org": token_stats_by_org  # Per-organization TOTAL token stats (all time)
    }


@router.get("/admin/token-stats", dependencies=[Depends(require_admin)])
async def get_token_stats_admin(
    _request: Request,
    organization_id: Optional[int] = None,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _lang: str = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """Get detailed token usage statistics (ADMIN ONLY)

    If organization_id is provided, returns stats for that organization only.
    Otherwise returns global stats.

    Returns separate stats for:
    - mindgraph: Diagram generation and related features
    - mindmate: AI assistant (Dify) conversations
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
    empty_breakdown = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "request_count": 0}
    by_service = {
        "mindgraph": {
            "today": empty_breakdown.copy(),
            "week": empty_breakdown.copy(),
            "month": empty_breakdown.copy(),
            "total": empty_breakdown.copy()
        },
        "mindmate": {
            "today": empty_breakdown.copy(),
            "week": empty_breakdown.copy(),
            "month": empty_breakdown.copy(),
            "total": empty_breakdown.copy()
        }
    }

    # Build base filter for organization if specified
    try:
        org_filter = []
        if organization_id:
            org = db.query(Organization).filter(Organization.id == organization_id).first()
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization not found"
                )
            org_filter.append(TokenUsage.organization_id == organization_id)

        # Today stats - sum all token usage today (including records with user_id=NULL)
        # Note: This includes API key usage without user_id, so it may be larger than sum of top users
        today_query = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= today_start,
            TokenUsage.success
        )
        if org_filter:
            today_query = today_query.filter(*org_filter)
        today_token_stats = today_query.first()

        # Also calculate today stats for authenticated users only (for comparison)
        today_user_token_stats_query = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= today_start,
            TokenUsage.success,
            TokenUsage.user_id.isnot(None)
        )
        if org_filter:
            today_user_token_stats_query = today_user_token_stats_query.filter(*org_filter)
        today_user_token_stats = today_user_token_stats_query.first()

        if today_token_stats:
            today_stats = {
                "input_tokens": int(today_token_stats.input_tokens or 0),
                "output_tokens": int(today_token_stats.output_tokens or 0),
                "total_tokens": int(today_token_stats.total_tokens or 0)
            }

        # Verify consistency: sum of top users should not exceed authenticated user total
        if today_user_token_stats:
            authenticated_total = int(today_user_token_stats.total_tokens or 0)
            all_total = today_stats.get('total_tokens', 0)
            # Log for debugging if there's a discrepancy
            logger.debug("Today token stats - All: %s, Authenticated users only: %s", all_total, authenticated_total)

            # Warn if authenticated total exceeds all total (shouldn't happen)
            if authenticated_total > all_total:
                logger.warning(
                    "Token count mismatch: Authenticated users (%s) > "
                    "All users (%s)",
                    authenticated_total,
                    all_total
                )

        # Past week stats
        week_query = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= week_ago,
            TokenUsage.success
        )
        if org_filter:
            week_query = week_query.filter(*org_filter)
        week_token_stats = week_query.first()

        if week_token_stats:
            week_stats = {
                "input_tokens": int(week_token_stats.input_tokens or 0),
                "output_tokens": int(week_token_stats.output_tokens or 0),
                "total_tokens": int(week_token_stats.total_tokens or 0)
            }

        # Past month stats
        month_query = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= month_ago,
            TokenUsage.success
        )
        if org_filter:
            month_query = month_query.filter(*org_filter)
        month_token_stats = month_query.first()

        if month_token_stats:
            month_stats = {
                "input_tokens": int(month_token_stats.input_tokens or 0),
                "output_tokens": int(month_token_stats.output_tokens or 0),
                "total_tokens": int(month_token_stats.total_tokens or 0)
            }

        # Total stats (all time)
        total_query = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.success
        )
        if org_filter:
            total_query = total_query.filter(*org_filter)
        total_token_stats = total_query.first()

        if total_token_stats:
            total_stats = {
                "input_tokens": int(total_token_stats.input_tokens or 0),
                "output_tokens": int(total_token_stats.output_tokens or 0),
                "total_tokens": int(total_token_stats.total_tokens or 0)
            }

        # Service breakdown: MindGraph vs MindMate
        # Query stats grouped by request_type for different time periods
        def get_service_stats(date_filter=None):
            """Get stats grouped by service type (mindgraph vs mindmate)"""
            query = db.query(
                TokenUsage.request_type,
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                _sql_count(TokenUsage.id).label('request_count')
            ).filter(TokenUsage.success)

            if date_filter is not None:
                query = query.filter(TokenUsage.created_at >= date_filter)
            if org_filter:
                query = query.filter(*org_filter)

            return query.group_by(TokenUsage.request_type).all()

        # Get breakdown for each time period
        for period, date_filter in [("today", today_start), ("week", week_ago), ("month", month_ago), ("total", None)]:
            service_results = get_service_stats(date_filter)
            for result in service_results:
                request_type = result.request_type or 'unknown'
                # Map request_type to service category
                if request_type == 'mindmate':
                    service = 'mindmate'
                else:
                    # All other types (diagram_generation, node_palette, autocomplete, etc.) are MindGraph
                    service = 'mindgraph'

                by_service[service][period]["input_tokens"] += int(result.input_tokens or 0)
                by_service[service][period]["output_tokens"] += int(result.output_tokens or 0)
                by_service[service][period]["total_tokens"] += int(result.total_tokens or 0)
                by_service[service][period]["request_count"] += int(result.request_count or 0)

        # Top 10 users by total tokens (all time), including organization name
        # Group by Organization.id (not name) to avoid issues with duplicate organization names
        # Skip top_users if organization_id is specified (not needed for organization-specific stats)
        top_users_query = db.query(
            User.id,
            User.phone,
            User.name,
            Organization.id.label('organization_id'),
            Organization.name.label('organization_name'),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label('total_tokens'),
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('input_tokens'),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('output_tokens')
        ).outerjoin(
            Organization,
            User.organization_id == Organization.id
        ).outerjoin(
            TokenUsage,
            and_(
                User.id == TokenUsage.user_id,
                TokenUsage.success
            )
        )
        if org_filter:
            top_users_query = top_users_query.filter(*org_filter)
        top_users_query = top_users_query.group_by(
            User.id,
            User.phone,
            User.name,
            Organization.id,
            Organization.name
        ).order_by(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).desc()
        ).limit(10).all()

        top_users = [
            {
                "id": user.id,
                "phone": user.phone,
                "name": user.name or user.phone,
                "organization_name": user.organization_name or "",
                "input_tokens": int(user.input_tokens or 0),
                "output_tokens": int(user.output_tokens or 0),
                "total_tokens": int(user.total_tokens or 0)
            }
            for user in top_users_query
        ]

        # Top 10 users by today's token usage, including organization name
        # Use inner join to only include users with actual token usage today
        # Group by Organization.id (not name) to avoid issues with duplicate organization names
        # Skip top_users_today if organization_id is specified (not needed for organization-specific stats)
        top_users_today_query = db.query(
            User.id,
            User.phone,
            User.name,
            Organization.id.label('organization_id'),
            Organization.name.label('organization_name'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens')
        ).join(
            Organization,
            User.organization_id == Organization.id,
            isouter=True
        ).join(
            TokenUsage,
            and_(
                User.id == TokenUsage.user_id,
                TokenUsage.created_at >= today_start,
                TokenUsage.success
            )
        )
        if org_filter:
            top_users_today_query = top_users_today_query.filter(*org_filter)
        top_users_today_query = top_users_today_query.group_by(
            User.id,
            User.phone,
            User.name,
            Organization.id,
            Organization.name
        ).having(
            func.sum(TokenUsage.total_tokens) > 0
        ).order_by(
            func.sum(TokenUsage.total_tokens).desc()
        ).limit(10).all()

        top_users_today = [
            {
                "id": user.id,
                "phone": user.phone,
                "name": user.name or user.phone,
                "organization_name": user.organization_name or "",
                "input_tokens": int(user.input_tokens or 0),
                "output_tokens": int(user.output_tokens or 0),
                "total_tokens": int(user.total_tokens or 0)
            }
            for user in top_users_today_query
        ]

        # Verify consistency: sum of top 10 users today should not exceed authenticated user total
        if today_user_token_stats and top_users_today:
            authenticated_total = int(today_user_token_stats.total_tokens or 0)
            top10_sum = sum(user['total_tokens'] for user in top_users_today)
            all_total = today_stats.get('total_tokens', 0)

            # Log for debugging
            logger.debug(
                "Today token verification - All: %s, Authenticated: %s, "
                "Top 10 sum: %s",
                all_total,
                authenticated_total,
                top10_sum
            )

            # Warn if top 10 sum exceeds authenticated total (indicates double counting or grouping issue)
            if top10_sum > authenticated_total:
                logger.warning(
                    "Token count mismatch: Top 10 users sum (%s) > "
                    "Authenticated users total (%s)",
                    top10_sum,
                    authenticated_total
                )
            # Warn if authenticated total exceeds all total (shouldn't happen)
            if authenticated_total > all_total:
                logger.warning(
                    "Token count mismatch: Authenticated users (%s) > "
                    "All users (%s)",
                    authenticated_total,
                    all_total
                )

    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for organization not found)
        raise
    except (ImportError, Exception) as e:
        logger.error("Error loading token stats: %s", e, exc_info=True)

    return {
        "today": today_stats,
        "past_week": week_stats,
        "past_month": month_stats,
        "total": total_stats,
        "top_users": top_users,
        "top_users_today": top_users_today if 'top_users_today' in locals() else [],
        "by_service": by_service  # MindGraph vs MindMate breakdown
    }
