"""Wire thinking coins to LLM usage (spend + earn)."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from config.db_sessions import open_async_session
from models.domain.auth import Organization, User
from models.domain.messages import Language, Messages
from services.auth.thinking_coin.activity_earn import try_daily_activity_earn
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
from services.auth.thinking_coin.task_registry import get_cost_for_request_type
from services.auth.thinking_coin.token_usage_link import (
    TokenUsageSnapshot,
    insert_token_usage_row,
)
from services.auth.thinking_coin.wallet_service import debit_wallet, get_balance, safe_commit
from services.infrastructure.http.error_handler import ThinkingCoinInsufficientError
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from utils.auth.thinking_coin_config import LEDGER_AI_SPEND, feature_thinking_coins_enabled
from utils.auth.user_daily_token_quota import assert_user_daily_token_budget

logger = logging.getLogger(__name__)


def thinking_coin_limit_message(lang: Language, balance: int, cost: int) -> str:
    """Localized insufficient-balance message."""
    return Messages.error("thinking_coin_insufficient", lang, balance, cost)


async def _resolve_user_org(
    user_id: int,
    organization_id: Optional[int],
) -> tuple[Optional[User], Optional[Organization]]:
    user = await user_cache.get_by_id(user_id)
    if user is None:
        return None, None
    org_id = organization_id if organization_id is not None else getattr(user, "organization_id", None)
    org = await org_cache.get_by_id(int(org_id)) if org_id else None
    return user, org


async def thinking_coins_apply_to_user(
    user_id: Optional[int],
    organization_id: Optional[int],
) -> bool:
    """True when this LLM call should use thinking coins instead of daily token cap."""
    if user_id is None or not feature_thinking_coins_enabled():
        return False
    user, org = await _resolve_user_org(int(user_id), organization_id)
    return user_eligible_for_thinking_coins(user, org)


async def assert_thinking_coin_llm_budget(
    user_id: Optional[int],
    organization_id: Optional[int],
    request_type: str,
    lang: Language = "en",
) -> bool:
    """
    Pre-flight balance check for thinking-coin users.

    Returns True when thinking coins handled (caller skips daily token cap).
    Raises ThinkingCoinInsufficientError when balance too low.
    """
    if not await thinking_coins_apply_to_user(user_id, organization_id):
        return False
    assert user_id is not None

    async with open_async_session() as db:
        cost = await get_cost_for_request_type(db, request_type)
        balance = await get_balance(db, int(user_id))
        if balance < cost:
            message = thinking_coin_limit_message(lang, balance, cost)
            raise ThinkingCoinInsufficientError(balance=balance, cost=cost, user_message=message)
    return True


async def assert_llm_usage_budget(
    user_id: Optional[int],
    organization_id: Optional[int],
    request_type: str,
    *,
    estimated_tokens: int = 0,
    lang: Language = "en",
) -> None:
    """Thinking coins for trial users; otherwise daily LLM token cap."""
    handled = await assert_thinking_coin_llm_budget(
        user_id,
        organization_id,
        request_type,
        lang,
    )
    if not handled:
        await assert_user_daily_token_budget(
            user_id,
            estimated_tokens=estimated_tokens,
            lang=lang,
        )


async def thinking_coin_post_llm_success(
    user_id: Optional[int],
    organization_id: Optional[int],
    request_type: str,
    usage_snapshot: Optional[TokenUsageSnapshot] = None,
) -> list[dict[str, int | str]]:
    """
    Debit spend and try usage_daily earns after successful LLM call.

    Returns earn events (for optional client toast).
    """
    if not await thinking_coins_apply_to_user(user_id, organization_id):
        return []
    assert user_id is not None

    events: list[dict[str, int | str]] = []
    async with open_async_session() as db:
        cost = await get_cost_for_request_type(db, request_type)
        ref_type = "request_type"
        ref_id: str = request_type
        if usage_snapshot is not None:
            token_usage_id = await insert_token_usage_row(db, usage_snapshot)
            ref_type = "token_usage"
            ref_id = str(token_usage_id)
        await debit_wallet(
            db,
            int(user_id),
            cost,
            LEDGER_AI_SPEND,
            ref_type=ref_type,
            ref_id=ref_id,
        )
        events = await try_daily_activity_earn(db, int(user_id), request_type)
        await safe_commit(db)
    return events


def result_is_learning_sheet(result: dict[str, object]) -> bool:
    """True when a diagram generation workflow result is a learning sheet."""
    if bool(result.get("is_learning_sheet")):
        return True
    spec = result.get("spec")
    if isinstance(spec, dict):
        if spec.get("is_learning_sheet") is True:
            return True
        if spec.get("isLearningSheet") is True:
            return True
    return False


async def try_learning_sheet_diagram_earn(
    db: AsyncSession,
    user_id: int,
    result: dict[str, object],
) -> list[dict[str, int | str]]:
    """Credit learning-sheet-specific usage_daily task after diagram generation."""
    if not result_is_learning_sheet(result):
        return []
    return await try_daily_activity_earn(
        db,
        user_id,
        "diagram_generation",
        is_learning_sheet=True,
    )


async def thinking_coin_post_diagram_generation(
    user_id: Optional[int],
    organization_id: Optional[int],
    result: dict[str, object],
) -> list[dict[str, int | str]]:
    """Credit learning-sheet diagram earn after successful generation workflow."""
    if not await thinking_coins_apply_to_user(user_id, organization_id):
        return []
    assert user_id is not None

    async with open_async_session() as db:
        events = await try_learning_sheet_diagram_earn(db, int(user_id), result)
        if events:
            await safe_commit(db)
        return events
