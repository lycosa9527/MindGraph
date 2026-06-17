"""Tests for PostgreSQL data-directory initialization helpers."""

from pathlib import Path

import pytest

from services.infrastructure.process._postgresql_init import _prepare_data_directory_for_initdb
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig


def _spawn_config() -> PostgresRuntimeConfig:
    return PostgresRuntimeConfig(
        database_url="postgresql://mindgraph_user:p@localhost:5432/mindgraph",
        host="localhost",
        port=5432,
        port_str="5432",
        database="mindgraph",
        runtime_user="mindgraph_user",
        provision_user="mindgraph_user",
        provision_password="p",
        spawn_subprocess=True,
        is_local=True,
    )


@pytest.fixture(autouse=True)
def _app_managed_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.infrastructure.process._postgresql_init.load_postgres_runtime_config",
        _spawn_config,
    )


def test_prepare_data_directory_removes_stale_config(tmp_path: Path) -> None:
    """Uninitialized data dir with stale config files is cleared before initdb."""
    data_path = tmp_path / "postgresql"
    data_path.mkdir()
    (data_path / "pg_hba.conf").write_text("host all all 127.0.0.1/32 trust\n", encoding="utf-8")

    _prepare_data_directory_for_initdb(data_path)

    assert not list(data_path.iterdir())


def test_prepare_data_directory_skips_initialized_cluster(tmp_path: Path) -> None:
    """Initialized cluster (PG_VERSION present) is left untouched."""
    data_path = tmp_path / "postgresql"
    data_path.mkdir()
    (data_path / "PG_VERSION").write_text("18\n", encoding="utf-8")
    (data_path / "pg_hba.conf").write_text("host all all 127.0.0.1/32 trust\n", encoding="utf-8")

    _prepare_data_directory_for_initdb(data_path)

    assert (data_path / "PG_VERSION").exists()
    assert (data_path / "pg_hba.conf").exists()


def test_prepare_data_directory_rejects_partial_cluster(tmp_path: Path) -> None:
    """Partial cluster without PG_VERSION exits with SystemExit."""
    data_path = tmp_path / "postgresql"
    data_path.mkdir()
    (data_path / "base").mkdir()

    with pytest.raises(SystemExit):
        _prepare_data_directory_for_initdb(data_path)


def test_prepare_data_directory_refuses_connect_only_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Connect-only runtime role refuses to prepare a data directory for initdb."""
    monkeypatch.setattr(
        "services.infrastructure.process._postgresql_init.load_postgres_runtime_config",
        lambda: PostgresRuntimeConfig(
            database_url="postgresql://mindgraph_app:p@localhost:5432/mindgraph",
            host="localhost",
            port=5432,
            port_str="5432",
            database="mindgraph",
            runtime_user="mindgraph_app",
            provision_user="mindgraph_user",
            provision_password="p",
            spawn_subprocess=False,
            is_local=True,
        ),
    )
    data_path = tmp_path / "postgresql"
    data_path.mkdir()

    with pytest.raises(SystemExit):
        _prepare_data_directory_for_initdb(data_path)
