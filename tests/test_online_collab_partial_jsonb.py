"""Partial jsonb_set flush SQL must declare :val_nodes for SQLAlchemy text()."""

from __future__ import annotations

import pytest

from services.online_collab.spec.online_collab_partial_jsonb import (
    JSONB_SPEC_AS_OBJECT_SQL,
    build_full_jsonb_flush_statement,
    build_partial_jsonb_flush_statement,
)


def test_nodes_bind_is_visible_to_sqlalchemy_text() -> None:
    """CAST(:val_nodes AS jsonb) — :val_nodes::jsonb is not a bind name."""
    stmt = build_partial_jsonb_flush_statement(frozenset({"nodes"}))
    bound = stmt.bindparams(val_nodes="[]", diagram_id="diag-1")
    compiled = str(bound)
    assert "CAST(:val_nodes AS jsonb)" in compiled
    assert ":val_nodes::jsonb" not in compiled


def test_nodes_and_connections_binds() -> None:
    """Test nodes and connections binds."""
    stmt = build_partial_jsonb_flush_statement(frozenset({"connections", "nodes"}))
    bound = stmt.bindparams(val_nodes="[]", val_connections="[]", diagram_id="diag-1")
    compiled = str(bound)
    assert "CAST(:val_nodes AS jsonb)" in compiled
    assert "CAST(:val_connections AS jsonb)" in compiled


def test_empty_keys_rejected() -> None:
    """Test empty keys rejected."""
    with pytest.raises(ValueError, match="nodes and/or connections"):
        build_partial_jsonb_flush_statement(frozenset({"__full__"}))


def test_partial_unwraps_leftover_string_scalar() -> None:
    """jsonb_set must start from an object, not a leftover JSON string."""
    stmt = build_partial_jsonb_flush_statement(frozenset({"nodes"}))
    compiled = str(stmt)
    assert JSONB_SPEC_AS_OBJECT_SQL in compiled
    assert "jsonb_typeof(spec) = 'string'" in compiled
    assert "COALESCE(spec, '{}'::jsonb)" not in compiled


def test_full_flush_casts_dumped_json_to_object() -> None:
    """ORM JSONB + Python str stored a scalar; CAST parses the dump."""
    stmt = build_full_jsonb_flush_statement()
    bound = stmt.bindparams(p_spec="{}", p_id="diag-1")
    compiled = str(bound)
    assert "CAST(:p_spec AS jsonb)" in compiled
    assert ":p_spec::jsonb" not in compiled
