"""Bind the signed-in account to a glasses photo of its settings QR.

The QR uses the same ``mg://sheet/{uuid}`` text the glasses app already
photographs. Ingest stores that photo on this account instead of a course sheet.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import GlassesWearerBind
from services.learning_space.glasses_contract import (
    BIND_DISPLAY,
    MAX_INGEST_BYTES,
    sheet_id_from_payload,
    sheet_payload,
)
from services.learning_space.image_storage import (
    build_logical_key,
    detect_image_content_type,
    put_image_bytes_sync,
    ref_for_key,
)
from utils.db.session_open import system_rls_session

_ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def wearer_qr_payload(token_id: str) -> str:
    """QR text. The glasses app treats this the same as a printed sheet code."""
    return sheet_payload(token_id)


def _image_suffix(data: bytes, declared: str) -> tuple[str, str]:
    if len(data) > MAX_INGEST_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is too large")
    detected = detect_image_content_type(data) or ""
    mime = detected if detected in _ALLOWED_TYPES else declared
    suffix = _ALLOWED_TYPES.get(mime)
    if suffix is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Use JPEG, PNG, or WebP")
    return mime, suffix


async def _owner_row(db: AsyncSession, user_id: int) -> Optional[GlassesWearerBind]:
    result = await db.execute(select(GlassesWearerBind).where(GlassesWearerBind.owner_user_id == int(user_id)))
    return result.scalar_one_or_none()


def _status_payload(row: Optional[GlassesWearerBind], token: str) -> dict[str, Any]:
    if row is None:
        return {"linked": False, "token": "", "qr_payload": ""}
    linked = row.bound_at is not None
    watching = token and token == row.id
    show_qr = not linked and (not token or watching)
    return {
        "linked": linked if not token else bool(watching and linked),
        "token": row.id,
        "qr_payload": wearer_qr_payload(row.id) if show_qr else "",
    }


async def start_wearer_bind(db: AsyncSession, user: User) -> dict[str, Any]:
    """Mint a fresh QR for this account. A bound row stays bound."""
    row = await _owner_row(db, int(user.id))
    if row is not None and row.bound_at is not None:
        return _status_payload(row, "")
    if row is not None:
        await db.delete(row)
        await db.flush()
    created = GlassesWearerBind(
        id=str(uuid.uuid4()),
        owner_user_id=int(user.id),
        organization_id=int(user.organization_id) if user.organization_id is not None else None,
    )
    db.add(created)
    await db.commit()
    await db.refresh(created)
    return _status_payload(created, "")


async def wearer_bind_status(db: AsyncSession, user: User, token: str) -> dict[str, Any]:
    """Whether this account, or one specific QR, has received a glasses photo."""
    row = await _owner_row(db, int(user.id))
    return _status_payload(row, token.strip())


async def clear_wearer_bind(db: AsyncSession, user: User) -> None:
    """Remove the glasses link for this account."""
    row = await _owner_row(db, int(user.id))
    if row is None:
        return
    await db.delete(row)
    await db.commit()


async def try_accept_wearer_photo(sheet_uuid: str, data: bytes, declared_type: str) -> Optional[dict[str, Any]]:
    """Store a settings-QR photo on that user. None when the code is not a bind QR."""
    token_id = sheet_id_from_payload(sheet_uuid) or (sheet_uuid or "").strip()
    if len(token_id) != 36:
        return None
    mime, suffix = _image_suffix(data, declared_type)
    async with system_rls_session() as db:
        result = await db.execute(select(GlassesWearerBind).where(GlassesWearerBind.id == token_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        logical_key = build_logical_key(owner_id=int(row.owner_user_id), filename=f"wearer{suffix}")
        await asyncio.to_thread(put_image_bytes_sync, logical_key, data, mime)
        row.image_ref = ref_for_key(logical_key)
        row.bound_at = datetime.now(UTC).replace(tzinfo=None)
        await db.commit()
    return {"accepted": True, "linked": True, "display": BIND_DISPLAY}
