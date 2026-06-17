"""Helpers for comparing DB datetimes with datetime.now(UTC).

TIMESTAMP WITHOUT TIME ZONE columns yield naive datetimes; datetime.now(UTC) is
timezone-aware, which raises TypeError when compared directly.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime


def as_utc_aware(dt: datetime) -> datetime:
    """Interpret naive datetimes as UTC; normalize aware values to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
