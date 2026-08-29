"""Issue or reuse the single per-user mgat_ API token."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.user_api_token import UserAPIToken
from services.auth.user_api_token_secret import decrypt_user_api_token, encrypt_user_api_token
from services.redis.cache.redis_user_token_cache import user_token_cache
from utils.auth.datetime_compat import as_utc_aware

TOKEN_TTL_DAYS = 90


@dataclass(frozen=True)
class IssuedUserApiToken:
    """Raw token plus expiry; ciphertext is stored for later display."""

    token: str
    account: str
    expires_at: datetime
    minted: bool


def reveal_stored_user_api_token(row: UserAPIToken) -> str | None:
    """Decrypt the stored secret when the row is still live."""
    if not row.is_active:
        return None
    if as_utc_aware(row.expires_at) <= datetime.now(UTC):
        return None
    cipher = row.token_ciphertext
    if not isinstance(cipher, str) or not cipher.strip():
        return None
    return decrypt_user_api_token(cipher)


async def peek_live_user_api_token(db: AsyncSession, user: User) -> IssuedUserApiToken | None:
    """Return the current raw token when it can be decrypted."""
    result = await db.execute(select(UserAPIToken).where(UserAPIToken.user_id == user.id))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    raw = reveal_stored_user_api_token(row)
    if raw is None:
        return None
    return IssuedUserApiToken(
        token=raw,
        account=str(user.phone or "").strip(),
        expires_at=as_utc_aware(row.expires_at),
        minted=False,
    )


async def issue_user_api_token(db: AsyncSession, user: User) -> IssuedUserApiToken:
    """Mint a raw mgat_ and persist hash plus ciphertext."""
    raw = f"mgat_{secrets.token_hex(32)}"
    token_hash_full = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=TOKEN_TTL_DAYS)
    ciphertext = encrypt_user_api_token(raw)

    result = await db.execute(select(UserAPIToken).where(UserAPIToken.user_id == user.id))
    existing = result.scalar_one_or_none()
    if existing:
        await user_token_cache.invalidate_by_token_hash_64(existing.token_hash)
        existing.token_hash = token_hash_full
        existing.token_ciphertext = ciphertext
        existing.expires_at = expires_at
        existing.is_active = True
        existing.created_at = now
        existing.last_used_at = None
        row = existing
    else:
        row = UserAPIToken(
            user_id=user.id,
            token_hash=token_hash_full,
            token_ciphertext=ciphertext,
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
        minted=True,
    )


async def ensure_user_api_token(db: AsyncSession, user: User) -> IssuedUserApiToken:
    """Reuse a live decryptable token, otherwise mint a new one."""
    existing = await peek_live_user_api_token(db, user)
    if existing is not None:
        return existing
    return await issue_user_api_token(db, user)
