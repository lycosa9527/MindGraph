"""Tests for connect-only PostgreSQL external startup helpers."""

from pathlib import Path

import pytest

from services.infrastructure.process import _postgresql_external as pg_ext
from services.infrastructure.process import _postgresql_paths as pg_paths
from services.infrastructure.process._postgresql_cluster_choice import ClusterChoice
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
    monkeypatch.setattr(pg_ext, "_find_pg_ctl_binary", lambda data_path=None: "/usr/bin/pg_ctl")
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

    monkeypatch.setattr(pg_ext, "use_persistent_mindgraph_cluster", lambda config: None)
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

    monkeypatch.setattr(pg_ext, "use_persistent_mindgraph_cluster", lambda config: None)
    monkeypatch.setattr(pg_ext, "postgresql_accepts_connections", lambda host, port: False)
    monkeypatch.setattr(pg_ext, "discover_ranked_cluster_details", lambda cfg: [unverified])

    def _ranked_start(items: list[RankedCluster], _port: int) -> bool:
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


def _mindgraph_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "mindgraph"
    data_dir.mkdir()
    (data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    (data_dir / "postgresql.conf").write_text("port = 5432\n", encoding="utf-8")
    return data_dir


def _patch_finish(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pg_ext, "_disable_competing_distro_cluster", lambda port, mindgraph: None)
    monkeypatch.setattr(pg_ext, "try_database_url_connect", lambda config, timeout=2: True)
    monkeypatch.setattr(pg_ext, "publish_cluster_env", lambda path: "unchanged")
    monkeypatch.setattr(pg_ext, "announce_cluster_choice", lambda config, choice, env_status: None)


def _choice(path: Path | None) -> ClusterChoice:
    return ClusterChoice(path=path, on_port=())


def test_use_persistent_returns_none_without_data_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Machines without a MindGraph data directory keep the normal startup path."""
    monkeypatch.setattr(pg_ext, "choose_cluster", lambda config: _choice(None))
    assert pg_ext.use_persistent_mindgraph_cluster(_connect_only_config()) is None


def test_use_persistent_keeps_listener_that_is_already_mindgraph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A postmaster already using the MindGraph data directory is left running."""
    data_dir = _mindgraph_dir(tmp_path)
    released: list[Path] = []
    monkeypatch.setattr(pg_ext, "choose_cluster", lambda config: _choice(data_dir))
    monkeypatch.setattr(pg_ext, "check_port_in_use", lambda host, port: (True, 1283))
    monkeypatch.setattr(pg_ext, "cluster_postmaster_pid", lambda path: None)
    monkeypatch.setattr(pg_ext, "postmaster_data_directory", lambda pid: data_dir)
    monkeypatch.setattr(
        pg_ext,
        "_release_foreign_cluster",
        lambda host, port, path: released.append(path) or True,
    )
    _patch_finish(monkeypatch)

    assert pg_ext.use_persistent_mindgraph_cluster(_connect_only_config()) is True
    assert not released


def test_use_persistent_stops_distro_cluster_then_starts_mindgraph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Port 5432 held by 18/main is released before the MindGraph cluster starts."""
    data_dir = _mindgraph_dir(tmp_path)
    foreign = Path("/var/lib/postgresql/18/main")
    commands: list[list[str]] = []
    started: list[Path] = []
    monkeypatch.delenv("POSTGRESQL_DATA_DIR", raising=False)
    monkeypatch.setattr(pg_ext, "choose_cluster", lambda config: _choice(data_dir))
    monkeypatch.setattr(pg_ext, "publish_cluster_env", lambda path: "updated")
    monkeypatch.setattr(pg_ext, "announce_cluster_choice", lambda config, choice, env_status: None)
    monkeypatch.setattr(pg_ext, "check_port_in_use", lambda host, port: (True, 1283))
    monkeypatch.setattr(pg_ext, "cluster_postmaster_pid", lambda path: None)
    monkeypatch.setattr(pg_ext, "postmaster_data_directory", lambda pid: foreign)
    monkeypatch.setattr(pg_ext, "find_system_postgresql_cluster", lambda port=None: None)
    monkeypatch.setattr(pg_ext, "_run_root", lambda cmd, timeout=60: commands.append(list(cmd)) or True)
    monkeypatch.setattr(pg_ext, "_wait_until_port_free", lambda host, port, attempts=15: True)
    monkeypatch.setattr(
        pg_ext,
        "try_start_persistent_cluster",
        lambda path, port: started.append(path) or True,
    )
    monkeypatch.setattr(pg_ext, "try_database_url_connect", lambda config, timeout=2: True)

    assert pg_ext.use_persistent_mindgraph_cluster(_connect_only_config()) is True
    assert commands == [
        ["systemctl", "disable", "--now", "postgresql@18-main"],
    ]
    assert started == [data_dir]


def test_use_persistent_keeps_env_cluster_when_port_is_already_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mindgraph directory already named in .env is kept when port 5432 accepts connections."""
    data_dir = _mindgraph_dir(tmp_path)
    released: list[Path] = []
    monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(data_dir))
    monkeypatch.setattr(pg_ext, "choose_cluster", lambda config: _choice(data_dir))
    monkeypatch.setattr(pg_ext, "publish_cluster_env", lambda path: "unchanged")
    monkeypatch.setattr(pg_ext, "announce_cluster_choice", lambda config, choice, env_status: None)
    monkeypatch.setattr(pg_ext, "check_port_in_use", lambda host, port: (True, None))
    monkeypatch.setattr(pg_ext, "cluster_postmaster_pid", lambda path: None)
    monkeypatch.setattr(pg_ext, "postmaster_data_directory", lambda pid: None)
    monkeypatch.setattr(pg_ext, "postgresql_accepts_connections", lambda host, port: True)
    monkeypatch.setattr(pg_ext, "try_database_url_connect", lambda config, timeout=2: True)
    monkeypatch.setattr(
        pg_ext,
        "_release_foreign_cluster",
        lambda host, port, path: released.append(path) or True,
    )

    assert pg_ext.use_persistent_mindgraph_cluster(_connect_only_config()) is True
    assert not released


