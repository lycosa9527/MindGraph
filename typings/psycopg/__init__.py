"""Minimal psycopg stub for optional scripts and PG LISTEN typing."""

from typing import Any

from psycopg import sql
from psycopg.AsyncConnection import AsyncConnection
from psycopg.Connection import Connection

__all__ = ["connect", "sql", "AsyncConnection", "Connection", "Error"]


class Error(Exception):
    """psycopg error base class."""


def connect(dsn: str, **kwargs: Any) -> Connection:
    """Connect stub."""
    _ = (dsn, kwargs)
    raise RuntimeError("psycopg stub only — install psycopg to use live PostgreSQL helpers")
