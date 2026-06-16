"""Tests for ``db_rls`` loader helpers (no live PostgreSQL)."""

from __future__ import annotations

from pathlib import Path

from utils.db import alembic_migration

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_db_rls_package_exists():
    path = _PROJECT_ROOT / "db_rls" / "policy_builder.py"
    assert path.is_file()


def test_load_rls_policy_builder_exposes_device_expr():
    builder = alembic_migration.load_rls_policy_builder()
    assert hasattr(builder, "DEVICE_EXPR")
    assert "student_id" in builder.DEVICE_EXPR
