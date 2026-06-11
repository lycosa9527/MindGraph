"""Tests for RLS bootstrap psql connection targeting (no live PostgreSQL)."""

from __future__ import annotations

import pytest

from scripts.db import rls_roles_bootstrap as bootstrap


@pytest.fixture(autouse=True)
def _clear_db_env(monkeypatch):
    for key in (
        "DATABASE_URL",
        "POSTGRESQL_PORT",
        "POSTGRESQL_DATA_DIR",
        "PG_ADMIN_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_psql_tcp_host_port_normalises_localhost(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:secret@localhost:5433/mindgraph",
    )
    host, port = bootstrap._psql_tcp_host_port()
    assert host == "127.0.0.1"
    assert port == "5433"


def test_psql_peer_auth_args_prefers_unix_socket():
    peer = bootstrap._psql_peer_auth_args()
    assert peer[0] == []


def test_psql_tcp_connection_args_includes_managed_socket(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:secret@127.0.0.1:5432/mindgraph",
    )
    data_dir = tmp_path / "pgdata"
    socket_dir = data_dir / "sockets"
    socket_dir.mkdir(parents=True)
    monkeypatch.setenv("POSTGRESQL_DATA_DIR", str(data_dir))

    arg_lists = bootstrap._psql_tcp_connection_args()
    assert arg_lists[0] == ["-h", "127.0.0.1", "-p", "5432"]
    assert arg_lists[1] == ["-h", str(socket_dir.resolve())]


def test_psql_host_connection_args_peer_before_tcp(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:secret@127.0.0.1:5432/mindgraph",
    )
    combined = bootstrap._psql_host_connection_args()
    assert combined[0] == []
    assert ["-h", "127.0.0.1", "-p", "5432"] in combined
