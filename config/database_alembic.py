"""Alembic migration runner (leaf module — keeps ``config.database`` import graph acyclic).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from scripts.db.migration_urls import configure_rls_migration_environment
from scripts.db.rls_roles_bootstrap import ensure_rls_roles_exist
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


def run_alembic_upgrade(
    *,
    database_url: str,
    alembic_ini: str,
    alembic_script_dir: str,
    project_root: Path,
    engine,
    migration_lock_key: str,
    migration_lock_ttl: int,
    migration_wait_interval_sec: float,
    migration_wait_max_attempts: int,
    get_alembic_version_num,
    acquire_migration_lock,
    release_migration_lock,
) -> None:
    """Apply pending Alembic migrations when the DB revision is behind head."""
    del engine, migration_lock_key, migration_lock_ttl
    if "postgresql" in database_url:
        roles_ok, roles_msg = ensure_rls_roles_exist()
        if not roles_ok:
            raise RuntimeError(f"RLS PostgreSQL bootstrap failed before Alembic: {roles_msg}")
        if roles_msg != "RLS roles already exist":
            logger.info("[Database] %s", roles_msg)
        try:
            configure_rls_migration_environment()
        except DATABASE_ERRORS as exc:
            logger.warning(
                "[Database] Could not auto-resolve DATABASE_MIGRATION_URL for Alembic: %s",
                exc,
            )

    alembic_cfg = AlembicConfig(alembic_ini)
    alembic_cfg.set_main_option("script_location", alembic_script_dir)
    alembic_cfg.set_main_option("prepend_sys_path", str(project_root))
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script_dir.get_current_head()

    current_rev = get_alembic_version_num()

    if current_rev == head_rev:
        logger.info("[Database] Schema is up to date (revision %s)", current_rev)
        return

    if head_rev is None:
        logger.error(
            "[Database] Database has revision %s but no Alembic head revision found on disk.",
            current_rev,
        )
        raise RuntimeError("Alembic script directory has no head revision; cannot apply migrations or wait for a peer.")

    if current_rev is None:
        logger.info("[Database] No alembic_version found — running initial migration")
    else:
        logger.info(
            "[Database] Pending migration: %s → %s",
            current_rev,
            head_rev,
        )

    lock_acquired = False
    try:
        lock_acquired = acquire_migration_lock()
        if not lock_acquired:
            wait_for_migration_completion(
                expected_head=head_rev,
                get_alembic_version_num=get_alembic_version_num,
                wait_interval_sec=migration_wait_interval_sec,
                wait_max_attempts=migration_wait_max_attempts,
            )
            return
        alembic_upgrade(alembic_cfg, "head")
        logger.info("[Database] Alembic upgrade to head completed")
    finally:
        if lock_acquired:
            release_migration_lock()


def wait_for_migration_completion(
    *,
    expected_head: str,
    get_alembic_version_num,
    wait_interval_sec: float,
    wait_max_attempts: int,
) -> None:
    """Poll until the winner worker finishes the migration (revision matches head)."""
    for attempt in range(wait_max_attempts):
        time.sleep(wait_interval_sec)
        current = get_alembic_version_num()
        if current == expected_head:
            logger.info(
                "[Database] Migration completed by another worker (revision %s)",
                current,
            )
            return
        if (attempt + 1) % 15 == 0:
            elapsed = int((attempt + 1) * wait_interval_sec)
            logger.info(
                "[Database] Still waiting for migration to complete (~%d s elapsed, max ~%d s)...",
                elapsed,
                int(wait_max_attempts * wait_interval_sec),
            )

    logger.error(
        "[Database] Timed out waiting for peer worker to finish migrations "
        "(expected revision %s). Refusing to start with a possibly incomplete schema.",
        expected_head,
    )
    raise RuntimeError(
        "Timed out waiting for another worker to complete Alembic migrations. "
        "If first-time baseline migrations legitimately take longer than the "
        f"configured maximum (~{int(wait_max_attempts * wait_interval_sec)} s), "
        "increase _MIGRATION_WAIT_MAX_ATTEMPTS / _MIGRATION_WAIT_INTERVAL_SEC in config/database.py, "
        "or run `alembic upgrade head` once before starting multiple workers."
    )
