"""Tests for PostgreSQL cluster discovery and ranking."""

from pathlib import Path

import pytest

from services.infrastructure.process import _postgresql_discovery as pg_disc
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig


def _connect_only_config(database: str = "mindgraph", port: int = 5432) -> PostgresRuntimeConfig:
    return PostgresRuntimeConfig(
        database_url=f"postgresql://mindgraph_app:p@localhost:{port}/{database}",
        host="localhost",
        port=port,
        port_str=str(port),
        database=database,
        runtime_user="mindgraph_app",
        provision_user="mindgraph_user",
        provision_password="p",
        spawn_subprocess=False,
        is_local=True,
    )


def _init_cluster(path: Path, port: int) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "PG_VERSION").write_text("18\n", encoding="utf-8")
    (path / "postgresql.conf").write_text(f"port = {port}\n", encoding="utf-8")
    base = path / "base"
    base.mkdir()
    (base / "1").mkdir()
    (base / "2").mkdir()
    return path


def test_invalid_database_name_sanitized_before_offline_probe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unsafe database names from config fall back to mindgraph before catalog probes."""
    cluster = _init_cluster(tmp_path / "mindgraph", 5432)
    captured: dict[str, str] = {}

    def _capture(_path: Path, database: str) -> bool:
        captured["database"] = database
        return False

    monkeypatch.setattr(pg_disc, "cluster_postmaster_pid", lambda path: None)
    monkeypatch.setattr(pg_disc, "_offline_cluster_has_database", _capture)

    assert pg_disc.cluster_has_database(cluster, "mindgraph;drop", 5432) is False
    assert captured["database"] == "mindgraph"


def test_scan_root_finds_nested_cluster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Filesystem sweep finds PG_VERSION in nested directories."""
    cluster = _init_cluster(tmp_path / "postgresql" / "mindgraph", 5432)
    monkeypatch.setattr(pg_disc, "_filesystem_scan_roots", lambda: [tmp_path / "postgresql"])
    found = pg_disc.scan_local_cluster_dirs()
    assert cluster.resolve() in found


def test_discover_ranked_clusters_prefers_verified_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Clusters with the configured database rank above unverified paths."""
    generic = _init_cluster(tmp_path / "generic", 5432)
    mindgraph = _init_cluster(tmp_path / "mindgraph", 5432)

    monkeypatch.setattr(pg_disc, "scan_local_cluster_dirs", lambda limit=32: [generic, mindgraph])

    def _has_db(data_path: Path, _database: str, _port: int) -> bool:
        return data_path == mindgraph

    monkeypatch.setattr(pg_disc, "cluster_has_database", _has_db)

    ranked = pg_disc.discover_ranked_clusters(_connect_only_config())
    assert ranked[0] == mindgraph


def test_discover_ranked_clusters_prefers_matching_port(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Clusters listening on DATABASE_URL port outrank other ports."""
    wrong_port = _init_cluster(tmp_path / "wrong", 5433)
    right_port = _init_cluster(tmp_path / "right", 5432)

    monkeypatch.setattr(
        pg_disc,
        "scan_local_cluster_dirs",
        lambda limit=32: [wrong_port, right_port],
    )
    monkeypatch.setattr(pg_disc, "cluster_has_database", lambda *args, **kwargs: False)

    ranked = pg_disc.discover_ranked_clusters(_connect_only_config())
    assert ranked[0] == right_port


def test_cluster_has_database_probes_stopped_cluster_while_port_is_busy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A stopped data directory is still checked when a different postmaster holds the port."""
    cluster = _init_cluster(tmp_path / "mindgraph", 5432)
    monkeypatch.setattr(pg_disc, "cluster_postmaster_pid", lambda path: None)
    monkeypatch.setattr(pg_disc, "_offline_cluster_has_database", lambda *args, **kwargs: True)

    assert pg_disc.cluster_has_database(cluster, "mindgraph", 5432) is True


def test_cluster_has_database_uses_running_cluster_pid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When this cluster is running, verify the database via a live catalog query."""
    cluster = _init_cluster(tmp_path / "mindgraph", 5432)
    monkeypatch.setattr(pg_disc, "cluster_postmaster_pid", lambda path: 12345)
    monkeypatch.setattr(pg_disc, "postmaster_data_directory", lambda pid: None)
    monkeypatch.setattr(pg_disc, "_database_exists_on_running_server", lambda host, port, db: db == "mindgraph")

    assert pg_disc.cluster_has_database(cluster, "mindgraph", 5432) is True


