"""Unit tests for ``parse_json_get_bulk`` RESP3 / redis-py aggregate shapes."""

from __future__ import annotations

import json

import pytest

from services.online_collab.spec.online_collab_live_spec_json import (
    _preview_json_get_raw,
    parse_json_get_bulk,
)


def test_preview_json_get_raw_nil_and_dict_bounded() -> None:
    assert _preview_json_get_raw(None) == "(nil)"
    many = {f"k{i}": i for i in range(15)}
    preview = _preview_json_get_raw(many)
    assert "n=15" in preview
    assert "…" in preview


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, None),
        ([], None),
        ({}, {}),
        ([{}], {}),
        ([{"v": 1, "nodes": []}], {"v": 1, "nodes": []}),
        ('{"v": 2}', {"v": 2}),
        ([json.dumps({"v": 3})], {"v": 3}),
        (b'[{"v": 4}]', {"v": 4}),
        ([[[{"v": 5}]]], {"v": 5}),
        (42, None),
        ("", None),
        ("   ", None),
        ("not-json", None),
    ],
)
def test_parse_json_get_bulk_shapes(
    raw: object,
    expected: dict | None,
) -> None:
    assert parse_json_get_bulk(raw) == expected
