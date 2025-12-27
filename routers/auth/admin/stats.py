"""
Admin Statistics Endpoints
=========================

Admin-only statistics and trends endpoints:
- GET /admin/stats - Get system statistics
- GET /admin/token-stats - Get detailed token usage statistics
- GET /admin/stats/trends - Get time-series trends data
- GET /admin/stats/trends/organization - Get organization token trends
- GET /admin/stats/trends/user - Get user token trends

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from config.database import get_db
from models.auth import User, Organization
from models.messages import Messages

from ..dependencies import get_language_dependency, require_admin
from ..helpers import get_beijing_now, get_beijing_today_start_utc, utc_to_beijing_iso, BEIJING_TIMEZONE

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/stats", dependencies=[Depends(require_admin)])
async def get_stats_admin(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
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
        func.count(User.id).label('user_count')
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
        from models.token_usage import TokenUsage
        
        # Global token stats for past week
        week_token_stats = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= week_ago,
            TokenUsage.success == True
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
            func.coalesce(func.count(TokenUsage.id), 0).label('request_count')
        ).outerjoin(
            TokenUsage, 
            and_(
                Organization.id == TokenUsage.organization_id,
                TokenUsage.success == True
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
        logger.debug(f"TokenUsage not available yet: {e}")
    
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
    request: Request,
    organization_id: Optional[int] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """Get detailed token usage statistics (ADMIN ONLY)
    
    If organization_id is provided, returns stats for that organization only.
    Otherwise returns global stats.
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
    
    # Import models first
    try:
        from models.token_usage import TokenUsage
        from models.auth import Organization, User
        
        # Build base filter for organization if specified
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
            TokenUsage.success == True
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
            TokenUsage.success == True,
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
            logger.debug(f"Today token stats - All: {all_total}, Authenticated users only: {authenticated_total}")
            
            # Warn if authenticated total exceeds all total (shouldn't happen)
            if authenticated_total > all_total:
                logger.warning(f"Token count mismatch: Authenticated users ({authenticated_total}) > All users ({all_total})")
        
        # Past week stats
        week_query = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= week_ago,
            TokenUsage.success == True
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
            TokenUsage.success == True
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
            TokenUsage.success == True
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
                TokenUsage.success == True
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
                TokenUsage.success == True
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
            logger.debug(f"Today token verification - All: {all_total}, Authenticated: {authenticated_total}, Top 10 sum: {top10_sum}")
            
            # Warn if top 10 sum exceeds authenticated total (indicates double counting or grouping issue)
            if top10_sum > authenticated_total:
                logger.warning(f"Token count mismatch: Top 10 users sum ({top10_sum}) > Authenticated users total ({authenticated_total})")
            # Warn if authenticated total exceeds all total (shouldn't happen)
            if authenticated_total > all_total:
                logger.warning(f"Token count mismatch: Authenticated users ({authenticated_total}) > All users ({all_total})")
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for organization not found)
        raise
    except (ImportError, Exception) as e:
        logger.error(f"Error loading token stats: {e}", exc_info=True)
    
    return {
        "today": today_stats,
        "past_week": week_stats,
        "past_month": month_stats,
        "total": total_stats,
        "top_users": top_users,
        "top_users_today": top_users_today if 'top_users_today' in locals() else []
    }


