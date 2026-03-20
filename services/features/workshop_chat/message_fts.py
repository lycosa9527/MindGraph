"""
PostgreSQL full-text search helpers for workshop chat messages.

Uses ``simple`` text search config (language-agnostic tokenization). Falls back
to ILIKE when the database is not PostgreSQL (e.g. SQLite in tests).
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from services.features.workshop_chat.message_search_normalize import (
    ilike_pattern_from_text,
)


def engine_is_postgresql(session: Session) -> bool:
    """True when the session is bound to PostgreSQL."""
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def normalized_fts_query(text: str) -> Optional[str]:
    """Return trimmed search text for ``plainto_tsquery``, or None if unusable."""
    raw = (text or "").strip()
    if not raw or len(raw) > 200:
        return None
    return raw


def channel_content_match(
    session: Session,
    content_column: Any,
    text: str,
    limit: int,
) -> Optional[Tuple[ColumnElement, Any, int]]:
    """
    Build (WHERE predicate, ORDER BY primary, limit) for channel message search.

    PostgreSQL: ``to_tsvector @@ plainto_tsquery``, ordered by ``ts_rank`` desc.
    Else: ILIKE substring, order by ``id`` at caller.
    Returns None when the query cannot be searched.
    """
    lim = min(max(limit, 1), 100)

    if engine_is_postgresql(session):
        fts_q = normalized_fts_query(text)
        if fts_q is None:
            return None
        tsv = func.to_tsvector("simple", content_column)
        tsq = func.plainto_tsquery("simple", fts_q)
        pred = tsv.op("@@")(tsq)
        rank = func.ts_rank(tsv, tsq)
        return pred, rank, lim

    pattern, ilim = ilike_pattern_from_text(text, limit)
    if pattern is None:
        return None
    return content_column.ilike(pattern), None, ilim


def dm_content_match(
    session: Session,
    content_column: Any,
    text: str,
    limit: int,
) -> Optional[Tuple[ColumnElement, Any, int]]:
    """Same as ``channel_content_match`` for DM rows."""
    return channel_content_match(session, content_column, text, limit)
