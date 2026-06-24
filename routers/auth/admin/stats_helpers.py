"""
Shared helpers for admin statistics route handlers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import coalesce as sa_coalesce
from sqlalchemy.sql.functions import count as sql_count
from sqlalchemy.sql.functions import sum as sa_sum

from models.domain.auth import Organization, User
from models.domain.token_usage import TokenUsage
from utils.auth.mindbot_token_stats import (
    aggregate_mindbot_tokens_by_linked_user,
    aggregate_mindbot_tokens_by_org,
    merge_mindbot_tokens_into_top_user_rows,
    merge_org_token_stats,
)
from utils.auth.token_stats_queries import token_usage_service_filter


def sql_count_column(column: Any) -> ColumnElement:
    """Sql count column."""
    return sql_count(column)


def mask_user_phone(phone: Optional[str]) -> str:
    """Mask user phone."""
    if phone and len(phone) == 11:
        return phone[:3] + "****" + phone[-4:]
    return phone or ""


def top_user_row_from_sql(
    row: Any,
    *,
    mask_phone: bool = False,
    include_org_name: bool = False,
    include_io_tokens: bool = False,
) -> Dict[str, Any]:
    """Top user row from sql."""
    raw_phone = row.phone or ""
    phone = mask_user_phone(raw_phone) if mask_phone else raw_phone
    display_name = row.name or raw_phone or str(row.id)
    if mask_phone and not row.name:
        display_name = phone or str(row.id)
    result: Dict[str, Any] = {
        "id": int(row.id),
        "phone": phone,
        "name": display_name,
        "total_tokens": int(row.total_tokens or 0),
    }
    if include_org_name:
        result["organization_name"] = row.organization_name or ""
    if include_io_tokens:
        result["input_tokens"] = int(row.input_tokens or 0)
        result["output_tokens"] = int(row.output_tokens or 0)
    return result


def _token_usage_join_conditions(
    *,
    created_since: Optional[datetime] = None,
    organization_id: Optional[int] = None,
    service: Optional[str] = None,
) -> list[ColumnElement]:
    """Token usage join conditions."""
    conditions = [
        User.id == TokenUsage.user_id,
        TokenUsage.success,
    ]
    if created_since is not None:
        conditions.append(TokenUsage.created_at >= created_since)
    if organization_id is not None:
        conditions.append(TokenUsage.organization_id == organization_id)
    service_filter = token_usage_service_filter(service)
    if service_filter is not None:
        conditions.append(service_filter)
    return conditions


async def token_stats_by_org(
    db: AsyncSession,
    created_since: Optional[datetime] = None,
    service: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Per-organization token usage since created_since (all-time when None)."""
    token_join = [
        Organization.id == TokenUsage.organization_id,
        TokenUsage.success,
    ]
    if created_since is not None:
        token_join.append(TokenUsage.created_at >= created_since)
    service_filter = token_usage_service_filter(service)
    if service_filter is not None:
        token_join.append(service_filter)

    org_rows = (
        await db.execute(
            select(
                Organization.id,
                Organization.name,
                sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                sa_coalesce(sql_count_column(TokenUsage.id), 0).label("request_count"),
            )
            .outerjoin(TokenUsage, and_(*token_join))
            .group_by(Organization.id, Organization.name)
        )
    ).all()

    by_org: Dict[str, Dict[str, Any]] = {}
    for org_stat in org_rows:
        if org_stat.request_count and org_stat.request_count > 0:
            by_org[org_stat.name] = {
                "org_id": org_stat.id,
                "input_tokens": int(org_stat.input_tokens or 0),
                "output_tokens": int(org_stat.output_tokens or 0),
                "total_tokens": int(org_stat.total_tokens or 0),
                "request_count": int(org_stat.request_count or 0),
            }
    return by_org


