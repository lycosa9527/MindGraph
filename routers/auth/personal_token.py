"""User API token endpoints for OpenClaw (mgat_) — browser session mints token."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.user_api_token import UserAPIToken
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.redis.cache.redis_user_token_cache import user_token_cache
from utils.auth import (
    get_current_user,
    require_not_mgat_for_token_mint,
)
from utils.auth.datetime_compat import as_utc_aware

router = APIRouter(tags=["Authentication"])

TOKEN_TTL_DAYS = 7


@router.post("/api-token", dependencies=[Depends(require_not_mgat_for_token_mint)])
async def create_user_api_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Create or replace the single user API token (mgat_). Session-JWT only."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "api_token_create",
        identifier,
        max_requests=10,
        window_seconds=3600,
    )

    raw = f"mgat_{secrets.token_hex(32)}"
    token_hash_full = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=TOKEN_TTL_DAYS)

    result = await db.execute(select(UserAPIToken).where(UserAPIToken.user_id == current_user.id))
    existing = result.scalar_one_or_none()
    if existing:
        await user_token_cache.invalidate_by_token_hash_64(existing.token_hash)
        existing.token_hash = token_hash_full
        existing.expires_at = expires_at
        existing.is_active = True
        existing.created_at = now
        existing.last_used_at = None
    else:
        row = UserAPIToken(
            user_id=current_user.id,
            token_hash=token_hash_full,
            expires_at=expires_at,
            created_at=now,
            last_used_at=None,
            is_active=True,
        )
        db.add(row)
        existing = row

    await db.commit()
    await db.refresh(existing)

    await user_token_cache.set_from_row(raw, existing)

    return {
        "token": raw,
        "expires_at": expires_at.isoformat(),
        "account": current_user.phone,
    }


@router.get("/api-token")
async def get_user_api_token_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Return metadata for the current user's API token (never the raw secret)."""
    result = await db.execute(
        select(UserAPIToken).where(
            UserAPIToken.user_id == current_user.id,
            UserAPIToken.is_active.is_(True),
        )
    )
    row = result.scalar_one_or_none()
    if not row or as_utc_aware(row.expires_at) <= datetime.now(UTC):
        return {
            "exists": False,
            "expires_at": None,
            "last_used_at": None,
            "created_at": None,
            "is_active": False,
        }
    return {
        "exists": True,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "is_active": bool(row.is_active),
    }


@router.delete("/api-token")
async def revoke_user_api_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Revoke the user's API token."""
    result = await db.execute(select(UserAPIToken).where(UserAPIToken.user_id == current_user.id))
    row = result.scalar_one_or_none()
    if not row:
        return {"ok": True, "revoked": False}
    await user_token_cache.invalidate_by_token_hash_64(row.token_hash)
    row.is_active = False
    await db.commit()
    return {"ok": True, "revoked": True}
