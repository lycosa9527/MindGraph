"""
Backfill User Usage Stats

One-time script to compute and populate user_usage_stats for all teachers.
Run after deploying the teacher usage feature.

Usage (from project root):
    python scripts/db/backfill_user_usage_stats.py

Uses DATABASE_URL from environment.
Creates user_activity_log and user_usage_stats tables if they do not exist.
"""
import sys
from pathlib import Path
from typing import cast

# Add project root to path before importing project modules
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

from config.database import SessionLocal, engine
from models.domain.auth import Base, User
from models.domain.user_activity_log import UserActivityLog
from models.domain.user_usage_stats import UserUsageStats
from models.domain.teacher_usage_config import TeacherUsageConfig
from services.teacher_usage_stats import compute_and_upsert_user_usage_stats


def main():
    """Backfill user_usage_stats for all teachers (role=user)."""
    print("Creating tables if not exist...")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            UserActivityLog.__table__,
            UserUsageStats.__table__,
            TeacherUsageConfig.__table__,
        ],
        checkfirst=True,
    )
    print("Tables ready.")

    db = SessionLocal()
    try:
        teachers = db.query(User).filter(User.role == "user").all()
        total = len(teachers)
    finally:
        db.close()

    success = 0
    failed = 0
    for i, user in enumerate(teachers):
        user_db = SessionLocal()
        try:
            if compute_and_upsert_user_usage_stats(cast(int, user.id), user_db):
                success += 1
            else:
                failed += 1
        finally:
            user_db.close()
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{total}...")
    print(f"Backfill complete: {success} success, {failed} failed, {total} total")


if __name__ == "__main__":
    main()
