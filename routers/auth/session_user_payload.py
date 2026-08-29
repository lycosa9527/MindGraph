"""Authenticated session user JSON shared by login, register, and /me."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from services.auth.thinking_coin.checkin_service import ensure_wallet_bootstrap
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
from services.auth.thinking_coin.wallet_payload import build_wallet_payload
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth import get_user_role
from utils.auth.thinking_coin_config import feature_thinking_coins_enabled
from utils.auth.user_daily_token_quota import current_user_daily_token_payload
from utils.user_avatar_defaults import DEFAULT_USER_AVATAR_EMOJI

from .org_profile import organization_session_payload
from .user_session_prefs import user_preference_fields


async def resolve_session_organization(
    user: User,
    org: Organization | None,
) -> Organization | None:
    """Use the caller org, or the cached org for ``user.organization_id``."""
    if org is not None:
        return org
    org_id = getattr(user, "organization_id", None)
    if not org_id:
        return None
    try:
        return await org_cache.get_by_id(org_id)
    except BACKGROUND_INFRA_ERRORS:
        return None


async def thinking_coins_session_summary(
    db: AsyncSession,
    user: User,
    org: Organization | None,
) -> dict[str, Any]:
    """Sidebar wallet fields. Same bootstrap as GET /me so login can show coins."""
    summary: dict[str, Any] = {"balance": 0, "eligible": False}
    if not feature_thinking_coins_enabled():
        return summary
    if user_eligible_for_thinking_coins(user, org):
        await ensure_wallet_bootstrap(db, user, org)
    wallet_payload = await build_wallet_payload(db, user, org)
    return {
        "balance": wallet_payload.get("balance", 0),
        "eligible": wallet_payload.get("eligible", False),
    }


async def build_session_user_payload(
    db: AsyncSession,
    user: User,
    org: Organization | None,
) -> dict[str, Any]:
    """User object embedded in login/register JSON and flattened on /me."""
    resolved_org = await resolve_session_organization(user, org)
    thinking_coins = await thinking_coins_session_summary(db, user, resolved_org)
    daily_tokens = await current_user_daily_token_payload(int(user.id))
    created_at = user.created_at.isoformat() if user.created_at else None
    last_login = user.last_login.isoformat() if user.last_login else None
    return {
        "id": user.id,
        "phone": user.phone,
        "email": getattr(user, "email", None),
        "name": user.name,
        "avatar": user.avatar or DEFAULT_USER_AVATAR_EMOJI,
        "role": get_user_role(user),
        "login_password_set": getattr(user, "login_password_set", True),
        "organization": organization_session_payload(resolved_org),
        "thinking_coins": thinking_coins,
        "daily_tokens": daily_tokens,
        "created_at": created_at,
        "last_login": last_login,
        **user_preference_fields(user),
    }