@router.get("/admin/stats/trends", dependencies=[Depends(require_admin)])
async def get_stats_trends_admin(
    request: Request,
    metric: str,  # 'users', 'organizations', 'registrations', 'tokens'
    days: int = 30,  # Number of days to look back
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """Get time-series trends data for dashboard charts (ADMIN ONLY)"""
    # Special case: days=0 means all-time (no limit)
    all_time = False
    if days == 0:
        all_time = True
        days = None  # Will fetch all data
    elif days > 90:
        days = 90  # Cap at 90 days for regular queries
    elif days < 1:
        days = 1  # Minimum 1 day
    
    # Use Beijing time for date calculations
    beijing_now = get_beijing_now()
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Handle all-time query (days=None or days=0)
    if all_time:
        start_date_utc = None  # No start date limit - fetch all data
        now_utc = beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
        # For date list generation, start from a reasonable date (e.g., 1 year ago or system start)
        # For tokens metric, we'll generate dates based on actual data range
        beijing_start = beijing_today_start - timedelta(days=365)  # Default to 1 year for all-time display
    else:
        # Calculate start date: N days ago from today start (00:00:00)
        # This ensures consistent date boundaries with token-stats endpoint
        # Example: If days=7 and today is Jan 15 00:00:00:
        #   - Calculate: Jan 15 00:00:00 - 7 days = Jan 8 00:00:00
        #   - Date list includes: Jan 8, 9, 10, 11, 12, 13, 14, 15 (8 days, including today)
        # This matches token-stats endpoint behavior: "Past Week" = last 7 days from today 00:00:00
        beijing_start = beijing_today_start - timedelta(days=days)
        # Convert to UTC for database queries
        start_date_utc = beijing_start.astimezone(timezone.utc).replace(tzinfo=None)
        now_utc = beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
    
    # Generate all dates in range using Beijing dates (for display)
    # Includes start date through today (inclusive)
    date_list = []
    current = beijing_start
    while current <= beijing_now:
        date_list.append(current.date())
        current += timedelta(days=1)
    
    trends_data = []
    
    if metric == 'users':
        # Daily cumulative user count
        try:
            # Get initial count before start_date_utc
            initial_count = db.query(func.count(User.id)).filter(
                User.created_at < start_date_utc
            ).scalar() or 0
            
            # Get user counts grouped by date (using UTC for DB query, but we'll map to Beijing dates)
            user_counts = db.query(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            ).filter(
                User.created_at >= start_date_utc
            ).group_by(
                func.date(User.created_at)
            ).all()
            
            # Map UTC dates to Beijing dates
            counts_by_date = {}
            for row in user_counts:
                utc_date = row.date
                # SQLite returns date as string, need to parse it
                if isinstance(utc_date, str):
                    utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
                utc_datetime = datetime.combine(utc_date, datetime.min.time())
                beijing_datetime = utc_datetime.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
                beijing_date_str = str(beijing_datetime.date())
                counts_by_date[beijing_date_str] = counts_by_date.get(beijing_date_str, 0) + row.count
            
            # Calculate cumulative counts
            cumulative = initial_count
            for date in date_list:
                date_str = str(date)
                if date_str in counts_by_date:
                    cumulative += counts_by_date[date_str]
                trends_data.append({
                    "date": date_str,
                    "value": cumulative
                })
        except Exception as e:
            logger.error(f"Error fetching user trends: {e}")
            # Return zeros if error
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})
    
    elif metric == 'organizations':
        # Daily cumulative organization count
        try:
            # Get initial count before start_date_utc
            initial_count = db.query(func.count(Organization.id)).filter(
                Organization.created_at < start_date_utc
            ).scalar() or 0
            
            org_counts = db.query(
                func.date(Organization.created_at).label('date'),
                func.count(Organization.id).label('count')
            ).filter(
                Organization.created_at >= start_date_utc
            ).group_by(
                func.date(Organization.created_at)
            ).all()
            
            # Map UTC dates to Beijing dates
            counts_by_date = {}
            for row in org_counts:
                utc_date = row.date
                # SQLite returns date as string, need to parse it
                if isinstance(utc_date, str):
                    utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
                utc_datetime = datetime.combine(utc_date, datetime.min.time())
                beijing_datetime = utc_datetime.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
                beijing_date_str = str(beijing_datetime.date())
                counts_by_date[beijing_date_str] = counts_by_date.get(beijing_date_str, 0) + row.count
            
            cumulative = initial_count
            for date in date_list:
                date_str = str(date)
                if date_str in counts_by_date:
                    cumulative += counts_by_date[date_str]
                trends_data.append({
                    "date": date_str,
                    "value": cumulative
                })
        except Exception as e:
            logger.error(f"Error fetching organization trends: {e}")
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})
    
    elif metric == 'registrations':
        # Daily new user registrations (non-cumulative)
        try:
            reg_counts = db.query(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            ).filter(
                User.created_at >= start_date_utc
            ).group_by(
                func.date(User.created_at)
            ).all()
            
            # Map UTC dates to Beijing dates
            counts_by_date = {}
            for row in reg_counts:
                utc_date = row.date
                # SQLite returns date as string, need to parse it
                if isinstance(utc_date, str):
                    utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
                utc_datetime = datetime.combine(utc_date, datetime.min.time())
                beijing_datetime = utc_datetime.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
                beijing_date_str = str(beijing_datetime.date())
                counts_by_date[beijing_date_str] = counts_by_date.get(beijing_date_str, 0) + row.count
            
            for date in date_list:
                date_str = str(date)
                trends_data.append({
                    "date": date_str,
                    "value": counts_by_date.get(date_str, 0)
                })
        except Exception as e:
            logger.error(f"Error fetching registration trends: {e}")
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})
    
    elif metric == 'tokens':
        # Daily token usage (non-cumulative)
        try:
            from models.token_usage import TokenUsage
            
            token_counts_query = db.query(
                func.date(TokenUsage.created_at).label('date'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens')
            ).filter(
                TokenUsage.success == True
            )
            # Apply date filter only if not all-time query
            if start_date_utc is not None:
                token_counts_query = token_counts_query.filter(TokenUsage.created_at >= start_date_utc)
            token_counts = token_counts_query.group_by(
                func.date(TokenUsage.created_at)
            ).all()
            
            # Map UTC dates to Beijing dates
            tokens_by_date = {}
            for row in token_counts:
                utc_date = row.date
                # SQLite returns date as string, need to parse it
                if isinstance(utc_date, str):
                    utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
                utc_datetime = datetime.combine(utc_date, datetime.min.time())
                beijing_datetime = utc_datetime.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
                beijing_date_str = str(beijing_datetime.date())
                if beijing_date_str not in tokens_by_date:
                    tokens_by_date[beijing_date_str] = {"total": 0, "input": 0, "output": 0}
                tokens_by_date[beijing_date_str]["total"] += int(row.total_tokens or 0)
                tokens_by_date[beijing_date_str]["input"] += int(row.input_tokens or 0)
                tokens_by_date[beijing_date_str]["output"] += int(row.output_tokens or 0)
            
            for date in date_list:
                date_str = str(date)
                tokens = tokens_by_date.get(date_str, {"total": 0, "input": 0, "output": 0})
                trends_data.append({
                    "date": date_str,
                    "value": tokens["total"],
                    "input": tokens["input"],
                    "output": tokens["output"]
                })
        except Exception as e:
            logger.error(f"Error fetching token trends: {e}")
            for date in date_list:
                trends_data.append({
                    "date": str(date),
                    "value": 0,
                    "input": 0,
                    "output": 0
                })
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric: {metric}. Must be one of: users, organizations, registrations, tokens"
        )
    
    return {
        "metric": metric,
        "days": days,
        "data": trends_data
    }


