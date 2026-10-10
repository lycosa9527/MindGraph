"""PostgreSQL text/jsonb cannot store U+0000."""

from __future__ import annotations

import json

from psycopg.adapt import PyFormat
from sqlalchemy.dialects.postgresql import JSONB

from config.database import async_engine, engine
from services.diagram.postgres_text import (
    diagram_payload_needs_nul_strip,
    pg_json_dumps,
    strip_postgres_nul,
)


def test_strip_postgres_nul_removes_null_from_nested_spec() -> None:
    """Worksheet baselines used to join lines with U+0000 inside textsById."""
    spec = {
        "type": "mindmap",
        "learning_sheet_baseline": {
            "textsById": {"topic": "浮力是什么\x00buoyancy"},
        },
    }
    cleaned = strip_postgres_nul(spec)
    assert cleaned["learning_sheet_baseline"]["textsById"]["topic"] == "浮力是什么buoyancy"
    assert "\x00" not in str(cleaned)


def test_strip_postgres_nul_keeps_identity_when_clean() -> None:
    """Unchanged payloads stay the same object so callers can skip extra copies."""
    spec = {"topic": "浮力是什么", "nodes": [{"text": "ok"}]}
    assert strip_postgres_nul(spec) is spec
    assert strip_postgres_nul("浮力是什么") == "浮力是什么"


def test_clean_diagram_json_skips_the_spec_walk() -> None:
    """The size-check text is enough to leave a clean spec untouched."""
    spec = {"topic": "浮力是什么", "nodes": [{"text": "ok"}]}
    assert diagram_payload_needs_nul_strip("浮力", json.dumps(spec), None) is False


def test_nul_in_spec_json_requests_a_strip_and_literal_text_is_unchanged() -> None:
    """A real null must be stripped. A typed backslash-u sequence is not one."""
    dirty = {"topic": "浮力\x00"}
    literal = {"literal": "\\u0000"}
    assert diagram_payload_needs_nul_strip("浮力", json.dumps(dirty), None) is True
    assert diagram_payload_needs_nul_strip("浮力", json.dumps(literal), None) is True
    assert strip_postgres_nul(literal) is literal


def test_strip_postgres_nul_cleans_title_string() -> None:
    """VARCHAR title columns reject U+0000 the same way jsonb does."""
    assert strip_postgres_nul("浮力是什么\x00") == "浮力是什么"


def test_pg_json_dumps_matches_json_dumps_when_clean() -> None:
    """A clean spec takes the same encoded text ``json.dumps`` would produce."""
    spec = {"topic": "浮力是什么", "nodes": [{"text": "ok"}]}
    assert pg_json_dumps(spec) == json.dumps(spec)
    assert pg_json_dumps(spec, ensure_ascii=False) == json.dumps(spec, ensure_ascii=False)


def test_pg_json_dumps_drops_nul_beside_a_literal_escape() -> None:
    """A null next to a typed backslash-u sequence drops only the null."""
    dumped = pg_json_dumps({"c": "x\x00y\\u0000z", "slash_nul": "\\\x00"})
    assert json.loads(dumped) == {"c": "xy\\u0000z", "slash_nul": "\\"}


def test_pg_json_dumps_drops_real_nul_and_keeps_literal_backslash_u() -> None:
    """A literal backslash-u sequence in user text must survive the serializer."""
    dumped = pg_json_dumps({"topic": "浮力是什么\x00", "literal": "\\u0000"})
    assert json.loads(dumped) == {"topic": "浮力是什么", "literal": "\\u0000"}
    assert "\x00" not in dumped


def test_app_engines_serialize_json_without_nul() -> None:
    """Sync and async engines both use the null-stripping JSON serializer."""
    for target in (engine, async_engine.sync_engine):
        _args, connect_params = target.dialect.create_connect_args(target.url)
        context = connect_params["context"]
        wrapped = JSONB().bind_processor(target.dialect)({"topic": "浮力\x00"})
        dumper_cls = context.adapters.get_dumper(type(wrapped), PyFormat.TEXT)
        raw = dumper_cls(type(wrapped), context).dump(wrapped)
        loaded = json.loads(bytes(raw).decode())
        assert loaded["topic"] == "浮力"
