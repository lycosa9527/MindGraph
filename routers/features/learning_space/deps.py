"""Learning Space FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db


async def get_learning_space_db(
    db: AsyncSession = Depends(get_async_db),
) -> AsyncIterator[AsyncSession]:
    """Request-scoped session. Class create uses admin routes and panel RLS."""
    yield db
