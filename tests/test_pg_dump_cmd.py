"""pg_dump command builder — RLS-safe flags and migrate URL for all backup paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from services.utils.pg_client_binaries import (
    build_pg_dump_cmd,
    pg_tools_connection_username,
    pg_tools_libpq_url,
)


def test_build_pg_dump_cmd_includes_rls_safe_flags() -> None:
    """Test build pg dump cmd includes rls safe flags."""
    cmd = build_pg_dump_cmd(
        "/usr/bin/pg_dump",
        Path("/tmp/mindgraph.dump"),
        "postgresql+psycopg://user:pass@localhost:5432/mindgraph",
    )

    assert cmd[0] == "/usr/bin/pg_dump"
    assert "-Fc" in cmd
    assert "--no-owner" in cmd
    assert "--no-policies" in cmd
    assert "-f" in cmd
    assert str(Path("/tmp/mindgraph.dump")) in cmd


def test_pg_tools_connection_username() -> None:
    """Extract username for backup logging without exposing password."""
    url = "postgresql+psycopg://mindgraph_migrate:secret@localhost:5432/mindgraph"
    assert pg_tools_connection_username(url) == "mindgraph_migrate"


def test_pg_tools_libpq_url_uses_migration_url() -> None:
    """pg_dump/pg_restore must connect as migrate role, not mindgraph_app."""
    migrate = "postgresql+psycopg://mindgraph_migrate:secret@localhost:5432/mindgraph"
    with patch("services.utils.pg_client_binaries.DATABASE_MIGRATION_URL", migrate):
        url = pg_tools_libpq_url()
    assert url == "postgresql://mindgraph_migrate:secret@localhost:5432/mindgraph"


def test_pg_tools_libpq_url_resolves_when_migration_url_is_app_role() -> None:
    """When DATABASE_MIGRATION_URL points at mindgraph_app, resolve migrate-capable URL."""
    app_url = "postgresql+psycopg://mindgraph_app:secret@localhost:5432/mindgraph"
    migrate_url = "postgresql+psycopg://mindgraph_migrate:migrate@localhost:5432/mindgraph"
    with patch("services.utils.pg_client_binaries.DATABASE_MIGRATION_URL", app_url):
        with patch(
            "services.utils.pg_client_binaries.resolve_migration_database_url",
            return_value=(migrate_url, "auto (mindgraph_migrate)"),
        ):
            url = pg_tools_libpq_url()
    assert url == "postgresql://mindgraph_migrate:migrate@localhost:5432/mindgraph"
