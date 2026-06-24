"""Tests for the pure dual Dify server credential helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from models.domain.auth import Organization
from services.dify.dify_server_schema import clear_dify_server_schema_cache, organization_dify_server_slots
from services.dify.dify_servers import (
    configured_dify_servers,
    failover_enabled,
    failover_partner_server,
    org_eligible_for_failover_probing,
    org_server_credentials,
    primary_server_no,
    standby_server_no,
)


def _org(**kwargs: object) -> Organization:
    """Build a duck-typed organization stand-in for the getattr-based helpers."""
    defaults = {
        "id": 1,
        "dify_api_base_url": None,
        "dify_api_key": None,
        "dify_api_base_url_2": None,
        "dify_api_key_2": None,
        "dify_api_base_url_3": None,
        "dify_api_key_3": None,
        "dify_active_server": 1,
        "dify_failover_enabled": True,
    }
    defaults.update(kwargs)
    return cast(Organization, SimpleNamespace(**defaults))


def test_server1_credentials_returned_when_both_set() -> None:
    """Server 1 creds resolve from the legacy columns when both are present."""
    org = _org(dify_api_base_url="https://s1/v1", dify_api_key="key1")
    assert org_server_credentials(org, 1) == ("key1", "https://s1/v1")


def test_server2_credentials_returned_when_both_set() -> None:
    """Server 2 creds resolve from the _2 columns."""
    org = _org(dify_api_base_url_2="https://s2/v1", dify_api_key_2="key2")
    assert org_server_credentials(org, 2) == ("key2", "https://s2/v1")


def test_server3_credentials_when_schema_slot_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Server 3 works once the Organization model exposes paired _3 columns."""
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
    org = _org(dify_api_base_url_3="https://s3/v1", dify_api_key_3="key3")
    assert org_server_credentials(org, 3) == ("key3", "https://s3/v1")
    clear_dify_server_schema_cache()


def test_credentials_none_when_partial() -> None:
    """A URL without a key (or vice-versa) yields no credentials."""
    org = _org(dify_api_base_url="https://s1/v1")
    assert org_server_credentials(org, 1) is None


def test_invalid_server_number_returns_none() -> None:
    """Server numbers absent from the schema return no credentials."""
    assert org_server_credentials(_org(), 999) is None


def test_primary_server_defaults_and_clamps() -> None:
    """Active-server selector defaults to 1 and clamps invalid values."""
    assert primary_server_no(_org(dify_active_server=2)) == 2
    assert primary_server_no(_org(dify_active_server=9)) == 1
    assert primary_server_no(_org(dify_active_server="bad")) == 1


def test_standby_is_the_other_server() -> None:
    """Standby is always the opposite of the primary."""
    assert standby_server_no(1) == 2
    assert standby_server_no(2) == 1


def test_failover_enabled_reads_flag() -> None:
    """Failover flag is read straight from the org (defaults True)."""
    assert failover_enabled(_org(dify_failover_enabled=False)) is False
    assert failover_enabled(_org()) is True


def test_configured_servers_lists_only_complete_pairs_in_order() -> None:
    """Only fully-configured servers are returned, ordered by number."""
    org = _org(
        dify_api_base_url="https://s1/v1",
        dify_api_key="key1",
        dify_api_base_url_2="https://s2/v1",
        dify_api_key_2="key2",
    )
    servers = configured_dify_servers(org)
    assert [s.server for s in servers] == [1, 2]
    assert servers[0].api_url == "https://s1/v1"
    assert servers[1].api_key == "key2"


def test_configured_servers_skips_incomplete() -> None:
    """A partially configured server 2 is omitted."""
    org = _org(
        dify_api_base_url="https://s1/v1",
        dify_api_key="key1",
        dify_api_base_url_2="https://s2/v1",
    )
    servers = configured_dify_servers(org)
    assert [s.server for s in servers] == [1]


def test_failover_partner_server_for_each_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    """Partner follows the school's configured pair, not a fixed 1<->2 mapping."""
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

    org_1_2 = _org(
        dify_api_base_url="https://s1/v1",
        dify_api_key="key1",
        dify_api_base_url_2="https://s2/v1",
        dify_api_key_2="key2",
        dify_active_server=1,
    )
    assert failover_partner_server(org_1_2) == 2

    org_2_3 = _org(
        dify_api_base_url_2="https://s2/v1",
        dify_api_key_2="key2",
        dify_api_base_url_3="https://s3/v1",
        dify_api_key_3="key3",
        dify_active_server=2,
    )
    assert failover_partner_server(org_2_3) == 3

    org_1_3 = _org(
        dify_api_base_url="https://s1/v1",
        dify_api_key="key1",
        dify_api_base_url_3="https://s3/v1",
        dify_api_key_3="key3",
        dify_active_server=1,
    )
    assert failover_partner_server(org_1_3) == 3
    clear_dify_server_schema_cache()


def test_failover_partner_none_with_single_server() -> None:
    """A single configured server has no failover partner."""
    assert failover_partner_server(_org(dify_api_base_url="https://s1/v1", dify_api_key="key1")) is None


def test_failover_partner_none_when_three_servers_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-failover requires exactly two configured servers."""
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
    org = _org(
        dify_api_base_url="https://s1/v1",
        dify_api_key="key1",
        dify_api_base_url_2="https://s2/v1",
        dify_api_key_2="key2",
        dify_api_base_url_3="https://s3/v1",
        dify_api_key_3="key3",
    )
    assert failover_partner_server(org) is None
    clear_dify_server_schema_cache()


def test_org_eligible_for_failover_probing() -> None:
    """Eligibility requires failover enabled and a resolvable partner pair."""
    assert org_eligible_for_failover_probing(_org(dify_failover_enabled=False)) is False
    assert org_eligible_for_failover_probing(
        _org(
            dify_api_base_url="https://s1/v1",
            dify_api_key="key1",
            dify_api_base_url_2="https://s2/v1",
            dify_api_key_2="key2",
        )
    ) is True
