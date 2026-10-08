"""Superadmin LLM routing diagram and live model/endpoint overrides.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from models.domain.token_usage import TokenUsage
from routers.auth.dependencies import get_async_db_with_request_rls, require_settings_llm_control
from services.infrastructure.utils.llm_routing_overrides import (
    RoutingStoreError,
    apply_routing_updates,
    refresh_routing_overrides,
)
from services.infrastructure.utils.llm_routing_store import (
    TokenRow,
    accumulate_token_rows,
    build_llm_control_view,
)
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin", "llm-control"])


class LlmControlUpdateBody(BaseModel):
    """Partial map of routing field to new value. Null clears that override."""

    model_config = ConfigDict(extra="forbid")

    updates: Dict[str, Optional[str]]


async def _token_rows(session: AsyncSession) -> List[TokenRow]:
    stmt = (
        select(
            TokenUsage.model_alias,
            TokenUsage.model_provider,
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
            func.count(TokenUsage.id),
        )
        .where(TokenUsage.success.is_(True))
        .group_by(TokenUsage.model_alias, TokenUsage.model_provider)
    )
    rows = (await session.execute(stmt)).all()
    parsed: List[TokenRow] = []
    for alias, provider, tokens, requests in rows:
        parsed.append((alias, provider, int(tokens or 0), int(requests or 0)))
    return parsed


async def _view(session: AsyncSession, redis_ok: bool) -> Dict[str, object]:
    tokens_ok = True
    try:
        totals = accumulate_token_rows(await _token_rows(session))
    except SQLAlchemyError:
        logger.exception("LLM control token totals failed")
        totals = {}
        tokens_ok = False
    weights = config.LOAD_BALANCING_WEIGHTS
    app_rpm = {
        "deepseek_dashscope": config.DASHSCOPE_QPM_LIMIT,
        "express": config.DASHSCOPE_QPM_LIMIT,
        "deepseek_volcengine": config.DEEPSEEK_VOLCENGINE_QPM_LIMIT,
        "qwen": config.QWEN_DASHSCOPE_QPM_LIMIT,
        "qwen38": config.QWEN38_DASHSCOPE_QPM_LIMIT,
        "doubao": config.DOUBAO_VOLCENGINE_QPM_LIMIT,
        "kimi": config.KIMI_VOLCENGINE_QPM_LIMIT,
    }
    return build_llm_control_view(
        tokens=totals,
        redis_ok=redis_ok,
        tokens_ok=tokens_ok,
        weights=weights,
        balancing_enabled=bool(config.LOAD_BALANCING_ENABLED),
        strategy=str(config.LOAD_BALANCING_STRATEGY),
        app_rpm=app_rpm,
    )


@router.get("/admin/llm-control")
async def get_llm_control(
    _scope: AdminScope = Depends(require_settings_llm_control),
    session: AsyncSession = Depends(get_async_db_with_request_rls),
) -> Dict[str, object]:
    """Traffic diagram plus the current DashScope names and Volcengine endpoints."""
    redis_ok = await refresh_routing_overrides(force=True)
    return await _view(session, redis_ok)


@router.put("/admin/llm-control")
async def update_llm_control(
    body: LlmControlUpdateBody,
    _scope: AdminScope = Depends(require_settings_llm_control),
    session: AsyncSession = Depends(get_async_db_with_request_rls),
) -> Dict[str, object]:
    """Store live overrides. Workers apply them on the next chat or node-explain call."""
    try:
        await apply_routing_updates(body.updates)
    except ValueError as exc:
        code = str(exc)
        if code not in ("invalid_value", "unknown_field"):
            code = "invalid_value"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from exc
    except RoutingStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="redis_unavailable") from exc
    return await _view(session, True)
