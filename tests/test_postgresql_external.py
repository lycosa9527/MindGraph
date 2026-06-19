"""Tests for connect-only PostgreSQL external startup helpers."""

from pathlib import Path

import pytest

from services.infrastructure.process import _postgresql_external as pg_ext
from services.infrastructure.process import _postgresql_paths as pg_paths
from services.infrastructure.process._postgresql_discovery import RankedCluster
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig


def _connect_only_config() -> PostgresRuntimeConfig:
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


def _ranked(path: Path, port: int = 5432, has_database: bool = True) -> RankedCluster:
    return RankedCluster(path=path, port=port, score=1000, has_database=has_database)


def test_read_cluster_port_from_conf(tmp_path: Path) -> None:
    """read_cluster_port parses an uncommented port line."""
    data_dir = tmp_path / "postgresql"
    data_dir.mkdir()
    (data_dir / "postgresql.conf").write_text(
        "# comment\nlisten_addresses = '127.0.0.1'\nport = 5433\n",
        encoding="utf-8",
    )
    assert pg_paths.read_cluster_port(data_dir) == 5433


def test_try_start_ranked_clusters_skips_wrong_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persistent startup ignores clusters configured on a different port."""
    data_dir = tmp_path / "mindgraph"
    data_dir.mkdir()
    (data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    (data_dir / "postgresql.conf").write_text("port = 5433\n", encoding="utf-8")

    monkeypatch.setattr(pg_ext, "postgresql_accepts_connections", lambda host, port: False)
    monkeypatch.setattr(pg_ext, "check_port_in_use", lambda host, port: (False, None))
    monkeypatch.setattr(pg_ext, "_find_pg_ctl_binary", lambda: "/usr/bin/pg_ctl")
    monkeypatch.setattr(pg_ext, "cleanup_stale_pid_file", lambda path: None)

    class _Result:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(pg_ext.subprocess, "run", lambda *args, **kwargs: _Result())

    assert pg_ext.try_start_ranked_clusters([_ranked(data_dir, port=5433)], 5432) is False

    (data_dir / "postgresql.conf").write_text("port = 5432\n", encoding="utf-8")
    monkeypatch.setattr(pg_ext, "postgresql_accepts_connections", lambda host, port: port == 5432)
    assert pg_ext.try_start_ranked_clusters([_ranked(data_dir)], 5432) is True


def test_ensure_local_external_prefers_verified_cluster_before_system(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verified MindGraph clusters start before distro system PostgreSQL."""
    config = _connect_only_config()
    mindgraph = tmp_path / "mindgraph"
    ranked = [_ranked(mindgraph)]
    calls: list[str] = []

    monkeypatch.setattr(pg_ext, "postgresql_accepts_connections", lambda host, port: False)
    monkeypatch.setattr(pg_ext, "discover_ranked_cluster_details", lambda cfg: ranked)
    monkeypatch.setattr(
        pg_ext,
        "try_start_ranked_clusters",
        lambda items, port: calls.append("ranked") or True,
    )
    monkeypatch.setattr(
        pg_ext,
        "try_start_system_postgresql",
        lambda port: calls.append("system") or True,
    )

    assert pg_ext.ensure_local_external_postgresql(config) is True
    assert calls == ["ranked"]


def test_ensure_local_external_falls_back_to_system_then_remaining_ranked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When verified clusters fail, system PostgreSQL then remaining ranked paths are tried."""
    config = _connect_only_config()
    unverified = _ranked(tmp_path / "unknown", has_database=False)
    calls: list[str] = []

    monkeypatch.setattr(pg_ext, "postgresql_accepts_connections", lambda host, port: False)
    monkeypatch.setattr(pg_ext, "discover_ranked_cluster_details", lambda cfg: [unverified])

    def _ranked_start(items: list[RankedCluster], port: int) -> bool:
        label = "verified" if items and items[0].has_database else "all"
        calls.append(label)
        return label == "all"

    monkeypatch.setattr(pg_ext, "try_start_ranked_clusters", _ranked_start)
    monkeypatch.setattr(
        pg_ext,
        "try_start_system_postgresql",
        lambda _port: calls.append("system") or False,
    )

    assert pg_ext.ensure_local_external_postgresql(config) is True
    assert calls == ["system", "all"]
