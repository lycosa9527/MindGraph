"""Uvicorn loop factory: SelectorEventLoop on Windows for psycopg async compatibility."""

from __future__ import annotations

import asyncio
import selectors


def windows_loop_factory() -> asyncio.AbstractEventLoop:
    """Create SelectorEventLoop on Windows so psycopg async DB works under uvicorn."""

    return asyncio.SelectorEventLoop(selectors.SelectSelector())
