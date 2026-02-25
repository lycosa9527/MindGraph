"""
Teacher Usage Stats Service
===========================

Computes and stores per-user usage metrics and 2-tier classification.
Called on login and token usage; teacher_usage API reads from user_usage_stats.
Classification thresholds are configurable via teacher_usage_config table.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session

from config.database import SessionLocal
from models.domain.teacher_usage_config import (
    TeacherUsageConfig,
    _default_thresholds,
)
from models.domain.token_usage import TokenUsage
from models.domain.user_activity_log import UserActivityLog
from models.domain.user_usage_stats import UserUsageStats

logger = logging.getLogger(__name__)

OBSERVATION_DAYS = 56
CONFIG_KEY = "classification_thresholds"
BEIJING_UTC_OFFSET = timedelta(hours=8)


def _get_window_cutoff_utc():
    """Get 56 days ago (start of observation window) in UTC."""
    beijing_tz = timezone(BEIJING_UTC_OFFSET)
    beijing_now = datetime.now(beijing_tz)
    beijing_today = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = (
        (beijing_today - timedelta(days=OBSERVATION_DAYS))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    return window_start


def _get_active_dates_for_user(
    db: Session,
    user_id: int,
    window_start,
) -> Set[Any]:
    """Get distinct active dates (as date objects) for user in observation window."""
    active_dates: Set[Any] = set()

    token_rows = (
        db.query(func.date(TokenUsage.created_at).label("d"))
        .filter(
            TokenUsage.user_id == user_id,
            TokenUsage.success.is_(True),
            TokenUsage.created_at >= window_start,
        )
        .distinct()
        .all()
    )
    for row in token_rows:
        if row.d:
            active_dates.add(row.d)

    try:
        log_db = SessionLocal()
        try:
            log_rows = (
                log_db.query(func.date(UserActivityLog.created_at).label("d"))
                .filter(
                    UserActivityLog.user_id == user_id,
                    UserActivityLog.activity_type == "login",
                    UserActivityLog.created_at >= window_start,
                )
                .distinct()
                .all()
            )
            for row in log_rows:
                if row.d:
                    active_dates.add(row.d)
        finally:
            log_db.close()
    except Exception as e:
        logger.debug("UserActivityLog query failed (table may not exist): %s", e)

    return active_dates


def _compute_metrics(active_dates: Set[Any], window_start) -> dict[str, int]:
    """Compute all metrics from active dates. window_start is naive UTC datetime."""
    window_start_date = window_start.date() if hasattr(window_start, "date") else window_start
    sorted_dates = sorted(active_dates)

    if not sorted_dates:
        return {
            "active_days": 0,
            "active_days_first10": 0,
            "active_days_last25": 0,
            "active_days_first25": 0,
            "active_days_last14": 0,
            "active_weeks": 0,
            "active_weeks_first4": 0,
            "active_weeks_last4": 0,
            "max_zero_gap_days": OBSERVATION_DAYS,
            "n_bursts": 0,
            "internal_max_zero_gap_days": 0,
        }

    day_1 = window_start_date
    day_10 = day_1 + timedelta(days=9)
    day_25 = day_1 + timedelta(days=24)
    day_32 = day_1 + timedelta(days=31)
    day_43 = day_1 + timedelta(days=42)
    day_56 = day_1 + timedelta(days=55)

    active_days_first10 = sum(1 for d in sorted_dates if day_1 <= d <= day_10)
    active_days_last25 = sum(1 for d in sorted_dates if day_32 <= d <= day_56)
    active_days_first25 = sum(1 for d in sorted_dates if day_1 <= d <= day_25)
    active_days_last14 = sum(1 for d in sorted_dates if day_43 <= d <= day_56)

    week_days = [(day_1 + timedelta(days=i * 7), day_1 + timedelta(days=i * 7 + 6))
                 for i in range(8)]
    active_weeks = 0
    active_weeks_first4 = 0
    active_weeks_last4 = 0
    for i, (w_start, w_end) in enumerate(week_days):
        has_activity = any(w_start <= d <= w_end for d in sorted_dates)
        if has_activity:
            active_weeks += 1
            if i < 4:
                active_weeks_first4 += 1
            else:
                active_weeks_last4 += 1

    max_zero_gap = 0
    prev = day_1
    for d in sorted_dates:
        gap = max(0, (d - prev).days - 1)
        if gap > max_zero_gap:
            max_zero_gap = gap
        prev = d
    end_gap = max(0, (day_56 - prev).days)
    if end_gap > max_zero_gap:
        max_zero_gap = end_gap

    n_bursts = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days > 1:
            n_bursts += 1

    internal_max_gap = 0
    if len(sorted_dates) >= 2:
        for i in range(1, len(sorted_dates)):
            g = (sorted_dates[i] - sorted_dates[i - 1]).days - 1
            if g > internal_max_gap:
                internal_max_gap = g

    return {
        "active_days": len(sorted_dates),
        "active_days_first10": active_days_first10,
        "active_days_last25": active_days_last25,
        "active_days_first25": active_days_first25,
        "active_days_last14": active_days_last14,
        "active_weeks": active_weeks,
        "active_weeks_first4": active_weeks_first4,
        "active_weeks_last4": active_weeks_last4,
        "max_zero_gap_days": max_zero_gap,
        "n_bursts": n_bursts,
        "internal_max_zero_gap_days": internal_max_gap,
    }


def get_classification_config(db: Session) -> dict:
    """Get classification thresholds from DB, or defaults if not set."""
    row = (
        db.query(TeacherUsageConfig)
        .filter(TeacherUsageConfig.config_key == CONFIG_KEY)
        .first()
    )
    if row and row.config_value:
        defaults = _default_thresholds()
        merged = {}
        for group in defaults:
            merged[group] = {**defaults[group], **(row.config_value.get(group) or {})}
        return merged
    return _default_thresholds()


def save_classification_config(db: Session, thresholds: dict) -> bool:
    """Save classification thresholds to DB. Returns True on success."""
    try:
        row = (
            db.query(TeacherUsageConfig)
            .filter(TeacherUsageConfig.config_key == CONFIG_KEY)
            .first()
        )
        if row:
            row.config_value = thresholds
            row.updated_at = datetime.utcnow()
        else:
            row = TeacherUsageConfig(
                config_key=CONFIG_KEY,
                config_value=thresholds,
            )
            db.add(row)
        db.commit()
        return True
    except Exception as e:
        logger.exception("save_classification_config failed: %s", e)
        db.rollback()
        return False


def _classify(metrics: dict[str, int], config: dict) -> tuple[str, Optional[str]]:
    """Return (tier1, tier2). tier2 is None for unused and continuous."""
    ad = metrics["active_days"]
    ad_f10 = metrics["active_days_first10"]
    ad_l25 = metrics["active_days_last25"]
    ad_f25 = metrics["active_days_first25"]
    ad_l14 = metrics["active_days_last14"]
    aw = metrics["active_weeks"]
    aw_f4 = metrics["active_weeks_first4"]
    aw_l4 = metrics["active_weeks_last4"]
    max_gap = metrics["max_zero_gap_days"]
    n_bursts = metrics["n_bursts"]
    internal_gap = metrics["internal_max_zero_gap_days"]

    if ad == 0:
        return ("unused", None)

    cont = config.get("continuous", {})
    if (
        aw >= cont.get("active_weeks_min", 5)
        and aw_f4 >= cont.get("active_weeks_first4_min", 1)
        and aw_l4 >= cont.get("active_weeks_last4_min", 1)
        and max_gap <= cont.get("max_zero_gap_days_max", 10)
    ):
        return ("continuous", None)

    rej = config.get("rejection", {})
    if (
        ad <= rej.get("active_days_max", 3)
        and ad_f10 >= rej.get("active_days_first10_min", 1)
        and ad_l25 <= rej.get("active_days_last25_max", 0)
        and max_gap >= rej.get("max_zero_gap_days_min", 25)
    ):
        return ("non_continuous", "rejection")

    stop = config.get("stopped", {})
    if (
        ad_f25 >= stop.get("active_days_first25_min", 3)
        and ad_l14 <= stop.get("active_days_last14_max", 0)
        and max_gap >= stop.get("max_zero_gap_days_min", 14)
    ):
        return ("non_continuous", "stopped")

    inter = config.get("intermittent", {})
    if (
        n_bursts >= inter.get("n_bursts_min", 2)
        and internal_gap >= inter.get("internal_max_zero_gap_days_min", 7)
    ):
        return ("non_continuous", "intermittent")

    return ("non_continuous", "intermittent")


def compute_and_upsert_user_usage_stats(user_id: int, db: Session) -> bool:
    """
    Compute metrics and classification for a user, upsert into user_usage_stats.

    Returns True on success, False on failure (caller should not fail the request).
    """
    try:
        window_start = _get_window_cutoff_utc()
        active_dates = _get_active_dates_for_user(db, user_id, window_start)
        metrics = _compute_metrics(active_dates, window_start)
        config = get_classification_config(db)
        tier1, tier2 = _classify(metrics, config)

        existing = db.query(UserUsageStats).filter(UserUsageStats.user_id == user_id).first()
        if existing:
            existing.active_days = metrics["active_days"]
            existing.active_days_first10 = metrics["active_days_first10"]
            existing.active_days_last25 = metrics["active_days_last25"]
            existing.active_days_first25 = metrics["active_days_first25"]
            existing.active_days_last14 = metrics["active_days_last14"]
            existing.active_weeks = metrics["active_weeks"]
            existing.active_weeks_first4 = metrics["active_weeks_first4"]
            existing.active_weeks_last4 = metrics["active_weeks_last4"]
            existing.max_zero_gap_days = metrics["max_zero_gap_days"]
            existing.n_bursts = metrics["n_bursts"]
            existing.internal_max_zero_gap_days = metrics["internal_max_zero_gap_days"]
            existing.tier1 = tier1
            existing.tier2 = tier2
            existing.computed_at = datetime.utcnow()
        else:
            stats = UserUsageStats(
                user_id=user_id,
                active_days=metrics["active_days"],
                active_days_first10=metrics["active_days_first10"],
                active_days_last25=metrics["active_days_last25"],
                active_days_first25=metrics["active_days_first25"],
                active_days_last14=metrics["active_days_last14"],
                active_weeks=metrics["active_weeks"],
                active_weeks_first4=metrics["active_weeks_first4"],
                active_weeks_last4=metrics["active_weeks_last4"],
                max_zero_gap_days=metrics["max_zero_gap_days"],
                n_bursts=metrics["n_bursts"],
                internal_max_zero_gap_days=metrics["internal_max_zero_gap_days"],
                tier1=tier1,
                tier2=tier2,
                computed_at=datetime.utcnow(),
            )
            db.add(stats)

        db.commit()
        return True
    except Exception as e:
        logger.exception("compute_and_upsert_user_usage_stats failed for user %s: %s", user_id, e)
        db.rollback()
        return False
