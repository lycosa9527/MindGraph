"""Minimal psycopg stub for optional scripts and PG LISTEN typing."""

from typing import Any

from psycopg import sql
from psycopg.AsyncConnection import AsyncConnection

__all__ = ["connect", "sql", "AsyncConnection"]


def connect(dsn: str, **kwargs: Any) -> Any:
    """Connect stub."""
    _ = (dsn, kwargs)
    raise RuntimeError("psycopg stub only — install psycopg to use live PostgreSQL helpers")
