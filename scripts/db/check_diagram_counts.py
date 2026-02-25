#!/usr/bin/env python3
"""
Diagnostic script to verify auto-complete counts for teacher usage.

Run: python scripts/db/check_diagram_counts.py

Shows 智能补全次数 (auto-complete count) per teacher for Teacher Usage page.
"""
import sys
from pathlib import Path
from typing import Callable, cast

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

from sqlalchemy import func

from config.database import SessionLocal
from models.domain.auth import User
from models.domain.token_usage import TokenUsage

_count: Callable = cast(Callable, getattr(func, "count"))


def main() -> None:
    """Check auto-complete counts for teachers."""
    db = SessionLocal()
    try:
        teachers = db.query(User).filter(User.role == "user").all()
        teacher_ids = [u.id for u in teachers]

        total_autocomplete = (
            db.query(_count(TokenUsage.id))
            .filter(
                TokenUsage.request_type == "autocomplete",
                TokenUsage.success.is_(True),
            )
            .scalar()
        )
        print(f"Total auto-complete uses (success): {total_autocomplete or 0}")

        if teacher_ids:
            rows = (
                db.query(TokenUsage.user_id, _count(TokenUsage.id).label("cnt"))
                .filter(
                    TokenUsage.user_id.in_(teacher_ids),
                    TokenUsage.request_type == "autocomplete",
                    TokenUsage.success.is_(True),
                )
                .group_by(TokenUsage.user_id)
                .all()
            )
            user_counts = {int(r.user_id): int(r.cnt or 0) for r in rows}
            print(f"Teachers with auto-complete: {len(user_counts)}")
            for uid, cnt in sorted(user_counts.items(), key=lambda x: -x[1])[:10]:
                user = db.get(User, uid)
                name = (user.name or user.phone or str(uid)) if user else str(uid)
                print(f"  user_id={uid} ({name}): {cnt} auto-complete")
        else:
            print("No teachers (role=user) found.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
