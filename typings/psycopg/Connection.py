"""psycopg Connection stub."""

from typing import Any, Self


class Connection:
    """psycopg sync Connection stub."""

    autocommit: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any) -> None:
        _ = args
        return None

    def close(self) -> None:
        return None

    def cursor(self, *args: Any, **kwargs: Any) -> Any:
        _ = (args, kwargs)
        return _Cursor()


class _Cursor:
    rowcount: int = 0

    def execute(self, query: Any, params: Any = None) -> Any:
        _ = (query, params)
        return None

    def fetchone(self) -> Any:
        return None

    def fetchall(self) -> list[Any]:
        return []

    def close(self) -> None:
        return None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any) -> None:
        _ = args
        return None
