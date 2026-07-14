"""User-facing wallet payload builder."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from models.domain.thinking_coin import ThinkingCoinEarnTask
from services.auth.thinking_coin.activity_earn import completed_usage_slugs_today
from services.auth.thinking_coin.checkin_service import is_checkin_completed_today
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
from services.auth.thinking_coin.task_registry import load_active_tasks
from services.auth.thinking_coin.wallet_service import get_balance
from utils.auth.thinking_coin_config import (
    HANDLER_AUTO_LOGIN,
    HANDLER_CLIENT_EVENT,
    HANDLER_NAVIGATE,
    HANDLER_USAGE_DAILY,
    SLUG_PUBLISH_CASE,
)


def _status_hint(task: ThinkingCoinEarnTask, completed: bool) -> Optional[str]:
    if task.slug == SLUG_PUBLISH_CASE:
        return "审核通过后发放"
    if task.handler_key == HANDLER_AUTO_LOGIN and completed:
        return "今日已签到"
    if task.handler_key == HANDLER_USAGE_DAILY and completed:
        return "今日已完成"
    if task.handler_key == HANDLER_CLIENT_EVENT and completed:
        return "今日已完成"
    return None


def _task_completed(
    task: ThinkingCoinEarnTask,
    *,
    checkin_done: bool,
    usage_slugs: set[str],
) -> bool:
    if task.handler_key == HANDLER_AUTO_LOGIN:
        return checkin_done
    if task.handler_key == HANDLER_USAGE_DAILY:
        return task.slug in usage_slugs
    if task.handler_key == HANDLER_CLIENT_EVENT:
        return task.slug in usage_slugs
    if task.handler_key == HANDLER_NAVIGATE:
        return False
    return False


async def build_wallet_payload(
    db: AsyncSession,
    user: User,
    org: Organization | None,
) -> dict[str, Any]:
    """Wallet summary for API."""
    eligible = user_eligible_for_thinking_coins(user, org)
    user_id = int(user.id)
    if not eligible:
        return {"balance": 0, "eligible": False, "earn_tasks": []}

    balance = await get_balance(db, user_id)
    tasks = await load_active_tasks(db)
    checkin_done = await is_checkin_completed_today(db, user_id)
    usage_slugs = await completed_usage_slugs_today(db, user_id)

    earn_tasks: list[dict[str, Any]] = []
    for task in tasks:
        completed = _task_completed(
            task,
            checkin_done=checkin_done,
            usage_slugs=usage_slugs,
        )
        earn_tasks.append(
            {
                "id": task.id,
                "slug": task.slug,
                "title": task.title,
                "subtitle": task.subtitle,
                "title_en": task.title_en,
                "subtitle_en": task.subtitle_en,
                "reward_amount": int(task.reward_amount),
                "handler_key": task.handler_key,
                "action_config": task.action_config or {},
                "completed_today": completed,
                "status_hint": _status_hint(task, completed),
                "coming_soon": False,
            }
        )

    return {
        "balance": balance,
        "eligible": True,
        "earn_tasks": earn_tasks,
    }
