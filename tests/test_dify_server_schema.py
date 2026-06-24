"""Tests for Organization schema-driven Dify server slot discovery."""

from __future__ import annotations

import pytest

from services.dify.dify_server_schema import (
    clear_dify_server_schema_cache,
    organization_dify_server_slots,
    server_slot_field_names,
)

def test_organization_slots_include_legacy_server_one() -> None:
    """Server 1 is discovered from legacy dify_api_* columns."""
    slots = organization_dify_server_slots()
    assert 1 in slots
    assert server_slot_field_names(1) == ("dify_api_base_url", "dify_api_key")


def test_organization_slots_include_server_two() -> None:
    """Server 2 is discovered from paired _2 columns on the model."""
    slots = organization_dify_server_slots()
    assert 2 in slots
    assert server_slot_field_names(2) == ("dify_api_base_url_2", "dify_api_key_2")


def test_unknown_server_has_no_fields() -> None:
    """Slots not present on the model return no field mapping."""
    assert server_slot_field_names(999) is None


def test_extra_slots_discovered_when_columns_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    """New paired columns on Organization are picked up without code changes."""
    clear_dify_server_schema_cache()
    monkeypatch.setattr(
        "services.dify.dify_server_schema._organization_column_names",
        lambda: frozenset(
            {
                "dify_api_base_url",
                "dify_api_key",
                "dify_api_base_url_2",
                "dify_api_key_2",
                "dify_api_base_url_3",
                "dify_api_key_3",
            }
        ),
    )
    organization_dify_server_slots.cache_clear()
    slots = organization_dify_server_slots()
    assert slots == (1, 2, 3)
    assert server_slot_field_names(3) == ("dify_api_base_url_3", "dify_api_key_3")
    clear_dify_server_schema_cache()
