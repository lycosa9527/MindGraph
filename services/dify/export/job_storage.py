"""
Filesystem + DB helpers for MindMate export jobs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import io
import json
import shutil
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import List, Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindmate_export_job import MindmateExportJob
from services.dify.export.export_config import ARTIFACT_TTL_SECONDS
from services.dify.export.transcript import (
    ExportBubble,
    ExportBundle,
    ExportConversation,
    ExportConversationSummary,
    render_html,
)
from services.dify.export.types import TargetFetchResult

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMP_EXPORTS_DIR = _PROJECT_ROOT / "temp_exports"


def export_job_dir(job_id: int) -> Path:
    """Return (and create) the on-disk workspace for one export job."""
    path = TEMP_EXPORTS_DIR / str(int(job_id))
    path.mkdir(parents=True, exist_ok=True)
    return path


def partial_jsonl_path(job_id: int) -> Path:
    """Path to the conversations JSONL checkpoint file."""
    return export_job_dir(job_id) / "partial.jsonl"


def summaries_jsonl_path(job_id: int) -> Path:
    """Path to the conversation summaries JSONL checkpoint file."""
    return export_job_dir(job_id) / "summaries.jsonl"


def target_results_jsonl_path(job_id: int) -> Path:
    """Path to the per-target fetch metadata JSONL file."""
    return export_job_dir(job_id) / "target_results.jsonl"


def warnings_jsonl_path(job_id: int) -> Path:
    """Path to the export warnings JSONL file."""
    return export_job_dir(job_id) / "warnings.jsonl"


def artifact_path_for(job_id: int, fmt: str, base_name: str) -> Path:
    """Path for the final artifact (html, json, or zip)."""
    ext = fmt if fmt in {"html", "json"} else "zip"
    return export_job_dir(job_id) / f"{base_name}.{ext}"


def expires_at_from_now() -> datetime:
    """Artifact expiry timestamp from configured TTL."""
    return datetime.now(UTC) + timedelta(seconds=ARTIFACT_TTL_SECONDS)


async def get_job(db: AsyncSession, job_id: int) -> Optional[MindmateExportJob]:
    """Load one export job row by id."""
    return (
        await db.execute(select(MindmateExportJob).where(MindmateExportJob.id == int(job_id)))
    ).scalar_one_or_none()


def _append_conversations_jsonl_blocking(job_id: int, conversations: List[ExportConversation]) -> None:
    path = partial_jsonl_path(job_id)
    with path.open("a", encoding="utf-8") as handle:
        for conv in conversations:
            handle.write(json.dumps(conv.to_dict(), ensure_ascii=False))
            handle.write("\n")


async def append_conversations_jsonl(job_id: int, conversations: List[ExportConversation]) -> None:
    """Append conversation rows to the JSONL checkpoint without blocking the loop."""
    await asyncio.to_thread(_append_conversations_jsonl_blocking, job_id, conversations)


def _append_summaries_jsonl_blocking(job_id: int, summaries: List[ExportConversationSummary]) -> None:
    path = summaries_jsonl_path(job_id)
    with path.open("a", encoding="utf-8") as handle:
        for summary in summaries:
            handle.write(json.dumps(summary.to_dict(), ensure_ascii=False))
            handle.write("\n")


async def append_summaries_jsonl(job_id: int, summaries: List[ExportConversationSummary]) -> None:
    """Append summary rows to the JSONL checkpoint without blocking the loop."""
    await asyncio.to_thread(_append_summaries_jsonl_blocking, job_id, summaries)


def _load_summaries_jsonl_blocking(job_id: int) -> List[ExportConversationSummary]:
    path = summaries_jsonl_path(job_id)
    if not path.is_file():
        return []
    out: List[ExportConversationSummary] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            out.append(
                ExportConversationSummary(
                    conversation_id=str(raw.get("conversation_id") or ""),
                    name=str(raw.get("name") or ""),
                    server=int(raw.get("server") or 1),
                    organization_id=int(raw.get("organization_id") or 0),
                    dify_user=str(raw.get("dify_user") or ""),
                    user_id=raw.get("user_id"),
                    user_label=str(raw.get("user_label") or ""),
                    channel=str(raw.get("channel") or "web"),
                    created_at=int(raw.get("created_at") or 0),
                    updated_at=int(raw.get("updated_at") or 0),
                    mindbot_config_id=raw.get("mindbot_config_id"),
                    endpoint_source=str(raw.get("endpoint_source") or "org_server"),
                )
            )
    return out


async def load_summaries_jsonl(job_id: int) -> List[ExportConversationSummary]:
    """Load all conversation summaries from the JSONL checkpoint."""
    return await asyncio.to_thread(_load_summaries_jsonl_blocking, job_id)


def _target_result_to_dict(result: TargetFetchResult) -> dict:
    return {
        "dify_user": result.dify_user,
        "endpoint_source": result.endpoint_source,
        "server": result.server,
        "organization_id": result.organization_id,
        "channel": result.channel,
        "conversations_fetched": result.conversations_fetched,
        "pagination_complete": result.pagination_complete,
        "fetch_errors": list(result.fetch_errors),
        "messages_by_conv_id": dict(result.messages_by_conv_id),
    }


def _target_result_from_dict(raw: dict) -> TargetFetchResult:
    return TargetFetchResult(
        dify_user=str(raw.get("dify_user") or ""),
        endpoint_source=str(raw.get("endpoint_source") or "org_server"),
        server=int(raw.get("server") or 1),
        organization_id=int(raw.get("organization_id") or 0),
        channel=str(raw.get("channel") or "web"),
        conversations_fetched=int(raw.get("conversations_fetched") or 0),
        pagination_complete=bool(raw.get("pagination_complete", True)),
        fetch_errors=[str(item) for item in (raw.get("fetch_errors") or []) if item],
        messages_by_conv_id={
            str(key): bool(value)
            for key, value in (raw.get("messages_by_conv_id") or {}).items()
        },
    )


def _append_target_results_jsonl_blocking(job_id: int, results: List[TargetFetchResult]) -> None:
    path = target_results_jsonl_path(job_id)
    with path.open("a", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(_target_result_to_dict(result), ensure_ascii=False))
            handle.write("\n")


async def append_target_results_jsonl(job_id: int, results: List[TargetFetchResult]) -> None:
    """Append target fetch metadata without blocking the loop."""
    await asyncio.to_thread(_append_target_results_jsonl_blocking, job_id, results)


def _load_target_results_jsonl_blocking(job_id: int) -> List[TargetFetchResult]:
    path = target_results_jsonl_path(job_id)
    if not path.is_file():
        return []
    out: List[TargetFetchResult] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            out.append(_target_result_from_dict(json.loads(line)))
    return out


async def load_target_results_jsonl(job_id: int) -> List[TargetFetchResult]:
    """Load target fetch metadata from the JSONL checkpoint."""
    return await asyncio.to_thread(_load_target_results_jsonl_blocking, job_id)


def _append_warnings_jsonl_blocking(job_id: int, warnings: List[str]) -> None:
    if not warnings:
        return
    path = warnings_jsonl_path(job_id)
    with path.open("a", encoding="utf-8") as handle:
        for warning in warnings:
            handle.write(json.dumps(str(warning), ensure_ascii=False))
            handle.write("\n")


async def append_warnings_jsonl(job_id: int, warnings: List[str]) -> None:
    """Append warning strings without blocking the loop."""
    await asyncio.to_thread(_append_warnings_jsonl_blocking, job_id, warnings)


def _load_warnings_jsonl_blocking(job_id: int) -> List[str]:
    path = warnings_jsonl_path(job_id)
    if not path.is_file():
        return []
    out: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            out.append(str(json.loads(line)))
    return out


async def load_warnings_jsonl(job_id: int) -> List[str]:
    """Load warning strings from the JSONL checkpoint."""
    return await asyncio.to_thread(_load_warnings_jsonl_blocking, job_id)


def _count_jsonl_lines_blocking(job_id: int) -> int:
    path = partial_jsonl_path(job_id)
    if not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


async def count_jsonl_lines(job_id: int) -> int:
    """Count non-empty lines in the conversations JSONL checkpoint."""
    return await asyncio.to_thread(_count_jsonl_lines_blocking, job_id)


def _load_conversations_jsonl_blocking(job_id: int) -> List[ExportConversation]:
    path = partial_jsonl_path(job_id)
    if not path.is_file():
        return []
    out: List[ExportConversation] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            bubbles = raw.pop("bubbles", [])
            conv = ExportConversation(
                conversation_id=str(raw.get("conversation_id") or ""),
                name=str(raw.get("name") or ""),
                server=int(raw.get("server") or 1),
                organization_id=int(raw.get("organization_id") or 0),
                dify_user=str(raw.get("dify_user") or ""),
                user_id=raw.get("user_id"),
                user_label=str(raw.get("user_label") or ""),
                channel=str(raw.get("channel") or "web"),
                created_at=int(raw.get("created_at") or 0),
                updated_at=int(raw.get("updated_at") or 0),
                mindbot_config_id=raw.get("mindbot_config_id"),
                endpoint_source=str(raw.get("endpoint_source") or "org_server"),
                bubbles=[
                    ExportBubble(
                        role=str(item.get("role") or "user"),
                        text=str(item.get("text") or ""),
                        created_at=int(item.get("created_at") or 0),
                        message_id=str(item.get("message_id") or ""),
                        files=[f for f in (item.get("files") or []) if isinstance(f, dict)],
                        feedback=item.get("feedback"),
                    )
                    for item in bubbles
                    if isinstance(item, dict)
                ],
            )
            out.append(conv)
    return out


async def load_conversations_jsonl(job_id: int) -> List[ExportConversation]:
    """Load full conversations (with bubbles) from the JSONL checkpoint."""
    return await asyncio.to_thread(_load_conversations_jsonl_blocking, job_id)


def _unlink_partial_jsonl_blocking(job_id: int) -> None:
    partial_jsonl_path(job_id).unlink(missing_ok=True)


async def unlink_partial_jsonl(job_id: int) -> None:
    """Remove the conversations JSONL checkpoint if present."""
    await asyncio.to_thread(_unlink_partial_jsonl_blocking, job_id)


def _write_artifact_blocking(bundle: ExportBundle, fmt: str, path: Path) -> bytes:
    if fmt == "json":
        content = bundle.to_json().encode("utf-8")
        path.write_bytes(content)
        return content
    if fmt == "html":
        content = render_html(bundle).encode("utf-8")
        path.write_bytes(content)
        return content
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("export.json", bundle.to_json())
        archive.writestr("export.html", render_html(bundle))
        archive.writestr(
            "verification.json",
            json.dumps(bundle.verification_report or {}, ensure_ascii=False, indent=2),
        )
    content = cast(bytes, buffer.getvalue())
    path.write_bytes(content)
    return content


async def write_artifact(bundle: ExportBundle, fmt: str, path: Path) -> bytes:
    """Write export bundle to disk without blocking the event loop."""
    return await asyncio.to_thread(_write_artifact_blocking, bundle, fmt, path)


def remove_job_dir(job_id: int) -> None:
    """Delete the on-disk workspace for one export job."""
    path = export_job_dir(job_id)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
