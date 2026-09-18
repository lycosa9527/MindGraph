"""Diagram cache database error message helpers."""

from __future__ import annotations

from services.redis.cache.diagram_save_errors import STALE_ACCOUNT_SAVE_ERROR, describe_diagram_db_error


def test_describe_diagram_db_error_maps_rls_violation() -> None:
    """Test describe diagram db error maps rls violation."""
    exc = RuntimeError('new row violates row-level security policy for table "diagrams"')
    assert describe_diagram_db_error(exc) == "Diagram save blocked by access policy"


def test_describe_diagram_db_error_maps_generic_failure() -> None:
    """Test describe diagram db error maps generic failure."""
    exc = RuntimeError("connection reset by peer")
    assert describe_diagram_db_error(exc) == "Failed to save diagram to database"


def test_describe_diagram_db_error_maps_stale_user_fk() -> None:
    """Test describe diagram db error maps stale user fk."""
    exc = RuntimeError('insert or update on table "diagrams" violates foreign key constraint "diagrams_user_id_fkey"')
    assert describe_diagram_db_error(exc) == STALE_ACCOUNT_SAVE_ERROR


def test_describe_diagram_db_error_maps_missing_column() -> None:
    """Test describe diagram db error maps missing column."""
    exc = RuntimeError('关系 "diagrams" 的 "source_channel" 字段不存在')
    assert describe_diagram_db_error(exc) == "Database schema is missing a required diagram column"


def test_describe_diagram_db_error_maps_null_id_violation() -> None:
    """Test describe diagram db error maps null id violation."""
    exc = RuntimeError('null value in column "id" of relation "diagrams" violates not-null constraint')
    assert describe_diagram_db_error(exc) == "Failed to assign diagram id"
