"""Tests for deduplicated Dify failover heartbeat probe planning."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from models.domain.auth import Organization
from services.dify.dify_health_probe_plan import build_deduped_probe_plan
from services.dify.dify_server_schema import clear_dify_server_schema_cache, organization_dify_server_slots


def _org(org_id: int, **kwargs: object) -> Organization:
    defaults = {
        "id": org_id,
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


def _enable_three_server_schema(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_platform_plan_covers_mixed_school_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Schools on 1+2, 2+3, and 1+3 together monitor schema slots 1, 2, and 3."""
    _enable_three_server_schema(monkeypatch)
    orgs = [
        _org(
            1,
            dify_api_base_url="https://s1/v1",
            dify_api_key="k1",
            dify_api_base_url_2="https://s2/v1",
            dify_api_key_2="k2",
        ),
        _org(
            2,
            dify_api_base_url_2="https://s2/v1",
            dify_api_key_2="k2",
            dify_api_base_url_3="https://s3/v1",
            dify_api_key_3="k3",
        ),
        _org(
            3,
            dify_api_base_url="https://s1/v1",
            dify_api_key="k1",
            dify_api_base_url_3="https://s3/v1",
            dify_api_key_3="k3",
        ),
    ]
    plan = build_deduped_probe_plan(orgs)
    assert plan.monitored_schema_slots == (1, 2, 3)
    assert plan.server_slot_count == 6
    assert plan.unique_endpoint_count == 3
    clear_dify_server_schema_cache()


def test_build_deduped_probe_plan_collapses_shared_endpoints() -> None:
    """Schools sharing the same endpoints produce fewer HTTP probes."""
    orgs = [
        _org(
            1,
            dify_api_base_url="https://main/v1",
            dify_api_key="main-key",
            dify_api_base_url_2="https://backup/v1",
            dify_api_key_2="backup-key",
        ),
        _org(
            2,
            dify_api_base_url="https://main/v1",
            dify_api_key="main-key",
            dify_api_base_url_2="https://backup/v1",
            dify_api_key_2="backup-key",
        ),
    ]
    plan = build_deduped_probe_plan(orgs)
    assert plan.contributing_school_count == 2
    assert plan.server_slot_count == 4
    assert plan.unique_endpoint_count == 2


def test_build_deduped_probe_plan_collapses_same_url_different_keys() -> None:
    """Same base URL with different app keys shares one host-level probe."""
    orgs = [
        _org(
            1,
            dify_api_base_url="https://main/v1",
            dify_api_key="key-a",
            dify_api_base_url_2="https://backup/v1",
            dify_api_key_2="backup-a",
        ),
        _org(
            2,
            dify_api_base_url="https://main/v1/",
            dify_api_key="key-b",
            dify_api_base_url_2="https://backup/v1",
            dify_api_key_2="backup-b",
        ),
    ]
    plan = build_deduped_probe_plan(orgs)
    assert plan.contributing_school_count == 2
    assert plan.server_slot_count == 4
    assert plan.unique_endpoint_count == 2
    by_url = {target.api_url: target for target in plan.unique_targets}
    assert set(by_url) == {"https://main/v1", "https://backup/v1"}
    assert by_url["https://main/v1"].api_keys == ("key-a", "key-b")
    assert by_url["https://backup/v1"].api_keys == ("backup-a", "backup-b")

    # Unstable input org order must not change candidate-key order (org_id asc).
    reversed_plan = build_deduped_probe_plan(list(reversed(orgs)))
    reversed_by_url = {target.api_url: target for target in reversed_plan.unique_targets}
    assert reversed_by_url["https://main/v1"].api_keys == ("key-a", "key-b")


def test_build_deduped_probe_plan_fans_out_shared_url_across_slots() -> None:
    """Same host used as primary for one school and backup for another is one probe."""
    orgs = [
        _org(
            10,
            dify_api_base_url="https://shared/v1",
            dify_api_key="school-a",
            dify_api_base_url_2="https://other/v1",
            dify_api_key_2="other-a",
        ),
        _org(
            20,
            dify_api_base_url="https://other/v1",
            dify_api_key="other-b",
            dify_api_base_url_2="https://shared/v1",
            dify_api_key_2="school-b",
        ),
    ]
    plan = build_deduped_probe_plan(orgs)
    assert plan.unique_endpoint_count == 2
    shared = next(target for target in plan.unique_targets if target.api_url == "https://shared/v1")
    assert shared.api_keys == ("school-a", "school-b")
    shared_assignments = next(
        assignments for target, assignments in plan.assignments_by_target if target.api_url == "https://shared/v1"
    )
    assert {(item.org_id, item.server) for item in shared_assignments} == {(10, 1), (20, 2)}
