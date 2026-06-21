"""Tests for MindMate export usage supplement (DingTalk group + 1:1 threads)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main as _main_app

assert _main_app.app.title

from repositories.mindbot_usage_repo import MindbotExportThread
from services.dify.export.transcript import ExportConversationSummary
from services.dify.export.types import UserTarget
from services.dify.export.usage_supplement import supplement_mindbot_summaries_from_usage


def _thread(
    *,
    conv_id: str = "dify-group-1",
    scope: str = "group",
    staff: str = "manager7439",
) -> MindbotExportThread:
    now = datetime(2026, 6, 21, 12, 52, 44, tzinfo=UTC)
    return MindbotExportThread(
        organization_id=5,
        dify_user_key=f"mindbot_5_{staff}",
        dify_conversation_id=conv_id,
        mindbot_config_id=11,
        dingtalk_conversation_id="cidMV7QvJW06mV",
        dingtalk_chat_scope=scope,
        dingtalk_staff_id=staff,
        sender_nick="王寸尺",
        linked_user_id=42,
        first_event_at=now,
        last_event_at=now,
    )


@pytest.mark.asyncio
async def test_supplement_adds_missing_group_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Usage telemetry adds group threads missing from the Dify conversation list."""
    targets = [
        UserTarget(
            organization_id=5,
            user_id=42,
            dify_user="mindbot_5_manager7439",
            label="王寸尺 · DingTalk",
            channel="mindbot",
        )
    ]
    existing = [
        ExportConversationSummary(
            conversation_id="dify-oto-1",
            name="1:1 chat",
            server=1,
            organization_id=5,
            dify_user="mindbot_5_manager7439",
            user_id=42,
            user_label="王寸尺 · DingTalk",
            channel="mindbot",
            created_at=100,
            updated_at=200,
            dingtalk_chat_scope="oto",
        )
    ]

    class _UsageRepo:
        async def list_dify_threads_for_export(self, org_id: int, **kwargs):
            del org_id, kwargs
            return [_thread()]

    monkeypatch.setattr(
        "services.dify.export.usage_supplement.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    merged, warnings = await supplement_mindbot_summaries_from_usage(
        MagicMock(),
        targets,
        existing,
    )
    assert len(merged) == 2
    assert {row.conversation_id for row in merged} == {"dify-oto-1", "dify-group-1"}
    group_row = next(row for row in merged if row.conversation_id == "dify-group-1")
    assert group_row.dingtalk_chat_scope == "group"
    assert group_row.name.startswith("DingTalk group")
    assert any("mindbot_usage_threads_merged" in item for item in warnings)


@pytest.mark.asyncio
async def test_supplement_labels_cross_org_group(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cross-org group threads are labeled distinctly in export summaries."""
    targets = [
        UserTarget(
            organization_id=5,
            user_id=None,
            dify_user="mindbot_5_unknown",
            label="Cross-org DingTalk groups · DingTalk (unbound)",
            channel="mindbot",
        )
    ]

    class _UsageRepo:
        async def list_dify_threads_for_export(self, org_id: int, **kwargs):
            del org_id, kwargs
            return [_thread(scope="cross_org_group", conv_id="dify-xorg-1")]

    monkeypatch.setattr(
        "services.dify.export.usage_supplement.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    merged, _warnings = await supplement_mindbot_summaries_from_usage(
        MagicMock(),
        targets,
        [],
    )
    assert len(merged) == 1
    assert merged[0].dingtalk_chat_scope == "cross_org_group"
    assert merged[0].name.startswith("DingTalk cross-org group")


@pytest.mark.asyncio
async def test_supplement_enriches_existing_row_with_chat_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """List API rows gain group/1:1 scope metadata from usage when missing."""
    targets = [
        UserTarget(
            organization_id=5,
            user_id=42,
            dify_user="mindbot_5_manager7439",
            label="王寸尺 · DingTalk",
            channel="mindbot",
        )
    ]
    existing = [
        ExportConversationSummary(
            conversation_id="dify-group-1",
            name="Untitled",
            server=1,
            organization_id=5,
            dify_user="mindbot_5_manager7439",
            user_id=42,
            user_label="王寸尺 · DingTalk",
            channel="mindbot",
            created_at=100,
            updated_at=200,
        )
    ]

    class _UsageRepo:
        async def list_dify_threads_for_export(self, org_id: int, **kwargs):
            del org_id, kwargs
            return [_thread()]

    monkeypatch.setattr(
        "services.dify.export.usage_supplement.MindbotUsageRepository",
        lambda _db: _UsageRepo(),
    )

    merged, _warnings = await supplement_mindbot_summaries_from_usage(
        MagicMock(),
        targets,
        existing,
    )
    assert len(merged) == 1
    assert merged[0].dingtalk_chat_scope == "group"
    assert merged[0].dingtalk_conversation_id == "cidMV7QvJW06mV"
