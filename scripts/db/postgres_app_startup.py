"""PostgreSQL + RLS preparation for ``python main.py`` (after the server is listening)."""

from __future__ import annotations

import logging

from scripts.db.migration_urls import configure_rls_migration_environment
from scripts.db.rls_roles_bootstrap import ensure_rls_roles_exist
from services.infrastructure.process._postgresql_helpers import try_database_url_connect
from services.infrastructure.process._postgresql_runtime import load_postgres_runtime_config
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


def verify_runtime_database_connection() -> tuple[bool, str]:
    """Confirm ``DATABASE_URL`` accepts connections after infrastructure startup."""
    config = load_postgres_runtime_config()
    if try_database_url_connect(config, timeout=5):
        return True, "DATABASE_URL connection verified"
    return (
        False,
        f"DATABASE_URL connection failed for {config.runtime_user}@{config.host}:{config.port}/{config.database}",
    )


def prepare_postgresql_rls_runtime() -> tuple[bool, str]:
    """
    Ensure RLS roles exist, refresh ``DATABASE_MIGRATION_URL``, and verify ``DATABASE_URL``.

    Call only after PostgreSQL accepts connections (reused instance or app subprocess).
    """
    roles_ok, roles_msg = ensure_rls_roles_exist()
    if not roles_ok:
        return False, roles_msg

    try:
        configure_rls_migration_environment()
    except DATABASE_ERRORS as exc:
        return False, f"Could not configure DATABASE_MIGRATION_URL: {exc}"

    verified, verify_msg = verify_runtime_database_connection()
    if not verified:
        return False, verify_msg

    if roles_msg != "RLS roles already exist":
        logger.info("[PostgreSQL] %s", roles_msg)
    return True, roles_msg
