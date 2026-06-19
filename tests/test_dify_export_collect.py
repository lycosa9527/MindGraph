"""Tests for the MindMate export collector (pagination, merge, failover-tolerance)."""

from __future__ import annotations

import main as _main_app

assert _main_app.app.title

from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from clients.dify import AsyncDifyClient
import services.dify.export.collect_service as collect
from services.dify.export.collect_service import (
    _dedupe_summaries,
    _fetch_all_messages,
    _within_range,
    collect_conversation_summaries,
)
from services.dify.export.types import UserTarget
from services.dify.export.endpoints import ExportDifyEndpoint
from services.dify.export.transcript import ExportConversationSummary
from tests.typing_helpers import as_type


class FakeDifyClient:
    """Minimal Dify client double driving paginated conversation/message pages."""

    def __init__(
        self,
        conversation_pages: Optional[List[dict]] = None,
        message_pages: Optional[Dict[str, List[dict]]] = None,
        raise_on_conversations: bool = False,
    ) -> None:
        self._conversation_pages = conversation_pages or []
        self._message_pages = message_pages or {}
        self._raise = raise_on_conversations
        self._conv_call = 0
        self._message_calls: dict[str, list[Optional[str]]] = {}

    async def get_conversations(self, _user: str, last_id: Optional[str] = None, limit: int = 100):
        """Return the next prepared conversation page (mirrors the Dify client API)."""
        del last_id, limit
        if self._raise:
            raise ConnectionError("boom")
        idx = self._conv_call
        self._conv_call += 1
        if idx >= len(self._conversation_pages):
            return {"data": [], "has_more": False}
        return self._conversation_pages[idx]

    async def get_messages(
        self, conversation_id: str, _user: str, first_id: Optional[str] = None, limit: int = 100
    ):
        """Return the prepared message page for a conversation id."""
        self._message_calls.setdefault(conversation_id, []).append(first_id)
        pages = self._message_pages.get(conversation_id, [])
        if not pages:
            return {"data": [], "has_more": False}
        if first_id is None:
            return pages[0]
        for page in pages[1:]:
            if page.get("_after") == first_id:
                return page
        return {"data": [], "has_more": False}


def _endpoint(server: int = 1, url: str = "u1") -> ExportDifyEndpoint:
    return ExportDifyEndpoint(
        organization_id=42,
        source="org_server",
        server=server,
        mindbot_config_id=None,
        api_key=f"k{server}",
        api_url=url,
    )


def test_within_range_is_inclusive_and_open_ended() -> None:
    """Range filter is inclusive and treats None bounds as open."""
    assert _within_range(100, None, None) is True
    assert _within_range(100, 100, 200) is True
    assert _within_range(200, 100, 200) is True
    assert _within_range(99, 100, 200) is False
    assert _within_range(201, 100, 200) is False


def test_dedupe_prefers_newer_updated_at() -> None:
    """Duplicate conversation ids keep the row with the latest updated_at."""
    older = ExportConversationSummary("c1", "A", 1, 42, "u", 1, "U", "web", 10, 20)
    newer = ExportConversationSummary("c1", "A", 2, 42, "u", 1, "U", "web", 10, 99)
    other = ExportConversationSummary("c2", "B", 1, 42, "u2", 1, "U", "mindbot", 5, 50)
    out = _dedupe_summaries([older, newer, other])
    assert [summary.conversation_id for summary in out] == ["c1", "c2"]
    assert next(summary for summary in out if summary.conversation_id == "c1").server == 2


@pytest.mark.asyncio
async def test_fetch_all_messages_uses_oldest_id_for_pagination() -> None:
    """Message pagination passes the oldest message id as first_id."""
    client = FakeDifyClient(
        message_pages={
            "conv1": [
                {
                    "data": [
                        {"id": "m2", "created_at": 2},
                        {"id": "m1", "created_at": 1},
                    ],
                    "has_more": True,
                },
                {
                    "_after": "m1",
                    "data": [{"id": "m0", "created_at": 0}],
                    "has_more": False,
                },
            ]
        }
    )
    page = await _fetch_all_messages(as_type(client, AsyncDifyClient), "conv1", "mg_user_1")
    assert [message["id"] for message in page.items] == ["m0", "m1", "m2"]
    assert page.pagination_complete is True
    assert client._message_calls["conv1"] == [None, "m1"]


@pytest.mark.asyncio
async def test_collect_summaries_merges_across_servers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Summaries from both servers are merged and date-filtered."""
    endpoints = [_endpoint(1, "u1"), _endpoint(2, "u2")]

    async def fake_endpoints(org, *, channel, dify_user, db, strict_org):
        del org, channel, dify_user, db, strict_org
        return endpoints

    async def fake_load_org(org_id: int):
        del org_id
        return MagicMock(id=42)

    clients = {
        "u1": FakeDifyClient(
            conversation_pages=[
                {
                    "data": [{"id": "c1", "name": "one", "created_at": 1000, "updated_at": 1000}],
                    "has_more": False,
                }
            ]
        ),
        "u2": FakeDifyClient(
            conversation_pages=[
                {
                    "data": [{"id": "c2", "name": "two", "created_at": 2000, "updated_at": 2000}],
                    "has_more": False,
                }
            ]
        ),
    }

    monkeypatch.setattr(collect, "_load_org", fake_load_org)
    monkeypatch.setattr(collect, "endpoints_for_target", fake_endpoints)
    monkeypatch.setattr(collect, "_client_for", lambda endpoint: clients[endpoint.api_url])

    targets = [
        UserTarget(organization_id=42, user_id=7, dify_user="mg_user_7", label="Alice", channel="web")
    ]
    db = MagicMock()
    db.in_transaction.return_value = False
    result = await collect_conversation_summaries(db, targets)
    assert {summary.conversation_id for summary in result.summaries} == {"c1", "c2"}
    assert {summary.server for summary in result.summaries} == {1, 2}


@pytest.mark.asyncio
async def test_collect_summaries_tolerates_server_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """One server raising does not abort the whole collection."""
    endpoints = [_endpoint(1, "u1"), _endpoint(2, "u2")]

    async def fake_endpoints(org, *, channel, dify_user, db, strict_org):
        del org, channel, dify_user, db, strict_org
        return endpoints

    async def fake_load_org(org_id: int):
        del org_id
        return MagicMock(id=42)

    clients = {
        "u1": FakeDifyClient(raise_on_conversations=True),
        "u2": FakeDifyClient(
            conversation_pages=[
                {
                    "data": [{"id": "c2", "name": "two", "created_at": 2000, "updated_at": 2000}],
                    "has_more": False,
                }
            ]
        ),
    }
    monkeypatch.setattr(collect, "_load_org", fake_load_org)
    monkeypatch.setattr(collect, "endpoints_for_target", fake_endpoints)
    monkeypatch.setattr(collect, "_client_for", lambda endpoint: clients[endpoint.api_url])

    targets = [
        UserTarget(organization_id=42, user_id=7, dify_user="mg_user_7", label="Alice", channel="web")
    ]
    db = MagicMock()
    db.in_transaction.return_value = False
    result = await collect_conversation_summaries(db, targets)
    assert [summary.conversation_id for summary in result.summaries] == ["c2"]
