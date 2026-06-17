"""Tests for RLS bootstrap psql connection targeting (no live PostgreSQL)."""

from __future__ import annotations

import pytest

from scripts.db import rls_roles_bootstrap as bootstrap


@pytest.fixture(autouse=True)
def _clear_db_env(monkeypatch):
    """Clear db env."""
    for key in (
        "DATABASE_URL",
        "POSTGRESQL_PORT",
        "POSTGRESQL_DATA_DIR",
        "PG_ADMIN_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_psql_tcp_host_port_normalises_localhost(monkeypatch):
    """Test psql tcp host port normalises localhost."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:secret@localhost:5433/mindgraph",
    )
    host, port = bootstrap.psql_tcp_host_port()
    assert host == "127.0.0.1"
    assert port == "5433"


def test_psql_peer_auth_args_prefers_unix_socket():
    """Test psql peer auth args prefers unix socket."""
    peer = bootstrap.psql_peer_auth_args()
    assert not peer[0]


def test_psql_tcp_connection_args_includes_managed_socket(tmp_path, monkeypatch):
    """Test psql tcp connection args includes managed socket."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:secret@127.0.0.1:5432/mindgraph",
    )
    data_dir = tmp_path / "pgdata"
    socket_dir = data_dir / "sockets"
    socket_dir.mkdir(parents=True)
    monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(data_dir))

    arg_lists = bootstrap.psql_tcp_connection_args()
    assert arg_lists[0] == ["-h", "127.0.0.1", "-p", "5432"]
    assert arg_lists[1] == ["-h", str(socket_dir.resolve())]


def test_psql_host_connection_args_peer_before_tcp(monkeypatch):
    """Test psql host connection args peer before tcp."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:secret@127.0.0.1:5432/mindgraph",
    )
    combined = bootstrap.psql_host_connection_args()
    assert combined[0] == []
    assert ["-h", "127.0.0.1", "-p", "5432"] in combined
