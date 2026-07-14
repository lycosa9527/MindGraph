"""Case Square audit log helpers."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.case_square_admin import CaseSquareAuditLog


async def write_case_square_audit(
    db: AsyncSession,
    *,
    actor_id: int,
    action: str,
    post_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    db.add(
        CaseSquareAuditLog(
            post_id=post_id,
            actor_id=actor_id,
            action=action,
            payload=payload,
        )
    )
