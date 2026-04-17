"""Keyset / cursor pagination helpers for repository methods.

Why keyset?
-----------
``OFFSET N`` makes PostgreSQL scan and discard ``N`` rows on every page, which
is O(page_index * page_size).  For large tables (token_usage, mindbot_usage,
community_post_*, library_*) deep pages become very slow and lock-heavy.

Keyset pagination uses a stable, indexed "cursor" column (typically the
primary key) and a ``WHERE col >|< :cursor`` clause so each page is O(page_size)
regardless of how deep the user is.

This module centralises the small amount of logic so individual repositories
just call :func:`apply_keyset` instead of duplicating the comparison.

The repositories accept BOTH ``offset`` (legacy) and the cursor parameters
(``before_id`` / ``after_id``).  When a cursor is supplied it wins; ``offset``
is ignored.  The ``offset`` argument is preserved purely for backward
compatibility with existing API contracts; new callers should always use the
cursor.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional, Sequence, TypeVar

from sqlalchemy.sql import Select


_T = TypeVar("_T")


def apply_keyset(
    stmt: Select,
    *,
    column,
    before: Optional[int] = None,
    after: Optional[int] = None,
) -> Select:
    """Return ``stmt`` with a keyset predicate appended when a cursor is given.

    Parameters
    ----------
    stmt:
        Base ``select(...)`` statement.
    column:
        SQLAlchemy column used as the keyset cursor; must be indexed and
        match the ``ORDER BY`` direction the caller has applied.
    before:
        Cursor for ``ORDER BY column DESC`` (next page = rows with id < cursor).
    after:
        Cursor for ``ORDER BY column ASC`` (next page = rows with id > cursor).
    """

    if before is not None:
        stmt = stmt.where(column < before)
    elif after is not None:
        stmt = stmt.where(column > after)
    return stmt


def next_cursor(rows: Sequence[_T], *, attr: str = "id") -> Optional[int]:
    """Return the cursor value to send back to the caller for the next page.

    Returns the last row's ``attr`` value, or ``None`` when the page is empty
    (signalling end-of-stream to the client).  The caller is expected to
    return this value in the API response so the next request can pass it as
    ``before_id`` (or ``after_id``).
    """

    if not rows:
        return None
    return getattr(rows[-1], attr)
