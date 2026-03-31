"""
Backfill Teacher Activity Logs (diagram_edit)

One-time script to populate user_activity_log with diagram_edit events derived
from the diagrams table. Run after deploying the teacher usage activity tracking.

Data sources analysis:
- diagram_edit (每日修改次数): CAN backfill from diagrams.updated_at
  - diagrams table has updated_at; when updated_at > created_at, the diagram
    was edited. We insert one UserActivityLog per diagram-update per day.
  - Limitation: multiple edits of same diagram on same day count as 1.
- autocomplete (自动生成次数): NO backfill needed - already in token_usage
  - Activity trends query TokenUsage directly; historical data exists.
- diagram_export (导出次数): CANNOT backfill - no historical data
  - Frontend export is client-side (html-to-image); no backend logging before.

Usage (from project root):
    python scripts/db/backfill_teacher_activity_logs.py [--dry-run] [--force]

Options:
    --dry-run   Print what would be inserted, do not write to DB.
    --force     Run even if diagram_edit logs already exist (default: skip).
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

from sqlalchemy.orm import Session

from config.database import SessionLocal
from models.domain.auth import User
from models.domain.diagrams import Diagram
from models.domain.user_activity_log import UserActivityLog

BEIJING_TZ = timezone(timedelta(hours=8))


def _utc_to_beijing_date(utc_dt: datetime) -> str:
    """Convert UTC datetime to Beijing date string."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    beijing_dt = utc_dt.astimezone(BEIJING_TZ)
    return str(beijing_dt.date())


def backfill_diagram_edit(db: Session, dry_run: bool, force: bool) -> int:
    """
    Backfill diagram_edit into user_activity_log from diagrams table.

    Returns inserted_count.
    """
    existing = db.query(UserActivityLog).filter(UserActivityLog.activity_type == "diagram_edit").count()
    if existing > 0 and not force:
        print(
            f"Found {existing} existing diagram_edit logs. "
            "Use --force to run anyway, or skip (assumes backfill already done)."
        )
        return 0

    beijing_now = datetime.now(BEIJING_TZ)
    cutoff = (beijing_now - timedelta(days=90)).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_utc = cutoff.astimezone(timezone.utc).replace(tzinfo=None)

    teachers = db.query(User.id).filter(User.role == "user").all()
    teacher_ids = [r.id for r in teachers]
    if not teacher_ids:
        print("No teachers (role=user) found.")
        return 0

    diagrams_updated = (
        db.query(Diagram)
        .filter(
            Diagram.user_id.in_(teacher_ids),
            Diagram.is_deleted.is_(False),
            Diagram.updated_at >= cutoff_utc,
            Diagram.updated_at > Diagram.created_at,
        )
        .all()
    )

    inserted = 0
    for d in diagrams_updated:
        updated_at = d.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if dry_run:
            print(
                f"  Would insert diagram_edit: user_id={d.user_id}, "
                f"date={_utc_to_beijing_date(cast(datetime, updated_at))}, diagram_id={d.id}"
            )
            inserted += 1
            continue
        log_entry = UserActivityLog(
            user_id=d.user_id,
            activity_type="diagram_edit",
            created_at=d.updated_at,
        )
        db.add(log_entry)
        inserted += 1

    if not dry_run and inserted > 0:
        db.commit()
    return inserted


def main():
    """Run backfill."""
    parser = argparse.ArgumentParser(description="Backfill teacher activity logs (diagram_edit) from diagrams table")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted, do not write",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if diagram_edit logs already exist",
    )
    args = parser.parse_args()

    print("Backfill Teacher Activity Logs (diagram_edit)")
    print("=" * 50)
    print("Data sources:")
    print("  - diagram_edit: from diagrams.updated_at (approximation)")
    print("  - autocomplete: already in token_usage, no backfill needed")
    print("  - diagram_export: no historical data, cannot backfill")
    print()

    db = SessionLocal()
    try:
        inserted = backfill_diagram_edit(db, dry_run=args.dry_run, force=args.force)
        mode = "Would insert" if args.dry_run else "Inserted"
        print(f"{mode}: {inserted} diagram_edit logs")
    finally:
        db.close()


if __name__ == "__main__":
    main()
