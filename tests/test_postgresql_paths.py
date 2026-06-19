"""Tests for PostgreSQL data-path resolution helpers."""

from pathlib import Path

import pytest

from services.infrastructure.process import _postgresql_paths as pg_paths


def test_is_initialized_cluster(tmp_path: Path) -> None:
    """is_initialized_cluster is true only when PG_VERSION exists."""
    data_dir = tmp_path / "postgresql"
    data_dir.mkdir()
    assert pg_paths.is_initialized_cluster(data_dir) is False
    (data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    assert pg_paths.is_initialized_cluster(data_dir) is True


def test_find_system_cluster_prefers_matching_port(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """find_system_postgresql_cluster selects the cluster whose port matches."""
    main18 = tmp_path / "pg18" / "main"
    main16 = tmp_path / "pg16" / "main"
    main18.mkdir(parents=True)
    main16.mkdir(parents=True)
    (main18 / "PG_VERSION").write_text("18\n", encoding="utf-8")
    (main16 / "PG_VERSION").write_text("16\n", encoding="utf-8")

    class _LsclustersResult:
        returncode = 0
        stdout = (
            f"18  main    5432 online postgres {main18} /var/log/postgresql/postgresql-18-main.log\n"
            f"16  main    5433 online postgres {main16} /var/log/postgresql/postgresql-16-main.log\n"
        )

    monkeypatch.setattr(
        "services.infrastructure.process._postgresql_paths.subprocess.run",
        lambda *args, **kwargs: _LsclustersResult(),
    )
    found = pg_paths.find_system_postgresql_cluster(5433)
    assert found == (main16, "16")
