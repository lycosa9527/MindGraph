"""Tests for MindBot Dify credential resolution (export)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.dify.credential_resolution import (
    distinct_mindbot_endpoints_for_org,
    resolve_mindbot_config_credentials,
)
from tests.typing_helpers import as_organization, as_type


def _org(**overrides: object):
    base = {
        "id": 5,
        "dify_api_base_url": "https://org.example/v1",
        "dify_api_key": "org-key",
        "dify_active_server": 1,
    }
    base.update(overrides)
    return as_organization(SimpleNamespace(**base))


def _cfg(**overrides: object) -> OrganizationMindbotConfig:
    base = {
        "id": 11,
        "organization_id": 5,
        "use_org_dify_settings": True,
        "dify_api_base_url": "https://old.example/v1",
        "dify_api_key": "old-key",
        "is_enabled": True,
    }
    base.update(overrides)
    return as_type(SimpleNamespace(**base), OrganizationMindbotConfig)


def test_resolve_mindbot_config_credentials_org_linked() -> None:
    """Org-linked bot uses live org primary credentials."""
    org = _org()
    cfg = _cfg(use_org_dify_settings=True)
    creds = resolve_mindbot_config_credentials(cfg, org)
    assert creds is not None
    assert creds.api_url == "https://org.example/v1"
    assert creds.api_key == "org-key"
    assert creds.mindbot_config_id == 11


def test_resolve_mindbot_config_credentials_custom_bot() -> None:
    """Custom bot keeps its own Dify app credentials."""
    org = _org()
    cfg = _cfg(
        use_org_dify_settings=False,
        dify_api_base_url="https://custom.example/v1",
        dify_api_key="custom-key",
    )
    creds = resolve_mindbot_config_credentials(cfg, org)
    assert creds is not None
    assert creds.api_url == "https://custom.example/v1"
    assert creds.api_key == "custom-key"


def test_resolve_mindbot_config_credentials_missing_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty credentials yield None when org and global env are unset."""
    monkeypatch.setattr(
        "services.mindbot.dify.credential_resolution.global_mindmate_dify_credentials",
        lambda: ("", ""),
    )
    org = _org(dify_api_base_url=None, dify_api_key=None)
    cfg = _cfg(use_org_dify_settings=True)
    assert resolve_mindbot_config_credentials(cfg, org) is None


@pytest.mark.asyncio
async def test_distinct_mindbot_endpoints_dedupes_same_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two bots sharing one Dify app collapse to one endpoint."""
    org = _org()
    cfg_a = _cfg(id=1)
    cfg_b = _cfg(id=2)

    class _Repo:
        async def list_by_organization_id(self, _org_id: int):
            return [cfg_a, cfg_b]

    class _Usage:
        async def distinct_config_ids_for_staff(self, _org_id: int, _staff: str):
            return set()

    monkeypatch.setattr(
        "services.mindbot.dify.credential_resolution.MindbotConfigRepository",
        lambda _db: _Repo(),
    )
    monkeypatch.setattr(
        "services.mindbot.dify.credential_resolution.MindbotUsageRepository",
        lambda _db: _Usage(),
    )

    endpoints = await distinct_mindbot_endpoints_for_org(MagicMock(), org)
    assert len(endpoints) == 1
    assert endpoints[0].mindbot_config_id == 1
