"""Shared aggregates for API-key and DingTalk generation usage in admin views.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sql_count

from models.domain.token_usage import TokenUsage

GENERATE_DINGTALK_ENDPOINT = "/api/generate_dingtalk"


async def dingtalk_request_counts_by_api_key_id(db: AsyncSession) -> dict[int, int]:
    """Successful POST /api/generate_dingtalk rows grouped by api_key_id."""
    rows = (
        await db.execute(
            select(
                TokenUsage.api_key_id,
                sql_count(TokenUsage.id).label("request_count"),
            )
            .where(
                TokenUsage.api_key_id.isnot(None),
                TokenUsage.endpoint_path == GENERATE_DINGTALK_ENDPOINT,
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
