"""Tests for MindMate export target resolution (web + MindBot identities)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import main as _main_app

assert _main_app.app.title

from services.dify.export.target_resolution import (
    build_export_targets,
    build_user_dify_targets,
    count_export_users,
)
from tests.typing_helpers import as_type, as_user


@pytest.mark.asyncio
async def test_build_user_dify_targets_web_and_mindbot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-user helper yields web MindMate + bound DingTalk MindBot keys."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    link = SimpleNamespace(dingtalk_staff_id="staff42")

    class _LinkRepo:
        async def map_for_users(self, org_id: int, user_ids: list[int]):
            """Return current staff links keyed by user id."""
            del org_id, user_ids
            return {7: link}

        async def map_for_users_all_orgs(self, user_ids: list[int]):
            """Return cross-org staff links keyed by user id."""
            del user_ids
            return {}

    class _UsageRepo:
        async def distinct_staff_for_users(self, org_id: int, user_ids: list[int]):
            """Return distinct historical staff ids for users in one org."""
            del org_id, user_ids
            return []

        async def distinct_staff_map_for_users(self, org_id: int, user_ids: list[int]):
            """Return historical staff ids grouped by user id."""
            del org_id, user_ids
            return {7: []}

        async def distinct_staff_for_org_with_usage(self, *args, **kwargs):
            """Return distinct staff ids with usage in one org."""
            del args, kwargs
            return []

        async def distinct_unbound_staff_for_org(self, *args, **kwargs):
            """Return unbound staff ids for one org."""
            del args, kwargs
            return []

        async def distinct_unbound_staff_all_orgs(self, *args, **kwargs):
            """Return unbound staff ids across orgs."""
            del args, kwargs
            return []

    monkeypatch.setattr(
        "services.dify.export.target_resolution.DingtalkStaffLinkRepository",
        lambda _db: _LinkRepo(),
    )
    monkeypatch.setattr(
        "services.dify.export.target_resolution.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    targets = await build_user_dify_targets(MagicMock(), as_user(user))
    assert len(targets) == 2
    assert targets[0].channel == "web"
    assert targets[0].dify_user == "mg_user_7"
    assert targets[1].channel == "mindbot"
    assert targets[1].dify_user == "mindbot_5_staff42"


@pytest.mark.asyncio
async def test_build_export_targets_web_and_mindbot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each user yields web MindMate + bound DingTalk MindBot Dify keys."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    link = SimpleNamespace(dingtalk_staff_id="staff42")

    class _LinkRepo:
        async def map_for_users(self, org_id: int, user_ids: list[int]):
            """Return current staff links keyed by user id."""
            del org_id, user_ids
            return {7: link}

        async def map_for_users_all_orgs(self, user_ids: list[int]):
            """Return cross-org staff links keyed by user id."""
            del user_ids
            return {}

    class _UsageRepo:
        async def distinct_staff_for_users(self, org_id: int, user_ids: list[int]):
            """Return distinct historical staff ids for users in one org."""
            del org_id, user_ids
            return []

        async def distinct_staff_map_for_users(self, org_id: int, user_ids: list[int]):
            """Return historical staff ids grouped by user id."""
            del org_id, user_ids
            return {7: []}

        async def distinct_staff_for_org_with_usage(self, *args, **kwargs):
            """Return distinct staff ids with usage in one org."""
            del args, kwargs
            return []

        async def distinct_unbound_staff_for_org(self, *args, **kwargs):
            """Return unbound staff ids for one org."""
            del args, kwargs
            return []

        async def distinct_unbound_staff_all_orgs(self, *args, **kwargs):
            """Return unbound staff ids across orgs."""
            del args, kwargs
            return []

    monkeypatch.setattr(
        "services.dify.export.target_resolution.DingtalkStaffLinkRepository",
        lambda _db: _LinkRepo(),
    )
    monkeypatch.setattr(
        "services.dify.export.target_resolution.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    result = await build_export_targets(
        MagicMock(),
        [as_user(user)],
        scope="whole",
        org_id=5,
    )
    assert len(result.targets) == 3
    assert result.targets[0].channel == "web"
    assert result.targets[0].dify_user == "mg_user_7"
    assert result.targets[1].channel == "mindbot"
    assert result.targets[1].dify_user == "mindbot_5_staff42"
    assert result.targets[2].channel == "mindbot"
    assert result.targets[2].dify_user == "mindbot_5_unknown"


@pytest.mark.asyncio
async def test_build_export_targets_includes_historical_staff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Usage events can add prior staff ids after re-bind."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    link = SimpleNamespace(dingtalk_staff_id="staff_new")

    class _LinkRepo:
        async def map_for_users(self, org_id: int, user_ids: list[int]):
            """Return current staff links keyed by user id."""
            del org_id, user_ids
            return {7: link}

        async def map_for_users_all_orgs(self, user_ids: list[int]):
            """Return cross-org staff links keyed by user id."""
            del user_ids
            return {}

    class _UsageRepo:
        async def distinct_staff_for_users(self, org_id: int, user_ids: list[int]):
            """Return distinct historical staff ids for users in one org."""
            del org_id, user_ids
            return [("staff_old", "Old Nick")]

        async def distinct_staff_map_for_users(self, org_id: int, user_ids: list[int]):
            """Return historical staff ids grouped by user id."""
            del org_id, user_ids
            return {7: [("staff_old", "Old Nick")]}

        async def distinct_staff_for_org_with_usage(self, *args, **kwargs):
            """Return distinct staff ids with usage in one org."""
            del args, kwargs
            return []

        async def distinct_unbound_staff_for_org(self, *args, **kwargs):
            """Return unbound staff ids for one org."""
            del args, kwargs
            return []

        async def distinct_unbound_staff_all_orgs(self, *args, **kwargs):
            """Return unbound staff ids across orgs."""
            del args, kwargs
            return []

    monkeypatch.setattr(
        "services.dify.export.target_resolution.DingtalkStaffLinkRepository",
        lambda _db: _LinkRepo(),
    )
    monkeypatch.setattr(
        "services.dify.export.target_resolution.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    result = await build_export_targets(
        MagicMock(),
        [as_user(user)],
        scope="whole",
        org_id=5,
    )
    mindbot_users = {target.dify_user for target in result.targets if target.channel == "mindbot"}
    assert mindbot_users == {"mindbot_5_staff_new", "mindbot_5_staff_old", "mindbot_5_unknown"}


@pytest.mark.asyncio
async def test_build_export_targets_always_includes_cross_org_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whole-school export always queries the shared cross-org (LWCP) Dify user."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    link = SimpleNamespace(dingtalk_staff_id="staff42")

    class _LinkRepo:
        async def map_for_users(self, org_id: int, user_ids: list[int]):
            """Return DingTalk staff links for the requested users."""
            del org_id, user_ids
            return {7: link}

        async def map_for_users_all_orgs(self, user_ids: list[int]):
            """Return cross-org staff links (empty for this scenario)."""
            del user_ids
            return {}

    class _UsageRepo:
        async def distinct_staff_for_users(self, org_id: int, user_ids: list[int]):
            """Return distinct staff ids with usage for selected users."""
            del org_id, user_ids
            return []

        async def distinct_staff_map_for_users(self, org_id: int, user_ids: list[int]):
            """Return per-user staff id lists from usage telemetry."""
            del org_id, user_ids
            return {7: []}

        async def distinct_staff_for_org_with_usage(self, *args, **kwargs):
            """Return org-wide staff ids with MindBot usage."""
            del args, kwargs
            return []

        async def distinct_unbound_staff_for_org(self, *args, **kwargs):
            """Return unbound staff ids for the organization."""
            del args, kwargs
            return []

        async def distinct_unbound_staff_all_orgs(self, *args, **kwargs):
            """Return unbound staff ids across all organizations."""
            del args, kwargs
            return []

    monkeypatch.setattr(
        "services.dify.export.target_resolution.DingtalkStaffLinkRepository",
        lambda _db: _LinkRepo(),
    )
    monkeypatch.setattr(
        "services.dify.export.target_resolution.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    result = await build_export_targets(
        MagicMock(),
        [as_user(user)],
        scope="whole",
        org_id=5,
        include_unbound=False,
    )
    mindbot_users = {target.dify_user for target in result.targets if target.channel == "mindbot"}
    assert "mindbot_5_staff42" in mindbot_users
    assert "mindbot_5_unknown" in mindbot_users


@pytest.mark.asyncio
async def test_build_export_targets_users_scope_includes_cross_org(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Org-scoped multi-user export still queries the shared cross-org Dify user."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    link = SimpleNamespace(dingtalk_staff_id="staff42")

    class _LinkRepo:
        async def map_for_users(self, org_id: int, user_ids: list[int]):
            """Return DingTalk staff links for the requested users."""
            del org_id, user_ids
            return {7: link}

        async def map_for_users_all_orgs(self, user_ids: list[int]):
            """Return cross-org staff links (empty for this scenario)."""
            del user_ids
            return {}

    class _UsageRepo:
        async def distinct_staff_map_for_users(self, org_id: int, user_ids: list[int]):
            """Return per-user staff id lists from usage telemetry."""
            del org_id, user_ids
            return {7: []}

    monkeypatch.setattr(
        "services.dify.export.target_resolution.DingtalkStaffLinkRepository",
        lambda _db: _LinkRepo(),
    )
    monkeypatch.setattr(
        "services.dify.export.target_resolution.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    result = await build_export_targets(
        MagicMock(),
        [as_user(user)],
        scope="users",
        org_id=5,
        include_unbound=False,
    )
    mindbot_users = {target.dify_user for target in result.targets if target.channel == "mindbot"}
    assert "mindbot_5_unknown" in mindbot_users


@pytest.mark.asyncio
async def test_build_export_targets_can_skip_cross_org(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Background job follow-up batches omit the shared cross-org target."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")

    class _LinkRepo:
        async def map_for_users(self, org_id: int, user_ids: list[int]):
            """Return DingTalk staff links for the requested users."""
            del org_id, user_ids
            return {}

        async def map_for_users_all_orgs(self, user_ids: list[int]):
            """Return cross-org staff links (empty for this scenario)."""
            del user_ids
            return {}

    class _UsageRepo:
        async def distinct_staff_map_for_users(self, org_id: int, user_ids: list[int]):
            """Return per-user staff id lists from usage telemetry."""
            del org_id, user_ids
            return {7: []}

    monkeypatch.setattr(
        "services.dify.export.target_resolution.DingtalkStaffLinkRepository",
        lambda _db: _LinkRepo(),
    )
    monkeypatch.setattr(
        "services.dify.export.target_resolution.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    result = await build_export_targets(
        MagicMock(),
        [as_user(user)],
        scope="whole",
        org_id=5,
        include_unbound=False,
        include_cross_org=False,
    )
    mindbot_users = {target.dify_user for target in result.targets if target.channel == "mindbot"}
    assert "mindbot_5_unknown" not in mindbot_users


@pytest.mark.asyncio
async def test_count_export_users_delegates() -> None:
    """count_export_users returns scalar count from DB."""

    class _Result:
        def scalar_one(self):
            """Return the single scalar value from the query."""
            return 42

    class _Db:
        async def execute(self, _stmt):
            """Execute the count query and return a scalar wrapper."""
            return _Result()

    total = await count_export_users(as_type(_Db(), AsyncSession), "whole", 5, None)
    assert total == 42
