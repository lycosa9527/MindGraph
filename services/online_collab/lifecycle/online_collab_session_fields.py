"""
Workshop DB field helpers (legacy backfill, clearing session columns).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.diagrams import Diagram


async def backfill_online_collab_expiry_if_needed(diagram: Diagram, db: AsyncSession) -> None:
    """Legacy rows: set expiry to 24h from diagram updated_at if missing.

    Flushes the mutations to the session only; the caller owns the
    transaction boundary (``db.commit()``). Committing here previously
    erased the caller's pending writes when this helper ran mid-loop
    (e.g. during the cleanup task), producing partial writes on crash.
    """
    if not diagram.workshop_code or diagram.workshop_expires_at is not None:
        return
    started = diagram.updated_at or diagram.created_at or datetime.now(UTC)
    diagram.workshop_started_at = started
    diagram.workshop_expires_at = started + timedelta(hours=24)
    diagram.workshop_duration_preset = "legacy"
    await db.flush()


def clear_online_collab_session_fields(diagram: Diagram) -> None:
    """Clear all workshop-related columns on a diagram row."""
    diagram.workshop_code = None
    diagram.workshop_visibility = None
    diagram.workshop_started_at = None
    diagram.workshop_expires_at = None
    diagram.workshop_duration_preset = None


async def clear_online_collab_session_by_id_returning(
    db: AsyncSession,
    diagram_id: str,
) -> Optional[str]:
    """
    Single-round-trip UPDATE...RETURNING to clear workshop session columns.

    Replaces the SELECT + mutate + COMMIT pattern (3 round-trips, locking,
    read-after-write race) with one atomic UPDATE. Returns the diagram id
    string if a row was found and cleared, or None if no eligible row was
    found. Caller owns the commit boundary.

    NOTE: we return ``Diagram.id`` (not ``Diagram.workshop_code``) because
    PostgreSQL RETURNING yields post-update values — after setting
    ``workshop_code = NULL`` the column is NULL, so returning it would always
    produce None, making it impossible to distinguish "no matching row" from
    "row cleared successfully". Returning the immutable primary key avoids
    this ambiguity.
    """
    stmt = (
        sql_update(Diagram)
        .where(
            Diagram.id == diagram_id,
            ~Diagram.is_deleted,
        )
        .values(
            workshop_code=None,
            workshop_visibility=None,
            workshop_started_at=None,
            workshop_expires_at=None,
            workshop_duration_preset=None,
        )
        .returning(Diagram.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
