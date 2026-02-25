"""Teacher Usage Analytics Endpoints.

Admin-only endpoint for teacher engagement classification:
- GET /admin/teacher-usage - Get teachers classified into 2-tier groups
- GET /admin/teacher-usage/config - Get classification thresholds
- PUT /admin/teacher-usage/config - Update classification thresholds
- POST /admin/teacher-usage/recompute - Recompute all user stats (after config change)

Reads from user_usage_stats (pre-computed). Groups: unused, continuous,
rejection, stopped, intermittent.
"""
from datetime import timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.token_usage import TokenUsage
from models.domain.user_usage_stats import UserUsageStats
from routers.auth.helpers import get_beijing_now
from services.teacher_usage_stats import (
    get_classification_config,
    save_classification_config,
    compute_and_upsert_user_usage_stats,
)

from ..dependencies import require_admin

router = APIRouter()


class ClassificationThresholds(BaseModel):
    """Configurable thresholds for each classification group."""

    continuous: dict[str, int] = Field(
        default_factory=lambda: {
            "active_weeks_min": 5,
            "active_weeks_first4_min": 1,
            "active_weeks_last4_min": 1,
            "max_zero_gap_days_max": 10,
        }
    )
    rejection: dict[str, int] = Field(
        default_factory=lambda: {
            "active_days_max": 3,
            "active_days_first10_min": 1,
            "active_days_last25_max": 0,
            "max_zero_gap_days_min": 25,
        }
    )
    stopped: dict[str, int] = Field(
        default_factory=lambda: {
            "active_days_first25_min": 3,
            "active_days_last14_max": 0,
            "max_zero_gap_days_min": 14,
        }
    )
    intermittent: dict[str, int] = Field(
        default_factory=lambda: {
            "n_bursts_min": 2,
            "internal_max_zero_gap_days_min": 7,
        }
    )

GROUP_IDS = ["unused", "continuous", "rejection", "stopped", "intermittent"]


def _get_group_key(tier1: str | None, tier2: str | None) -> str:
    """Map tier1/tier2 to group key for API."""
    if not tier1 or tier1 == "unused":
        return "unused"
    if tier1 == "continuous":
        return "continuous"
    if tier1 == "non_continuous" and tier2:
        return tier2
    return "intermittent"


