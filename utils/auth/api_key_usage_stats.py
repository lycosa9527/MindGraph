"""Shared aggregates for external-API (X-API-Key) generation usage in admin views.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sql_count

from models.domain.token_usage import TokenUsage

GENERATE_DINGTALK_ENDPOINT = "/api/generate_dingtalk"
GENERATE_TEXT_TO_IMAGE_ENDPOINT = "/api/generate-text-to-image"

EXTERNAL_API_ENDPOINTS = (
    GENERATE_DINGTALK_ENDPOINT,
    GENERATE_TEXT_TO_IMAGE_ENDPOINT,
)


async def _request_counts_by_api_key_id(
    db: AsyncSession,
    endpoint_path: str,
) -> dict[int, int]:
    """Successful TokenUsage rows for one endpoint, grouped by api_key_id."""
    rows = (
        await db.execute(
            select(
                TokenUsage.api_key_id,
                sql_count(TokenUsage.id).label("request_count"),
            )
            .where(
                TokenUsage.api_key_id.isnot(None),
                TokenUsage.endpoint_path == endpoint_path,
                TokenUsage.success,
            )
            .group_by(TokenUsage.api_key_id)
        )
    ).all()
    counts: dict[int, int] = {}
    for row in rows:
        key_id = row.api_key_id
        if key_id is None:
            continue
        counts[int(key_id)] = int(row.request_count or 0)
    return counts


async def dingtalk_request_counts_by_api_key_id(db: AsyncSession) -> dict[int, int]:
    """Successful POST /api/generate_dingtalk rows grouped by api_key_id."""
    return await _request_counts_by_api_key_id(db, GENERATE_DINGTALK_ENDPOINT)


async def image_request_counts_by_api_key_id(db: AsyncSession) -> dict[int, int]:
    """Successful POST /api/generate-text-to-image rows grouped by api_key_id."""
    return await _request_counts_by_api_key_id(db, GENERATE_TEXT_TO_IMAGE_ENDPOINT)


async def external_api_request_counts_by_api_key_id(
    db: AsyncSession,
) -> dict[int, dict[str, int]]:
    """
    Per-key request counts for diagram (generate_dingtalk) and image
    (generate-text-to-image).

    Returns ``{api_key_id: {"diagram": n, "image": m, "total": n+m}}``.
    """
    diagram = await dingtalk_request_counts_by_api_key_id(db)
    image = await image_request_counts_by_api_key_id(db)
    key_ids = set(diagram) | set(image)
    result: dict[int, dict[str, int]] = {}
    for key_id in key_ids:
        d_count = diagram.get(key_id, 0)
        i_count = image.get(key_id, 0)
        result[key_id] = {
            "diagram": d_count,
            "image": i_count,
            "total": d_count + i_count,
        }
    return result


async def count_successful_endpoint_calls(
    db: AsyncSession,
    endpoint_path: str,
    *,
    created_since: Optional[object] = None,
    organization_id: Optional[int] = None,
) -> int:
    """Count successful TokenUsage rows for an endpoint (optional time/org filter)."""
    stmt = select(sql_count(TokenUsage.id)).where(
        TokenUsage.endpoint_path == endpoint_path,
        TokenUsage.success,
    )
    if created_since is not None:
        stmt = stmt.where(TokenUsage.created_at >= created_since)
    if organization_id is not None:
        stmt = stmt.where(TokenUsage.organization_id == organization_id)
    row = (await db.execute(stmt)).scalar()
    return int(row or 0)
