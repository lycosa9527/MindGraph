"""psycopg.sql stub."""

from typing import Any


def SQL(query: str) -> Any:
    return query


def Identifier(name: str) -> Any:
    _ = name
    return name
