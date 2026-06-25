"""Tests for dump-first export source router."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import main as _main_app

assert _main_app.app.title

from services.dify.export.endpoints import ExportDifyEndpoint
from services.dify.export.raw_collect_backend import ExportSourceRouter
from services.dify.export.raw_dump_index import MultiServerDumpStore

FIXTURE_BASE = Path(__file__).resolve().parent / "fixtures" / "dify_raw_dump"


@pytest.mark.asyncio
async def test_router_uses_dump_for_conversations() -> None:
    store = MultiServerDumpStore.load(FIXTURE_BASE)
    router = ExportSourceRouter(store)
    endpoint = ExportDifyEndpoint(
        organization_id=1,
        source="org_server",
        server=1,
        mindbot_config_id=None,
        api_key="tok1",
        api_url="http://example/v1",
    )

    async def fail_api(_client):
        raise AssertionError("live Dify API is disabled")

    result = await router.fetch_conversations(
        MagicMock(),
        endpoint,
        "mg_user_1",
        fail_api,
    )
    assert result.source == "dump"
    assert len(result.items) == 1
    assert result.items[0]["id"] == "c1"


@pytest.mark.asyncio
async def test_router_skips_when_dump_missing_for_slot() -> None:
    router = ExportSourceRouter(MultiServerDumpStore.load(FIXTURE_BASE))
    endpoint = ExportDifyEndpoint(
        organization_id=1,
        source="org_server",
        server=2,
        mindbot_config_id=None,
        api_key="missing",
        api_url="http://example/v1",
    )

    async def fail_api(_client):
        raise AssertionError("live Dify API is disabled")

    result = await router.fetch_conversations(
        MagicMock(),
        endpoint,
        "mg_user_1",
        fail_api,
    )
    assert result.source == "dump"
    assert result.items == []
    assert any("dump_snapshot_missing" in warning for warning in router.warnings)
