"""Tests for PG merge incremental dedup and analyze preview."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from services.admin import pg_merge_table_ops
from services.admin.pg_merge_table_ops import merge_table, preview_table

_TS = datetime(2026, 1, 15, 12, 0, 0)
_TS2 = datetime(2026, 1, 16, 12, 0, 0)


@pytest.fixture(name="nullable_fk_patch")
def _nullable_fk_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite lacks PostgreSQL information_schema ANY(); treat FK cols as nullable."""
    monkeypatch.setattr(
        pg_merge_table_ops,
        "_fetch_nullable_fk_cols",
        lambda _engine, _table, fk_columns: set(fk_columns),
    )


def _create_merge_tables(engine: Engine) -> None:
    ddl = """
    CREATE TABLE organizations (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(200) NOT NULL
    );
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        phone VARCHAR(64) UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(30) NOT NULL DEFAULT 'teacher'
    );
    CREATE TABLE token_usage (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        organization_id INTEGER,
        api_key_id INTEGER,
        session_id VARCHAR(100),
        conversation_id VARCHAR(100),
        model_provider VARCHAR(50),
        model_name VARCHAR(100),
        model_alias VARCHAR(50),
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        input_cost REAL DEFAULT 0.0,
        output_cost REAL DEFAULT 0.0,
        total_cost REAL DEFAULT 0.0,
        request_type VARCHAR(50),
        diagram_type VARCHAR(50),
        endpoint_path VARCHAR(200),
        success BOOLEAN DEFAULT 1,
        response_time REAL,
        created_at DATETIME NOT NULL
    );
    CREATE TABLE update_notifications (
        id INTEGER PRIMARY KEY,
        enabled BOOLEAN DEFAULT 0,
        version VARCHAR(50) DEFAULT '',
        title VARCHAR(200) DEFAULT '',
        message VARCHAR(10000) DEFAULT '',
        start_date DATETIME,
        end_date DATETIME,
        organization_id INTEGER,
        updated_at DATETIME
    );
    """
    with engine.begin() as conn:
        for statement in ddl.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))


@pytest.fixture(name="live_engine")
def _live_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_merge_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO organizations (id, code, name) VALUES (1, 'org-a', 'Org A')"))
        conn.execute(
            text("INSERT INTO users (id, phone, password_hash, role) VALUES (1, '10000000001', 'hash', 'teacher')")
        )
        conn.execute(
            text(
                "INSERT INTO token_usage "
                "(id, user_id, session_id, created_at, total_tokens) "
                "VALUES (5, 1, 'sess-dup', :ts, 100)"
            ),
            {"ts": _TS},
        )
        conn.execute(
            text(
                "INSERT INTO update_notifications "
                "(id, enabled, version, title, message, updated_at) "
                "VALUES (1, 1, '1.0.0', 'Live', 'Already live', :ts)"
            ),
            {"ts": _TS},
        )
    return engine


@pytest.fixture(name="staging_engine")
def _staging_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_merge_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO organizations (id, code, name) VALUES (1, 'org-a', 'Org A')"))
        conn.execute(
            text("INSERT INTO users (id, phone, password_hash, role) VALUES (1, '10000000001', 'hash', 'teacher')")
        )
        conn.execute(
            text(
                "INSERT INTO token_usage "
                "(id, user_id, session_id, created_at, total_tokens) "
                "VALUES (10, 1, 'sess-dup', :ts, 100), "
                "(11, 1, 'sess-new', :ts2, 50)"
            ),
            {"ts": _TS, "ts2": _TS2},
        )
        conn.execute(
            text(
                "INSERT INTO update_notifications "
                "(id, enabled, version, title, message, updated_at) "
                "VALUES (1, 1, '1.0.0', 'Staging dup', 'Dup', :ts), "
                "(2, 1, '2.0.0', 'Staging new', 'New', :ts2)"
            ),
            {"ts": _TS, "ts2": _TS2},
        )
    return engine


def _base_id_maps() -> dict[str, dict[int, int]]:
    return {
        "organizations": {1: 1},
        "users": {1: 1},
    }


@pytest.mark.usefixtures("nullable_fk_patch")
def test_token_usage_preview_counts(
    live_engine: Engine,
    staging_engine: Engine,
) -> None:
    """Preview counts new, duplicate, and orphaned token_usage rows."""
    id_maps = _base_id_maps()
    preview = preview_table("token_usage", staging_engine, live_engine, id_maps)
    assert preview == {"new_rows": 1, "duplicate_rows": 1, "orphaned_rows": 0}


@pytest.fixture(name="orm_row_patch")
def _orm_row_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite returns DATETIME as str; PostgreSQL staging restores real datetimes."""
    original = getattr(pg_merge_table_ops, "_row_for_orm_table")

    def _coerce_datetimes(table, values):
        row = original(table, values)
        for key, val in list(row.items()):
            if isinstance(val, str) and key.endswith("_at"):
                try:
                    row[key] = datetime.fromisoformat(val.replace("Z", "+00:00"))
                except ValueError:
                    pass
        return row

    monkeypatch.setattr(pg_merge_table_ops, "_row_for_orm_table", _coerce_datetimes)


@pytest.mark.usefixtures("nullable_fk_patch", "orm_row_patch")
def test_token_usage_merge_is_idempotent(
    live_engine: Engine,
    staging_engine: Engine,
) -> None:
    """Second merge pass skips rows already inserted from staging."""
    id_maps = _base_id_maps()
    first = merge_table("token_usage", staging_engine, live_engine, id_maps)
    assert first["inserted"] == 1
    assert first["skipped"] == 1
    assert first["orphaned"] == 0

    with live_engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM token_usage")).scalar()
    assert count == 2

    id_maps_second = _base_id_maps()
    second = merge_table("token_usage", staging_engine, live_engine, id_maps_second)
    assert second["inserted"] == 0
    assert second["skipped"] == 2

    with live_engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM token_usage")).scalar()
    assert count == 2


@pytest.mark.usefixtures("nullable_fk_patch")
def test_update_notifications_preserve_pk_skips_conflicts(
    live_engine: Engine,
    staging_engine: Engine,
) -> None:
    """Conflicting update_notifications primary keys are skipped, not overwritten."""
    id_maps = _base_id_maps()
    result = merge_table("update_notifications", staging_engine, live_engine, id_maps)
    assert result["inserted"] == 1
    assert result["skipped"] == 1

    with live_engine.connect() as conn:
        rows = conn.execute(text("SELECT id, title FROM update_notifications ORDER BY id")).fetchall()
    assert rows == [(1, "Live"), (2, "Staging new")]
