"""
MindMate export job runner — batched collect, artifact build, verification.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Optional, cast

from sqlalchemy import select

from models.domain.mindmate_export_job import MindmateExportJob
from services.auth.security_logger import security_log
from services.dify.export.collect_service import (
    CollectOptions,
    CollectResult,
    _dedupe_summaries,
    collect_conversation_summaries_batch,
    collect_messages_for_summaries,
)
from services.dify.export.export_config import USER_BATCH_SIZE
from services.dify.export.job_events import (
    ExportJobControlState,
    export_job_to_dict,
    publish_export_job_progress,
)
from services.dify.export.job_storage import (
    append_conversations_jsonl,
    append_summaries_jsonl,
    append_target_results_jsonl,
    append_warnings_jsonl,
    artifact_path_for,
    count_jsonl_lines,
    expires_at_from_now,
    get_job,
    load_conversations_jsonl,
    load_summaries_jsonl,
    load_target_results_jsonl,
    load_warnings_jsonl,
    unlink_partial_jsonl,
    write_artifact,
)
from services.dify.export.target_resolution import (
    build_export_targets,
    count_export_users,
    export_scope_label,
    load_export_users_page,
)
from services.dify.export.transcript import ExportBundle
from services.dify.export.types import ExportScope
from services.dify.export.verify import (
    build_scope_manifest,
    embed_report_in_bundle,
    final_job_status,
    reconcile_collection,
    verify_artifact_integrity,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.rls_context import RlsContext, rls_async_session

logger = logging.getLogger(__name__)

MESSAGE_BATCH = 25
TERMINAL_CANCEL = frozenset({"cancelled", "failed", "failed_verification"})


def _parse_scope(raw: str) -> ExportScope:
    if raw in ("all", "whole", "users"):
        return cast(ExportScope, raw)
    return "whole"


async def _refresh_job(db, job_id: int) -> Optional[MindmateExportJob]:
    return (await db.execute(select(MindmateExportJob).where(MindmateExportJob.id == int(job_id)))).scalar_one_or_none()


async def _should_stop(
    db,
    job_id: int,
    control: ExportJobControlState,
) -> bool:
    if control.should_stop():
        return True
    job = await _refresh_job(db, job_id)
    if job is None:
        return True
    if job.status in TERMINAL_CANCEL:
        return True
    if job.status == "paused":
        return True
    if job.cancel_requested_at is not None:
        return True
    return False


async def _update_progress(
    db,
    job: MindmateExportJob,
    *,
    stage: str,
    percent: int,
    detail: dict,
) -> None:
    job.current_stage = stage
    job.progress_percent = max(0, min(100, int(percent)))
    job.progress_detail = detail
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await publish_export_job_progress(int(job.id), export_job_to_dict(job))


async def run_export_job(job_id: int, user_id: int) -> None:
    """Execute one export job (called from Celery)."""
    logger.info("[MindMateExportJob] job=%s started user=%s", job_id, user_id)
    try:
        await _run_export_job_inner(job_id, user_id)
    except (*BACKGROUND_INFRA_ERRORS, *DATABASE_ERRORS, OSError, ValueError, RuntimeError) as exc:
        logger.error("[MindMateExportJob] job=%s failed: %s", job_id, exc, exc_info=True)
        async with rls_async_session(RlsContext.for_celery_user(user_id)) as db:
            job = await get_job(db, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.updated_at = datetime.now(UTC)
                await db.commit()
                await publish_export_job_progress(job_id, export_job_to_dict(job))


async def _run_export_job_inner(job_id: int, user_id: int) -> None:
    """Execute one export job (called from Celery)."""
    control = ExportJobControlState(job_id)
    await control.start()
    try:
        async with rls_async_session(RlsContext.for_celery_user(user_id)) as db:
            job = await get_job(db, job_id)
            if job is None:
                logger.warning("[MindMateExportJob] job=%s not found", job_id)
                return
            filters = dict(job.filters or {})
            scope = _parse_scope(str(filters.get("scope") or "whole"))
            org_id_raw = filters.get("org_id")
            org_id = int(org_id_raw) if org_id_raw is not None else None
            user_ids = filters.get("user_ids") or None
            start = filters.get("start")
            end = filters.get("end")
            fmt = str(filters.get("format") or "zip").lower()
            org_name = str(filters.get("org_name") or "Export")

            job.status = "running"
            job.current_stage = "resolving_targets"
            job.updated_at = datetime.now(UTC)
            await db.commit()
            await publish_export_job_progress(job_id, export_job_to_dict(job))
            logger.info(
                "[MindMateExportJob] job=%s running scope=%s org=%s fmt=%s",
                job_id,
                scope,
                org_id,
                fmt,
            )

            users_total = await count_export_users(db, scope, org_id, user_ids)
            checkpoint = dict(job.checkpoint or {})
            after_user_id = checkpoint.get("last_user_id")
            after_user_id_int = int(after_user_id) if after_user_id is not None else None
            users_done = int(checkpoint.get("users_done") or 0)
            targets_total = int(checkpoint.get("targets_total") or 0)

            if job.verification_expected is None:
                job.verification_expected = build_scope_manifest(
                    scope=scope,
                    org_id=org_id,
                    user_ids=user_ids,
                    start=start,
                    end=end,
                    users_total=users_total,
                    targets_total=0,
                    generated_at=int(datetime.now(UTC).timestamp()),
                )
                await db.commit()

            all_collect = CollectResult()
            all_collect.warnings = await load_warnings_jsonl(job_id)
            all_collect.target_results = await load_target_results_jsonl(job_id)
            all_collect.partial_failures = int(checkpoint.get("partial_failures") or 0)
            all_collect.skipped_targets = int(checkpoint.get("skipped_targets") or 0)
            messages_complete: dict[str, bool] = {}

            while users_done < users_total:
                if await _should_stop(db, job_id, control):
                    refreshed = await _refresh_job(db, job_id)
                    if refreshed and (refreshed.cancel_requested_at is not None or control.cancel_requested):
                        refreshed.status = "cancelled"
                        await db.commit()
                        await publish_export_job_progress(job_id, export_job_to_dict(refreshed))
                        logger.info(
                            "[MindMateExportJob] job=%s cancelled during user batch users_done=%s",
                            job_id,
                            users_done,
                        )
                    elif refreshed and (refreshed.status == "paused" or control.pause_requested):
                        await publish_export_job_progress(job_id, export_job_to_dict(refreshed))
                    return

                page = await load_export_users_page(
                    db,
                    scope,
                    org_id,
                    user_ids,
                    after_user_id=after_user_id_int,
                    limit=USER_BATCH_SIZE,
                )
                if not page:
                    break

                include_unbound = users_done + len(page) >= users_total
                include_cross_org = after_user_id_int is None
                target_result = await build_export_targets(
                    db,
                    page,
                    scope=scope,
                    org_id=org_id,
                    start=start,
                    end=end,
                    include_unbound=include_unbound,
                    include_cross_org=include_cross_org,
                )
                targets_total += len(target_result.targets)
                all_collect.warnings.extend(target_result.warnings)

                async def _control() -> bool:
                    return not await _should_stop(db, job_id, control)

                options = CollectOptions(control=_control)
                batch_collect = await collect_conversation_summaries_batch(
                    db,
                    target_result.targets,
                    start=start,
                    end=end,
                    strict_org=scope != "all",
                    options=options,
                )
                all_collect.summaries.extend(batch_collect.summaries)
                all_collect.warnings.extend(batch_collect.warnings)
                all_collect.target_results.extend(batch_collect.target_results)
                all_collect.partial_failures += batch_collect.partial_failures
                all_collect.skipped_targets += batch_collect.skipped_targets
                await append_summaries_jsonl(job_id, batch_collect.summaries)
                await append_target_results_jsonl(job_id, batch_collect.target_results)
                await append_warnings_jsonl(job_id, batch_collect.warnings)

                users_done += len(page)
                after_user_id_int = int(page[-1].id)
                checkpoint["last_user_id"] = after_user_id_int
                checkpoint["users_done"] = users_done
                checkpoint["targets_total"] = targets_total
                checkpoint["partial_failures"] = all_collect.partial_failures
                checkpoint["skipped_targets"] = all_collect.skipped_targets
                job.checkpoint = checkpoint
                await _update_progress(
                    db,
                    job,
                    stage="fetching_conversations",
                    percent=int((users_done / max(users_total, 1)) * 40),
                    detail={
                        "users_total": users_total,
                        "users_done": users_done,
                        "targets_total": targets_total,
                        "conversations_found": len(all_collect.summaries),
                        "warnings": list(all_collect.warnings),
                    },
                )

            expected = dict(job.verification_expected or {})
            expected["targets_total"] = targets_total
            job.verification_expected = expected
            await db.commit()

            summaries = _dedupe_summaries(await load_summaries_jsonl(job_id))
            all_collect.summaries = summaries
            all_collect.warnings = await load_warnings_jsonl(job_id)
            all_collect.target_results = await load_target_results_jsonl(job_id)

            msg_done = await count_jsonl_lines(job_id)
            messages_offset = int(checkpoint.get("messages_summary_offset") or 0)
            if messages_offset == 0 and msg_done == 0:
                await unlink_partial_jsonl(job_id)

            for offset in range(messages_offset, len(summaries), MESSAGE_BATCH):
                if await _should_stop(db, job_id, control):
                    refreshed = await _refresh_job(db, job_id)
                    if refreshed is not None:
                        await publish_export_job_progress(job_id, export_job_to_dict(refreshed))
                    return
                chunk = summaries[offset : offset + MESSAGE_BATCH]

                async def _control_msg() -> bool:
                    return not await _should_stop(db, job_id, control)

                conversations, msg_warnings, chunk_complete = await collect_messages_for_summaries(
                    db,
                    chunk,
                    strict_org=scope != "all",
                    options=CollectOptions(control=_control_msg),
                )
                messages_complete.update(chunk_complete)
                all_collect.warnings.extend(msg_warnings)
                await append_conversations_jsonl(job_id, conversations)
                msg_done = await count_jsonl_lines(job_id)
                checkpoint["messages_summary_offset"] = offset + len(chunk)
                job.checkpoint = checkpoint
                await _update_progress(
                    db,
                    job,
                    stage="fetching_messages",
                    percent=40 + int((offset + len(chunk)) / max(len(summaries), 1) * 40),
                    detail={
                        "users_total": users_total,
                        "users_done": users_done,
                        "targets_total": targets_total,
                        "conversations_found": len(summaries),
                        "messages_fetched": msg_done,
                        "warnings": list(all_collect.warnings),
                    },
                )

            scope_text = export_scope_label(scope, org_id, users_total)
            loaded_conversations = await load_conversations_jsonl(job_id)
            report = reconcile_collection(
                dict(job.verification_expected or {}),
                users_done=users_done,
                targets_done=targets_total,
                collect_result=all_collect,
                messages_complete=messages_complete,
            )
            report.actual["messages"] = sum(len(conv.bubbles) for conv in loaded_conversations)

            job.current_stage = "building_artifact"
            await db.commit()
            await publish_export_job_progress(job_id, export_job_to_dict(job))

            base_name = f"mindmate-export-job{job_id}"
            bundle = ExportBundle(
                organization_id=org_id,
                organization_name=org_name,
                scope=scope_text,
                conversations=loaded_conversations,
                warnings=all_collect.warnings,
                partial_failures=all_collect.partial_failures,
            )
            embed_report_in_bundle(bundle, report)
            artifact_file = artifact_path_for(job_id, fmt, base_name)
            artifact_bytes = await write_artifact(bundle, fmt, artifact_file)

            job.current_stage = "verifying"
            await db.commit()
            await publish_export_job_progress(job_id, export_job_to_dict(job))

            report = verify_artifact_integrity(
                report,
                artifact_bytes=artifact_bytes,
                jsonl_line_count=await count_jsonl_lines(job_id),
                bubble_count=sum(len(c.bubbles) for c in bundle.conversations),
                verified_at=int(datetime.now(UTC).timestamp()),
            )
            job.verification_report = report.to_dict()
            job.artifact_sha256 = report.artifact_sha256
            job.artifact_path = str(artifact_file)
            job.artifact_format = fmt
            job.artifact_size_bytes = len(artifact_bytes)
            job.status = final_job_status(report)
            job.progress_percent = 100
            job.expires_at = expires_at_from_now()
            job.updated_at = datetime.now(UTC)
            await db.commit()
            await publish_export_job_progress(job_id, export_job_to_dict(job))
            logger.info(
                "[MindMateExportJob] job=%s finished status=%s conversations=%s artifact_bytes=%s partial_failures=%s",
                job_id,
                job.status,
                len(bundle.conversations),
                job.artifact_size_bytes,
                all_collect.partial_failures,
            )
            security_log.data_export(
                "MindMate export job completed",
                user_id=user_id,
                job_id=job_id,
                org_id=org_id,
                scope=scope_text,
                fmt=fmt,
                status=job.status,
                conversations=len(bundle.conversations),
                users_total=users_total,
                targets_total=targets_total,
                partial_failures=all_collect.partial_failures,
                verification_status=report.status,
                gaps_count=len(report.gaps),
                start=start,
                end=end,
            )
    finally:
        await control.stop()