@router.get("/admin/stats/trends/organization", dependencies=[Depends(require_admin)])
async def get_organization_token_trends_admin(
    request: Request,
    organization_id: Optional[int] = None,
    organization_name: Optional[str] = None,
    days: int = 30,  # Number of days to look back
    hourly: bool = False,  # If True, return hourly data (only for days=1)
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """Get token usage trends for a specific organization (ADMIN ONLY)"""
    if not organization_id and not organization_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either organization_id or organization_name must be provided"
        )
    
    # Special case: days=0 means all-time (no limit)
    all_time = False
    if days == 0:
        all_time = True
        days = None  # Will fetch all data
    elif days > 90:
        days = 90  # Cap at 90 days for regular queries
    elif days < 1:
        days = 1  # Minimum 1 day
    
    # Find organization
    org = None
    if organization_id:
        org = db.query(Organization).filter(Organization.id == organization_id).first()
    elif organization_name:
        org = db.query(Organization).filter(Organization.name == organization_name).first()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Use Beijing time for date calculations
    beijing_now = get_beijing_now()
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Handle all-time query (days=None or days=0)
    if all_time:
        start_date_utc = None  # No start date limit - fetch all data
        now_utc = beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
        # For date list generation, start from organization creation
        beijing_start = org.created_at.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
        beijing_start = beijing_start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # Calculate start date: N days ago from today start (00:00:00)
        # This ensures consistent date boundaries with token-stats endpoint
        # Example: If days=7 and today is Jan 15 00:00:00:
        #   - Calculate: Jan 15 00:00:00 - 7 days = Jan 8 00:00:00
        #   - Date list includes: Jan 8, 9, 10, 11, 12, 13, 14, 15 (8 days, including today)
        # This matches token-stats endpoint behavior: "Past Week" = last 7 days from today 00:00:00
        beijing_start = beijing_today_start - timedelta(days=days)
        # Convert to UTC for database queries
        start_date_utc = beijing_start.astimezone(timezone.utc).replace(tzinfo=None)
        now_utc = beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
    
    trends_data = []
    
    # Hourly data (only for days=1, not for all-time)
    if hourly and days == 1 and start_date_utc is not None:
        # Generate hourly intervals for today
        hour_list = []
        beijing_start = start_date_utc.astimezone(BEIJING_TIMEZONE)
        current = beijing_start
        while current <= beijing_now:
            hour_list.append(current.replace(minute=0, second=0, microsecond=0))
            current += timedelta(hours=1)
        
        try:
            from models.token_usage import TokenUsage
            
            # Query hourly token usage
            token_counts = db.query(
                func.strftime('%Y-%m-%d %H:00:00', TokenUsage.created_at).label('datetime'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens')
            ).filter(
                TokenUsage.organization_id == org.id,
                TokenUsage.success == True
            )
            if start_date_utc is not None:
                token_counts = token_counts.filter(TokenUsage.created_at >= start_date_utc)
            token_counts = token_counts.group_by(
                func.strftime('%Y-%m-%d %H:00:00', TokenUsage.created_at)
            ).all()
            
            # Map UTC datetimes to Beijing hours
            tokens_by_hour = {}
            for row in token_counts:
                utc_datetime_str = row.datetime
                # Parse UTC datetime string
                utc_datetime = datetime.strptime(utc_datetime_str, "%Y-%m-%d %H:00:00")
                utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
                beijing_datetime = utc_datetime.astimezone(BEIJING_TIMEZONE)
                beijing_hour_str = beijing_datetime.strftime("%Y-%m-%d %H:00:00")
                if beijing_hour_str not in tokens_by_hour:
                    tokens_by_hour[beijing_hour_str] = {"total": 0, "input": 0, "output": 0}
                tokens_by_hour[beijing_hour_str]["total"] += int(row.total_tokens or 0)
                tokens_by_hour[beijing_hour_str]["input"] += int(row.input_tokens or 0)
                tokens_by_hour[beijing_hour_str]["output"] += int(row.output_tokens or 0)
            
            for hour in hour_list:
                hour_str = hour.strftime("%Y-%m-%d %H:00:00")
                tokens = tokens_by_hour.get(hour_str, {"total": 0, "input": 0, "output": 0})
                trends_data.append({
                    "date": hour_str,
                    "value": tokens["total"],
                    "input": tokens["input"],
                    "output": tokens["output"]
                })
        except Exception as e:
            logger.error(f"Error fetching hourly organization token trends: {e}")
            for hour in hour_list:
                trends_data.append({
                    "date": hour.strftime("%Y-%m-%d %H:00:00"),
                    "value": 0,
                    "input": 0,
                    "output": 0
                })
    else:
        # Daily token usage for this organization (non-cumulative)
        # Generate all dates in range using Beijing dates (for display)
        date_list = []
        current = beijing_start
        while current <= beijing_now:
            date_list.append(current.date())
            current += timedelta(days=1)
        
        try:
            from models.token_usage import TokenUsage
            
            token_counts = db.query(
                func.date(TokenUsage.created_at).label('date'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens')
            ).filter(
                TokenUsage.organization_id == org.id,
                TokenUsage.success == True
            )
            if start_date_utc is not None:
                token_counts = token_counts.filter(TokenUsage.created_at >= start_date_utc)
            token_counts = token_counts.group_by(
                func.date(TokenUsage.created_at)
            ).all()
            
            # Map UTC dates to Beijing dates
            tokens_by_date = {}
            for row in token_counts:
                utc_date = row.date
                # SQLite returns date as string, need to parse it
                if isinstance(utc_date, str):
                    utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
                utc_datetime = datetime.combine(utc_date, datetime.min.time())
                beijing_datetime = utc_datetime.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
                beijing_date_str = str(beijing_datetime.date())
                if beijing_date_str not in tokens_by_date:
                    tokens_by_date[beijing_date_str] = {"total": 0, "input": 0, "output": 0}
                tokens_by_date[beijing_date_str]["total"] += int(row.total_tokens or 0)
                tokens_by_date[beijing_date_str]["input"] += int(row.input_tokens or 0)
                tokens_by_date[beijing_date_str]["output"] += int(row.output_tokens or 0)
            
            for date in date_list:
                date_str = str(date)
                tokens = tokens_by_date.get(date_str, {"total": 0, "input": 0, "output": 0})
                trends_data.append({
                    "date": date_str,
                    "value": tokens["total"],
                    "input": tokens["input"],
                    "output": tokens["output"]
                })
        except Exception as e:
            logger.error(f"Error fetching organization token trends: {e}")
            for date in date_list:
                trends_data.append({
                    "date": str(date),
                    "value": 0,
                    "input": 0,
                    "output": 0
                })
    
    return {
        "organization_id": org.id,
        "organization_name": org.name,
        "days": days,
        "data": trends_data
    }


@router.get("/admin/stats/trends/user", dependencies=[Depends(require_admin)])
async def get_user_token_trends_admin(
    request: Request,
    user_id: Optional[int] = None,
    days: int = 10,  # Number of days to look back, default 10
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """Get token usage trends for a specific user (ADMIN ONLY)"""
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must be provided"
        )
    
    # Special case: days=0 means all-time (no limit)
    all_time = False
    if days == 0:
        all_time = True
        days = None  # Will fetch all data
    elif days > 90:
        days = 90  # Cap at 90 days for regular queries
    elif days < 1:
        days = 1  # Minimum 1 day
    
    # Find user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Use Beijing time for date calculations
    beijing_now = get_beijing_now()
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Handle all-time query (days=None or days=0)
    if all_time:
        start_date_utc = None  # No start date limit - fetch all data
        now_utc = beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
        # For date list generation, start from user creation
        beijing_start = user.created_at.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
        beijing_start = beijing_start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # Calculate start date: N days ago from today start (00:00:00)
        # This ensures consistent date boundaries with token-stats endpoint
        # Example: If days=7 and today is Jan 15 00:00:00:
        #   - Calculate: Jan 15 00:00:00 - 7 days = Jan 8 00:00:00
        #   - Date list includes: Jan 8, 9, 10, 11, 12, 13, 14, 15 (8 days, including today)
        # This matches token-stats endpoint behavior: "Past Week" = last 7 days from today 00:00:00
        beijing_start = beijing_today_start - timedelta(days=days)
        # Convert to UTC for database queries
        start_date_utc = beijing_start.astimezone(timezone.utc).replace(tzinfo=None)
        now_utc = beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
    
    # Generate all dates in range using Beijing dates (for display)
    date_list = []
    current = beijing_start
    while current <= beijing_now:
        date_list.append(current.date())
        current += timedelta(days=1)
    
    trends_data = []
    
    # Daily token usage for this user (non-cumulative)
    try:
        from models.token_usage import TokenUsage
        
        token_counts = db.query(
            func.date(TokenUsage.created_at).label('date'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens')
        ).filter(
            TokenUsage.user_id == user.id,
            TokenUsage.success == True
        )
        if start_date_utc is not None:
            token_counts = token_counts.filter(TokenUsage.created_at >= start_date_utc)
        token_counts = token_counts.group_by(
            func.date(TokenUsage.created_at)
        ).all()
        
        # Map UTC dates to Beijing dates
        tokens_by_date = {}
        for row in token_counts:
            utc_date = row.date
            # SQLite returns date as string, need to parse it
            if isinstance(utc_date, str):
                utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
            utc_datetime = datetime.combine(utc_date, datetime.min.time())
            beijing_datetime = utc_datetime.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
            beijing_date_str = str(beijing_datetime.date())
            if beijing_date_str not in tokens_by_date:
                tokens_by_date[beijing_date_str] = {"total": 0, "input": 0, "output": 0}
            tokens_by_date[beijing_date_str]["total"] += int(row.total_tokens or 0)
            tokens_by_date[beijing_date_str]["input"] += int(row.input_tokens or 0)
            tokens_by_date[beijing_date_str]["output"] += int(row.output_tokens or 0)
        
        for date in date_list:
            date_str = str(date)
            tokens = tokens_by_date.get(date_str, {"total": 0, "input": 0, "output": 0})
            trends_data.append({
                "date": date_str,
                "value": tokens["total"],
                "input": tokens["input"],
                "output": tokens["output"]
            })
    except Exception as e:
        logger.error(f"Error fetching user token trends: {e}")
        for date in date_list:
            trends_data.append({
                "date": str(date),
                "value": 0,
                "input": 0,
                "output": 0
            })
    
    return {
        "user_id": user.id,
        "user_name": user.name or user.phone,
        "user_phone": user.phone,
        "days": days,
        "data": trends_data
    }