async def token_stats_by_org_today(
    db: AsyncSession,
    today_start,
    service: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Per-organization token usage for the current Beijing calendar day."""
    return await token_stats_by_org(db, created_since=today_start, service=service)


async def top_users_by_tokens(
    db: AsyncSession,
    created_since: Optional[datetime] = None,
    *,
    organization_id: Optional[int] = None,
    service: Optional[str] = None,
    limit: int = 10,
    mask_phone: bool = False,
    include_org_name: bool = False,
    include_io_tokens: bool = False,
    merge_mindbot: bool = True,
) -> list[Dict[str, Any]]:
    """Top users by token usage since created_since (all-time when None)."""
    usage_join = _token_usage_join_conditions(
        created_since=created_since,
        organization_id=organization_id,
        service=service,
    )
    stmt = (
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
        .select_from(User)
        .join(TokenUsage, and_(*usage_join))
        .outerjoin(Organization, User.organization_id == Organization.id)
    )
    if organization_id is not None:
        stmt = stmt.where(User.organization_id == organization_id)
    rows = (
        await db.execute(
            stmt.group_by(User.id, User.phone, User.name, Organization.id, Organization.name)
            .having(sa_coalesce(sa_sum(TokenUsage.total_tokens), 0) > 0)
            .order_by(desc(sa_coalesce(sa_sum(TokenUsage.total_tokens), 0)))
            .limit(limit)
        )
    ).all()
    users = [
        top_user_row_from_sql(
            row,
            mask_phone=mask_phone,
            include_org_name=include_org_name,
            include_io_tokens=include_io_tokens,
        )
        for row in rows
    ]
    if merge_mindbot:
        mindbot_by_user = await aggregate_mindbot_tokens_by_linked_user(
            db,
            created_since=created_since,
            organization_id=organization_id,
        )
        users = await merge_mindbot_tokens_into_top_user_rows(
            db,
            users,
            mindbot_by_user,
            organization_id=organization_id,
            limit=limit,
            mask_phone=mask_phone,
            include_org_name=include_org_name,
            include_io_tokens=include_io_tokens,
        )
    return users


async def top_users_by_tokens_today(
    db: AsyncSession,
    today_start,
    **kwargs: Any,
) -> list[Dict[str, Any]]:
    """Top users by token usage for the current Beijing calendar day."""
    return await top_users_by_tokens(db, created_since=today_start, **kwargs)


async def top_users_by_tokens_all_time(
    db: AsyncSession,
    **kwargs: Any,
) -> list[Dict[str, Any]]:
    """Top users by all-time token usage."""
    return await top_users_by_tokens(db, created_since=None, **kwargs)


async def build_admin_token_rankings(
    db: AsyncSession,
    *,
    today_start: datetime,
    week_ago: datetime,
    month_ago: datetime,
) -> Dict[str, Dict[str, Any]]:
    """Token usage rankings by period for the admin data center."""
    periods: list[tuple[str, Optional[datetime]]] = [
        ("today", today_start),
        ("week", week_ago),
        ("month", month_ago),
        ("total", None),
    ]
    rankings: Dict[str, Dict[str, Any]] = {}
    for period_key, since in periods:
        by_org = await token_stats_by_org(db, since)
        by_org_mindgraph = await token_stats_by_org(db, since, "mindgraph")
        by_org_mindmate = await token_stats_by_org(db, since, "mindmate")
        mindbot_orgs = await aggregate_mindbot_tokens_by_org(db, since)
        by_org = merge_org_token_stats(by_org, mindbot_orgs)
        by_org_mindmate = merge_org_token_stats(by_org_mindmate, mindbot_orgs)
        top_users = await top_users_by_tokens(
            db,
            since,
            mask_phone=True,
            include_org_name=True,
        )
        rankings[period_key] = {
            "by_org": by_org,
            "by_org_mindgraph": by_org_mindgraph,
            "by_org_mindmate": by_org_mindmate,
            "top_users": top_users,
        }
    return rankings
