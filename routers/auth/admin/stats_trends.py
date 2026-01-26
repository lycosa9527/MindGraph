"""Admin Statistics Trends Endpoints.

Trends endpoints for time-series data:
- GET /admin/stats/trends - Get time-series trends data
- GET /admin/stats/trends/organization - Get organization token trends
- GET /admin/stats/trends/user - Get user token trends

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User, Organization
from models.domain.token_usage import TokenUsage
from ..dependencies import get_language_dependency, require_admin
from ..helpers import get_beijing_now, BEIJING_TIMEZONE
from .stats import _sql_count

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/stats/trends", dependencies=[Depends(require_admin)])
async def get_stats_trends_admin(
    _request: Request,
    metric: str,  # 'users', 'organizations', 'registrations', 'tokens'
    days: Optional[int] = 30,  # Number of days to look back
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _lang: str = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """Get time-series trends data for dashboard charts (ADMIN ONLY)"""
    # Special case: days=0 means all-time (no limit)
    all_time = False
    if days == 0:
        all_time = True
        days = None  # Will fetch all data
    elif days is not None:
        if days > 90:
            days = 90  # Cap at 90 days for regular queries
        elif days < 1:
            days = 1  # Minimum 1 day

    # Use Beijing time for date calculations
    beijing_now = get_beijing_now()
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Handle all-time query (days=None or days=0)
    if all_time:
        start_date_utc = None  # No start date limit - fetch all data
        beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
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
        days_value = days if days is not None else 30
        beijing_start = beijing_today_start - timedelta(days=days_value)
        # Convert to UTC for database queries
        start_date_utc = beijing_start.astimezone(timezone.utc).replace(tzinfo=None)
        beijing_now.astimezone(timezone.utc).replace(tzinfo=None)

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
            initial_count = db.query(_sql_count(User.id)).filter(
                User.created_at < start_date_utc
            ).scalar() or 0

            # Get user counts grouped by date (using UTC for DB query, but we'll map to Beijing dates)
            user_counts = db.query(
                func.date(User.created_at).label('date'),
                _sql_count(User.id).label('count')
            ).filter(
                User.created_at >= start_date_utc
            ).group_by(
                func.date(User.created_at)
            ).all()

            # Map UTC dates to Beijing dates
            counts_by_date = {}
            for row in user_counts:
                utc_date = row.date
                # Database may return date as string, need to parse it
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
            logger.error("Error fetching user trends: %s", e)
            # Return zeros if error
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})

    elif metric == 'organizations':
        # Daily cumulative organization count
        try:
            # Get initial count before start_date_utc
            initial_count = db.query(_sql_count(Organization.id)).filter(
                Organization.created_at < start_date_utc
            ).scalar() or 0

            org_counts = db.query(
                func.date(Organization.created_at).label('date'),
                _sql_count(Organization.id).label('count')
            ).filter(
                Organization.created_at >= start_date_utc
            ).group_by(
                func.date(Organization.created_at)
            ).all()

            # Map UTC dates to Beijing dates
            counts_by_date = {}
            for row in org_counts:
                utc_date = row.date
                # Database may return date as string, need to parse it
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
            logger.error("Error fetching organization trends: %s", e)
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})

    elif metric == 'registrations':
        # Daily new user registrations (non-cumulative)
        try:
            reg_counts = db.query(
                func.date(User.created_at).label('date'),
                _sql_count(User.id).label('count')
            ).filter(
                User.created_at >= start_date_utc
            ).group_by(
                func.date(User.created_at)
            ).all()

            # Map UTC dates to Beijing dates
            counts_by_date = {}
            for row in reg_counts:
                utc_date = row.date
                # Database may return date as string, need to parse it
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
            logger.error("Error fetching registration trends: %s", e)
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})

    elif metric == 'tokens':
        # Daily token usage (non-cumulative)
        try:
            token_counts_query = db.query(
                func.date(TokenUsage.created_at).label('date'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens')
            ).filter(
                TokenUsage.success
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
                # Database may return date as string, need to parse it
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
            logger.error("Error fetching token trends: %s", e)
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
    _request: Request,
    organization_id: Optional[int] = None,
    organization_name: Optional[str] = None,
    days: Optional[int] = 30,  # Number of days to look back
    hourly: bool = False,  # If True, return hourly data (only for days=1)
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _lang: str = Depends(get_language_dependency)
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
    elif days is not None:
        if days > 90:
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
        beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
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
        days_value = days if days is not None else 30
        beijing_start = beijing_today_start - timedelta(days=days_value)
        # Convert to UTC for database queries
        start_date_utc = beijing_start.astimezone(timezone.utc).replace(tzinfo=None)
        beijing_now.astimezone(timezone.utc).replace(tzinfo=None)

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
            # Query hourly token usage
            token_counts = db.query(
                func.strftime('%Y-%m-%d %H:00:00', TokenUsage.created_at).label('datetime'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens')
            ).filter(
                TokenUsage.organization_id == org.id,
                TokenUsage.success
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
            logger.error("Error fetching hourly organization token trends: %s", e)
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
            token_counts = db.query(
                func.date(TokenUsage.created_at).label('date'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens')
            ).filter(
                TokenUsage.organization_id == org.id,
                TokenUsage.success
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
                # Database may return date as string, need to parse it
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
            logger.error("Error fetching organization token trends: %s", e)
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
    _request: Request,
    user_id: Optional[int] = None,
    days: Optional[int] = 10,  # Number of days to look back, default 10
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _lang: str = Depends(get_language_dependency)
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
    elif days is not None:
        if days > 90:
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
        beijing_now.astimezone(timezone.utc).replace(tzinfo=None)
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
        days_value = days if days is not None else 10
        beijing_start = beijing_today_start - timedelta(days=days_value)
        # Convert to UTC for database queries
        start_date_utc = beijing_start.astimezone(timezone.utc).replace(tzinfo=None)
        beijing_now.astimezone(timezone.utc).replace(tzinfo=None)

    # Generate all dates in range using Beijing dates (for display)
    date_list = []
    current = beijing_start
    while current <= beijing_now:
        date_list.append(current.date())
        current += timedelta(days=1)

    trends_data = []

    # Daily token usage for this user (non-cumulative)
    try:
        token_counts = db.query(
            func.date(TokenUsage.created_at).label('date'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens')
        ).filter(
            TokenUsage.user_id == user.id,
            TokenUsage.success
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
            # Database may return date as string, need to parse it
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
        logger.error("Error fetching user token trends: %s", e)
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