@router.get("/admin/teacher-usage", dependencies=[Depends(require_admin)])
async def get_teacher_usage(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get teacher engagement classification (ADMIN ONLY).

    Reads from user_usage_stats. Groups: unused, continuous, rejection,
    stopped, intermittent.
    """
    beijing_now = get_beijing_now()
    beijing_today = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_90d = (
        (beijing_today - timedelta(days=90))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    teachers = db.query(User).filter(User.role == "user").all()
    teacher_ids = [u.id for u in teachers]

    stats_map = {}
    try:
        stats_rows = (
            db.query(UserUsageStats)
            .filter(UserUsageStats.user_id.in_(teacher_ids))
            .all()
        )
        for row in stats_rows:
            stats_map[row.user_id] = (row.tier1, row.tier2)
    except Exception:
        pass

    token_rows = (
        db.query(
            TokenUsage.user_id,
            func.sum(TokenUsage.total_tokens).label("total"),
            func.max(TokenUsage.created_at).label("last_at"),
        )
        .filter(
            TokenUsage.user_id.in_(teacher_ids),
            TokenUsage.success.is_(True),
        )
        .group_by(TokenUsage.user_id)
        .all()
    )
    user_token_total = {r.user_id: int(r.total or 0) for r in token_rows}
    user_last_active = {r.user_id: r.last_at for r in token_rows}

    user_autocomplete_count: dict[int, int] = {}
    if teacher_ids:
        autocomplete_rows = (
            db.query(TokenUsage.user_id, func.count(TokenUsage.id).label("cnt"))
            .filter(
                TokenUsage.user_id.in_(teacher_ids),
                TokenUsage.request_type == "autocomplete",
                TokenUsage.success.is_(True),
            )
            .group_by(TokenUsage.user_id)
            .all()
        )
        user_autocomplete_count = {
            int(r.user_id): int(r.cnt or 0) for r in autocomplete_rows
        }

    groups: dict[str, list[dict[str, Any]]] = {gid: [] for gid in GROUP_IDS}

    for user in teachers:
        tier1, tier2 = stats_map.get(user.id, (None, None))
        group_key = _get_group_key(tier1, tier2)
        last_at = user_last_active.get(user.id)
        last_str = last_at.strftime("%Y-%m-%d") if last_at else ""
        groups[group_key].append(
            {
                "id": user.id,
                "username": user.name or user.phone or str(user.id),
                "diagrams": user_autocomplete_count.get(user.id, 0),
                "tokens": user_token_total.get(user.id, 0),
                "lastActive": last_str,
            }
        )

    total_teachers = len(teachers)
    group_user_ids = {gid: [t["id"] for t in teachers_list] for gid, teachers_list in groups.items()}

    weekly_by_group = {}
    for gid, uids in group_user_ids.items():
        if not uids:
            weekly_by_group[gid] = []
            continue
        try:
            weekly_rows = (
                db.query(
                    func.date_trunc("week", TokenUsage.created_at).label("week"),
                    func.sum(TokenUsage.total_tokens).label("total"),
                )
                .filter(
                    TokenUsage.user_id.in_(uids),
                    TokenUsage.success.is_(True),
                    TokenUsage.created_at >= cutoff_90d,
                )
                .group_by(func.date_trunc("week", TokenUsage.created_at))
                .order_by(func.date_trunc("week", TokenUsage.created_at))
                .all()
            )
            weekly_by_group[gid] = [int(r.total or 0) for r in weekly_rows]
        except Exception:
            weekly_by_group[gid] = []

    return {
        "stats": {
            "totalTeachers": total_teachers,
            "unused": len(groups["unused"]),
            "continuous": len(groups["continuous"]),
            "rejection": len(groups["rejection"]),
            "stopped": len(groups["stopped"]),
            "intermittent": len(groups["intermittent"]),
        },
        "groups": {
            gid: {
                "count": len(teachers_list),
                "totalTokens": sum(t["tokens"] for t in teachers_list),
                "teachers": teachers_list,
                "weeklyTokens": weekly_by_group.get(gid, []),
            }
            for gid, teachers_list in groups.items()
        },
    }


@router.get(
    "/admin/teacher-usage/user/{user_id}/weekly-tokens",
    dependencies=[Depends(require_admin)],
)
async def get_user_weekly_tokens(
    user_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get weekly token usage for a specific user (ADMIN ONLY)."""
    user = db.query(User).filter(User.id == user_id, User.role == "user").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    beijing_now = get_beijing_now()
    beijing_today = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_90d = (
        (beijing_today - timedelta(days=90))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    try:
        weekly_rows = (
            db.query(
                func.date_trunc("week", TokenUsage.created_at).label("week"),
                func.sum(TokenUsage.total_tokens).label("total"),
            )
            .filter(
                TokenUsage.user_id == user_id,
                TokenUsage.success.is_(True),
                TokenUsage.created_at >= cutoff_90d,
            )
            .group_by(func.date_trunc("week", TokenUsage.created_at))
            .order_by(func.date_trunc("week", TokenUsage.created_at))
            .all()
        )
        weekly_tokens = [int(r.total or 0) for r in weekly_rows]
    except Exception:
        weekly_tokens = []
    return {
        "userId": user_id,
        "username": user.name or user.phone or str(user_id),
        "weeklyTokens": weekly_tokens,
    }


@router.get("/admin/teacher-usage/config", dependencies=[Depends(require_admin)])
async def get_teacher_usage_config(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get classification thresholds (ADMIN ONLY)."""
    return get_classification_config(db)


@router.put("/admin/teacher-usage/config", dependencies=[Depends(require_admin)])
async def put_teacher_usage_config(
    body: ClassificationThresholds,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update classification thresholds (ADMIN ONLY)."""
    thresholds = {
        "continuous": body.continuous,
        "rejection": body.rejection,
        "stopped": body.stopped,
        "intermittent": body.intermittent,
    }
    ok = save_classification_config(db, thresholds)
    return {"success": ok, "config": get_classification_config(db)}


def _run_recompute(db: Session) -> tuple[int, int]:
    """Recompute user_usage_stats for all teachers. Returns (success, failed)."""
    teachers = db.query(User).filter(User.role == "user").all()
    success = 0
    failed = 0
    for user in teachers:
        if compute_and_upsert_user_usage_stats(user.id, db):
            success += 1
        else:
            failed += 1
    return success, failed


@router.post("/admin/teacher-usage/recompute", dependencies=[Depends(require_admin)])
async def post_teacher_usage_recompute(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Recompute all teacher classifications (ADMIN ONLY). Run after config change."""
    success, failed = _run_recompute(db)
    return {"success": True, "recomputed": success, "failed": failed}
