"""Showcase audit log helpers."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.showcase_admin import ShowcaseAuditLog


async def write_showcase_audit(
    db: AsyncSession,
    *,
    actor_id: int,
    action: str,
    post_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    db.add(
        ShowcaseAuditLog(
            post_id=post_id,
            actor_id=actor_id,
            action=action,
            payload=payload,
        )
    )
