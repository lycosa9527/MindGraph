"""Tests for choosing the PostgreSQL data directory and recording it in .env."""

from pathlib import Path

import pytest

from services.infrastructure.process import _postgresql_cluster_choice as choice
from services.infrastructure.process._postgresql_discovery import RankedCluster
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig


def _config() -> PostgresRuntimeConfig:
    return PostgresRuntimeConfig(
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
    )


def _ranked(path: Path, *, port: int = 5432, has_database: bool = False, score: int = 1) -> RankedCluster:
    return RankedCluster(path=path, port=port, score=score, has_database=has_database)


def _init_cluster(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "PG_VERSION").write_text("18\n", encoding="utf-8")
    (path / "postgresql.conf").write_text("port = 5432\n", encoding="utf-8")
    return path


def test_env_locks_listed_mindgraph_cluster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Once clusters are listed, .env keeps the mindgraph directory that has the database."""
    env_path = tmp_path / ".env"
    mindgraph = _init_cluster(tmp_path / "postgresql")
    other = _init_cluster(tmp_path / "other")
    env_path.write_text(f"POSTGRESQL_DATA_DIR={mindgraph}\n", encoding="utf-8")
    monkeypatch.setenv("MINDGRAPH_ENV_FILE", str(env_path))
    monkeypatch.delenv("POSTGRESQL_DATA_DIR", raising=False)
    monkeypatch.setattr(
        choice,
        "discover_ranked_cluster_details",
        lambda config: [
            _ranked(other, has_database=True, score=2000),
            _ranked(mindgraph, has_database=True, score=1000),
        ],
    )

    selected = choice.choose_cluster(_config())
    assert selected.path == mindgraph


def test_choose_verified_mindgraph_over_distro_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cluster that contains the database is chosen while the distro cluster is not."""
    distro = tmp_path / "18" / "main"
    mindgraph = tmp_path / "mindgraph"
    monkeypatch.delenv("POSTGRESQL_DATA_DIR", raising=False)
    monkeypatch.setattr(
        choice,
        "discover_ranked_cluster_details",
        lambda config: [
            _ranked(distro, has_database=False, score=240),
            _ranked(mindgraph, has_database=True, score=1200),
        ],
    )

    selected = choice.choose_cluster(_config())
    assert selected.path == mindgraph


def test_configured_dir_loses_when_another_cluster_has_the_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POSTGRESQL_DATA_DIR is rewritten in memory when it points at the wrong cluster."""
    distro = _init_cluster(tmp_path / "18" / "main")
    mindgraph = tmp_path / "mindgraph"
    monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(distro))
    monkeypatch.setattr(
        choice,
        "discover_ranked_cluster_details",
        lambda config: [
            _ranked(distro, has_database=False, score=240),
            _ranked(mindgraph, has_database=True, score=1200),
        ],
    )

    selected = choice.choose_cluster(_config())
    assert selected.path == mindgraph


def test_configured_dir_kept_when_nothing_else_has_the_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An initialized POSTGRESQL_DATA_DIR stays when no surveyed cluster has the database."""
    configured = _init_cluster(tmp_path / "mindgraph")
    monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(configured))
    monkeypatch.setattr(
        choice,
        "discover_ranked_cluster_details",
        lambda config: [_ranked(configured, has_database=False, score=300)],
    )

    selected = choice.choose_cluster(_config())
    assert selected.path == configured


def test_publish_cluster_env_writes_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Launch records the located data directory in .env."""
    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=postgresql://mindgraph_app:p@localhost:5432/mindgraph\n", encoding="utf-8")
    data_dir = tmp_path / "mindgraph"
    monkeypatch.setenv("MINDGRAPH_ENV_FILE", str(env_path))
    monkeypatch.delenv("POSTGRESQL_DATA_DIR", raising=False)

    status = choice.publish_cluster_env(data_dir)
    text = env_path.read_text(encoding="utf-8")

    assert status == "updated"
    assert f"POSTGRESQL_DATA_DIR={data_dir}" in text
    assert "DATABASE_URL=" in text
    assert choice.publish_cluster_env(data_dir) == "unchanged"


def test_mindgraph_path_beats_unverified_env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mindgraph data directory replaces POSTGRESQL_DATA_DIR when that directory has no database."""
    configured = _init_cluster(tmp_path / "storage" / "postgresql")
    mindgraph = tmp_path / "var" / "mindgraph"
    monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(configured))
    monkeypatch.setattr(
        choice,
        "discover_ranked_cluster_details",
        lambda config: [
            _ranked(configured, has_database=False, score=200),
            _ranked(mindgraph, has_database=False, score=380),
        ],
    )

    selected = choice.choose_cluster(_config())
    assert selected.path == mindgraph


def test_env_pointing_at_empty_main_loses_to_populated_cluster(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified empty distro main cluster does not stay selected via POSTGRESQL_DATA_DIR."""
    empty_main = _init_cluster(tmp_path / "19" / "main")
    populated = _init_cluster(tmp_path / "mindgraph")
    monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(empty_main))
    monkeypatch.setattr(
        choice,
        "discover_ranked_cluster_details",
        lambda config: [
            _ranked(empty_main, has_database=True, score=1040),
            _ranked(populated, has_database=True, score=1380),
        ],
    )

    selected = choice.choose_cluster(_config())
    assert selected.path == populated


def test_named_mindgraph_dir_used_when_unverified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mindgraph-named data directory is used when catalog probes cannot confirm it."""
    distro = tmp_path / "18" / "main"
    mindgraph = tmp_path / "mindgraph"
    monkeypatch.delenv("POSTGRESQL_DATA_DIR", raising=False)
    monkeypatch.setattr(
        choice,
        "discover_ranked_cluster_details",
        lambda config: [
            _ranked(distro, has_database=False, score=240),
            _ranked(mindgraph, has_database=False, score=380),
        ],
    )

    selected = choice.choose_cluster(_config())
    assert selected.path == mindgraph
