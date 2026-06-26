"""Tests for the MindMate export collector (pagination, merge, failover-tolerance)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest

import main as _main_app

assert _main_app.app.title

from clients.dify import AsyncDifyClient
import services.dify.export.collect_service as collect
from services.dify.export.collect_service import (
    _conversation_in_export_range,
    _dedupe_summaries,
    _fetch_all_messages,
    _within_range,
    collect_conversation_summaries,
)
from services.dify.export.raw_collect_backend import ExportSourceRouter
from services.dify.export.time_range import activity_overlaps_range
from services.dify.export.types import UserTarget
from services.dify.export.endpoints import ExportDifyEndpoint
from services.dify.export.transcript import ExportConversationSummary
from tests.typing_helpers import as_type

FIXTURE_MINIMAL = Path(__file__).resolve().parent / "fixtures" / "dify_raw_dump" / "dify" / "minimal"
DUMP_TIMESTAMP = "2026-06-26_120000Z"


def _install_dump_copy(
    tmp_path: Path,
    label: str,
    slot: int,
    *,
    conversation_id: str = "c1",
) -> None:
    dest = tmp_path / label / DUMP_TIMESTAMP
    shutil.copytree(FIXTURE_MINIMAL, dest)
    manifest = json.loads((FIXTURE_MINIMAL / "manifest.json").read_text(encoding="utf-8"))
    manifest["server_label"] = label
    manifest["mindgraph_server_slot"] = slot
    (dest / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if conversation_id != "c1":
        conv_csv = dest / "conversations.csv"
        conv_csv.write_text(
            conv_csv.read_text(encoding="utf-8").replace("c1", conversation_id),
            encoding="utf-8",
        )


def _dump_router(tmp_path: Path) -> ExportSourceRouter:
    return ExportSourceRouter.from_store(tmp_path)


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
        self.message_calls: dict[str, list[Optional[str]]] = {}

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

    async def get_messages(self, conversation_id: str, _user: str, first_id: Optional[str] = None, limit: int = 100):
        """Return the prepared message page for a conversation id."""
        del limit
        self.message_calls.setdefault(conversation_id, []).append(first_id)
        pages = self._message_pages.get(conversation_id, [])
        if not pages:
            return {"data": [], "has_more": False}
        if first_id is None:
            return pages[0]
        for page in pages[1:]:
            if page.get("_after") == first_id:
                return page
        return {"data": [], "has_more": False}


def _endpoint(server: int = 1, url: str = "u1", api_key: str = "tok1") -> ExportDifyEndpoint:
    return ExportDifyEndpoint(
        organization_id=42,
        source="org_server",
        server=server,
        mindbot_config_id=None,
        api_key=api_key,
        api_url=url,
    )


def test_conversation_in_export_range_uses_activity_overlap() -> None:
    """Export window includes conversations with any activity in the period."""
    # Last update inside window
    assert _conversation_in_export_range(100, 500, 400, 600) is True
    # Long thread: created before window, updated after — still active in window
    assert _conversation_in_export_range(100, 900, 400, 600) is True
    # Entirely before window
    assert _conversation_in_export_range(100, 200, 400, 600) is False
    # Entirely after window
    assert _conversation_in_export_range(700, 800, 400, 600) is False
    assert _conversation_in_export_range(100, 500, None, None) is True


def test_activity_overlaps_range() -> None:
    """Shared overlap helper treats bounds as inclusive."""
    assert activity_overlaps_range(100, 900, 400, 600) is True
    assert activity_overlaps_range(500, 500, 500, 500) is True
    assert activity_overlaps_range(100, 200, 400, 600) is False


def test_within_range_is_inclusive_and_open_ended() -> None:
    """Range filter is inclusive and treats None bounds as open."""
    assert _within_range(100, None, None) is True
    assert _within_range(100, 100, 200) is True
    assert _within_range(200, 100, 200) is True
    assert _within_range(99, 100, 200) is False
    assert _within_range(201, 100, 200) is False


def test_dedupe_keeps_distinct_servers() -> None:
    """Same conversation id on different servers are both kept."""
    server_one = ExportConversationSummary("c1", "A", 1, 42, "u", 1, "U", "web", 10, 20)
    server_two = ExportConversationSummary("c1", "A", 2, 42, "u", 1, "U", "web", 10, 99)
    other = ExportConversationSummary("c2", "B", 1, 42, "u2", 1, "U", "mindbot", 5, 50)
    out = _dedupe_summaries([server_one, server_two, other])
    assert {summary.conversation_id for summary in out} == {"c1", "c2"}
    servers_for_c1 = {summary.server for summary in out if summary.conversation_id == "c1"}
    assert servers_for_c1 == {1, 2}


def test_dedupe_prefers_newer_updated_at_on_same_server() -> None:
    """Duplicate conversation ids on one server keep the latest updated_at."""
    older = ExportConversationSummary("c1", "A", 1, 42, "u", 1, "U", "web", 10, 20)
    newer = ExportConversationSummary("c1", "A", 1, 42, "u", 1, "U", "web", 10, 99)
    out = _dedupe_summaries([older, newer])
    assert len(out) == 1
    assert out[0].updated_at == 99


@pytest.mark.skip(reason="live Dify API export disabled; dump-only mode")
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
    assert client.message_calls["conv1"] == [None, "m1"]


@pytest.mark.asyncio
async def test_collect_summaries_merges_across_servers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Summaries from both dump server slots are merged."""
    _install_dump_copy(tmp_path, "dify", 1, conversation_id="c1")
    _install_dump_copy(tmp_path, "neodify", 2, conversation_id="c2")
    monkeypatch.setenv("MINDMATE_EXPORT_RAW_DUMP_DIR", str(tmp_path))
    monkeypatch.setattr(
        collect.ExportSourceRouter,
        "bootstrap",
        lambda *_args, **_kwargs: _dump_router(tmp_path),
    )
    endpoints = [_endpoint(1, "u1"), _endpoint(2, "u2")]

    async def fake_endpoints(org, *, channel, dify_user, db, strict_org):
        del org, channel, dify_user, db, strict_org
        return endpoints

    async def fake_load_org(org_id: int):
        del org_id
        return MagicMock(id=42)

    monkeypatch.setattr(collect, "_load_org", fake_load_org)
    monkeypatch.setattr(collect, "endpoints_for_target", fake_endpoints)

    targets = [
        UserTarget(
            organization_id=42,
            user_id=7,
            dify_user="mg_user_1",
            label="Alice",
            channel="web",
        )
    ]
    db = MagicMock()
    db.in_transaction.return_value = False
    result = await collect_conversation_summaries(db, targets)
    assert {summary.conversation_id for summary in result.summaries} == {"c1", "c2"}
    assert {summary.server for summary in result.summaries} == {1, 2}


