"""PostgreSQL + RLS preparation for ``python main.py`` (after the server is listening)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def prepare_postgresql_rls_runtime() -> tuple[bool, str]:
    """
    Ensure RLS roles exist and refresh ``DATABASE_MIGRATION_URL`` in the environment.

    Call only after PostgreSQL accepts connections (reused instance or app subprocess).
    """
    from scripts.db.migration_urls import configure_rls_migration_environment
    from scripts.db.rls_roles_bootstrap import ensure_rls_roles_exist

    roles_ok, roles_msg = ensure_rls_roles_exist()
    if not roles_ok:
        return False, roles_msg

    try:
        configure_rls_migration_environment()
    except Exception as exc:
        return False, f"Could not configure DATABASE_MIGRATION_URL: {exc}"

    if roles_msg != "RLS roles already exist":
        logger.info("[PostgreSQL] %s", roles_msg)
    return True, roles_msg
