"""Live PostgreSQL checks: an empty upgrade cluster must not hide the data directory.

These tests initdb two temporary clusters and start one postmaster on a free
port. They do not connect to, stop, or rewrite the server on port 5432.
"""

from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path

import pytest

from services.infrastructure.process import _postgresql_discovery as pg_disc
from services.infrastructure.process._postgresql_cluster_choice import choose_cluster
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig

_BIN_DIR = Path("/usr/lib/postgresql/18/bin")
_INITDB = _BIN_DIR / "initdb"
_PG_CTL = _BIN_DIR / "pg_ctl"
_CREATEDB = _BIN_DIR / "createdb"
_PSQL = _BIN_DIR / "psql"
_PG_ISREADY = _BIN_DIR / "pg_isready"

pytestmark = pytest.mark.skipif(
    not _INITDB.is_file() or not _PG_CTL.is_file(),
    reason="PostgreSQL 18 server binaries are not installed",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _init_cluster(path: Path, port: int, socket_dir: Path) -> None:
    socket_dir.mkdir(parents=True, exist_ok=True)
    result = _run(
        [
            str(_INITDB),
            "-D",
            str(path),
            "--no-sync",
            "--locale=C",
            "--encoding=UTF8",
            "--auth=trust",
            "--username=postgres",
        ],
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    with (path / "postgresql.conf").open("a", encoding="utf-8") as conf:
        conf.write(f"\nlisten_addresses = '127.0.0.1'\nport = {port}\n")
        conf.write(f"unix_socket_directories = '{socket_dir}'\n")
    (path / "pg_hba.conf").write_text(
        "local all all trust\nhost all all 127.0.0.1/32 trust\nhost all all ::1/128 trust\n",
        encoding="utf-8",
    )


def _pg_ctl(path: Path, action: str, log_path: Path) -> subprocess.CompletedProcess[str]:
    return _run([str(_PG_CTL), "-D", str(path), "-l", str(log_path), action], timeout=60)


def _wait_ready(port: int) -> None:
    for _ in range(30):
        result = _run([str(_PG_ISREADY), "-h", "127.0.0.1", "-p", str(port), "-t", "1"], timeout=5)
        if result.returncode == 0:
            return
        time.sleep(0.2)
    raise RuntimeError(f"postmaster on port {port} did not accept connections")


def _config(port: int) -> PostgresRuntimeConfig:
    return PostgresRuntimeConfig(
        database_url=f"postgresql://mindgraph_app:p@127.0.0.1:{port}/mindgraph",
        host="127.0.0.1",
        port=port,
        port_str=str(port),
        database="mindgraph",
        runtime_user="mindgraph_app",
        provision_user="mindgraph_user",
        provision_password="p",
        spawn_subprocess=False,
        is_local=True,
    )


def test_live_empty_upgrade_cluster_loses_to_mindgraph_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A running empty <version>/main cluster loses to a stopped directory that has the database."""
    port = _free_port()
    empty = tmp_path / "19" / "main"
    populated = tmp_path / "mindgraph"
    empty_log = tmp_path / "empty.log"
    populated_log = tmp_path / "populated.log"
    _init_cluster(empty, port, tmp_path / "empty-sock")
    _init_cluster(populated, port, tmp_path / "populated-sock")

    started_empty = False
    try:
        start_populated = _pg_ctl(populated, "start", populated_log)
        if start_populated.returncode != 0:
            raise RuntimeError(populated_log.read_text(encoding="utf-8", errors="replace"))
        _wait_ready(port)
        created = _run(
            [str(_CREATEDB), "-h", "127.0.0.1", "-p", str(port), "-U", "postgres", "mindgraph"],
            timeout=30,
        )
        if created.returncode != 0:
            raise RuntimeError(created.stderr or created.stdout)
        inserted = _run(
            [
                str(_PSQL),
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-U",
                "postgres",
                "-d",
                "mindgraph",
                "-c",
                "CREATE TABLE kept (id int); INSERT INTO kept VALUES (1);",
            ],
            timeout=30,
        )
        if inserted.returncode != 0:
            raise RuntimeError(inserted.stderr or inserted.stdout)
        _pg_ctl(populated, "stop", populated_log)

        start_empty = _pg_ctl(empty, "start", empty_log)
        if start_empty.returncode != 0:
            raise RuntimeError(empty_log.read_text(encoding="utf-8", errors="replace"))
        started_empty = True
        _wait_ready(port)

        monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(empty))
        monkeypatch.delenv("MINDGRAPH_ENV_FILE", raising=False)
        monkeypatch.setattr(pg_disc, "_filesystem_scan_roots", lambda: [tmp_path])

        assert pg_disc.cluster_has_database(empty, "mindgraph", port) is False
        assert pg_disc.cluster_has_database(populated, "mindgraph", port) is True

        selected = choose_cluster(_config(port))
        assert selected.path == populated.resolve()
    finally:
        if started_empty:
            _pg_ctl(empty, "stop", empty_log)
        _pg_ctl(populated, "stop", populated_log)
