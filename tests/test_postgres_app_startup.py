"""Tests for post-startup DATABASE_URL verification."""

import pytest

from scripts.db import postgres_app_startup as pg_startup
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig


def test_verify_runtime_database_connection_success(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(pg_startup, "load_postgres_runtime_config", lambda: config)
    monkeypatch.setattr(pg_startup, "try_database_url_connect", lambda _config, timeout=5: True)
    ok, message = pg_startup.verify_runtime_database_connection()
    assert ok is True
    assert "verified" in message


def test_verify_runtime_database_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(pg_startup, "load_postgres_runtime_config", lambda: config)
    monkeypatch.setattr(pg_startup, "try_database_url_connect", lambda _config, timeout=5: False)
    ok, message = pg_startup.verify_runtime_database_connection()
    assert ok is False
    assert "mindgraph_app" in message
