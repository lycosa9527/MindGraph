"""Claim client events for eligible trial-org members."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
from services.auth.thinking_coin.event_hub import track_client_event
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.thinking_coin_config import feature_thinking_coins_enabled

logger = logging.getLogger(__name__)


async def load_user_org(user: User) -> Organization | None:
    """Resolve organization for thinking coin eligibility."""
    org_id = getattr(user, "organization_id", None)
    if not org_id:
        return None
    try:
        return await org_cache.get_by_id(int(org_id))
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[ThinkingCoin] org cache failed: %s", exc)
        return None


async def claim_client_event(
    db: AsyncSession,
    user: User,
    org: Organization | None,
    event_key: str,
) -> tuple[int, int, str | None]:
    """Credit a client event when eligible; returns (credited, balance, slug)."""
    if not feature_thinking_coins_enabled() or not user_eligible_for_thinking_coins(user, org):
        return 0, 0, None

    mutation = await track_client_event(db, user, org, event_key)
    return mutation.credited, mutation.balance, mutation.task_slug


async def claim_client_event_for_user(
    db: AsyncSession,
    user: User,
    event_key: str,
) -> tuple[int, int, str | None]:
    """Load org and claim a client event."""
    org = await load_user_org(user)
    return await claim_client_event(db, user, org, event_key)
