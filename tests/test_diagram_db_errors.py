"""Diagram cache database error message helpers."""

from __future__ import annotations

from services.redis.cache.diagram_save_errors import describe_diagram_db_error


def test_describe_diagram_db_error_maps_rls_violation() -> None:
    exc = RuntimeError('new row violates row-level security policy for table "diagrams"')
    assert describe_diagram_db_error(exc) == "Diagram save blocked by access policy"


def test_describe_diagram_db_error_maps_generic_failure() -> None:
    exc = RuntimeError("connection reset by peer")
    assert describe_diagram_db_error(exc) == "Failed to save diagram to database"


def test_describe_diagram_db_error_maps_null_id_violation() -> None:
    exc = RuntimeError('null value in column "id" of relation "diagrams" violates not-null constraint')
    assert describe_diagram_db_error(exc) == "Failed to assign diagram id"
