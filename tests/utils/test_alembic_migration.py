"""Tests for Alembic RLS module loader (no live PostgreSQL)."""

from __future__ import annotations

from pathlib import Path

from utils.db import alembic_migration

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_migration_support_file_lives_under_alembic():
    path = _PROJECT_ROOT / "alembic" / "migration_support.py"
    assert path.is_file()


def test_load_rls_policy_builder_exposes_device_expr():
    builder = alembic_migration.load_rls_policy_builder()
    assert hasattr(builder, "DEVICE_EXPR")
    assert "student_id" in builder.DEVICE_EXPR
