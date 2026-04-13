"""Helpers for comparing DB datetimes with datetime.now(UTC).

TIMESTAMP WITHOUT TIME ZONE columns yield naive datetimes; datetime.now(UTC) is
timezone-aware, which raises TypeError when compared directly.
"""

from datetime import UTC, datetime


def as_utc_aware(dt: datetime) -> datetime:
    """Interpret naive datetimes as UTC; normalize aware values to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
