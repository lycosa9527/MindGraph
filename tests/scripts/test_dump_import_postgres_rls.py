"""Tests for RLS-safe pg_dump manifest helpers used by dump/import paths."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.utils.pg_backup_manifest import (
    StatsEngineResolutionError,
    build_pg_dump_manifest,
    collect_db_stats,
    resolve_stats_engine,
)

def test_build_pg_dump_manifest_includes_size_bytes_and_tables(tmp_path: Path) -> None:
    """Manifest matches shared contract: size_bytes, tables, totals."""
    dump_path = tmp_path / "mindgraph.postgresql.20260101_120000.dump"
    dump_path.write_bytes(b"fake-dump-bytes")

    mock_engine = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["diagrams", "users"]
    mock_inspector.get_columns.side_effect = lambda name: [{"name": "id"}] if name == "diagrams" else [{"name": "id"}, {"name": "phone"}]

    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.side_effect = [10, 5]
    mock_conn.execute.return_value = mock_result
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_conn
    mock_cm.__exit__.return_value = None
    mock_engine.connect.return_value = mock_cm

    when = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    with patch("services.utils.pg_backup_manifest.inspect", return_value=mock_inspector):
        manifest = build_pg_dump_manifest(
            dump_path,
            mock_engine,
            dump_file=dump_path.name,
            timestamp=when,
            source="localhost:5432/mindgraph",
        )

    assert manifest["dump_file"] == dump_path.name
    assert manifest["timestamp"] == when.isoformat()
    assert manifest["size_bytes"] == len(b"fake-dump-bytes")
    assert manifest["source"] == "localhost:5432/mindgraph"
    assert manifest["tables"] == {"diagrams": 10, "users": 5}
    assert manifest["total_tables"] == 2
    assert manifest["total_columns"] == 3
    assert manifest["total_records"] == 15


def test_collect_db_stats_sums_row_counts() -> None:
    """collect_db_stats returns table, column, and record totals."""
    mock_engine = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["a", "b"]
    mock_inspector.get_columns.side_effect = lambda _: [{"name": "id"}]

    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.side_effect = [3, 7]
    mock_conn.execute.return_value = mock_result
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_conn
    mock_cm.__exit__.return_value = None
    mock_engine.connect.return_value = mock_cm

    with patch("services.utils.pg_backup_manifest.inspect", return_value=mock_inspector):
        tables, columns, records, counts = collect_db_stats(mock_engine)

    assert tables == 2
    assert columns == 2
    assert records == 10
    assert counts == {"a": 3, "b": 7}


def test_resolve_stats_engine_uses_migration_url(monkeypatch) -> None:
    """resolve_stats_engine configures env and builds engine from DATABASE_MIGRATION_URL."""
    migrate = "postgresql+psycopg://mindgraph_migrate:secret@localhost:5432/mindgraph"
    mock_engine = MagicMock()

    import config.database as cfg

    monkeypatch.setattr(cfg, "DATABASE_MIGRATION_URL", migrate)

    with patch("services.utils.pg_backup_manifest.configure_rls_migration_environment"):
        with patch(
            "services.utils.pg_backup_manifest.create_migration_engine",
            return_value=mock_engine,
        ) as create_engine:
            engine = resolve_stats_engine(bootstrap_rls=False)

    assert engine is mock_engine
    create_engine.assert_called_once_with(migrate)


def test_resolve_stats_engine_raises_when_rls_bootstrap_fails() -> None:
    """Default resolve_stats_engine fails fast when RLS roles or migrate URL are missing."""
    with patch(
        "services.utils.pg_backup_manifest.prepare_pg_dump_rls",
        return_value=(False, "mindgraph_migrate missing"),
    ):
        with pytest.raises(StatsEngineResolutionError, match="mindgraph_migrate missing"):
            resolve_stats_engine()
