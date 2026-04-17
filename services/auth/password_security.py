"""
Shared cache, refresh token, and session invalidation after password database writes.

Used by self-service password reset/change and admin password reset.
"""

import logging

from models.domain.auth import User
from services.redis.cache.redis_user_cache import user_cache
from services.redis.session import get_refresh_token_manager, get_session_manager

logger = logging.getLogger(__name__)


async def invalidate_user_cache_after_password_write(user: User, context_label: str) -> None:
    """Invalidate and re-cache user after password hash changed in DB."""
    try:
        await user_cache.invalidate(user.id, user.phone, getattr(user, "email", None))
        await user_cache.cache_user(user)
        logger.info("[Auth] %s: cache updated for user ID %s", context_label, user.id)
    except Exception as exc:
        logger.warning(
            "[Auth] Failed to update cache after password write (%s, user=%s): %s",
            context_label,
            user.id,
            exc,
        )


async def revoke_refresh_tokens_and_sessions(user_id: int, refresh_reason: str) -> None:
    """Revoke all refresh tokens and clear access-token sessions in Redis."""
    try:
        await get_refresh_token_manager().revoke_all_refresh_tokens(
            user_id=user_id,
            reason=refresh_reason,
        )
    except Exception as exc:
        logger.warning(
            "[Auth] Failed to revoke refresh tokens after password write (user=%s): %s",
            user_id,
            exc,
        )
    try:
        await get_session_manager().invalidate_user_sessions(user_id)
    except Exception as exc:
        logger.warning(
            "[Auth] Failed to invalidate sessions after password write (user=%s): %s",
            user_id,
            exc,
        )
