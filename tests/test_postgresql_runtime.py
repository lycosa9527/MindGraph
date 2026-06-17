"""Tests for PostgreSQL runtime configuration from .env."""

import pytest

from scripts.db.migration_urls import ROLE_APP, ROLE_LEGACY
from services.infrastructure.process._postgresql_runtime import (
    PostgresRuntimeConfig,
    load_postgres_runtime_config,
)


def test_rls_runtime_user_is_connect_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_app:mindgraph_password@localhost:5432/mindgraph",
    )
    config = load_postgres_runtime_config()
    assert config.runtime_user == ROLE_APP
    assert config.spawn_subprocess is False
    assert config.is_local is True
    assert config.uses_rls_runtime_role is True
    assert "connect only" in config.mode_label


def test_legacy_user_allows_app_managed_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:mindgraph_password@localhost:5432/mindgraph",
    )
    monkeypatch.setenv("POSTGRESQL_MANAGED_BY_APP", "true")
    config = load_postgres_runtime_config()
    assert config.runtime_user == ROLE_LEGACY
    assert config.spawn_subprocess is True
    assert "subprocess" in config.mode_label


def test_managed_false_disables_spawn_even_for_legacy_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:mindgraph_password@localhost:5432/mindgraph",
    )
    monkeypatch.setenv("POSTGRESQL_MANAGED_BY_APP", "false")
    config = load_postgres_runtime_config()
    assert config.spawn_subprocess is False


def test_remote_host_is_external(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_app:secret@db.example.com:5432/mindgraph",
    )
    config = load_postgres_runtime_config()
    assert config.is_local is False
    assert config.spawn_subprocess is False
    assert config.host == "db.example.com"


def test_postgresql_port_env_overrides_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://mindgraph_app:secret@localhost:5432/mindgraph",
    )
    monkeypatch.setenv("POSTGRESQL_PORT", "5433")
    config = load_postgres_runtime_config()
    assert config.port == 5433


def test_connection_probe_host_normalises_localhost() -> None:
    config = PostgresRuntimeConfig(
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
    assert config.connection_probe_host == "127.0.0.1"
