"""Tests for PostgreSQL dependency installation checks."""

from pathlib import Path

import pytest

from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig
from services.infrastructure.utils import dependency_checker as deps


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


def test_connect_only_accepts_system_cluster_without_initdb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(deps, "load_postgres_runtime_config", _connect_only_config)
    monkeypatch.setattr(
        deps,
        "find_system_postgresql_cluster",
        lambda port=None: (Path("/var/lib/postgresql/18/main"), "18"),
    )
    ok, message = deps.check_postgresql_installed()
    assert ok is True
    assert "connect only" in message


def test_connect_only_remote_requires_client_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        deps,
        "load_postgres_runtime_config",
        lambda: PostgresRuntimeConfig(
            database_url="postgresql://mindgraph_app:p@db.example.com:5432/mindgraph",
            host="db.example.com",
            port=5432,
            port_str="5432",
            database="mindgraph",
            runtime_user="mindgraph_app",
            provision_user="mindgraph_user",
            provision_password="p",
            spawn_subprocess=False,
            is_local=False,
        ),
    )
    monkeypatch.setattr(deps, "find_system_postgresql_cluster", lambda port=None: None)
    ok, message = deps.check_postgresql_installed()
    assert ok is True
    assert "remote" in message.lower()
