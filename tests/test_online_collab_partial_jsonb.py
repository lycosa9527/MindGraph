"""Partial jsonb_set flush SQL must declare :val_nodes for SQLAlchemy text()."""

from __future__ import annotations

import pytest

from services.online_collab.spec.online_collab_partial_jsonb import (
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
