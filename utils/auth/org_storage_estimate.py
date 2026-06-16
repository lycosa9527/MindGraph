"""Organization diagram storage usage estimates from PostgreSQL."""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from models.domain.auth import User
from models.domain.diagrams import Diagram
from models.domain.diagram_snapshots import DiagramSnapshot
from models.domain.school_zone import SharedDiagram

ColumnBytesFn = Callable[[Any], ColumnElement[Any]]


def _pg_column_bytes(column: Any) -> ColumnElement[Any]:
    """Stored byte size for a PostgreSQL column value (0 when NULL)."""
    return func.coalesce(func.pg_column_size(column), 0)


def _text_fallback_bytes(column: Any) -> ColumnElement[Any]:
    """Fallback payload size when pg_column_size is unavailable (e.g. SQLite tests)."""
    return func.coalesce(func.octet_length(cast(column, Text)), 0)


def _column_bytes_fn(dialect_name: str) -> ColumnBytesFn:
    if dialect_name == "postgresql":
        return _pg_column_bytes
    return _text_fallback_bytes


async def _sum_diagram_bytes(db: AsyncSession, org_id: int, col_bytes: ColumnBytesFn) -> int:
    spec_bytes = col_bytes(Diagram.spec)
    thumb_bytes = col_bytes(Diagram.thumbnail)
    stmt = (
        select(func.coalesce(func.sum(spec_bytes + thumb_bytes), 0))
        .select_from(Diagram)
        .join(User, Diagram.user_id == User.id)
        .where(
            User.organization_id == org_id,
            Diagram.is_deleted.is_(False),
        )
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _sum_snapshot_bytes(db: AsyncSession, org_id: int, col_bytes: ColumnBytesFn) -> int:
    spec_bytes = col_bytes(DiagramSnapshot.spec)
    stmt = (
        select(func.coalesce(func.sum(spec_bytes), 0))
        .select_from(DiagramSnapshot)
        .join(User, DiagramSnapshot.user_id == User.id)
        .where(User.organization_id == org_id)
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _sum_shared_diagram_bytes(db: AsyncSession, org_id: int, col_bytes: ColumnBytesFn) -> int:
    data_bytes = col_bytes(SharedDiagram.diagram_data)
    thumb_bytes = col_bytes(SharedDiagram.thumbnail)
    stmt = (
        select(func.coalesce(func.sum(data_bytes + thumb_bytes), 0))
        .select_from(SharedDiagram)
        .where(
            SharedDiagram.organization_id == org_id,
            SharedDiagram.is_active.is_(True),
        )
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def org_diagram_storage_estimate(db: AsyncSession, org_id: int) -> dict[str, int]:
    """
    Estimate org diagram storage from database column sizes.

    Sums PostgreSQL stored bytes for:
    - active member diagrams (spec + thumbnail)
    - diagram version snapshots (spec)
    - active school-zone shared diagrams (diagram_data + thumbnail)

    Uses pg_column_size on PostgreSQL (includes JSONB/TOAST storage). This is an
    estimate: it excludes indexes, row metadata, and other non-diagram org assets.
    """
    conn = await db.connection()
    col_bytes = _column_bytes_fn(conn.dialect.name)

    diagrams_bytes = await _sum_diagram_bytes(db, org_id, col_bytes)
    snapshots_bytes = await _sum_snapshot_bytes(db, org_id, col_bytes)
    shared_bytes = await _sum_shared_diagram_bytes(db, org_id, col_bytes)
    total_bytes = diagrams_bytes + snapshots_bytes + shared_bytes

    return {
        "total_bytes": total_bytes,
        "diagrams_bytes": diagrams_bytes,
        "snapshots_bytes": snapshots_bytes,
        "shared_diagrams_bytes": shared_bytes,
    }