def test_scan_local_cluster_dirs_uses_configured_data_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """POSTGRESQL_DATA_DIR is included in the sweep roots."""
    cluster = _init_cluster(tmp_path / "data", 5432)
    monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(cluster))
    monkeypatch.setattr(pg_disc, "_filesystem_scan_roots", lambda: [cluster])

    found = pg_disc.scan_local_cluster_dirs()
    assert cluster.resolve() in found


def test_offline_probe_reads_postgresql_18_single_user_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """PostgreSQL 18 single-user mode reports a hit without the old ``(1 row)`` footer."""
    cluster = _init_cluster(tmp_path / "mindgraph", 5432)
    monkeypatch.setattr(pg_disc, "cluster_postmaster_pid", lambda path: None)
    monkeypatch.setattr(pg_disc, "postgres_binary_for_cluster", lambda path: "/usr/lib/postgresql/18/bin/postgres")

    class _Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    outputs = iter(
        [
            _Result('backend> \t 1: ?column? = "1"\t(typeid = 23)\n'),
            _Result("backend> \t 1: ?column?\t(typeid = 23)\n\t----\n"),
        ]
    )
    monkeypatch.setattr(pg_disc.subprocess, "run", lambda *args, **kwargs: next(outputs))

    assert pg_disc.cluster_has_database(cluster, "mindgraph", 5432) is True
    assert pg_disc.cluster_has_database(cluster, "mindgraph", 5432) is False


def test_foreign_postmaster_pid_does_not_count_as_this_cluster(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A live pid whose data directory is elsewhere cannot verify an empty cluster."""
    cluster = _init_cluster(tmp_path / "19" / "main", 5432)
    monkeypatch.setattr(pg_disc, "cluster_postmaster_pid", lambda path: 99)
    monkeypatch.setattr(pg_disc, "postmaster_data_directory", lambda pid: Path("/var/lib/postgresql/mindgraph"))
    monkeypatch.setattr(pg_disc, "_database_exists_on_running_server", lambda host, port, db: True)
    monkeypatch.setattr(pg_disc, "_offline_cluster_has_database", lambda path, database: False)

    assert pg_disc.cluster_has_database(cluster, "mindgraph", 5432) is False


def test_mindgraph_directory_is_probed_before_upgrade_mains(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Repeated package upgrades do not consume the probe budget before the data directory."""
    mains = [_init_cluster(tmp_path / str(version) / "main", 5432) for version in range(14, 22)]
    mindgraph = _init_cluster(tmp_path / "mindgraph", 5432)
    probed: list[Path] = []

    def _probe(path: Path, _database: str, _port: int) -> bool:
        probed.append(path)
        return path == mindgraph

    monkeypatch.setattr(pg_disc, "scan_local_cluster_dirs", lambda limit=32: [*mains, mindgraph])
    monkeypatch.setattr(pg_disc, "cluster_has_database", _probe)

    ranked = pg_disc.discover_ranked_clusters(_connect_only_config())
    assert probed[0] == mindgraph
    assert ranked[0] == mindgraph


def test_clusters_on_port_filters_ranked_list(tmp_path: Path) -> None:
    """clusters_on_port keeps only entries configured for the target port."""
    on_port = pg_disc.RankedCluster(path=tmp_path / "a", port=5432, score=1, has_database=True)
    off_port = pg_disc.RankedCluster(path=tmp_path / "b", port=5433, score=1, has_database=False)
    filtered = pg_disc.clusters_on_port([off_port, on_port], 5432)
    assert filtered == [on_port]
