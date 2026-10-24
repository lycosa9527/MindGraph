"""UTC instants for Learning Space clocks.

Assignment columns are ``TIMESTAMP WITHOUT TIME ZONE``. Store a naive UTC
wall clock. psycopg sends an aware datetime as ``timestamptz``, and PostgreSQL
then keeps the session time zone's digits. API payloads add the UTC offset so
clients can render Asia/Shanghai.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_naive(value: datetime | None) -> datetime | None:
    """UTC wall clock with ``tzinfo`` removed, for a naive timestamp column."""
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).replace(tzinfo=None)


def utc_isoformat(value: datetime | None) -> str | None:
    """Serialize a learning-space timestamp as a UTC instant, or None."""
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()
