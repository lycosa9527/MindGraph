"""
Backfill user_usage_activities from historical MindGraph data.

Sources:
- diagrams (non-deleted): diagram_save rows with title and diagram_type
- generation_preview_links (user_id set): dingtalk_diagram rows

MindMate / DingTalk chat previews are not backfilled (no message text in DB).

Usage (from project root):
    python scripts/db/backfill_user_usage_activities.py [--dry-run]
"""

try:
    from _path_setup import project_root
except ModuleNotFoundError:
    from scripts.db._path_setup import project_root

import argparse
from datetime import UTC

from sqlalchemy.orm import Session

from config.database import SyncSessionLocal
from models.domain.auth import User
from models.domain.diagrams import Diagram
from models.domain.generation_preview_link import GenerationPreviewLink
from models.domain.user_usage_activity import UserUsageActivity
from services.admin.user_usage_activity import clip_activity_preview, clip_activity_title

_ = project_root


def _exists_diagram_row(db: Session, user_id: int, action: str, diagram_id: str) -> bool:
    found = (
        db.query(UserUsageActivity.id)
        .filter(
            UserUsageActivity.user_id == user_id,
            UserUsageActivity.action == action,
            UserUsageActivity.diagram_id == diagram_id,
        )
        .first()
    )
    return found is not None


def _exists_preview_link_row(db: Session, user_id: int, preview_id: str) -> bool:
    marker = f"preview:{preview_id}"
    found = (
        db.query(UserUsageActivity.id)
        .filter(
            UserUsageActivity.user_id == user_id,
            UserUsageActivity.action == "dingtalk_diagram",
            UserUsageActivity.conversation_id == marker,
        )
        .first()
    )
    return found is not None


def backfill_diagrams(db: Session, dry_run: bool) -> int:
    """Insert diagram_save rows from diagrams table."""
    inserted = 0
    rows = (
        db.query(Diagram, User.organization_id)
        .join(User, User.id == Diagram.user_id)
        .filter(~Diagram.is_deleted)
        .order_by(Diagram.created_at.asc())
        .all()
    )
    for diagram, org_id in rows:
        if _exists_diagram_row(db, diagram.user_id, "diagram_save", diagram.id):
            continue
        title = clip_activity_title(diagram.title)
        if not title:
            continue
        created = diagram.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        row = UserUsageActivity(
            user_id=int(diagram.user_id),
            organization_id=int(org_id) if org_id is not None else None,
            source="mindgraph",
            action="diagram_save",
            title=title,
            diagram_type=(diagram.diagram_type or "")[:50] or None,
            diagram_id=diagram.id,
            success=True,
            created_at=created,
        )
        if dry_run:
            inserted += 1
            continue
        db.add(row)
        inserted += 1
    return inserted


def backfill_preview_links(db: Session, dry_run: bool) -> int:
    """Insert dingtalk_diagram rows from generation_preview_links."""
    inserted = 0
    links = (
        db.query(GenerationPreviewLink)
        .filter(GenerationPreviewLink.user_id.isnot(None))
        .order_by(GenerationPreviewLink.created_at.asc())
        .all()
    )
    for link in links:
        uid = link.user_id
        if uid is None or uid <= 0:
            continue
        diagram_id = (link.diagram_id or "").strip() or None
        if diagram_id and _exists_diagram_row(db, uid, "dingtalk_diagram", diagram_id):
            continue
        if _exists_preview_link_row(db, uid, link.preview_id):
            continue
        title = clip_activity_title(link.title)
        prompt = clip_activity_preview(link.title)
        if not title and not prompt:
            continue
        created = link.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        row = UserUsageActivity(
            user_id=int(uid),
            organization_id=int(link.organization_id) if link.organization_id is not None else None,
            source="dingtalk",
            action="dingtalk_diagram",
            title=title,
            prompt_preview=prompt,
            diagram_type=(link.diagram_type or "")[:50] or None,
            diagram_id=diagram_id,
            conversation_id=f"preview:{link.preview_id}",
            success=True,
            created_at=created,
        )
        if dry_run:
            inserted += 1
            continue
        db.add(row)
        inserted += 1
    return inserted


def main() -> None:
    """Run backfill."""
    parser = argparse.ArgumentParser(description="Backfill user_usage_activities from MindGraph history")
    parser.add_argument("--dry-run", action="store_true", help="Count rows only, do not write")
    args = parser.parse_args()

    db = SyncSessionLocal()
    try:
        diagram_count = backfill_diagrams(db, args.dry_run)
        preview_count = backfill_preview_links(db, args.dry_run)
        if not args.dry_run:
            db.commit()
        mode = "would insert" if args.dry_run else "inserted"
        print(f"Backfill complete: {mode} {diagram_count} diagram_save, {preview_count} dingtalk_diagram")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
