"""
MindMate export verification — expected vs actual reconciliation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services.dify.export.collect_service import CollectResult
from services.dify.export.export_config import BLOCK_ON_GAPS
from services.dify.export.transcript import ExportBundle
from services.dify.export.types import TargetFetchResult


@dataclass
class VerificationGap:
    """One reconciliation gap between expected and actual export scope."""

    code: str
    detail: str

    def to_dict(self) -> dict:
        """Serialize gap for JSON APIs."""
        return {"code": self.code, "detail": self.detail}


@dataclass
class VerificationReport:
    """Post-collect verification outcome."""

    status: str
    expected: dict
    actual: dict
    gaps: List[VerificationGap] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    artifact_sha256: Optional[str] = None
    verified_at: int = 0
    spot_check: Optional[dict] = None

    def to_dict(self) -> dict:
        """Serialize report for JSON APIs and export bundles."""
        payload = {
            "status": self.status,
            "expected": self.expected,
            "actual": self.actual,
            "gaps": [gap.to_dict() for gap in self.gaps],
            "warnings": self.warnings,
            "artifact_sha256": self.artifact_sha256,
            "verified_at": self.verified_at,
        }
        if self.spot_check is not None:
            payload["spot_check"] = self.spot_check
        return payload


def build_scope_manifest(
    *,
    scope: str,
    org_id: Optional[int],
    user_ids: Optional[List[int]],
    start: Optional[int],
    end: Optional[int],
    users_total: int,
    targets_total: int,
    generated_at: int,
) -> dict:
    """Build the expected-scope manifest persisted at job start."""
    return {
        "scope": scope,
        "org_id": org_id,
        "user_ids": user_ids or [],
        "start": start,
        "end": end,
        "users_total": users_total,
        "targets_total": targets_total,
        "generated_at": generated_at,
    }


def reconcile_collection(
    expected: dict,
    *,
    users_done: int,
    targets_done: int,
    collect_result: CollectResult,
    messages_complete: Optional[Dict[str, bool]] = None,
) -> VerificationReport:
    """Compare expected scope to collection outcomes."""
    gaps: List[VerificationGap] = []
    warnings = list(collect_result.warnings)

    users_total = int(expected.get("users_total") or 0)
    targets_total = int(expected.get("targets_total") or 0)

    if users_done < users_total:
        gaps.append(
            VerificationGap(
                code="users_incomplete",
                detail=f"users_done={users_done} users_total={users_total}",
            )
        )
    if targets_done < targets_total:
        gaps.append(
            VerificationGap(
                code="targets_incomplete",
                detail=f"targets_done={targets_done} targets_total={targets_total}",
            )
        )
    if collect_result.skipped_targets > 0:
        gaps.append(
            VerificationGap(
                code="targets_skipped",
                detail=f"skipped={collect_result.skipped_targets}",
            )
        )

    for target_result in collect_result.target_results:
        _check_target_result(target_result, gaps)

    if messages_complete:
        for conv_key, complete in messages_complete.items():
            if not complete:
                gaps.append(
                    VerificationGap(
                        code="incomplete_messages",
                        detail=conv_key,
                    )
                )

    if collect_result.partial_failures > 0:
        gaps.append(
            VerificationGap(
                code="partial_failures",
                detail=f"count={collect_result.partial_failures}",
            )
        )

    conversations = len(collect_result.summaries)
    messages = 0
    if messages_complete is not None:
        messages = len(messages_complete)

    actual = {
        "users_done": users_done,
        "targets_done": targets_done,
        "conversations": conversations,
        "messages": messages,
        "partial_failures": collect_result.partial_failures,
    }

    status = "pass" if not gaps else "gaps"
    return VerificationReport(
        status=status,
        expected=expected,
        actual=actual,
        gaps=gaps,
        warnings=warnings,
    )


def _check_target_result(target_result: TargetFetchResult, gaps: List[VerificationGap]) -> None:
    if target_result.fetch_errors and target_result.conversations_fetched == 0:
        gaps.append(
            VerificationGap(
                code="dify_fetch_error",
                detail=(
                    f"user={target_result.dify_user} endpoint={target_result.endpoint_source}/{target_result.server}"
                ),
            )
        )
    if not target_result.pagination_complete and target_result.conversations_fetched > 0:
        gaps.append(
            VerificationGap(
                code="incomplete_pagination",
                detail=(
                    f"user={target_result.dify_user} endpoint={target_result.endpoint_source}/{target_result.server}"
                ),
            )
        )
    for conv_id, complete in target_result.messages_by_conv_id.items():
        if not complete:
            gaps.append(
                VerificationGap(
                    code="incomplete_messages",
                    detail=f"{target_result.dify_user}:{conv_id}",
                )
            )


def sha256_bytes(data: bytes) -> str:
    """Return hex SHA-256 digest for artifact integrity checks."""
    return hashlib.sha256(data).hexdigest()


def verify_artifact_integrity(
    report: VerificationReport,
    *,
    artifact_bytes: bytes,
    jsonl_line_count: Optional[int] = None,
    bubble_count: Optional[int] = None,
    verified_at: int,
) -> VerificationReport:
    """Validate artifact checksum and optional count reconciliation."""
    digest = sha256_bytes(artifact_bytes)
    report.artifact_sha256 = digest
    report.verified_at = verified_at

    if jsonl_line_count is not None:
        conv_actual = int(report.actual.get("conversations") or 0)
        if jsonl_line_count != conv_actual:
            report.gaps.append(
                VerificationGap(
                    code="artifact_line_mismatch",
                    detail=f"lines={jsonl_line_count} expected={conv_actual}",
                )
            )

    if bubble_count is not None:
        msg_actual = int(report.actual.get("messages") or 0)
        if bubble_count != msg_actual and msg_actual > 0:
            report.gaps.append(
                VerificationGap(
                    code="artifact_bubble_mismatch",
                    detail=f"bubbles={bubble_count} expected={msg_actual}",
                )
            )

    if report.gaps:
        report.status = "fail" if any(g.code.startswith("artifact_") for g in report.gaps) else "gaps"
    else:
        report.status = "pass"
    return report


def final_job_status(report: VerificationReport) -> str:
    """Map verification report status to terminal job status."""
    if report.status == "fail":
        return "failed_verification"
    if report.status == "gaps":
        if BLOCK_ON_GAPS:
            return "failed_verification"
        return "completed_with_gaps"
    return "completed"


def embed_report_in_bundle(bundle: ExportBundle, report: VerificationReport) -> ExportBundle:
    """Attach verification report to export bundle JSON."""
    bundle.verification_report = report.to_dict()
    return bundle


def pick_spot_check_conversations(
    summaries: List,
    sample_size: int,
) -> List:
    """Pick a random sample of summaries for optional spot-check verification."""
    if sample_size <= 0 or not summaries:
        return []
    size = min(sample_size, len(summaries))
    return random.sample(list(summaries), size)
