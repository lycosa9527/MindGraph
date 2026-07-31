"""
Shared transaction helpers for Maite domain services.

Repository writes are flush-only; callers must commit the unit of work so
rows survive ``get_async_db`` session close (which otherwise rolls back).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


async def commit_maite(session: AsyncSession) -> None:
    """Commit the current Maite DB unit of work."""
    await session.commit()
