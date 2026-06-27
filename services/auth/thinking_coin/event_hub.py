"""Central async hub for thinking coin earn/spend mutations."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from services.auth.thinking_coin.activity_earn import completed_usage_slugs_today
from services.auth.thinking_coin.checkin_service import is_checkin_completed_today, try_daily_checkin
from services.auth.thinking_coin.client_event_earn import try_client_event_earn
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
from services.auth.thinking_coin.wallet_service import get_balance, safe_commit
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.thinking_coin_config import SLUG_DAILY_CHECKIN, SLUG_PUBLISH_CASE, feature_thinking_coins_enabled

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThinkingCoinMutation:
    """Result of one thinking coin mutation for API/SSE footers."""

    eligible: bool
    balance: int
    credited: int
    debited: int
    task_slug: str | None
    earn_events: tuple[dict[str, int | str], ...] = field(default_factory=tuple)
    completed_slugs_today: tuple[str, ...] = field(default_factory=tuple)


def empty_mutation() -> ThinkingCoinMutation:
    """Ineligible / no-op mutation."""
    return ThinkingCoinMutation(
        eligible=False,
        balance=0,
        credited=0,
        debited=0,
        task_slug=None,
    )


async def _completed_slugs_for_user(db: AsyncSession, user_id: int) -> tuple[str, ...]:
    slugs = set(await completed_usage_slugs_today(db, user_id))
    if await is_checkin_completed_today(db, user_id):
        slugs.add(SLUG_DAILY_CHECKIN)
    return tuple(sorted(slugs))


async def _build_mutation(
    db: AsyncSession,
    user_id: int,
    *,
    eligible: bool,
    balance: int,
    credited: int = 0,
    debited: int = 0,
    task_slug: str | None = None,
    earn_events: list[dict[str, int | str]] | None = None,
) -> ThinkingCoinMutation:
    completed = await _completed_slugs_for_user(db, user_id) if eligible else ()
    return ThinkingCoinMutation(
        eligible=eligible,
        balance=balance,
        credited=credited,
        debited=debited,
        task_slug=task_slug,
        earn_events=tuple(earn_events or ()),
        completed_slugs_today=completed,
    )


def merge_mutation_footers(*footers: dict[str, Any]) -> dict[str, Any]:
    """Prefer last non-empty eligible footer (earn after spend)."""
    merged: dict[str, Any] = {}
    for footer in footers:
        if footer.get("eligible"):
            merged = footer
    return merged


def mutation_to_footer(mutation: ThinkingCoinMutation) -> dict[str, Any]:
    """JSON-serializable footer for API and SSE payloads."""
    if not mutation.eligible:
        return {"eligible": False, "balance": 0}
    return {
        "eligible": True,
        "balance": mutation.balance,
        "credited": mutation.credited,
        "debited": mutation.debited,
        "task_slug": mutation.task_slug,
        "earn_events": [dict(item) for item in mutation.earn_events],
        "completed_slugs_today": list(mutation.completed_slugs_today),
    }


def schedule_mutation_log(
    *,
    user_id: int,
    event_key: str | None,
    request_type: str | None,
    mutation: ThinkingCoinMutation,
) -> None:
    """Fire-and-forget structured audit log (never raises to callers)."""

    async def _log() -> None:
        if not mutation.eligible:
            return
        logger.info(
            "[ThinkingCoin] mutation user_id=%s event=%s request_type=%s credited=%s debited=%s balance=%s slug=%s",
            user_id,
            event_key,
            request_type,
            mutation.credited,
            mutation.debited,
            mutation.balance,
            mutation.task_slug,
        )

    asyncio.create_task(_log())


async def track_client_event(
    db: AsyncSession,
    user: User,
    org: Organization | None,
    event_key: str,
) -> ThinkingCoinMutation:
    """Credit a client_event task once per day when eligible."""
    if not feature_thinking_coins_enabled() or not user_eligible_for_thinking_coins(user, org):
        return empty_mutation()

    user_id = int(user.id)
    balance_before = await get_balance(db, user_id)
    credited, slug = await try_client_event_earn(db, user_id, event_key)
    balance = await get_balance(db, user_id)
    if credited > 0:
        await safe_commit(db)

    mutation = await _build_mutation(
        db,
        user_id,
        eligible=True,
        balance=balance,
        credited=credited,
        task_slug=slug,
    )
    schedule_mutation_log(user_id=user_id, event_key=event_key, request_type=None, mutation=mutation)
    if credited == 0 and balance_before == balance:
        return mutation
    return mutation


async def track_checkin(
    db: AsyncSession,
    user: User,
    org: Organization | None,
) -> ThinkingCoinMutation:
    """Explicit daily check-in credit."""
    if not feature_thinking_coins_enabled() or not user_eligible_for_thinking_coins(user, org):
        return empty_mutation()

    user_id = int(user.id)
    credited = await try_daily_checkin(db, user, org)
    balance = await get_balance(db, user_id)
    if credited > 0:
        await safe_commit(db)

    mutation = await _build_mutation(
        db,
        user_id,
        eligible=True,
        balance=balance,
        credited=credited,
        task_slug=SLUG_DAILY_CHECKIN if credited > 0 else None,
    )
    schedule_mutation_log(user_id=user_id, event_key="checkin", request_type=None, mutation=mutation)
    return mutation


async def mutation_from_spend_result(
    db: AsyncSession,
    user_id: int,
    *,
    debited: int,
    balance: int,
    earn_events: list[dict[str, int | str]],
) -> ThinkingCoinMutation:
    """Build footer after LLM spend + optional usage_daily earns."""
    credited = sum(int(item.get("amount", 0)) for item in earn_events)
    mutation = await _build_mutation(
        db,
        user_id,
        eligible=True,
        balance=balance,
        credited=credited,
        debited=debited,
        earn_events=earn_events,
    )
    schedule_mutation_log(user_id=user_id, event_key=None, request_type="ai_spend", mutation=mutation)
    return mutation


def attach_footer(payload: dict[str, Any], mutation: ThinkingCoinMutation) -> dict[str, Any]:
    """Merge thinking_coins footer into a response dict."""
    if not mutation.eligible:
        return payload
    merged = dict(payload)
    merged["thinking_coins"] = mutation_to_footer(mutation)
    return merged


def is_publish_case_coming_soon(slug: str) -> bool:
    """Publish case has no moderation credit path yet."""
    return slug == SLUG_PUBLISH_CASE


async def build_eligible_mutation(
    db: AsyncSession,
    user_id: int,
    *,
    balance: int,
    credited: int = 0,
    debited: int = 0,
    task_slug: str | None = None,
    earn_events: list[dict[str, int | str]] | None = None,
) -> ThinkingCoinMutation:
    """Public wrapper for eligible-user mutation footers."""
    return await _build_mutation(
        db,
        user_id,
        eligible=True,
        balance=balance,
        credited=credited,
        debited=debited,
        task_slug=task_slug,
        earn_events=earn_events,
    )


async def log_hub_infra_failure(context: str, exc: BaseException) -> None:
    """Log background hub failures without raising."""
    logger.debug("[ThinkingCoin] %s failed: %s", context, exc)


async def safe_track_client_event(
    db: AsyncSession,
    user: User,
    org: Organization | None,
    event_key: str,
) -> ThinkingCoinMutation:
    """Track client event; swallow infra errors."""
    try:
        return await track_client_event(db, user, org, event_key)
    except BACKGROUND_INFRA_ERRORS as exc:
        await log_hub_infra_failure(f"track_client_event({event_key})", exc)
        return empty_mutation()
