"""psycopg AsyncConnection stub module."""

from collections.abc import AsyncIterator
from typing import Any, Self


class _Notify:
    payload: str = ""


class AsyncConnection:
    """psycopg AsyncConnection stub."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    @classmethod
    async def connect(cls, conninfo: str, **kwargs: Any) -> Self:
        _ = (conninfo, kwargs)
        return cls()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> None:
        _ = args
        return None

    async def execute(self, query: Any, params: Any = None) -> Any:
        _ = (query, params)
        return None

    async def close(self) -> None:
        return None

    async def notifies(self) -> AsyncIterator[_Notify]:
        if False:
            yield _Notify()

    def cursor(self, *args: Any, **kwargs: Any) -> Any:
        _ = (args, kwargs)
        return _AsyncCursor()


class _AsyncCursor:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> None:
        _ = args
        return None

    async def execute(self, query: Any, params: Any = None) -> Any:
        _ = (query, params)
        return None
