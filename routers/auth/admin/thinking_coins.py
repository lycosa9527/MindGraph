"""Admin thinking coin task and settings API."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinEarnTask, ThinkingCoinSetting
from routers.auth.dependencies import get_async_db_with_request_rls, require_settings_thinking_coins
from services.auth.thinking_coin.task_registry import (
    invalidate_task_cache,
    load_all_tasks,
    load_settings_map,
    settings_payload,
)
from services.auth.thinking_coin.wallet_service import safe_commit
from utils.auth.admin_scope import AdminScope
from utils.auth.thinking_coin_config import (
    HANDLER_AUTO_LOGIN,
    HANDLER_CLIENT_EVENT,
    HANDLER_CUSTOM_CTA,
    HANDLER_NAVIGATE,
    HANDLER_REFERRAL,
    HANDLER_USAGE_DAILY,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/thinking-coins", tags=["admin-thinking-coins"])

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
_PHASE1_HANDLERS = frozenset(
    {
        HANDLER_AUTO_LOGIN,
        HANDLER_USAGE_DAILY,
        HANDLER_CLIENT_EVENT,
        HANDLER_NAVIGATE,
        HANDLER_CUSTOM_CTA,
    }
)


class EarnTaskBody(BaseModel):
    """Create earn task request."""

    slug: str
    title: str
    subtitle: Optional[str] = None
    title_en: Optional[str] = None
    subtitle_en: Optional[str] = None
    reward_amount: int = Field(ge=0)
    monthly_cap: Optional[int] = Field(default=None, ge=0)
    handler_key: str
    action_config: Optional[dict[str, Any]] = None
    sort_order: int = 0
    is_active: bool = True


class EarnTaskUpdateBody(BaseModel):
    """Partial earn task update."""

    title: Optional[str] = None
    subtitle: Optional[str] = None
    title_en: Optional[str] = None
    subtitle_en: Optional[str] = None
    reward_amount: Optional[int] = Field(default=None, ge=0)
    monthly_cap: Optional[int] = Field(default=None, ge=0)
    handler_key: Optional[str] = None
    action_config: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class SettingsBody(BaseModel):
    """Global thinking coin economy settings."""

    signup_grant: int = Field(ge=0)
    daily_earn_cap: int = Field(ge=0)
    cost_mindmate_turn: int = Field(ge=0)
    cost_diagram_gen: int = Field(ge=0)
    cost_canvas_assist: int = Field(ge=0)


def _task_to_dict(task: ThinkingCoinEarnTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "slug": task.slug,
        "title": task.title,
        "subtitle": task.subtitle,
        "title_en": task.title_en,
        "subtitle_en": task.subtitle_en,
        "reward_amount": int(task.reward_amount),
        "monthly_cap": task.monthly_cap,
        "handler_key": task.handler_key,
        "action_config": task.action_config,
        "sort_order": int(task.sort_order),
        "is_active": bool(task.is_active),
        "is_system": bool(task.is_system),
    }


def _validate_handler(handler_key: str, *, allow_referral: bool = False) -> None:
    allowed = set(_PHASE1_HANDLERS)
    if allow_referral:
        allowed.add(HANDLER_REFERRAL)
    if handler_key not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported handler_key: {handler_key}",
        )


@router.get("/tasks")
async def list_tasks(
    _scope: AdminScope = Depends(require_settings_thinking_coins),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, Any]:
    """List all earn tasks including inactive rows."""
    tasks = await load_all_tasks(db)
    return {"tasks": [_task_to_dict(task) for task in tasks]}


@router.post("/tasks")
async def create_task(
    body: EarnTaskBody,
    _scope: AdminScope = Depends(require_settings_thinking_coins),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, Any]:
    """Create a non-system earn task."""
    if not _SLUG_RE.match(body.slug):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid slug")
    _validate_handler(body.handler_key)

    existing = (
        await db.execute(select(ThinkingCoinEarnTask).where(ThinkingCoinEarnTask.slug == body.slug))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")

    task = ThinkingCoinEarnTask(
        slug=body.slug,
        title=body.title,
        subtitle=body.subtitle,
        title_en=body.title_en,
        subtitle_en=body.subtitle_en,
        reward_amount=body.reward_amount,
        monthly_cap=body.monthly_cap,
        handler_key=body.handler_key,
        action_config=body.action_config,
        sort_order=body.sort_order,
        is_active=body.is_active,
        is_system=False,
    )
    db.add(task)
    await safe_commit(db)
    invalidate_task_cache()
    await db.refresh(task)
    return {"task": _task_to_dict(task)}


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: EarnTaskUpdateBody,
    _scope: AdminScope = Depends(require_settings_thinking_coins),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, Any]:
    """Update reward, copy, or active flag for an earn task."""
    task = (
        await db.execute(select(ThinkingCoinEarnTask).where(ThinkingCoinEarnTask.id == task_id))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if body.handler_key is not None:
        _validate_handler(body.handler_key, allow_referral=task.slug == "referral_register")
        if task.is_system and body.handler_key != task.handler_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change system handler")
        task.handler_key = body.handler_key

    if body.title is not None:
        task.title = body.title
    if body.subtitle is not None:
        task.subtitle = body.subtitle
    if body.title_en is not None:
        task.title_en = body.title_en
    if body.subtitle_en is not None:
        task.subtitle_en = body.subtitle_en
    if body.reward_amount is not None:
        task.reward_amount = body.reward_amount
    if body.monthly_cap is not None:
        task.monthly_cap = body.monthly_cap
    if body.action_config is not None:
        task.action_config = body.action_config
    if body.sort_order is not None:
        task.sort_order = body.sort_order
    if body.is_active is not None:
        task.is_active = body.is_active

    await safe_commit(db)
    invalidate_task_cache()
    await db.refresh(task)
    return {"task": _task_to_dict(task)}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    _scope: AdminScope = Depends(require_settings_thinking_coins),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, bool]:
    """Delete a non-system earn task."""
    task = (
        await db.execute(select(ThinkingCoinEarnTask).where(ThinkingCoinEarnTask.id == task_id))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System tasks cannot be deleted")

    await db.execute(delete(ThinkingCoinEarnTask).where(ThinkingCoinEarnTask.id == task_id))
    await safe_commit(db)
    invalidate_task_cache()
    return {"ok": True}


@router.get("/settings")
async def get_settings(
    _scope: AdminScope = Depends(require_settings_thinking_coins),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, int]:
    """Return merged global settings with code defaults."""
    stored = await load_settings_map(db)
    return settings_payload(stored)


@router.put("/settings")
async def put_settings(
    body: SettingsBody,
    _scope: AdminScope = Depends(require_settings_thinking_coins),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, int]:
    """Persist global signup grant and AI spend costs."""
    mapping = {
        "signup_grant": body.signup_grant,
        "daily_earn_cap": body.daily_earn_cap,
        "cost_mindmate_turn": body.cost_mindmate_turn,
        "cost_diagram_gen": body.cost_diagram_gen,
        "cost_canvas_assist": body.cost_canvas_assist,
    }
    for key, value in mapping.items():
        row = (await db.execute(select(ThinkingCoinSetting).where(ThinkingCoinSetting.key == key))).scalar_one_or_none()
        if row is None:
            db.add(ThinkingCoinSetting(key=key, value_int=value))
        else:
            row.value_int = value
    await safe_commit(db)
    invalidate_task_cache()
    return settings_payload(mapping)
