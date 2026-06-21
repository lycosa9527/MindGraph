"""
PostgreSQL orphan detection and cleanup for the admin database panel.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Dict

from sqlalchemy import text
from sqlalchemy.engine import Engine

from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


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
            except DATABASE_ERRORS as exc:
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
            except DATABASE_ERRORS as exc:
                logger.warning(
                    "[OrphanCleanup] %s failed: %s",
                    label,
                    exc,
                )
    return cleaned
