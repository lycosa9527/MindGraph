"""Tests for pg_dump failure logging and RLS operator hints."""

from __future__ import annotations

import logging

from services.utils.pg_client_binaries import log_pg_dump_failure


def test_log_pg_dump_failure_includes_rls_hint(caplog) -> None:
    """Permission/RLS errors should log DATABASE_MIGRATION_URL guidance."""
    caplog.set_level(logging.ERROR)
    log_pg_dump_failure("pg_dump: error: permission denied for table api_keys")

    combined = caplog.text.lower()
    assert "permission denied" in combined
    assert "database_migration_url" in combined
    assert "mindgraph_migrate" in combined
