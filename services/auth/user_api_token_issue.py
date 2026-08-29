"""Issue or replace the single per-user mgat_ API token."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.user_api_token import UserAPIToken
from services.redis.cache.redis_user_token_cache import user_token_cache

TOKEN_TTL_DAYS = 90


@dataclass(frozen=True)
class IssuedUserApiToken:
    """Raw token shown once; only the hash is stored."""

    token: str
    account: str
    expires_at: datetime


async def issue_user_api_token(db: AsyncSession, user: User) -> IssuedUserApiToken:
    """Return a raw mgat_ for the caller.

    Creates a row if the user has never had a token (or the old row is
    reused). Replaces an existing token because only the hash is stored.
    """
    raw = f"mgat_{secrets.token_hex(32)}"
    token_hash_full = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=TOKEN_TTL_DAYS)

    result = await db.execute(select(UserAPIToken).where(UserAPIToken.user_id == user.id))
    existing = result.scalar_one_or_none()
    if existing:
        await user_token_cache.invalidate_by_token_hash_64(existing.token_hash)
        existing.token_hash = token_hash_full
        existing.expires_at = expires_at
        existing.is_active = True
        existing.created_at = now
        existing.last_used_at = None
        row = existing
    else:
        row = UserAPIToken(
            user_id=user.id,
            token_hash=token_hash_full,
            expires_at=expires_at,
            created_at=now,
            last_used_at=None,
            is_active=True,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    await user_token_cache.set_from_row(raw, row)
    return IssuedUserApiToken(
        token=raw,
        account=str(user.phone or "").strip(),
        expires_at=expires_at,
    )