@pytest.mark.asyncio
async def test_collect_summaries_tolerates_missing_dump_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing dump for one server slot does not abort collection for the other."""
    _install_dump_copy(tmp_path, "neodify", 2, conversation_id="c2")
    monkeypatch.setenv("MINDMATE_EXPORT_RAW_DUMP_DIR", str(tmp_path))
    monkeypatch.setattr(
        collect.ExportSourceRouter,
        "bootstrap",
        lambda *_args, **_kwargs: _dump_router(tmp_path),
    )
    endpoints = [_endpoint(1, "u1"), _endpoint(2, "u2")]

    async def fake_endpoints(org, *, channel, dify_user, db, strict_org):
        del org, channel, dify_user, db, strict_org
        return endpoints

    async def fake_load_org(org_id: int):
        del org_id
        return MagicMock(id=42)

    monkeypatch.setattr(collect, "_load_org", fake_load_org)
    monkeypatch.setattr(collect, "endpoints_for_target", fake_endpoints)

    targets = [
        UserTarget(
            organization_id=42,
            user_id=7,
            dify_user="mg_user_1",
            label="Alice",
            channel="web",
        )
    ]
    db = MagicMock()
    db.in_transaction.return_value = False
    result = await collect_conversation_summaries(db, targets)
    assert [summary.conversation_id for summary in result.summaries] == ["c2"]
    assert any("dump_snapshot_missing" in warning for warning in result.warnings)
