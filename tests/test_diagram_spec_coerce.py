"""Tests for JSONB spec unwrap of leftover string scalars."""

from __future__ import annotations

import json

from services.diagram.spec_coerce import coerce_diagram_spec


def test_coerce_dict_passthrough() -> None:
    """Test coerce dict passthrough."""
    spec = {"nodes": [{"id": "topic"}]}
    assert coerce_diagram_spec(spec) is spec


def test_coerce_json_string_scalar() -> None:
    """Leftover full-flush stored dumps() as a JSON string."""
    inner = {"nodes": [{"id": "topic"}], "type": "mind_map"}
    assert coerce_diagram_spec(json.dumps(inner)) == inner


def test_coerce_bytes_json_string() -> None:
    """Test coerce bytes json string."""
    inner = {"connections": []}
    assert coerce_diagram_spec(json.dumps(inner).encode("utf-8")) == inner


def test_coerce_invalid_and_non_object() -> None:
    """Test coerce invalid and non object."""
    assert coerce_diagram_spec(None) == {}
    assert coerce_diagram_spec("") == {}
    assert coerce_diagram_spec("not-json") == {}
    assert coerce_diagram_spec("[1, 2]") == {}
    assert coerce_diagram_spec(12) == {}
