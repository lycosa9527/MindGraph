"""
Backfill User Usage Stats

One-time script to compute and populate user_usage_stats for all teachers.
Run after deploying the teacher usage feature.

Usage (from project root):
    python scripts/db/backfill_user_usage_stats.py

Uses DATABASE_URL from environment.
Creates user_activity_log and user_usage_stats tables if they do not exist.
"""

import asyncio
import sys
from pathlib import Path
from typing import cast

_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

from sqlalchemy import select

from config.database import AsyncSessionLocal, async_engine
from models.domain.auth import Base, User
from models.domain.user_activity_log import UserActivityLog
from models.domain.user_usage_stats import UserUsageStats
from models.domain.teacher_usage_config import TeacherUsageConfig
from services.teacher_usage_stats import compute_and_upsert_user_usage_stats_async


async def _create_tables() -> None:
    """Create supporting tables if they do not exist."""
    async with async_engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                UserActivityLog.__table__,
                UserUsageStats.__table__,
                TeacherUsageConfig.__table__,
            ],
            checkfirst=True,
        )


async def _run_backfill() -> None:
    """Backfill user_usage_stats for all teachers (role=user)."""
    print("Creating tables if not exist...")
    await _create_tables()
    print("Tables ready.")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.role == "user"))
        teachers = list(result.scalars().all())
    total = len(teachers)

    success = 0
    failed = 0
    for i, user in enumerate(teachers):
        async with AsyncSessionLocal() as user_db:
            if await compute_and_upsert_user_usage_stats_async(cast(int, user.id), user_db):
                success += 1
            else:
                failed += 1
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{total}...")
    print(f"Backfill complete: {success} success, {failed} failed, {total} total")


def main() -> None:
    """Sync entry point that runs the async backfill via ``asyncio.run``."""
    try:
        asyncio.run(_run_backfill())
    finally:
        asyncio.run(async_engine.dispose())


if __name__ == "__main__":
    main()