def test_use_persistent_does_not_wait_when_sudo_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused sudo returns at once instead of sleeping until the port check times out."""
    data_dir = _mindgraph_dir(tmp_path)
    waits: list[int] = []
    monkeypatch.delenv("POSTGRESQL_DATA_DIR", raising=False)
    monkeypatch.setattr(pg_ext, "choose_cluster", lambda config: _choice(data_dir))
    monkeypatch.setattr(pg_ext, "publish_cluster_env", lambda path: "updated")
    monkeypatch.setattr(pg_ext, "announce_cluster_choice", lambda config, choice, env_status: None)
    monkeypatch.setattr(pg_ext, "check_port_in_use", lambda host, port: (True, 1283))
    monkeypatch.setattr(pg_ext, "cluster_postmaster_pid", lambda path: None)
    monkeypatch.setattr(pg_ext, "postmaster_data_directory", lambda pid: Path("/var/lib/postgresql/18/main"))
    monkeypatch.setattr(pg_ext, "_run_root", lambda cmd, timeout=60: False)
    monkeypatch.setattr(
        pg_ext,
        "_wait_until_port_free",
        lambda host, port, attempts=15: waits.append(attempts) or False,
    )

    assert pg_ext.use_persistent_mindgraph_cluster(_connect_only_config()) is False
    assert waits == [1]


def test_use_persistent_reports_failure_when_port_stays_busy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup fails when the distro cluster cannot be moved off the MindGraph port."""
    data_dir = _mindgraph_dir(tmp_path)
    monkeypatch.delenv("POSTGRESQL_DATA_DIR", raising=False)
    monkeypatch.setattr(pg_ext, "choose_cluster", lambda config: _choice(data_dir))
    monkeypatch.setattr(pg_ext, "publish_cluster_env", lambda path: "updated")
    monkeypatch.setattr(pg_ext, "announce_cluster_choice", lambda config, choice, env_status: None)
    monkeypatch.setattr(pg_ext, "check_port_in_use", lambda host, port: (True, 1283))
    monkeypatch.setattr(pg_ext, "cluster_postmaster_pid", lambda path: None)
    monkeypatch.setattr(
        pg_ext,
        "postmaster_data_directory",
        lambda pid: Path("/var/lib/postgresql/18/main"),
    )
    monkeypatch.setattr(pg_ext, "_release_foreign_cluster", lambda host, port, path: False)
    monkeypatch.setattr(pg_ext, "try_start_persistent_cluster", lambda path, port: True)

    assert pg_ext.use_persistent_mindgraph_cluster(_connect_only_config()) is False
