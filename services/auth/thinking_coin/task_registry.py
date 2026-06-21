"""Load earn tasks and settings with short TTL cache."""

from __future__ import annotations

import time
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinEarnTask, ThinkingCoinSetting
from utils.auth.thinking_coin_config import (
    CANVAS_ASSIST_REQUEST_TYPES,
    HANDLER_CLIENT_EVENT,
    HANDLER_USAGE_DAILY,
    SETTING_COST_CANVAS,
    SETTING_COST_DIAGRAM,
    SETTING_COST_MINDMATE,
    SETTING_DAILY_EARN_CAP,
    SETTING_SIGNUP_GRANT,
    THINKING_COIN_COST_CANVAS_ASSIST_DEFAULT,
    THINKING_COIN_COST_DIAGRAM_GEN_DEFAULT,
    THINKING_COIN_COST_MINDMATE_TURN_DEFAULT,
    THINKING_COIN_DAILY_EARN_CAP_DEFAULT,
    THINKING_COIN_SIGNUP_GRANT_DEFAULT,
)

_CACHE_TTL_SEC = 30.0


class _TaskRegistryCacheHolder:
    """Singleton holder for short-lived task/settings cache entries."""

    tasks: tuple[float, list[ThinkingCoinEarnTask]] | None = None
    settings: tuple[float, dict[str, int]] | None = None


def invalidate_task_cache() -> None:
    """Clear in-memory task/settings cache after admin edits."""
    _TaskRegistryCacheHolder.tasks = None
    _TaskRegistryCacheHolder.settings = None


async def load_all_tasks(db: AsyncSession) -> list[ThinkingCoinEarnTask]:
    """All earn tasks ordered for admin."""
    now = time.monotonic()
    cached = _TaskRegistryCacheHolder.tasks
    if cached is not None:
        cached_at, cached_rows = cached
        if now - cached_at < _CACHE_TTL_SEC:
            return list(cached_rows)
    rows = (
        await db.execute(
            select(ThinkingCoinEarnTask).order_by(
                ThinkingCoinEarnTask.sort_order.asc(),
                ThinkingCoinEarnTask.id.asc(),
            )
        )
    ).scalars().all()
    tasks = list(rows)
    _TaskRegistryCacheHolder.tasks = (now, tasks)
    return tasks


async def load_active_tasks(db: AsyncSession) -> list[ThinkingCoinEarnTask]:
    """Active earn tasks for user-facing UI."""
    tasks = await load_all_tasks(db)
    return [task for task in tasks if task.is_active]


async def get_task_by_slug(db: AsyncSession, slug: str) -> Optional[ThinkingCoinEarnTask]:
    """Resolve task by slug."""
    tasks = await load_all_tasks(db)
    for task in tasks:
        if task.slug == slug:
            return task
    return None


async def load_settings_map(db: AsyncSession) -> dict[str, int]:
    """Integer settings keyed by name."""
    now = time.monotonic()
    cached = _TaskRegistryCacheHolder.settings
    if cached is not None:
        cached_at, cached_values = cached
        if now - cached_at < _CACHE_TTL_SEC:
            return dict(cached_values)
    rows = (await db.execute(select(ThinkingCoinSetting))).scalars().all()
    values: dict[str, int] = {}
    for row in rows:
        if row.value_int is not None:
            values[row.key] = int(row.value_int)
    _TaskRegistryCacheHolder.settings = (now, values)
    return values


async def get_signup_grant(db: AsyncSession) -> int:
    """Signup grant amount."""
    settings = await load_settings_map(db)
    return settings.get(SETTING_SIGNUP_GRANT, THINKING_COIN_SIGNUP_GRANT_DEFAULT)


async def get_daily_earn_cap(db: AsyncSession) -> int:
    """Max task earn credits per Beijing day; 0 disables the cap."""
    settings = await load_settings_map(db)
    return settings.get(SETTING_DAILY_EARN_CAP, THINKING_COIN_DAILY_EARN_CAP_DEFAULT)


