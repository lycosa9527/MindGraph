"""Tests for RLS migration URL resolution (no live PostgreSQL)."""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.engine import Engine, make_url

from scripts.db import migration_urls as urls


@pytest.fixture(autouse=True)
def _clear_db_env(monkeypatch):
    """Clear db env."""
    for key in (
        "DATABASE_URL",
        "DATABASE_MIGRATION_URL",
        "PG_ADMIN_URL",
        "MINDGRAPH_APP_PASSWORD",
        "MINDGRAPH_MIGRATE_PASSWORD",
        "POSTGRESQL_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)


def test_runtime_app_skips_app_in_migration_candidates(monkeypatch):
    """Test runtime app skips app in migration candidates."""
    runtime = "postgresql://mindgraph_app:secret@localhost:5432/mindgraph"
    monkeypatch.setenv("DATABASE_URL", runtime)
    candidates = urls.migration_url_candidates(runtime)
    users = [make_url(url).username or "" for url, _ in candidates]
    assert urls.ROLE_APP not in users
    assert urls.ROLE_MIGRATE in users
    assert urls.ROLE_LEGACY in users


def test_explicit_migration_url_app_is_ignored(monkeypatch):
    """Test explicit migration url app is ignored."""
    runtime = "postgresql://mindgraph_app:secret@localhost:5432/mindgraph"
    monkeypatch.setenv("DATABASE_URL", runtime)
    monkeypatch.setenv(
        "DATABASE_MIGRATION_URL",
        "postgresql://mindgraph_app:secret@localhost:5432/mindgraph",
    )
    candidates = urls.migration_url_candidates(runtime)
    users = [make_url(url).username or "" for url, _ in candidates]
    assert users.count(urls.ROLE_APP) == 0


def test_url_for_dotenv_strips_driver_suffix():
    """Test url for dotenv strips driver suffix."""
    raw = "postgresql+psycopg://mindgraph_user:pw@localhost:5432/mindgraph"
    assert urls.url_for_dotenv(raw) == "postgresql://mindgraph_user:pw@localhost:5432/mindgraph"


def test_build_role_url_rejects_masked_password(monkeypatch):
    """Test build role url rejects masked password."""
    runtime = "postgresql://mindgraph_app:****@localhost:5432/mindgraph"
    monkeypatch.setenv("DATABASE_URL", runtime)
    app_url = urls.url_for_dotenv(urls.build_role_url(runtime, urls.ROLE_APP))
    assert "mindgraph_password" in app_url
    assert "****" not in app_url
    assert "://mindgraph_app:" in app_url


def test_env_rls_database_urls_match(tmp_path, monkeypatch):
    """Test env rls database urls match."""
    runtime = "postgresql://mindgraph_app:secret@localhost:5432/mindgraph"
    monkeypatch.setenv("DATABASE_URL", runtime)
    monkeypatch.setenv("MINDGRAPH_APP_PASSWORD", "secret")
    monkeypatch.setenv("MINDGRAPH_MIGRATE_PASSWORD", "secret")

    class FakeEngine:
        """Minimal SQLAlchemy engine stand-in for dialect checks."""

        dialect = type("D", (), {"name": "postgresql"})()

    env_path = tmp_path / ".env"
    app_url = urls.url_for_dotenv(urls.build_role_url(runtime, urls.ROLE_APP))
    migrate_url = urls.url_for_dotenv(urls.build_role_url(runtime, urls.ROLE_MIGRATE))
    env_path.write_text(
        f"DATABASE_URL={app_url}\nDATABASE_MIGRATION_URL={migrate_url}\n",
        encoding="utf-8",
    )

    def fake_role_exists(_engine, role: str) -> bool:
        return role in (urls.ROLE_APP, urls.ROLE_MIGRATE)

    monkeypatch.setattr(urls, "_role_exists", fake_role_exists)
    assert urls.env_rls_database_urls_match(env_path, cast(Engine, FakeEngine()))


def test_env_rls_database_urls_mismatch(tmp_path, monkeypatch):
    """Test env rls database urls mismatch."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://mindgraph_app:secret@localhost:5432/mindgraph")
    env_path = tmp_path / ".env"
    env_path.write_text(
        "DATABASE_URL=postgresql://mindgraph_user:old@localhost:5432/mindgraph\n",
        encoding="utf-8",
    )

    class FakeEngine:
        """Minimal SQLAlchemy engine stand-in for dialect checks."""

        dialect = type("D", (), {"name": "postgresql"})()

    monkeypatch.setattr(urls, "_role_exists", lambda _e, role: role == urls.ROLE_APP)
    assert not urls.env_rls_database_urls_match(env_path, cast(Engine, FakeEngine()))


def test_apply_env_database_patches_inserts_migration_url_after_database_url():
    """Test apply env database patches inserts migration url after database url."""
    lines = ["DATABASE_URL=postgresql://old\n", "REDIS_URL=redis://localhost\n"]
    patched = urls.apply_env_database_patches(
        lines,
        {
            "DATABASE_URL": "postgresql://mindgraph_app:secret@localhost:5432/mindgraph",
            "DATABASE_MIGRATION_URL": ("postgresql://mindgraph_migrate:secret@localhost:5432/mindgraph"),
        },
    )
    text = "".join(patched)
    assert "DATABASE_URL=postgresql://mindgraph_app:secret@localhost:5432/mindgraph" in text
    assert "DATABASE_MIGRATION_URL=postgresql://mindgraph_migrate:secret" in text
    db_idx = text.index("DATABASE_URL=")
    mig_idx = text.index("DATABASE_MIGRATION_URL=")
    redis_idx = text.index("REDIS_URL=")
    assert db_idx < mig_idx < redis_idx
