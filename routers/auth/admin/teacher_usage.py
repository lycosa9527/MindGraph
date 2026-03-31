"""Teacher Usage Analytics Endpoints.

Admin-only endpoint for teacher engagement classification:
- GET /admin/teacher-usage - Get teachers classified into 2-tier groups
- GET /admin/teacher-usage/config - Get classification thresholds
- PUT /admin/teacher-usage/config - Update classification thresholds
- POST /admin/teacher-usage/recompute - Recompute all user stats (after config change)

Reads from user_usage_stats (pre-computed). Groups: unused, continuous,
rejection, stopped, intermittent.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import count as sql_count

from config.database import get_db
from models.domain.auth import User
from models.domain.token_usage import TokenUsage
from models.domain.user_activity_log import UserActivityLog
from models.domain.user_usage_stats import UserUsageStats
from routers.auth.helpers import BEIJING_TIMEZONE, get_beijing_now
from services.teacher_usage_stats import (
    get_classification_config,
    save_classification_config,
    compute_and_upsert_user_usage_stats,
)

from ..dependencies import require_admin

logger = logging.getLogger(__name__)

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
def get_teacher_usage(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get teacher engagement classification (ADMIN ONLY).

    Reads from user_usage_stats. Groups: unused, continuous, rejection,
    stopped, intermittent.
    """
    beijing_now = get_beijing_now()
    beijing_today = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_90d = (beijing_today - timedelta(days=90)).astimezone(timezone.utc).replace(tzinfo=None)

    teachers = db.query(User).filter(User.role == "user").all()
    teacher_ids = [u.id for u in teachers]

    stats_map = {}
    try:
        stats_rows = db.query(UserUsageStats).filter(UserUsageStats.user_id.in_(teacher_ids)).all()
        for row in stats_rows:
            stats_map[row.user_id] = (row.tier1, row.tier2)
    except Exception as exc:
        logger.debug("Failed to fetch usage stats: %s", exc)

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
            db.query(TokenUsage.user_id, sql_count(TokenUsage.id).label("cnt"))
            .filter(
                TokenUsage.user_id.in_(teacher_ids),
                TokenUsage.request_type == "autocomplete",
                TokenUsage.success.is_(True),
            )
            .group_by(TokenUsage.user_id)
            .all()
        )
        user_autocomplete_count = {int(r.user_id): int(r.cnt or 0) for r in autocomplete_rows}

    user_concept_gen_count: dict[int, int] = {}
    user_rel_labels_count: dict[int, int] = {}
    if teacher_ids:
        try:
            concept_gen_rows = (
                db.query(UserActivityLog.user_id, sql_count(UserActivityLog.id).label("cnt"))
                .filter(
                    UserActivityLog.user_id.in_(teacher_ids),
                    UserActivityLog.activity_type == "concept_generation",
                )
                .group_by(UserActivityLog.user_id)
                .all()
            )
            user_concept_gen_count = {int(r.user_id): int(r.cnt or 0) for r in concept_gen_rows}
            rel_labels_rows = (
                db.query(UserActivityLog.user_id, sql_count(UserActivityLog.id).label("cnt"))
                .filter(
                    UserActivityLog.user_id.in_(teacher_ids),
                    UserActivityLog.activity_type == "relationship_labels",
                )
                .group_by(UserActivityLog.user_id)
                .all()
            )
            user_rel_labels_count = {int(r.user_id): int(r.cnt or 0) for r in rel_labels_rows}
        except Exception as exc:
            logger.debug("Failed to fetch activity log counts: %s", exc)

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
                "conceptGen": user_concept_gen_count.get(user.id, 0),
                "relationshipLabels": user_rel_labels_count.get(user.id, 0),
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
    "/admin/teacher-usage/users",
    dependencies=[Depends(require_admin)],
)
def get_teacher_usage_users(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> dict[str, Any]:
    """List teachers with usage stats, paginated (ADMIN ONLY)."""
    teachers = db.query(User).filter(User.role == "user").all()
    teacher_ids = [u.id for u in teachers]
    user_token_total: dict[int, int] = {}
    user_last_active: dict[int, Any] = {}
    user_autocomplete_count: dict[int, int] = {}
    user_concept_gen_count: dict[int, int] = {}
    user_rel_labels_count: dict[int, int] = {}
    if teacher_ids:
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
        autocomplete_rows = (
            db.query(TokenUsage.user_id, sql_count(TokenUsage.id).label("cnt"))
            .filter(
                TokenUsage.user_id.in_(teacher_ids),
                TokenUsage.request_type == "autocomplete",
                TokenUsage.success.is_(True),
            )
            .group_by(TokenUsage.user_id)
            .all()
        )
        user_autocomplete_count = {int(r.user_id): int(r.cnt or 0) for r in autocomplete_rows}
        try:
            concept_gen_rows = (
                db.query(UserActivityLog.user_id, sql_count(UserActivityLog.id).label("cnt"))
                .filter(
                    UserActivityLog.user_id.in_(teacher_ids),
                    UserActivityLog.activity_type == "concept_generation",
                )
                .group_by(UserActivityLog.user_id)
                .all()
            )
            user_concept_gen_count = {int(r.user_id): int(r.cnt or 0) for r in concept_gen_rows}
            rel_labels_rows = (
                db.query(UserActivityLog.user_id, sql_count(UserActivityLog.id).label("cnt"))
                .filter(
                    UserActivityLog.user_id.in_(teacher_ids),
                    UserActivityLog.activity_type == "relationship_labels",
                )
                .group_by(UserActivityLog.user_id)
                .all()
            )
            user_rel_labels_count = {int(r.user_id): int(r.cnt or 0) for r in rel_labels_rows}
        except Exception as exc:
            logger.debug("Failed to fetch paginated activity log counts: %s", exc)
    total = len(teachers)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = teachers[start:end]
    users_list = []
    for user in paginated:
        last_at = user_last_active.get(user.id)
        last_str = last_at.strftime("%Y-%m-%d") if last_at else ""
        users_list.append(
            {
                "id": user.id,
                "username": user.name or user.phone or str(user.id),
                "diagrams": user_autocomplete_count.get(user.id, 0),
                "conceptGen": user_concept_gen_count.get(user.id, 0),
                "relationshipLabels": user_rel_labels_count.get(user.id, 0),
                "tokens": user_token_total.get(user.id, 0),
                "lastActive": last_str,
            }
        )
    return {
        "users": users_list,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.get(
    "/admin/teacher-usage/user/{user_id}/weekly-tokens",
    dependencies=[Depends(require_admin)],
)
def get_user_weekly_tokens(
    user_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get weekly token usage for a specific user (ADMIN ONLY)."""
    user = db.query(User).filter(User.id == user_id, User.role == "user").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    beijing_now = get_beijing_now()
    beijing_today = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_90d = (beijing_today - timedelta(days=90)).astimezone(timezone.utc).replace(tzinfo=None)
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


@router.get(
    "/admin/teacher-usage/user/{user_id}/detail",
    dependencies=[Depends(require_admin)],
)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get user detail with usage metrics and token stats (ADMIN ONLY)."""
    user = db.query(User).filter(User.id == user_id, User.role == "user").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    beijing_now = get_beijing_now()
    beijing_today = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = beijing_today.astimezone(timezone.utc).replace(tzinfo=None)
    week_ago = (beijing_today - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
    month_ago = (beijing_today - timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None)
    cutoff_90d = (beijing_today - timedelta(days=90)).astimezone(timezone.utc).replace(tzinfo=None)
    diagrams = 0
    concept_gen = 0
    rel_labels = 0
    weekly_data: list[dict[str, Any]] = []
    activity_trends: list[dict[str, Any]] = []
    token_stats = {
        "today": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "week": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "month": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "total": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    try:
        ac_row = (
            db.query(sql_count(TokenUsage.id).label("cnt"))
            .filter(
                TokenUsage.user_id == user_id,
                TokenUsage.request_type == "autocomplete",
                TokenUsage.success.is_(True),
            )
            .first()
        )
        diagrams = int(ac_row.cnt or 0) if ac_row else 0
        cg_row = (
            db.query(sql_count(UserActivityLog.id).label("cnt"))
            .filter(
                UserActivityLog.user_id == user_id,
                UserActivityLog.activity_type == "concept_generation",
            )
            .first()
        )
        concept_gen = int(cg_row.cnt or 0) if cg_row else 0
        rl_row = (
            db.query(sql_count(UserActivityLog.id).label("cnt"))
            .filter(
                UserActivityLog.user_id == user_id,
                UserActivityLog.activity_type == "relationship_labels",
            )
            .first()
        )
        rel_labels = int(rl_row.cnt or 0) if rl_row else 0

        activity_trends = []
        beijing_start = (beijing_today - timedelta(days=90)).astimezone(timezone.utc).replace(tzinfo=None)
        date_list = []
        current = beijing_today - timedelta(days=90)
        while current <= beijing_now:
            date_list.append(current.date())
            current += timedelta(days=1)

        edit_by_date: dict[str, int] = {}
        export_by_date: dict[str, int] = {}
        autocomplete_by_date: dict[str, int] = {}

        edit_rows = (
            db.query(
                func.date(UserActivityLog.created_at).label("d"),
                sql_count(UserActivityLog.id).label("cnt"),
            )
            .filter(
                UserActivityLog.user_id == user_id,
                UserActivityLog.activity_type == "diagram_edit",
                UserActivityLog.created_at >= beijing_start,
            )
            .group_by(func.date(UserActivityLog.created_at))
            .all()
        )
        for row in edit_rows:
            utc_date = row.d
            if isinstance(utc_date, str):
                utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
            utc_dt = datetime.combine(utc_date, datetime.min.time())
            beijing_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
            edit_by_date[str(beijing_dt.date())] = int(row.cnt or 0)

        export_rows = (
            db.query(
                func.date(UserActivityLog.created_at).label("d"),
                sql_count(UserActivityLog.id).label("cnt"),
            )
            .filter(
                UserActivityLog.user_id == user_id,
                UserActivityLog.activity_type == "diagram_export",
                UserActivityLog.created_at >= beijing_start,
            )
            .group_by(func.date(UserActivityLog.created_at))
            .all()
        )
        for row in export_rows:
            utc_date = row.d
            if isinstance(utc_date, str):
                utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
            utc_dt = datetime.combine(utc_date, datetime.min.time())
            beijing_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
            export_by_date[str(beijing_dt.date())] = int(row.cnt or 0)

        ac_rows = (
            db.query(
                func.date(TokenUsage.created_at).label("d"),
                sql_count(TokenUsage.id).label("cnt"),
            )
            .filter(
                TokenUsage.user_id == user_id,
                TokenUsage.request_type == "autocomplete",
                TokenUsage.success.is_(True),
                TokenUsage.created_at >= beijing_start,
            )
            .group_by(func.date(TokenUsage.created_at))
            .all()
        )
        for row in ac_rows:
            utc_date = row.d
            if isinstance(utc_date, str):
                utc_date = datetime.strptime(utc_date, "%Y-%m-%d").date()
            utc_dt = datetime.combine(utc_date, datetime.min.time())
            beijing_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(BEIJING_TIMEZONE)
            autocomplete_by_date[str(beijing_dt.date())] = int(row.cnt or 0)

        for d in date_list:
            date_str = str(d)
            activity_trends.append(
                {
                    "date": date_str,
                    "editCount": edit_by_date.get(date_str, 0),
                    "exportCount": export_by_date.get(date_str, 0),
                    "autocompleteCount": autocomplete_by_date.get(date_str, 0),
                }
            )

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
        for r in weekly_rows:
            week_dt = r.week
            date_str = week_dt.strftime("%Y-%m-%d") if week_dt else ""
            weekly_data.append({"date": date_str, "tokens": int(r.total or 0)})
        for period, start_ts in [
            ("today", today_start),
            ("week", week_ago),
            ("month", month_ago),
            ("total", None),
        ]:
            q = db.query(
                func.sum(TokenUsage.input_tokens).label("input_tokens"),
                func.sum(TokenUsage.output_tokens).label("output_tokens"),
                func.sum(TokenUsage.total_tokens).label("total_tokens"),
            ).filter(
                TokenUsage.user_id == user_id,
                TokenUsage.success.is_(True),
            )
            if start_ts is not None:
                q = q.filter(TokenUsage.created_at >= start_ts)
            row = q.first()
            if row:
                token_stats[period] = {
                    "input_tokens": int(row.input_tokens or 0),
                    "output_tokens": int(row.output_tokens or 0),
                    "total_tokens": int(row.total_tokens or 0),
                }
    except Exception as exc:
        logger.debug("Failed to fetch token stats: %s", exc)
    return {
        "userId": user_id,
        "username": user.name or user.phone or str(user_id),
        "diagrams": diagrams,
        "conceptGen": concept_gen,
        "relationshipLabels": rel_labels,
        "weeklyData": weekly_data,
        "activityTrends": activity_trends,
        "tokenStats": token_stats,
    }


@router.get("/admin/teacher-usage/config", dependencies=[Depends(require_admin)])
def get_teacher_usage_config(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get classification thresholds (ADMIN ONLY)."""
    return get_classification_config(db)


@router.put("/admin/teacher-usage/config", dependencies=[Depends(require_admin)])
def put_teacher_usage_config(
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
def post_teacher_usage_recompute(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Recompute all teacher classifications (ADMIN ONLY). Run after config change."""
    success, failed = _run_recompute(db)
    return {"success": True, "recomputed": success, "failed": failed}