async def get_cost_for_request_type(db: AsyncSession, request_type: str) -> int:
    """Spend cost for an LLM request_type."""
    settings = await load_settings_map(db)
    if request_type == "mindmate":
        return settings.get(SETTING_COST_MINDMATE, THINKING_COIN_COST_MINDMATE_TURN_DEFAULT)
    if request_type == "diagram_generation":
        return settings.get(SETTING_COST_DIAGRAM, THINKING_COIN_COST_DIAGRAM_GEN_DEFAULT)
    if request_type in CANVAS_ASSIST_REQUEST_TYPES:
        return settings.get(SETTING_COST_CANVAS, THINKING_COIN_COST_CANVAS_ASSIST_DEFAULT)
    return settings.get(SETTING_COST_DIAGRAM, THINKING_COIN_COST_DIAGRAM_GEN_DEFAULT)


def task_request_type(task: ThinkingCoinEarnTask) -> Optional[str]:
    """Extract request_type from usage_daily task config."""
    config = task.action_config or {}
    raw = config.get("request_type")
    return str(raw) if raw else None


def task_client_event_key(task: ThinkingCoinEarnTask) -> Optional[str]:
    """Extract event_key from client_event task config."""
    config = task.action_config or {}
    raw = config.get("event_key")
    return str(raw) if raw else None


def tasks_for_client_event(
    tasks: Sequence[ThinkingCoinEarnTask],
    event_key: str,
) -> list[ThinkingCoinEarnTask]:
    """Active client_event tasks matching event_key."""
    matched: list[ThinkingCoinEarnTask] = []
    for task in tasks:
        if not task.is_active or task.handler_key != HANDLER_CLIENT_EVENT:
            continue
        configured = task_client_event_key(task)
        if configured == event_key:
            matched.append(task)
    return matched


def task_usage_context_matches(
    task: ThinkingCoinEarnTask,
    *,
    is_learning_sheet: bool | None = None,
) -> bool:
    """True when optional usage_daily action_config flags match the usage context."""
    config = task.action_config or {}
    if "is_learning_sheet" in config:
        if is_learning_sheet is None:
            return False
        return bool(config["is_learning_sheet"]) is bool(is_learning_sheet)
    return True


def tasks_for_request_type(
    tasks: Sequence[ThinkingCoinEarnTask],
    request_type: str,
    *,
    is_learning_sheet: bool | None = None,
) -> list[ThinkingCoinEarnTask]:
    """Active usage_daily tasks matching request_type and optional context flags."""
    matched: list[ThinkingCoinEarnTask] = []
    for task in tasks:
        if not task.is_active or task.handler_key != HANDLER_USAGE_DAILY:
            continue
        configured = task_request_type(task)
        if configured != request_type:
            continue
        if not task_usage_context_matches(task, is_learning_sheet=is_learning_sheet):
            continue
        matched.append(task)
    return matched


def settings_defaults() -> dict[str, int]:
    """Default global settings for seed/admin."""
    return {
        SETTING_SIGNUP_GRANT: THINKING_COIN_SIGNUP_GRANT_DEFAULT,
        SETTING_DAILY_EARN_CAP: THINKING_COIN_DAILY_EARN_CAP_DEFAULT,
        SETTING_COST_MINDMATE: THINKING_COIN_COST_MINDMATE_TURN_DEFAULT,
        SETTING_COST_DIAGRAM: THINKING_COIN_COST_DIAGRAM_GEN_DEFAULT,
        SETTING_COST_CANVAS: THINKING_COIN_COST_CANVAS_ASSIST_DEFAULT,
    }


def settings_payload(settings: dict[str, int]) -> dict[str, int]:
    """Merge DB settings with defaults for API."""
    merged = settings_defaults()
    merged.update(settings)
    return merged
