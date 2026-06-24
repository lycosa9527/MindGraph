"""Tests for MindMate export verification."""

from __future__ import annotations

from services.dify.export.collect_service import CollectResult
from services.dify.export.transcript import ExportConversationSummary
from services.dify.export.types import TargetFetchResult
from services.dify.export.verify import (
    build_scope_manifest,
    final_job_status,
    reconcile_collection,
    sha256_bytes,
    verify_artifact_integrity,
)


def test_reconcile_pass_when_counts_match() -> None:
    """Reconciliation passes when user and message counts match expectations."""
    expected = build_scope_manifest(
        scope="whole",
        org_id=5,
        user_ids=None,
        start=None,
        end=None,
        users_total=2,
        targets_total=4,
        generated_at=1,
    )
    collect = CollectResult(
        summaries=[
            ExportConversationSummary(
                conversation_id="c1",
                name="Test 1",
                server=1,
                organization_id=5,
                dify_user="mg_user_1",
                user_id=1,
                user_label="User 1",
                channel="web",
                created_at=1,
                updated_at=1,
            ),
            ExportConversationSummary(
                conversation_id="c2",
                name="Test 2",
                server=1,
                organization_id=5,
                dify_user="mg_user_2",
                user_id=2,
                user_label="User 2",
                channel="web",
                created_at=1,
                updated_at=1,
            ),
        ]
    )
    report = reconcile_collection(
        expected,
        users_done=2,
        targets_done=4,
        collect_result=collect,
        messages_complete={"u:c1": True},
    )
    assert report.status == "pass"
    assert not report.gaps


def test_reconcile_gaps_on_partial_failures() -> None:
    """Partial fetch failures produce gap entries in the reconcile report."""
    expected = build_scope_manifest(
        scope="whole",
        org_id=5,
        user_ids=None,
        start=None,
        end=None,
        users_total=1,
        targets_total=1,
        generated_at=1,
    )
    collect = CollectResult(
        partial_failures=1,
        target_results=[
            TargetFetchResult(
                dify_user="mg_user_1",
                endpoint_source="org_server",
                server=1,
                organization_id=5,
                channel="web",
                pagination_complete=False,
                fetch_errors=["dify_pagination_cap"],
            )
        ],
    )
    report = reconcile_collection(
        expected,
        users_done=1,
        targets_done=1,
        collect_result=collect,
    )
    assert report.status == "gaps"
    assert any(gap.code == "partial_failures" for gap in report.gaps)


def test_artifact_integrity_sha256() -> None:
    """Artifact SHA256 is recorded and completed status is derived from the report."""
    expected = build_scope_manifest(
        scope="whole",
        org_id=1,
        user_ids=None,
        start=None,
        end=None,
        users_total=1,
        targets_total=1,
        generated_at=1,
    )
    collect = CollectResult()
    report = reconcile_collection(
        expected,
        users_done=1,
        targets_done=1,
        collect_result=collect,
    )
    data = b'{"hello": "world"}'
    report = verify_artifact_integrity(
        report,
        artifact_bytes=data,
        verified_at=123,
    )
    assert report.artifact_sha256 == sha256_bytes(data)
    assert final_job_status(report) == "completed"
