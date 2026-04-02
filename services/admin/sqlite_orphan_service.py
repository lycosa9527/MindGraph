"""
SQLite and PostgreSQL Orphan Detection / Cleanup

Provides functions to detect and remove dangling FK references in both
a SQLite export file and the running PostgreSQL database.

These are extracted from sqlite_merge_service to keep file sizes under
the 800-line limit.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved -- Proprietary License
"""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Set

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ── SQLite helpers ───────────────────────────────────────────────────


def _sqlite_table_names(conn: sqlite3.Connection) -> Set[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur.fetchall()}


# ── SQLite orphan cleanup ────────────────────────────────────────────


def cleanup_sqlite_orphans(sqlite_path: Path) -> Dict[str, int]:
    """Delete orphaned records from a SQLite file and return counts."""
    conn = sqlite3.connect(str(sqlite_path))
    try:
        return _cleanup_sqlite_orphans_impl(conn)
    finally:
        conn.close()


def _cleanup_sqlite_orphans_impl(sq: sqlite3.Connection) -> Dict[str, int]:
    cur = sq.cursor()
    table_names = _sqlite_table_names(sq)
    cleaned: Dict[str, int] = {}

    cur.execute(
        "DELETE FROM users WHERE organization_id IS NOT NULL AND organization_id NOT IN (SELECT id FROM organizations)"
    )
    if cur.rowcount > 0:
        cleaned["users_nullified_missing_org"] = cur.rowcount

    if "token_usage" in table_names:
        cur.execute("DELETE FROM token_usage WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)")
        if cur.rowcount > 0:
            cleaned["token_usage_deleted_missing_user"] = cur.rowcount

        cur.execute(
            "DELETE FROM token_usage "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)"
        )
        if cur.rowcount > 0:
            cleaned["token_usage_deleted_missing_org"] = cur.rowcount

    if "dashboard_activities" in table_names:
        cur.execute(
            "DELETE FROM dashboard_activities WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)"
        )
        if cur.rowcount > 0:
            cleaned["dashboard_deleted_missing_user"] = cur.rowcount

    if "update_notification_dismissed" in table_names:
        cur.execute(
            "DELETE FROM update_notification_dismissed "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)"
        )
        if cur.rowcount > 0:
            cleaned["dismissed_deleted_missing_user"] = cur.rowcount

    if "diagrams" in table_names:
        cur.execute("DELETE FROM diagrams WHERE user_id NOT IN (SELECT id FROM users)")
        if cur.rowcount > 0:
            cleaned["diagrams_deleted_missing_user"] = cur.rowcount

    sq.commit()

    total = sum(cleaned.values())
    logger.info(
        "[SQLiteMerge] SQLite orphan cleanup: %d records removed (%s)",
        total,
        cleaned,
    )
    return cleaned


# ── PG orphan detection ──────────────────────────────────────────────


def detect_pg_orphans(pg_engine: Engine) -> Dict[str, int]:
    """Detect orphaned FK references in the current PostgreSQL database."""
    orphans: Dict[str, int] = {}
    fk_checks = [
        (
            "users_missing_org",
            "SELECT COUNT(*) FROM users "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)",
        ),
        (
            "token_usage_missing_user",
            "SELECT COUNT(*) FROM token_usage WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "token_usage_missing_org",
            "SELECT COUNT(*) FROM token_usage "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)",
        ),
        (
            "dashboard_activities_missing_user",
            "SELECT COUNT(*) FROM dashboard_activities "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "update_dismissed_missing_user",
            "SELECT COUNT(*) FROM update_notification_dismissed "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "diagrams_missing_user",
            "SELECT COUNT(*) FROM diagrams WHERE user_id NOT IN (SELECT id FROM users)",
        ),
    ]
    with pg_engine.connect() as conn:
        for label, query in fk_checks:
            try:
                result = conn.execute(text(query))
                count = result.scalar() or 0
                if count > 0:
                    orphans[label] = count
            except Exception as exc:
                logger.debug("[OrphanDetect] %s failed: %s", label, exc)
    return orphans


def cleanup_pg_orphans(pg_engine: Engine) -> Dict[str, int]:
    """Delete or nullify orphaned FK references in PostgreSQL."""
    cleaned: Dict[str, int] = {}
    operations = [
        (
            "users_nullify_missing_org",
            "UPDATE users SET organization_id = NULL "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)",
        ),
        (
            "token_usage_delete_missing_user",
            "DELETE FROM token_usage WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "token_usage_nullify_missing_org",
            "UPDATE token_usage SET organization_id = NULL "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)",
        ),
        (
            "dashboard_delete_missing_user",
            "DELETE FROM dashboard_activities WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "dismissed_delete_missing_user",
            "DELETE FROM update_notification_dismissed "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "diagrams_delete_missing_user",
            "DELETE FROM diagrams WHERE user_id NOT IN (SELECT id FROM users)",
        ),
    ]
    with pg_engine.begin() as conn:
        for label, query in operations:
            try:
                result = conn.execute(text(query))
                affected = result.rowcount
                if affected > 0:
                    cleaned[label] = affected
                    logger.info(
                        "[OrphanCleanup] %s: %d rows affected",
                        label,
                        affected,
                    )
            except Exception as exc:
                logger.warning(
                    "[OrphanCleanup] %s failed: %s",
                    label,
                    exc,
                )
    return cleaned
