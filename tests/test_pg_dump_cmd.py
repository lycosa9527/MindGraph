"""pg_dump command builder — RLS-safe flags for all backup paths."""

from __future__ import annotations

from pathlib import Path

from services.utils.pg_client_binaries import build_pg_dump_cmd


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
