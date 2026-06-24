"""Tests for MindMate export job filesystem checkpoint helpers."""

from __future__ import annotations

import pytest

from services.dify.export.job_storage import (
    append_summaries_jsonl,
    append_target_results_jsonl,
    append_warnings_jsonl,
    export_job_dir,
    load_summaries_jsonl,
    load_target_results_jsonl,
    load_warnings_jsonl,
    remove_job_dir,
)
from services.dify.export.transcript import ExportConversationSummary
from services.dify.export.types import TargetFetchResult


@pytest.mark.asyncio
async def test_summaries_jsonl_roundtrip() -> None:
    """Summaries append to JSONL and reload with the same fields."""
    job_id = 999001
    remove_job_dir(job_id)
    summary = ExportConversationSummary(
        conversation_id="conv-1",
        name="Test",
        server=1,
        organization_id=10,
        dify_user="user-a",
        user_id=5,
        user_label="User A",
        channel="web",
        created_at=100,
        updated_at=200,
    )
    await append_summaries_jsonl(job_id, [summary])
    loaded = await load_summaries_jsonl(job_id)
    assert len(loaded) == 1
    assert loaded[0].conversation_id == "conv-1"
    assert loaded[0].dify_user == "user-a"
    remove_job_dir(job_id)


@pytest.mark.asyncio
async def test_target_results_and_warnings_jsonl() -> None:
    """Target results and warnings round-trip through JSONL checkpoints."""
    job_id = 999002
    remove_job_dir(job_id)
    result = TargetFetchResult(
        dify_user="user-b",
        endpoint_source="org_server",
        server=2,
        organization_id=11,
        channel="dingtalk",
        conversations_fetched=3,
        pagination_complete=False,
        fetch_errors=["timeout"],
        messages_by_conv_id={"c1": True, "c2": False},
    )
    await append_target_results_jsonl(job_id, [result])
    await append_warnings_jsonl(job_id, ["page cap reached"])
    loaded_results = await load_target_results_jsonl(job_id)
    assert len(loaded_results) == 1
    assert loaded_results[0].pagination_complete is False
    assert loaded_results[0].messages_by_conv_id["c2"] is False
    assert await load_warnings_jsonl(job_id) == ["page cap reached"]
    remove_job_dir(job_id)


def test_export_job_dir_creates_directory() -> None:
    """export_job_dir creates a per-job working directory."""
    job_id = 999003
    remove_job_dir(job_id)
    path = export_job_dir(job_id)
    assert path.is_dir()
    remove_job_dir(job_id)
